#!/usr/bin/env python3
"""Offline, prospective blind-demo ledger. See references/demo-blind.md."""
import argparse
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
from tempfile import TemporaryDirectory


RUBRIC = ("gameplay", "hook", "variety", "readability", "replay")
# The source and window belong to the target, not to the person entering a result.
TARGETS = {
    "demo_reviews_d14": ("demo", "demo_review_snapshot", 14),
    "demo_players_d14": ("demo", "owner_unique_players", 14),
    # Fixed denominator: launch-day cohort, not raw traffic or the entire wishlist.
    "demo_returns_first20_d7": ("demo", "owner_d0_cohort_first20", 7),
    "game_reviews_d30": ("game", "game_review_snapshot", 30),
    "game_units_d30": ("game", "owner_net_paid_units", 30),
}
VERSION = "demo-blind-v1"
STATES = {"ready", "insufficient", "contaminated", "unplayable"}
LEAK = re.compile(r"https?://|www\.|steam(?:db|community|powered|://)|\b(?:app[\s_-]?id|"
                  r"recension[ei]|reviews?|wishlist\w*|followers?|copie vendute|"
                  r"sales|vendite|players? online|ccu|publisher|leaderboard)\b", re.I)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def fields(obj, names):
    require(isinstance(obj, dict) and set(obj) == set(names.split()),
            "Campi attesi: " + names)


def text(val, label):
    require(isinstance(val, str) and val.strip(), f"{label}: testo vuoto")
    return val


def blind_text(val):
    require(not LEAK.search(text(val, "testo cieco")), "Possibile identificatore o segnale di performance")
    return val


def token(val):
    require(isinstance(val, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", val), "ID non valido")
    return val


def day(raw):
    require(isinstance(raw, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw), "Data richiesta: YYYY-MM-DD")
    return date.fromisoformat(raw)


def count(val):
    require(type(val) is int and val >= 0, "Serve un conteggio intero non negativo")
    return val


def target_count(metric, value):
    count(value)
    if metric == "demo_returns_first20_d7":
        require(value <= 20, "La coorte di ritorno ha esattamente 20 partecipanti")
    return value


def read(path):
    def unique(pairs):
        obj = dict(pairs)
        require(len(pairs) == len(obj), "Chiave JSON duplicata")
        return obj
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def encode(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, allow_nan=False)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clock(plan, args):
    today = datetime.now(timezone.utc).date()
    if args.as_of:
        require(plan["mode"] == "rehearsal", "--as-of vietato nel test prospettico")
        chosen = day(args.as_of)
        require(chosen <= today, "Data nel futuro")
        return chosen
    return today


def setup(db):
    db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            batch TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, target TEXT NOT NULL,
            day TEXT NOT NULL, recorded_utc TEXT NOT NULL, body TEXT NOT NULL,
            PRIMARY KEY(batch,kind,id,target));
        CREATE TRIGGER IF NOT EXISTS immutable_update BEFORE UPDATE ON events
            BEGIN SELECT RAISE(ABORT,'Registro append-only'); END;
        CREATE TRIGGER IF NOT EXISTS immutable_delete BEFORE DELETE ON events
            BEGIN SELECT RAISE(ABORT,'Registro append-only'); END;
    """)


def put(db, batch, kind, when, body, case="", target=""):
    db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)", (batch, kind, case, target,
               when.isoformat(), datetime.now(timezone.utc).isoformat(), encode(body)))


def rows(db, batch, kind):
    return [(c, t, d, json.loads(b)) for c, t, d, b in db.execute(
        "SELECT id,target,day,body FROM events WHERE batch=? AND kind=? ORDER BY id,target", (batch, kind))]


def one(db, batch, kind):
    events = rows(db, batch, kind)
    require(events, f"{kind}: fase mancante per {batch}")
    return events[0][3]


def plan_batch(db, args):
    p = read(args.input)
    fields(p, "batch mode start end train_through frame_kind country sampling model setup targets")
    b = token(p["batch"])
    require(p["mode"] in ("prospective", "rehearsal"), "mode: prospective o rehearsal")
    require(p["frame_kind"] in ("steam_listed", "private"), "frame_kind: steam_listed o private")
    require((p["frame_kind"] == "private" and p["country"] is None) or
            (p["frame_kind"] == "steam_listed" and isinstance(p["country"], str)
             and re.fullmatch("[A-Z]{2}", p["country"])), "country: codice Steam, null per frame privato")
    when = clock(p, args)
    start, end = day(p["start"]), day(p["end"])
    require(when < start <= end <= start + timedelta(days=2),
            "Preregistrare entro il giorno prima; massimo tre giorni UTC per batch")
    for (body,) in db.execute("SELECT body FROM events WHERE kind='plan'"):
        prior = json.loads(body)
        same_pool = all(p[k] == prior[k] for k in ("mode", "frame_kind", "country"))
        require(not (same_pool and start <= day(prior["end"]) and day(prior["start"]) <= end),
                "Finestra sovrapposta nello stesso bacino: non scegliere il batch a posteriori")
    cutoff = day(p["train_through"])
    require(cutoff < when, "Date d'addestramento/baseline non precedenti alla preregistrazione")
    for key in ("sampling", "model", "setup"):
        text(p[key], key)
    require(isinstance(p["targets"], list) and p["targets"], "Nessun target")
    seen = set()
    for t in p["targets"]:
        fields(t, "metric threshold history")
        key = t["metric"]
        require(key in TARGETS and key not in seen, "Target sconosciuto o ripetuto")
        seen.add(key)
        require(target_count(key, t["threshold"]) > 0, "Soglia deve essere positiva")
        h = t["history"]
        require(isinstance(h, list), "history: lista (vuota = baseline ingenua p=0.5)")
        groups = set()
        for obs in h:
            fields(obs, "group observed value evidence")
            g = token(obs["group"])
            require(g not in groups and day(obs["observed"]) <= cutoff, "Gruppo o data baseline non validi")
            groups.add(g)
            target_count(key, obs["value"])
            text(obs["evidence"], "Provenienza storica")
        t["baseline"] = sum(row["value"] >= t["threshold"] for row in h) / len(h) if h else 0.5
    p["version"] = VERSION
    put(db, b, "plan", when, p)
    return {"batch": b, "version": VERSION, "registered": str(when)}


def private_frame(db, args, p, when):
    require(p["frame_kind"] == "private" and when > day(p["end"]), "Frame privato: attendere fine finestra")
    f = read(args.input)
    fields(f, "complete cases")
    require(f["complete"] is True and isinstance(f["cases"], list), "Serve la lista consecutiva completa")
    for r in f["cases"]:
        fields(r, "group released")
        token(r["group"])
        require(day(p["start"]) <= day(r["released"]) <= day(p["end"]), "Data fuori finestra")
    receipt = {"snapshot": sha(Path(args.input)), "cases": f["cases"]}
    put(db, p["batch"], "frame", when, receipt)
    return {"snapshot": receipt["snapshot"], "enrolled": len(f["cases"])}


def intake(db, args, p, when):
    data = read(args.input)
    fields(data, "snapshot complete cases")
    require(data["complete"] is True and isinstance(data["snapshot"], str)
            and re.fullmatch(r"[0-9a-f]{64}", data["snapshot"]), "Serve un manifest privato completo con SHA-256")
    require(isinstance(data["cases"], list), "cases deve essere una lista, anche vuota")
    require(day(p["end"]) < when, "Attendere la fine della finestra UTC")
    if p["frame_kind"] == "steam_listed":
        require(args.manifest, "Serve --manifest: snapshot privato indipendente del radar demo")
        manifest = Path(args.manifest)
        m = read(manifest)
        require(isinstance(m, dict) and m.get("complete") is True and not m.get("warnings") and
                m.get("window") == [p["start"], p["end"]] and m.get("country") == p["country"],
                "Manifest parziale o finestra/regione errata")
        stamp = datetime.fromisoformat(text(m.get("observed_at"), "data del censimento").replace("Z", "+00:00"))
        require(stamp.tzinfo is not None and stamp <= datetime.now(timezone.utc) and
                day(p["end"]) < stamp.astimezone(timezone.utc).date() <= when,
                "Timestamp del censimento incompatibile con la finestra")
        candidates = m.get("candidates")
        require(isinstance(candidates, list), "Manifest senza candidati")
        keys = []
        for candidate in candidates:
            fields(candidate, "appid release_date")
            require(count(candidate["appid"]) > 0, "AppID non valido")
            keys.append((day(candidate["release_date"]), candidate["appid"]))
        require(keys == sorted(keys) and len({a for _, a in keys}) == len(keys),
                "Manifest non ordinato o con AppID duplicati")
        from demo_intake import expected_cases
        digest, expected = expected_cases(manifest)
    else:
        require(not args.manifest, "Cohort privata: usare frame, non il manifest Steam")
        frozen = one(db, p["batch"], "frame")
        digest, expected = frozen["snapshot"], frozen["cases"]
    require(data["snapshot"] == digest, "Hash diverso dalla lista indipendente")
    require(len(data["cases"]) == len(expected), "Righe mancanti o aggiunte al censimento")
    used = {h["group"] for (body,) in db.execute("SELECT body FROM events WHERE kind='plan'")
            for t in json.loads(body)["targets"] for h in t["history"]}
    for (body,) in db.execute("SELECT body FROM events WHERE kind='intake'"):
        used.update(row["group"] for row in json.loads(body)["cases"])
    base = Path(args.input).resolve().parent
    prev = ""
    for i, r in enumerate(data["cases"], 1):
        fields(r, "group released status reason trace media")
        original = expected[i - 1]
        require(all(r[k] == original[k] for k in ("group", "released")), "Ordine o gruppo diverso dal censimento")
        g = token(r["group"])
        require(g not in used or r["status"] == "contaminated",
                "Gruppo già nel test, nella baseline o nel batch: conservarlo come contaminated")
        used.add(g)
        require(day(p["start"]) <= day(r["released"]) <= day(p["end"]), "Demo fuori dalla finestra")
        require(prev <= r["released"], "Ordine cronologico non rispettato")
        prev = r["released"]
        require(r["status"] in STATES and isinstance(r["trace"], list) and isinstance(r["media"], list),
                "Stato o materiali non validi")
        if r["status"] != "ready":
            text(r["reason"], "Motivo privato")
            require(not r["trace"] and not r["media"], "Non importare materiali esclusi")
        else:
            require(r["reason"] == "" and (r["trace"] or r["media"]), "Serve materiale cieco reale")
        for line in r["trace"]:
            blind_text(line)
        artifacts = []
        for j, name in enumerate(r["media"], 1):
            require(isinstance(name, str) and not Path(name).is_absolute(), "Media: percorso relativo")
            src = (base / name).resolve()
            require(base in src.parents and src.is_file() and src.stat().st_size > 0 and
                    src.suffix.lower() in (".png", ".jpg", ".mp4", ".wav"), "Media assente o non ammesso")
            artifacts.append({"file": f"clip-{j:02}{src.suffix.lower()}", "path": str(src), "sha256": sha(src)})
        r.update(id=f"D{i:04}", media=artifacts)
    put(db, p["batch"], "intake", when, data)
    return {"batch": p["batch"], "cases": len(data["cases"]), "status": dict(Counter(
        r["status"] for r in data["cases"]))}


def pack(args, p, case):
    require(case["status"] == "ready", "Caso non valutabile")
    dst = Path(args.out).resolve()
    require(not dst.exists(), "Destinazione già presente: non sovrascrivo")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=dst.parent) as tmp:
        staged = Path(tmp) / "pack"
        staged.mkdir()
        files = []
        for m in case["media"]:
            path = staged / m["file"]
            shutil.copyfile(m["path"], path)
            require(sha(path) == m["sha256"], "Media modificato dopo intake")
            files.append({"file": m["file"], "sha256": m["sha256"]})
        public = {"id": case["id"], "rubric": VERSION, "trace": case["trace"], "media": files,
                  "targets": [{"metric": t["metric"], "threshold": t["threshold"]} for t in p["targets"]]}
        (staged / "dossier.json").write_text(encode(public), encoding="utf-8")
        staged.rename(dst)
    return {"export": str(dst), "id": case["id"]}


def judge(db, args, p, when, case):
    b = p["batch"]
    require(case["status"] == "ready" and not rows(db, b, "seal"), "Batch chiuso o caso non ammesso")
    require(p["version"] == VERSION, "Ripristinare la versione del protocollo preregistrata")
    require(not db.execute("SELECT 1 FROM events WHERE batch=? AND kind='quarantine' AND id=?",
                           (b, case["id"])).fetchone(), "Caso già in quarantena")
    require(when <= day(case["released"]) + timedelta(days=3), "Tempo di giudizio scaduto")
    r = read(args.input)
    if isinstance(r, dict) and r.get("status") != "scored":
        fields(r, "id status reason")
        require(r["status"] in STATES - {"ready"}, "Stato non ammesso")
        text(r["reason"], "Motivo di astensione")
    else:
        fields(r, "id status basis run scores uncertainty")
        require((r["basis"] == "trace" and case["trace"]) or
                (r["basis"] == "recording" and case["media"]), "Base mancante nel dossier")
        blind_text(r["uncertainty"])
        refs = {f"trace:{i}" for i in range(1, len(case["trace"]) + 1)} | {m["file"] for m in case["media"]}

        def evidence(ref):
            require(isinstance(ref, str) and ref.split("@")[0] in refs, "Prova non presente nel dossier")

        fields(r["run"], "first_decision repeated_loop return_choice")
        for step in r["run"].values():
            fields(step, "evidence observation response")
            evidence(step["evidence"])
            blind_text(step["observation"])
            blind_text(step["response"])
        fields(r["scores"], " ".join(RUBRIC))
        for score in r["scores"].values():
            fields(score, "value evidence why")
            require(type(score["value"]) is int and 1 <= score["value"] <= 5, "Voti interi da 1 a 5")
            evidence(score["evidence"])
            blind_text(score["why"])
        mean = sum(s["value"] for s in r["scores"].values()) / len(RUBRIC)
        r["probabilities"] = {t["metric"]: round(max(0.01, min(0.99, t["baseline"] + (mean - 3) / 8)), 6)
                              for t in p["targets"]}
    require(r["id"] == case["id"], "ID del giudizio diverso dal dossier")
    put(db, b, "judge", when, r, case["id"])
    return {"frozen": case["id"], "status": r["status"], "sha256": hashlib.sha256(encode(r).encode()).hexdigest(),
            "probabilities": r.get("probabilities", {})}


def seal(db, p, when, cases):
    b = p["batch"]
    judged = {c for c, _, _, _ in rows(db, b, "judge")}
    missing = [r for r in cases if r["status"] == "ready" and r["id"] not in judged]
    require(all(when > day(r["released"]) + timedelta(days=3) for r in missing),
            "Giudizi mancanti: registrare anche le astensioni prima di aprire gli esiti")
    receipt = hashlib.sha256(encode(list(db.execute(
        "SELECT kind,id,day,recorded_utc,body FROM events WHERE batch=? ORDER BY kind,id", (b,)))).encode()).hexdigest()
    result = {"batch": b, "seal_sha256": receipt, "missed_deadline": [r["id"] for r in missing]}
    put(db, b, "seal", when, result)
    return result


def reveal(db, args, p, when, case):
    # Do not even open the outcome file until the entire batch has been sealed.
    one(db, p["batch"], "seal")
    r = read(args.input)
    fields(r, "id metric status source evidence as_of value game_release")
    metric = r["metric"]
    require(r["id"] == case["id"] and metric in {t["metric"] for t in p["targets"]},
            "Caso o target diverso dal piano")
    kind, source, horizon = TARGETS[metric]
    if kind == "game":
        for target, body in db.execute("SELECT target,body FROM events WHERE batch=? AND id=? AND kind='outcome'",
                                       (p["batch"], case["id"])):
            if TARGETS[target][0] == "game":
                require(r["game_release"] == json.loads(body)["game_release"],
                        "Stessa uscita del gioco richiesta per tutti i target gioco del caso")
    demo_day = day(case["released"])
    start = demo_day
    last_release = demo_day + timedelta(days=180)
    if kind == "game" and r["game_release"] is not None:
        start = day(r["game_release"])
        require(demo_day < start <= last_release, "Uscita del gioco non successiva alla demo o oltre D180")
    due = start + timedelta(days=horizon)
    if kind == "game" and r["game_release"] is None:
        require(r["status"] in ("not_released", "missing"), "Serve la data di uscita del gioco")
        due = last_release
    elif kind == "demo":
        require(r["game_release"] is None, "Non mescolare demo e gioco")
    require(when > due and day(r["as_of"]) == due, "Esito prematuro o riferito alla finestra sbagliata")
    text(r["evidence"], "Fonte archiviata e motivo se assente")
    require(r["source"] == source, "Fonte incompatibile: stime/proxy non sono dati proprietari")
    if r["status"] == "observed":
        target_count(metric, r["value"])
    else:
        require(r["value"] is None and (r["status"] == "missing" or
                (r["status"] == "not_released" and kind == "game" and r["game_release"] is None)),
                "Mancante non è zero")
    put(db, p["batch"], "outcome", when, r, case["id"], metric)
    return {"recorded": case["id"], "metric": metric, "status": r["status"]}


def report(db, p, cases):
    b = p["batch"]
    sealed = one(db, b, "seal")
    judged = {c: body for c, _, _, body in rows(db, b, "judge")}
    outcomes = {(c, t): body for c, t, _, body in rows(db, b, "outcome")}
    quarantine = {c for c, _, _, _ in rows(db, b, "quarantine")}
    states = {c["id"]: ("contaminated" if c["id"] in quarantine else
              judged[c["id"]]["status"] if c["id"] in judged else
              "missed_deadline" if c["status"] == "ready" else c["status"]) for c in cases}
    res = {"batch": b, "mode": p["mode"], "frame": "verified_listed_census" if p["frame_kind"] == "steam_listed"
           else "self_declared", "out_of_time": p["mode"] == "prospective",
           "model": p["model"], "setup": p["setup"], "sampling": p["sampling"],
           "train_through": p["train_through"], "test_window": [p["start"], p["end"]],
           "version": p["version"], "seal_sha256": sealed["seal_sha256"],
           "enrolled": len(cases), "dispositions": dict(Counter(states.values())), "targets": {}}
    for t in p["targets"]:
        key, base = t["metric"], t["baseline"]
        paired, all_frozen, bins, labels = [], [], [[] for _ in range(5)], Counter()
        for c, state in states.items():
            outcome = outcomes.get((c, key))
            labels[outcome["status"] if outcome else "pending"] += 1
            if judged.get(c, {}).get("status") != "scored" or not outcome or outcome["status"] != "observed":
                continue
            prob = judged[c]["probabilities"][key]
            y = int(outcome["value"] >= t["threshold"])
            all_frozen.append(((prob-y)**2, (base-y)**2))
            if state != "scored":
                continue
            bins[min(4, int(prob * 5))].append((prob, y))
            paired.append({"id": c, "p": prob, "actual": y, "value": outcome["value"],
                           "squared_error": (prob-y)**2, "baseline_error": (base-y)**2,
                           "direction": "over" if prob > y else "under" if prob < y else "exact",
                           "scores": judged[c]["scores"], "uncertainty": judged[c]["uncertainty"]})
        n = len(paired)
        mean = lambda k: math.fsum(row[k] for row in paired) / n if n else None
        bs, bs_base = mean("squared_error"), mean("baseline_error")
        predicted = sum(v == "scored" for v in states.values())
        res["targets"][key] = {
            "threshold": t["threshold"], "baseline": base, "baseline_n": len(t["history"]),
            "baseline_kind": "historical" if t["history"] else "naive",
            "outcomes_all_enrolled": dict(labels), "scored": predicted, "paired": n,
            "coverage_enrolled": n / len(cases) if cases else None,
            "coverage_scored": n / predicted if predicted else None,
            "brier": bs, "baseline_brier_same_cases": bs_base,
            "all_frozen_including_quarantine": {
                "paired": len(all_frozen),
                "brier": math.fsum(a for a, _ in all_frozen)/len(all_frozen) if all_frozen else None,
                "baseline_brier": math.fsum(a for _, a in all_frozen)/len(all_frozen) if all_frozen else None},
            "brier_gain": bs_base - bs if n else None,
            "calibration": [{"lower": i/5, "upper": (i+1)/5, "n": len(v),
                             "mean_p": math.fsum(x for x, _ in v)/len(v) if v else None,
                             "frequency": sum(y for _, y in v)/len(v) if v else None}
                            for i, v in enumerate(bins)],
            "largest_errors": sorted(paired, key=lambda r: -r["squared_error"])[:5],
            "interpretation": ("Rehearsal: nessuna accuratezza empirica." if p["mode"] == "rehearsal" else
                               "Descrittivo sul batch; non dimostra accuratezza generale.")}
    return res


def series(db):
    """All planned windows (including failures); never mix target, method or censuses."""
    groups = {}
    for (body,) in db.execute("SELECT body FROM events WHERE kind='plan' ORDER BY day,batch"):
        p = json.loads(body)
        b = p["batch"]
        intake_rows = rows(db, b, "intake")
        cases = intake_rows[0][3]["cases"] if intake_rows else []
        result = report(db, p, cases) if rows(db, b, "seal") else None
        for t in p["targets"]:
            config = {k: p[k] for k in ("version", "model", "setup", "mode", "frame_kind", "country", "sampling")}
            config.update(metric=t["metric"], threshold=t["threshold"],
                          baseline_method="historical" if t["history"] else "naive")
            g = groups.setdefault(encode(config), {"config": config, "windows": [], "enrolled_known": 0,
                                  "unknown_census": 0, "paired": 0, "sum_error": 0., "sum_base_error": 0.})
            metric = result["targets"][t["metric"]] if result else None
            g["windows"].append({"batch": b, "start": p["start"], "end": p["end"],
                                 "train_through": p["train_through"], "baseline": t["baseline"],
                                 "enrolled": len(cases) if intake_rows else None,
                                 "sealed": result is not None, "paired": metric["paired"] if metric else 0,
                                 "brier_gain": metric["brier_gain"] if metric else None})
            g["enrolled_known"] += len(cases)
            g["unknown_census"] += int(not intake_rows)
            if metric and metric["paired"]:
                n = metric["paired"]
                g["paired"] += n
                g["sum_error"] += n * metric["brier"]
                g["sum_base_error"] += n * metric["baseline_brier_same_cases"]
    for g in groups.values():
        n = g["paired"]
        err, base = g.pop("sum_error"), g.pop("sum_base_error")
        g.update(brier=err/n if n else None, baseline_brier=base/n if n else None,
                 coverage=n/g["enrolled_known"] if g["enrolled_known"] and not g["unknown_census"] else None)
    return list(groups.values())


def run(args):
    root = (Path(args.launch_dir) / "_raw" if args.launch_dir else
            Path(os.environ.get("GLS_HOME") or Path.home() / ".game-launch-strategist"))
    path = root / "demo-blind.sqlite3"
    readonly = args.cmd in ("batches", "series", "report", "pack")
    if readonly:
        if not path.exists():
            if args.cmd in ("batches", "series"):
                return []
            raise ValueError("Nessun batch registrato in questo archivio")
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    else:
        root.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    with closing(conn) as db, db:
        if not readonly:
            setup(db)
        db.execute("BEGIN" if readonly else "BEGIN IMMEDIATE")
        if args.cmd == "plan":
            return plan_batch(db, args)
        if args.cmd == "series":
            return series(db)
        if args.cmd == "batches":
            return [{"batch": b, "mode": pl["mode"], "frame_kind": pl["frame_kind"],
                     "window": [pl["start"], pl["end"]], "intake": bool(rows(db, b, "intake")),
                     "sealed": bool(rows(db, b, "seal")), "outcomes": len(rows(db, b, "outcome"))}
                    for (b,) in db.execute("SELECT batch FROM events WHERE kind='plan' ORDER BY day,batch")
                    for pl in [one(db, b, "plan")]]
        p = one(db, args.batch, "plan")
        when = clock(p, args)
        latest = db.execute("SELECT MAX(day) FROM events WHERE batch=?", (args.batch,)).fetchone()[0]
        require(when >= day(latest), "Non retrodatare il registro")
        if args.cmd == "frame":
            return private_frame(db, args, p, when)
        if args.cmd == "intake":
            return intake(db, args, p, when)
        cases = one(db, args.batch, "intake")["cases"]
        if args.cmd == "seal":
            return seal(db, p, when, cases)
        if args.cmd == "report":
            return report(db, p, cases)
        case = next((r for r in cases if r["id"] == args.case), None)
        require(case, "ID caso sconosciuto")
        if args.cmd == "pack":
            return pack(args, p, case)
        if args.cmd == "judge":
            return judge(db, args, p, when, case)
        if args.cmd == "quarantine":
            text(args.reason, "Motivo")
            put(db, args.batch, "quarantine", when, {"reason": args.reason}, args.case)
            return {"contaminated": args.case}
        return reveal(db, args, p, when, case)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(required=True, dest="cmd")
    for name, help_text in (
            ("plan", "Preregistra finestra, baseline, modello e target"),
            ("batches", "Elenca anche le coorti senza risultati o saltate"),
            ("series", "Confronta tutte le finestre per target e protocollo, senza selezionare i successi"),
            ("frame", "Congela il censimento di una fonte privata prima dei dossier"),
            ("intake", "Ammessa l'intera lista consecutiva del curatore"),
            ("pack", "Esporta un solo dossier anonimo in una cartella nuova"),
            ("judge", "Congela voti e pronostici oppure astensione"),
            ("seal", "Sigilla tutti i giudizi prima del reveal"),
            ("reveal", "Registra un'osservazione datata nella finestra del target"),
            ("quarantine", "Annota contaminazione scoperta dopo l'ammissione"),
            ("report", "Misura baseline e calibrazione sullo stesso campione")):
        cmd = sub.add_parser(name, help=help_text)
        cmd.add_argument("--launch-dir", help="Registro privato progetto; default: archivio GLS_HOME")
        cmd.add_argument("--as-of", help="Solo rehearsal, data simulata UTC (mai nel futuro)")
        if name not in ("plan", "batches", "series"):
            cmd.add_argument("--batch", required=True)
        if name in ("plan", "frame", "intake", "judge", "reveal"):
            cmd.add_argument("--input", required=True)
        if name == "intake":
            cmd.add_argument("--manifest", help="Snapshot completo demo_intake, privato")
        if name in ("pack", "judge", "reveal", "quarantine"):
            cmd.add_argument("--case", required=True)
        if name == "pack":
            cmd.add_argument("--out", required=True)
        if name == "quarantine":
            cmd.add_argument("--reason", required=True)
    try:
        print(encode(run(parser.parse_args())))
    except (ValueError, TypeError, OSError, sqlite3.Error) as e:
        print("demo_blind: " + str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
