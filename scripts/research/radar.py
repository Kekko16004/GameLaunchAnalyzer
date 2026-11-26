#!/usr/bin/env python3
"""Radar del mercato. `check` legge solo il disco; solo `run` avvia la raccolta.
Ripeti `run` dopo un errore parziale (codice 2): salta le fasi già riuscite nel
periodo, riprova quelle incomplete e poi le dipendenti. Codice 3: radar occupato.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

from cohort_bench import MILESTONES, last_full_week, week_name
from common import user_dir

HERE = Path(__file__).resolve().parent
TASK = "GameLaunchStrategist-Radar"
DEFAULT_WEEKS = 4


def read_object(path, missing=None):
    if not path.exists():
        return {} if missing is None else missing
    with path.open(encoding="utf-8-sig") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f"{path}: atteso un oggetto JSON")
    return obj


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     delete=False) as f:
        tmp = Path(f.name)
        try:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            f.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


class Busy(Exception):
    pass


@contextmanager
def locked(home):
    """Kernel lock, released on exit/crash. Never unlink: that would race a waiter."""
    base = home / "radar"
    base.mkdir(parents=True, exist_ok=True)
    with (base / "lock").open("a+b") as f:
        f.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise Busy("Radar occupato: nessun secondo giro avviato.") from exc
        yield


def expected_weeks(today, n):
    start, end = last_full_week(today)
    return [week_name(start - dt.timedelta(weeks=i), end - dt.timedelta(weeks=i))
            for i in range(n)]


def quality(ds, week):
    csv = ds / (week + ".csv")
    path = csv.with_suffix(".quality.json")
    if not path.is_file():
        return {"status": "unverified" if csv.is_file() else "missing"}
    try:
        q = read_object(path)
        counts = {k: q[k] for k in ("n_games", "n_reviews", "n_store")}
        if not all(type(v) is int and v >= 0 for v in counts.values()):
            raise ValueError("conteggi non validi")
        dt.date.fromisoformat(q["generated_on"][:10])
        if any(type(q[k]) is not bool for k in ("complete", "window_complete")):
            raise ValueError("completezza non valida")
        if q["complete"] and (q["n_games"] == 0 or not q["window_complete"]
                              or not q["n_games"] == q["n_store"] == q["n_reviews"]):
            raise ValueError("manifest contraddittorio")
    except (OSError, ValueError, TypeError, KeyError):
        return {"status": "invalid"}
    status = "complete" if q["complete"] and csv.is_file() else "missing" if q["complete"] else "partial"
    return dict(status=status,
                generated_on=q["generated_on"], window_complete=q["window_complete"], **counts)


def profile_file(home):
    return home / "radar" / "profiles.json"


def configure(home, action, name, path=None):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name):
        raise ValueError("Nome profilo: da 1 a 64 lettere ASCII, cifre, '-' o '_'.")
    with locked(home):
        profiles = read_object(profile_file(home))
        if action == "add":
            dest = Path(path).expanduser().resolve()
            if not dest.is_dir():
                raise ValueError("--launch-dir deve indicare una cartella launch esistente")
            if dest == HERE / "launch" or HERE in dest.parents:
                raise ValueError("Il profilo deve puntare ai file del progetto, non alla skill")
            if name in profiles and Path(profiles[name]) != dest:
                raise ValueError("Nome già assegnato: rimuovi esplicitamente il profilo prima di spostarlo")
            if any(k != name and Path(v) == dest for k, v in profiles.items()):
                raise ValueError("Questa cartella ha già un profilo")
            profiles[name] = str(dest)
        else:
            profiles.pop(name, None)
        save(profile_file(home), profiles)
        return profiles


@dataclass(frozen=True)
class Step:
    key: str
    period: str
    argv: list
    deps: tuple = ()
    root: Path | None = None
    observes: tuple = ()


def plan(home, today, n, cadence, profiles):
    """Daily observations are never backdated. Weekly bucket = last eligible release week."""
    day = today.isoformat()
    week = expected_weeks(today, 1)[0]
    ds, market, cal = home / "cohorts", home / "market", home / "calibration.json"
    cohort = [HERE / "cohort_bench.py", "--today", day, "--dir", home / "radar" / "work"]
    tracker = [HERE / "market_tracker.py", "--today", day, "--market-dir", market]
    steps = []

    def add(key, period, argv, deps=(), root=None, observes=()):
        steps.append(Step(key, period, [sys.executable, *map(str, argv)], deps, root, observes))

    batch = f"{week}:{n}"
    if cadence != "daily":
        add("cohorts", batch, [*cohort, "update", "--dataset", ds, "--new-weeks", n])
        add("discover", week, [*tracker, "discover", "--top-sellers", 20, "--most-played", 20,
                               "--breakouts", 10])
        news = []
        for w in expected_weeks(today, n):
            key = "news:" + w
            add(key, w, [HERE / "cohort_bench.py", "--dir", ds / "_work" / w, "news",
                         "--paid-only", "--max-requests", max(1, 120 // n)])
            news.append(key)
        add("calibrate", batch, [*cohort, "calibrate", "--dataset", ds, "--market-dir", market,
                                 "--out", cal], ("cohorts",))
        add("metro", batch, [*cohort, "metro", "--dataset", ds, "--calibration", cal], ("calibrate", *news))
    if cadence != "weekly":
        add("demo_intake", day, [HERE / "demo_intake.py", "--days", 1])
        add("players", day, [*tracker, "snapshot", "--players-only"])
        add("snapshots", day, [*tracker, "snapshot"])
    shared = tuple(s.key for s in steps)
    for name, value in sorted(profiles.items()):
        root = Path(value)
        prefix = name + "." + hashlib.sha256(os.fsencode(root)).hexdigest()[:10] + "/"
        if cadence != "daily":
            deps = ()
            if (root / "comps.csv").is_file():
                key = prefix + "comps"
                add(key, batch, [*tracker, "comps", "--csv", root / "comps.csv",
                                 "--calibration", cal, "-o", root / "_raw" / "comps_calibrated.json"],
                    ("calibrate",), root)
                deps = (key,)
            features = root / "prelaunch.json"
            raw = root / "_raw"
            score = ()
            if features.is_file() or (raw / "radar-score.json").is_file():
                try:
                    feature_id = hashlib.sha256(features.read_bytes()).hexdigest() if features.exists() else "missing"
                except OSError:
                    feature_id = "unreadable"
                score = (prefix + "score",)
                add(score[0], batch + ":" + feature_id, [*cohort, "score", "--calibration", cal,
                    "--features", features, "-o", raw / "metro.radar-pending.json"], ("metro",), root)
            # With project features, never register a prediction before refreshing its score.
            add(prefix + "predictions", week, [HERE / "predictions.py", "--launch-dir", root,
                                               "--today", day, "sync"], score, root)
            add(prefix + "moves", batch, [HERE / "top_moves.py", "apply", "--launch-dir", root,
                                         "--calibration", cal, "--today", day],
                deps + ("metro", prefix + "predictions"), root, observes=score)
        observed = shared + tuple(s.key for s in steps if s.key.startswith(prefix))
        add(prefix + "status", day, [HERE / "status_page.py", "--launch-dir", root,
                                    "--today", day], root=root, observes=observed)
    return steps


def collect(step, home):
    # Never copy child logs to state: old tools can print URLs, keys or project text.
    result = subprocess.run(step.argv, cwd=step.root or home, env=dict(os.environ, GLS_HOME=str(home),
                            PYTHONIOENCODING="utf-8"), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode:
        return f"comando terminato con codice {result.returncode}"
    if re.search(rb"(?im)^\s*WARN\b", result.stderr):
        return "il raccoglitore ha segnalato un avviso; controllare prima di usare il dato"
    return None


def player_gaps(home, day, tracked):
    """If a crash happened after the write, do not sample again just to mark success."""
    missing = set(tracked)
    path = home / "market" / "players.csv"
    if missing and path.is_file():
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("ts") or "")[:10] == day and (r.get("players") or "").isdigit():
                    missing.discard(r.get("appid"))
    return missing


def read_state(home):
    state = read_object(home / "radar" / "state.json", {"version": 1, "phases": {}})
    if state.get("version") != 1 or not isinstance(state.get("phases"), dict):
        raise ValueError("Stato del radar non riconosciuto; non è stato sostituito")
    if any(not isinstance(p, dict) or p.get("status") not in ("running", "ok", "partial", "blocked")
           or type(p.get("attempts")) is not int for p in state["phases"].values()):
        raise ValueError("Stato delle fasi non valido; non è stato sostituito")
    return state


def prepare_score(raw):
    # Quarantine the old displayed score before invoking the child, also on a blocked run.
    # Don't leave yesterday's individual prediction available to predictions/top_moves.
    raw.mkdir(parents=True, exist_ok=True)
    for name in ("metro", "metro.fallback"):
        active = raw / (name + ".json")
        if active.exists():
            os.replace(active, raw / (name + ".previous.json"))
    (raw / "metro.radar-pending.json").unlink(missing_ok=True)
    save(raw / "radar-score.json", {"state": "pending"})


def publish_score(raw, today):
    pending = raw / "metro.radar-pending.json"
    result = read_object(pending)
    sc, meta = result.get("score") or {}, result.get("metro") or {}
    mode = sc.get("mode")
    if result.get("scored_on") != today.isoformat():
        raise ValueError("punteggio mancante o non corrente")
    if (mode == "model" and meta.get("validated") is True and meta.get("protocol") == "asof-v1"
            and meta.get("target") in ("y30", "y90")
            and all(type(sc.get(k)) in (int, float) and 0 <= sc[k] <= 1 for k in ("p100", "p1k", "p10k"))
            and sc.get("band") in ("<100", "100-1k", "1k-10k", ">10k")):
        dest, note = "metro.json", None
    elif mode in ("base_rate", "not_applicable") and meta.get("validated") is False:
        dest = "metro.fallback.json"
        note = ("Solo frequenze del campione, non una previsione individuale."
                if mode == "base_rate" else "Il modello non si applica a questo progetto.")
    else:
        raise ValueError("punteggio non verificato")
    os.replace(pending, raw / dest)
    save(raw / "radar-score.json", {"state": mode, "as_of": today.isoformat()})
    return note


def run(home, today, n, cadence, runner=collect):
    with locked(home):
        state = read_state(home)
        phases = state["phases"]
        statefile = home / "radar" / "state.json"
        steps = plan(home, today, n, cadence, read_object(profile_file(home)))
        done = {}
        report = {}

        def verified():
            return all(quality(home / "cohorts", w)["status"] == "complete" for w in expected_weeks(today, n))

        for step in steps:
            previous = phases.get(step.key, {})
            same = previous.get("period") == step.period
            blocked = [k for k in step.deps if not done[k]]
            inputs = {k: phases[k].get("revision") for k in step.deps}
            for k in step.observes:
                v = phases[k]
                inputs[k] = [v["status"], v.get("revision"), v.get("reason"), v.get("note")]
            is_score = step.key.endswith("/score")
            is_status = step.key.endswith("/status")
            is_news = step.key.startswith("news:")
            news_ok = not is_news or quality(home / "cohorts", step.period)["status"] == "complete"
            retry = (not news_ok or is_score and step.root.is_dir()
                     and not (step.root / "_raw" / ("metro.fallback.json" if previous.get("note") else "metro.json")).is_file())
            if not blocked and same and previous["status"] == "ok" and previous.get("inputs") == inputs:
                if not retry and (step.key != "cohorts" or verified()):
                    done[step.key], report[step.key] = True, "already_done"
                    continue
            record = phases[step.key] = {
                "period": step.period, "status": "running", "started": dt.datetime.now().isoformat(timespec="seconds"),
                "attempts": (previous.get("attempts", 0) if same else 0), "command": step.argv, "inputs": inputs,
            }
            error = None
            if is_score and step.root.is_dir():
                try:
                    prepare_score(step.root / "_raw")
                except OSError as exc:
                    error = f"impossibile ritirare il punteggio precedente: {type(exc).__name__}"
            if error:
                pass
            elif blocked:
                error = "dipendenze da riprovare: " + ", ".join(blocked)
            elif not news_ok:
                error = "settimana non verificata: news rinviate"
            elif step.root is not None and not step.root.is_dir():
                error = "cartella progetto non disponibile (non ricreata)"
            elif not Path(step.argv[1]).is_file() and runner is collect:
                error = "raccoglitore non disponibile in questa installazione"
            else:
                record["attempts"] += 1
                save(statefile, state)
                try:
                    if is_status:
                        prefix = step.key.rpartition("/")[0] + "/"
                        issues = {k.removeprefix(prefix): v.get("reason") or v.get("note")
                                  for k, v in phases.items() if k != step.key and
                                  (k.startswith(prefix) or "/" not in k) and
                                  (not k.startswith("news:") or k[5:] in expected_weeks(today, n)) and
                                  (v.get("status") != "ok" or v.get("note"))}
                        save(step.root / "_raw" / "radar_status.json", {"as_of": today.isoformat(), "issues": issues})
                    tracked = read_object(home / "market" / "tracked.json") if step.key in ("players", "snapshots") else {}
                    if step.key in ("players", "snapshots") and not tracked:
                        error = "nessun gioco seguito: completare la scoperta settimanale"
                    elif step.key == "players" and not player_gaps(home, today.isoformat(), tracked):
                        pass
                    else:
                        error = runner(step, home)
                    if not error and is_score:
                        record["note"] = publish_score(step.root / "_raw", today)
                    if not error and step.key == "players":
                        missing = player_gaps(home, today.isoformat(), tracked)
                        if missing:
                            error = f"giocatori: {len(missing)} giochi senza misura odierna"
                    if not error and step.key == "cohorts" and not verified():
                        error = "settimane mancanti, parziali o non verificate: vedi check"
                    if not error and step.key == "discover" and not read_object(home / "market" / "tracked.json"):
                        error = "nessun gioco trovato: controllare la fonte"
                except (OSError, ValueError, subprocess.SubprocessError) as exc:
                    error = "errore locale: " + type(exc).__name__
            done[step.key] = error is None
            report[step.key] = record["status"] = "blocked" if blocked else "partial" if error else "ok"
            record["finished"] = dt.datetime.now().isoformat(timespec="seconds")
            if error:
                record["reason"] = error
                if is_score and step.root.is_dir():
                    try:
                        save(step.root / "_raw" / "radar-score.json",
                             {"state": "unavailable", "as_of": today.isoformat(), "reason": error})
                    except OSError:
                        record["reason"] += "; cartella del punteggio non scrivibile"
            else:
                record["revision"] = str(uuid.uuid4())
            save(statefile, state)
        return dict(complete=all(done.values()), phases=report,
                    notes={k: phases[k]["note"] for k in done if phases[k].get("note")},
                    errors={k: phases[k]["reason"] for k in done if not done[k]})


def outstanding(ds, weeks, today):
    """Counts only verified weeks. A due milestone is not an observed zero."""
    rows = []
    for week, q in weeks.items():
        if q["status"] != "complete":
            continue
        grades = 0
        due = dict.fromkeys(MILESTONES, 0)
        with (ds / (week + ".csv")).open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                global_vote = (r.get("global_tier") in ("A", "B", "C") and
                               r.get("grade_scope") == "global_verified" and r.get("anchor_pack") and r.get("visual_batch"))
                grades += r.get("status") == "keep" and not global_vote
                if r.get("status") == "missing" or not r.get("release_date"):
                    continue
                try:
                    age = (today - dt.date.fromisoformat(r["release_date"])).days
                except ValueError:
                    continue
                for days in MILESTONES:
                    if age >= days and not r.get(f"checked_d{days}"):
                        due[days] += 1
        if grades or any(due.values()):
            rows.append(dict(week=week, capsules_to_grade=grades, due_measurements=due))
    return rows


def check(home, today, n, launch=None):
    profiles = read_object(profile_file(home))
    state = read_state(home)["phases"]
    steps = plan(home, today, n, "auto", profiles)
    ds = home / "cohorts"
    expected = expected_weeks(today, n)
    known = (set(expected) | {p.stem for p in ds.glob("cohort_*.csv")}
             | {p.name[:-len(".quality.json")] for p in ds.glob("cohort_*.quality.json")})
    weeks = {w: quality(ds, w) for w in sorted(known)}
    # Expose dates, backlog and last errors, not a false green from "file exists".
    queue = []
    for step in steps:
        last = state.get(step.key, {})
        why = None
        if last.get("period") != step.period:
            why = "due"
        elif last.get("status") != "ok":
            why = last.get("reason") or last.get("status")
        elif step.key == "cohorts" and any(weeks[w]["status"] != "complete" for w in expected):
            why = "qualità da verificare"
        if why:
            queue.append(dict(phase=step.key, period=step.period, reason=why, command=step.argv))
    missing = [name for name, path in profiles.items() if not Path(path).is_dir()]
    cal = read_object(home / "calibration.json")
    metro = cal.get("metro") or {}
    from market_page import validated_model
    result = dict(as_of=today.isoformat(), home=str(home), expected_weeks=expected, cohorts=weeks,
                  queue=queue, cohort_backlog=outstanding(ds, weeks, today), profiles=profiles,
                  unavailable_profiles=missing, last_phases=state,
                  calibration=dict(generated_on=cal.get("generated_on"), n_graded=cal.get("n_graded"),
                                    outcome_window=cal.get("primary"), metro_available=bool(metro.get("available")),
                                    metro_protocol=metro.get("protocol"), metro_validated=bool(validated_model(metro)),
                                   metro_reason=metro.get("why")))
    if launch is not None:
        result["selected_profiles"] = [name for name, value in profiles.items()
                                       if Path(value) == Path(launch).expanduser().resolve()]
    return result


# Only static PowerShell is executed. User paths and arguments are data in one JSON
# environment variable, not interpolated into code or passed through cmd.exe.
INSPECT = r"""
$all = @(Get-ScheduledTask -ErrorAction Stop)
$owned = @($all | Where-Object { $_.TaskPath -eq '\' -and $_.TaskName -eq $p.name })
$legacy = @($all | Where-Object {
    $task = $_
    $foreign = !($task.TaskPath -eq '\' -and $task.TaskName -eq $p.name)
    $commands = @($task.Actions | ForEach-Object { [string]$_.Execute + ' ' + [string]$_.Arguments })
    $foreign -and ($task.TaskName -match '(Weekly[-_ ]?Market|Daily[-_ ]?Players)' -or
      ($commands -match '(Weekly[-_ ]?Market|Daily[-_ ]?Players)' -or
       $commands -match '(?:^|[\\/\s"])market_tracker\.py["\s].*\b(?:discover|snapshot)\b' -or
       $commands -match '(?:^|[\\/\s"])cohort_bench\.py["\s].*\bupdate\b' -or
       $commands -match '(?:^|[\\/\s"])radar\.py["\s].*\brun\b'))
  } |
    ForEach-Object { $_.TaskPath + $_.TaskName })
$same = $false
$next = $null; $last = $null; $code = $null; $state = $null
if ($owned.Count -eq 1) {
  $info = $owned[0] | Get-ScheduledTaskInfo -ErrorAction Stop
  if ($info.NextRunTime) { $next = $info.NextRunTime.ToString('s') }
  if ($info.LastRunTime) { $last = $info.LastRunTime.ToString('s') }
  $code = $info.LastTaskResult; $state = [string]$owned[0].State
}
if ($owned.Count -eq 1 -and $p.marker) {
  $a = @($owned[0].Actions)
  $same = ($owned[0].Description -ceq $p.marker -and $a.Count -eq 1 -and
           $a[0].Execute -eq $p.program -and $a[0].Arguments -ceq $p.arguments)
}
"""

OPERATE = r"""
if ($p.operation -eq 'install') {
  if ($legacy.Count) { throw 'WeeklyMarket/DailyPlayers presenti: nessuna modifica' }
  if ($owned.Count -and !$same) { throw 'Nome occupato: nessuna modifica' }
  if (!$owned.Count) {
    $action = New-ScheduledTaskAction -Execute $p.program -Argument $p.arguments
    $at = [datetime]::ParseExact($p.time, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
    $trigger = New-ScheduledTaskTrigger -Daily -At $at
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
    $me = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $principal = New-ScheduledTaskPrincipal -UserId $me -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskPath '\' -TaskName $p.name -Action $action -Trigger $trigger `
      -Principal $principal -Settings $settings -Description $p.marker -ErrorAction Stop | Out-Null
  }
} elseif ($p.operation -eq 'uninstall' -and $owned.Count) {
  if (!$same) { throw 'Proprietà non verificata: task non rimosso' }
  Unregister-ScheduledTask -InputObject $owned[0] -Confirm:$false -ErrorAction Stop
}
"""


def windows_tasks(payload, mutate=False):
    if os.name != "nt":
        raise ValueError("Pianificazione disponibile solo su Windows")
    script = """$ErrorActionPreference='Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$p = $env:GLS_RADAR_TASK | ConvertFrom-Json
""" + INSPECT + (OPERATE if mutate else "") + """
[pscustomobject]@{present=[bool]$owned.Count; matches=$same; legacy=$legacy;
  next=$next; last=$last; last_result=$code; state=$state} | ConvertTo-Json -Compress
"""
    binary = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    r = subprocess.run([str(binary), "-NoProfile", "-NonInteractive", "-Command", script],
                       env=dict(os.environ, GLS_RADAR_TASK=json.dumps(payload)), capture_output=True,
                       encoding="utf-8", errors="replace", timeout=90)
    if r.returncode:
        raise ValueError("Task Scheduler: " + (r.stderr.strip() or f"codice {r.returncode}"))
    result = json.loads(r.stdout)
    if (not isinstance(result, dict) or type(result.get("present")) is not bool
            or type(result.get("matches")) is not bool or not isinstance(result.get("legacy"), list)):
        raise ValueError("Impossibile verificare i task esistenti: nessuna altra operazione")
    return result


def schedule(home, operation, apply, at, backend=windows_tasks):
    receipt = home / "radar" / "task.json"
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", at):
        raise ValueError("Ora locale non valida: usare HH:MM")
    desired = dict(name=TASK, program=sys.executable, time=at,
                   arguments=subprocess.list2cmdline([str(HERE / "radar.py"), "--home", str(home), "run"]))

    def act():
        saved = read_object(receipt)
        payload = dict(desired, marker="")
        if saved:
            if (saved.get("name") != TASK or not all(isinstance(saved.get(k), str) and saved[k]
                    for k in ("program", "arguments", "time", "marker"))):
                raise ValueError("Ricevuta del task non valida: nessuna modifica")
            payload = {k: saved[k] for k in payload}
        view = backend(payload)
        info = dict(task=TASK, operation=operation, applied=False, desired=desired, registered=saved or None, **view)
        if operation == "status" or not apply:
            return info
        if view["present"] and not view["matches"]:
            raise ValueError("Nome occupato o azione modificata: non sovrascrivo e non rimuovo questo task")
        if operation == "install":
            if view["legacy"]:
                raise ValueError("Task precedenti presenti: " + ", ".join(view["legacy"]) +
                                 ". Nessuna modifica; decidi tu se disattivarli e rimuoverli.")
            if view["present"]:
                if any(payload[k] != desired[k] for k in desired):
                    raise ValueError("Configurazione diversa: disinstalla il task Radar prima di cambiare ora o percorso")
                return info
            payload = dict(desired, marker=f"GameLaunchStrategist Radar {uuid.uuid4()}")
            save(receipt, payload)  # allows safe retry even if killed just after registration
        if operation == "install" or view["present"]:
            backend(dict(payload, operation=operation), mutate=True)
        after = backend(payload)
        if (operation == "install" and not (after["present"] and after["matches"])
                or operation == "uninstall" and after["present"]):
            raise ValueError("Verifica dopo la modifica fallita: consultare schedule status")
        if operation == "install" and after["legacy"]:
            raise ValueError("Rilevata pianificazione concorrente dopo la registrazione: consulta schedule status "
                             "e rimuovi il solo task Radar. Nessun task precedente è stato toccato.")
        if operation == "uninstall":
            receipt.unlink(missing_ok=True)
        return dict(info, **after, applied=True,
                    registered=payload if operation == "install" else None)

    if apply and operation != "status":
        with locked(home):
            return act()
    return act()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", default=user_dir(), help="archivio privato (predefinito: GLS_HOME)")
    cmd = ap.add_subparsers(dest="cmd", required=True)
    for key in ("check", "run"):
        p = cmd.add_parser(key, description=__doc__)
        p.add_argument("--new-weeks", type=int, default=DEFAULT_WEEKS,
                       help="settimane recenti da coprire (0: solo ricontrolli)")
        if key == "check":
            p.add_argument("--launch-dir", help="indica quali profili sono associati a questo progetto")
        else:
            p.add_argument("--cadence", choices=["auto", "weekly", "daily"], default="auto")
    profiles = cmd.add_parser("profile").add_subparsers(dest="action", required=True)
    p = profiles.add_parser("add")
    p.add_argument("name")
    p.add_argument("--launch-dir", required=True)
    profiles.add_parser("remove").add_argument("name")
    profiles.add_parser("list")
    sched = cmd.add_parser("schedule").add_subparsers(dest="action", required=True)
    for key in ("install", "uninstall", "status"):
        p = sched.add_parser(key)
        if key != "status":
            p.add_argument("--apply", action="store_true", help="esegui invece di mostrare soltanto il piano")
        if key == "install":
            p.add_argument("--at", default="09:00", help="ora locale HH:MM")
    args = ap.parse_args(argv)
    home = Path(args.home).expanduser().resolve()
    try:
        if args.cmd in ("run", "check"):
            if not 0 <= args.new_weeks <= 52:
                raise ValueError("--new-weeks deve essere tra 0 e 52")
            today = dt.date.today()
            result = (run(home, today, args.new_weeks, args.cadence) if args.cmd == "run"
                      else check(home, today, args.new_weeks, args.launch_dir))
        elif args.cmd == "profile":
            result = (read_object(profile_file(home)) if args.action == "list"
                      else configure(home, args.action, args.name, getattr(args, "launch_dir", None)))
        else:
            result = schedule(home, args.action, getattr(args, "apply", False), getattr(args, "at", "09:00"))
    except (OSError, ValueError, subprocess.SubprocessError, Busy) as exc:
        print(str(exc), file=sys.stderr)
        return 3 if isinstance(exc, Busy) else 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.cmd == "run" and not result["complete"] else 0


if __name__ == "__main__":
    sys.exit(main())
