#!/usr/bin/env python3
"""Optional blind-demo challenger. No network, clock overrides, or writes to the primary ledger."""
import argparse
from collections import Counter
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys

from demo_blind import RUBRIC, TARGETS, VERSION, day, encode, read, require, token


METHOD = "demo-challenger-ridge-v2.0"
CONTEXT = ("version", "frame_kind", "country", "sampling", "model", "setup", "baseline_method")
MIN_N, MIN_CLASS, MIN_FIT_WINDOWS = 30, 6, 2
MIN_COVERAGE = .8
GATE = dict(min_windows=3, min_pairs=30, min_each_class=6, min_window_coverage=.8,
            min_pooled_gain=.01, positive_gain_every_window=True)


def utcnow():
    return datetime.now(timezone.utc)


def stamp(s):
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    require(t.tzinfo is not None, "Timestamp UTC mancante")
    return t.astimezone(timezone.utc)


def digest(x):
    return hashlib.sha256(encode(x).encode()).hexdigest()


def events(db, batch, kind, target=None):
    sql = "SELECT id,day,recorded_utc,body FROM events WHERE batch=? AND kind=?"
    params = [batch, kind]
    if target is not None:
        sql += " AND target=?"
        params.append(target)
    return {i: (day(d), stamp(ts), json.loads(body))
            for i, d, ts, body in db.execute(sql + " ORDER BY id", params)}


def primary_plan(db, batch):
    rec = events(db, batch, "plan").get("")
    require(rec is not None, "Piano v1 assente: " + batch)
    return rec


def matches(plan, selector):
    if plan["mode"] != "prospective" or any(plan[k] != selector[k] for k in CONTEXT[:-1]):
        return None
    return next((t for t in plan["targets"] if t["metric"] == selector["metric"]
                 and t["threshold"] == selector["threshold"]
                 and ("historical" if t["history"] else "naive") == selector["baseline_method"]), None)


def protocol_time(rec, now):
    # Rehearsals can backdate `day`; real records must agree with their actual timestamp.
    return rec[0] == rec[1].date() and rec[1] <= now


def features(judge):
    scores = [judge["scores"][k]["value"] for k in RUBRIC]
    require(all(type(x) is int and 1 <= x <= 5 for x in scores), "Pagella v1 non valida")
    return [(x-3)/2 for x in scores]


def prob(intercept, weights, x):
    z = intercept + sum(w*v for w, v in zip(weights, x))
    return 1/(1+math.exp(-max(-25, min(25, z))))


def coefficients(samples):
    """Fixed ridge logistic regression; no search over holdouts or hyperparameters."""
    n = len(samples)
    positive = sum(y for _, y in samples)
    prior = math.log((positive+1)/(n-positive+1))
    bias, weights = prior, [0.]*len(RUBRIC)
    for _ in range(300):
        grad = [.1*(bias-prior)] + [.15*w for w in weights]
        for x, y in samples:
            error = (prob(bias, weights, x)-y)/n
            grad[0] += error
            for j, v in enumerate(x, 1):
                grad[j] += error*v
        bias -= .5*grad[0]
        weights = [w-.5*g for w, g in zip(weights, grad[1:])]
    return bias, weights


def save(store, artifact, kind, batch, now, data):
    store.execute("INSERT INTO ledger VALUES(?,?,?,?,?)", (artifact,kind,batch,now.isoformat(),encode(data)))


def load(store, artifact, kind, batch=""):
    row = store.execute("SELECT body FROM ledger WHERE artifact=? AND kind=? AND batch=?",
                        (artifact,kind,batch)).fetchone()
    require(row, f"{kind} assente: {artifact} {batch}")
    return json.loads(row[0])


def fit(db, store, args, now):
    require(not store.execute("SELECT 1 FROM ledger WHERE artifact=?", (args.artifact,)).fetchone(),
            "Artefatto già congelato: non sovrascrivo")
    selector = read(args.context)
    require(isinstance(selector, dict) and set(selector) == set(CONTEXT), "Campi contesto: " + ", ".join(CONTEXT))
    require(selector["version"] == VERSION and selector["baseline_method"] in ("historical","naive")
            and args.threshold > 0, "Contesto, baseline o soglia non compatibile")
    require(args.metric in TARGETS or args.metric == "demo_returns_first20_d7", "Target primario sconosciuto")
    require(args.metric != "demo_returns_first20_d7" or args.threshold <= 20, "D7: soglia massima 20")
    require(selector["frame_kind"] in ("private","steam_listed") and
            all(isinstance(selector[k],str) and selector[k].strip() for k in ("sampling","setup","model")),
            "Specificare frame, popolazione, modello e protocollo originali")
    selector.update(metric=args.metric, threshold=args.threshold)
    cutoff = now.date()
    seen, used_batches, skipped, samples, known_groups = set(), [], [], [], set()
    cells = Counter()
    total = 0
    for (b,) in db.execute("SELECT batch FROM events WHERE kind='plan' ORDER BY day,batch"):
        plan_ev = primary_plan(db, b)
        p = plan_ev[2]
        target = matches(p, selector)
        if target is None or day(p["end"]) >= cutoff:
            continue
        intake, seal = (events(db, b, k).get("") for k in ("intake","seal"))
        if not intake or not seal:
            skipped.append({"batch": b, "reason": "censimento/sigillo mancante"})
            continue
        outcomes = events(db,b,"outcome",args.metric)
        judges = events(db,b,"judge")
        quarantine = events(db,b,"quarantine")
        cases = intake[2]["cases"]
        if (set(outcomes) != {c["id"] for c in cases} or
                any(not protocol_time(e, now) or e[1].date() >= cutoff for e in
                    (plan_ev,intake,seal,*judges.values(),*outcomes.values()))):
            skipped.append({"batch":b,"reason":"esiti non tutti finali prima del giorno di fit"})
            continue
        require(plan_ev[0] < day(p["start"]) and day(p["train_through"]) < plan_ev[0],
                "Cronologia v1 non prospettica")
        known_groups.update(c["group"] for c in cases)
        known_groups.update(h["group"] for t in p["targets"] for h in t["history"])
        paired = []
        total += len(cases)
        for c in cases:
            i, g = c["id"], c["group"]
            o, j = outcomes[i], judges.get(i)
            require(seal[1] < o[1] and day(o[2]["as_of"]) < o[0], "Esito anticipato nel registro primario")
            if c["status"] != "ready" or i in quarantine or not j or j[2]["status"] != "scored":
                cells["non_scored_or_quarantined"] += 1
                continue
            if o[2]["status"] != "observed":
                cells[o[2]["status"]] += 1
                continue
            require(g not in seen, "Gruppo addestrabile duplicato: verificare il registro")
            require(intake[1] <= j[1] <= seal[1] and day(c["released"]) <= j[0] <=
                    day(c["released"]) + timedelta(days=3), "Pronostico v1 non prospettico")
            seen.add(g)
            x, y = features(j[2]), int(o[2]["value"] >= args.threshold)
            samples.append((x, y))
            paired.append({"id":i, "group":g, "judge_sha256":digest(j[2]), "observed_utc":o[1].isoformat(),
                           "outcome_sha256":digest(o[2])})
        used_batches.append({"batch":b, "window":[p["start"],p["end"]], "seal":seal[2]["seal_sha256"],
                             "enrolled":len(cases), "paired":paired})
    n, positives = len(samples), sum(y for _, y in samples)
    summary = {"paired":n, "enrolled_in_mature_windows":total, "positives":positives, "negatives":n-positives,
               "windows_with_pairs":sum(bool(w["paired"]) for w in used_batches), "excluded":dict(cells),
               "omitted_windows":skipped, "coverage":n/total if total else None}
    if (n < MIN_N or min(positives,n-positives) < MIN_CLASS or summary["windows_with_pairs"] < MIN_FIT_WINDOWS
            or summary["coverage"] < MIN_COVERAGE):
        return {"status":"non addestrabile","summary":summary,"artifact_created":False}
    ws = sorted((day(w["window"][0]),day(w["window"][1])) for w in used_batches)
    require(all(a[1] < b[0] for a,b in zip(ws,ws[1:])), "Finestre addestramento sovrapposte")
    bias, weights = coefficients(samples)
    artifact = {"id":args.artifact, "method":METHOD,"fit_utc":now.isoformat(),"cutoff_exclusive":str(cutoff),
                "context":selector,"features":list(RUBRIC),"intercept":bias,"weights":weights,
                "training":used_batches,"known_groups":sorted(known_groups),"summary":summary,"gate":GATE}
    save(store,args.artifact,"model","",now,artifact)
    return {"status":"addestrato, non validato","artifact":args.artifact,"sha256":digest(artifact),"summary":summary}


def reserve(db, store, args, model, now):
    windows = []
    for b in args.batches:
        pe = primary_plan(db, b)
        p = pe[2]
        require(protocol_time(pe, now) and matches(p, model["context"]) and
                day(p["start"]) > now.date() and not events(db,b,"intake"),
                "Serve un piano futuro dello stesso contesto e target, senza dossier aperti")
        require(not db.execute("SELECT 1 FROM events WHERE batch=? AND kind='outcome'",(b,)).fetchone(),
                "Esiti già disponibili")
        windows.append({"batch":b,"start":p["start"],"end":p["end"],"plan_sha256":digest(p)})
    windows.sort(key=lambda v:v["start"])
    require(all(a["end"] < b["start"] for a,b in zip(windows,windows[1:])), "Finestre ripetute o sovrapposte")
    for (body,) in store.execute("SELECT body FROM ledger WHERE kind='contest'"):
        prev = json.loads(body)
        require(prev["metric"] != model["context"]["metric"] or
                not ({w["batch"] for w in windows} & {w["batch"] for w in prev["windows"]}),
                "Holdout già riservato sul target; vietata la selezione fra challenger")
    contest = {"model_sha256":digest(model),"metric":model["context"]["metric"],"reserved_utc":now.isoformat(),
               "windows":windows,"gate":model["gate"]}
    save(store,args.artifact,"contest","",now,contest)
    return contest


def freeze(db, store, args, model, contest, now):
    window = next((w for w in contest["windows"] if w["batch"] == args.batch), None)
    require(window is not None, "Lotto non preregistrato")
    b = args.batch
    p = primary_plan(db,b)[2]
    require(digest(p) == window["plan_sha256"] and day(p["end"]) < now.date() <= day(p["start"])+timedelta(days=3),
            "Piano cambiato o freeze fuori finestra D+3")
    require(not db.execute("SELECT 1 FROM events WHERE batch=? AND kind='outcome'",(b,)).fetchone(),
            "Esito già aperto: non rigiocare il batch")
    intake, seal = (events(db,b,k).get("") for k in ("intake","seal"))
    require(intake and seal and all(protocol_time(e,now) for e in (intake,seal))
            and stamp(contest["reserved_utc"]) < intake[1] <= seal[1], "Serve sigillo v1 successivo alla prenotazione")
    metric = contest["metric"]
    target = matches(p,model["context"])
    used = set(model["known_groups"])
    used.update(h["group"] for t in p["targets"] for h in t["history"])
    for (body,) in store.execute("SELECT body FROM ledger WHERE artifact=? AND kind='freeze'",(args.artifact,)):
        used.update(r["group"] for r in json.loads(body)["cases"])
    quarantine, judges = events(db,b,"quarantine"), events(db,b,"judge")
    cases = []
    for c in intake[2]["cases"]:
        i, g = c["id"], c["group"]
        j = judges.get(i)
        state = ("crossover" if g in used else "contaminated" if i in quarantine else
                 j[2]["status"] if j else "missed_deadline" if c["status"] == "ready" else c["status"])
        r = {"id":i,"group":g,"status":state}
        used.add(g)
        if state == "scored":
            require(c["status"] == "ready" and protocol_time(j,now) and intake[1] <= j[1] <= seal[1] and
                    day(c["released"]) <= j[0] <= day(c["released"])+timedelta(days=3), "Giudizio v1 fuori tempo")
            r.update(v2=round(prob(model["intercept"],model["weights"],features(j[2])),8),
                     v1=j[2]["probabilities"][metric], baseline=target["baseline"], judge_sha256=digest(j[2]))
        cases.append(r)
    frozen = {"batch":b,"frozen_utc":now.isoformat(),"seal":seal[2]["seal_sha256"],"cases":cases}
    save(store,args.artifact,"freeze",b,now,frozen)
    return {"batch":b,"sha256":digest(frozen),"predictions":cases}


def evaluate(db, store, model, contest, now):
    total, all_pairs, wins, windows = 0, [], [], []
    key = contest["metric"]
    for w in contest["windows"]:
        b = w["batch"]
        intake = events(db,b,"intake").get("")
        row = store.execute("SELECT body FROM ledger WHERE artifact=? AND kind='freeze' AND batch=?",
                            (model["id"],b)).fetchone()
        cases = intake[2]["cases"] if intake else []
        total += len(cases)
        result = dict(batch=b, enrolled=len(cases) if intake else None)
        windows.append(result)
        if not row:
            result.update(state="freeze_mancante" if now.date() > day(w["start"])+timedelta(days=3)
                          else "in_attesa_del_freeze",paired=0)
            continue
        frozen = json.loads(row[0])
        require(digest(primary_plan(db,b)[2]) == w["plan_sha256"] and
                events(db,b,"seal")[""][2]["seal_sha256"] == frozen["seal"], "Registro primario cambiato")
        labels, states, pairs = Counter(), Counter(), []
        q, outcomes = events(db,b,"quarantine"), events(db,b,"outcome",key)
        require(intake and [c["id"] for c in cases] == [c["id"] for c in frozen["cases"]], "Roster cambiato")
        for r in frozen["cases"]:
            i = r["id"]
            o = outcomes.get(i)
            state = "contaminated" if i in q else r["status"]
            states[state] += 1
            label = o[2]["status"] if o else "pending"
            labels[label] += 1
            if state != "scored" or label != "observed":
                continue
            require(protocol_time(o, now) and o[1] > stamp(frozen["frozen_utc"]) and day(o[2]["as_of"]) < o[0],
                    "Risultato incompatibile con la previsione registrata")
            y = int(o[2]["value"] >= model["context"]["threshold"])
            pairs.append((y, *( (r[k]-y)**2 for k in ("v2","v1","baseline"))))
        n = len(pairs)
        coverage = n/len(cases) if cases else None
        losses = briers(pairs)
        mature = not labels["pending"]
        result.update(state="maturato" if mature else "esiti_in_attesa",paired=n,coverage=coverage,
                      dispositions=dict(states),outcomes=dict(labels),brier=losses)
        all_pairs.extend(pairs)
        # A quarantine after freeze is important evidence but not a license to drop hard losses.
        late_quarantine = any(r["status"] == "scored" and r["id"] in q for r in frozen["cases"])
        result["quarantine_after_prediction"] = late_quarantine
        wins.append(bool(n and mature and coverage >= GATE["min_window_coverage"] and not late_quarantine
                         and losses["v2"] < min(losses["v1"],losses["baseline"])))
    n = len(all_pairs)
    bs = briers(all_pairs)
    positives = sum(r[0] for r in all_pairs)
    invalidated = any(set(events(db,w["batch"],"quarantine")).intersection(r["id"] for r in w["paired"])
                      for w in model["training"])
    passed = (not invalidated and len(windows) >= GATE["min_windows"] and len(wins) == len(windows) and all(wins)
              and n >= GATE["min_pairs"] and min(positives,n-positives) >= GATE["min_each_class"]
              and min(bs["v1"],bs["baseline"])-bs["v2"] >= GATE["min_pooled_gain"])
    return {"artifact":model["id"],"windows":windows,"paired":n,"positives":positives,"negatives":n-positives,
            "coverage":n/total if total and all(w["enrolled"] is not None for w in windows) else None,
            "brier":bs,"training_quarantined_after_fit":invalidated, "gate":GATE,
            "decision":"candidato a revisione umana" if passed else "non promuovere",
            "primary_unchanged":True}


def briers(pairs):
    return {k:math.fsum(r[j] for r in pairs)/len(pairs) if pairs else None
            for j,k in enumerate(("v2","v1","baseline"),1)}


def run(args):
    token(args.artifact)
    root = Path(args.launch_dir)/"_raw" if args.launch_dir else Path(
        os.environ.get("GLS_HOME") or Path.home()/".game-launch-strategist")
    uri = (root/"demo-blind.sqlite3").resolve().as_uri()+"?mode=ro"
    with closing(sqlite3.connect(uri,uri=True)) as db, closing(sqlite3.connect(root/"demo-challenger.sqlite3")) as store, store:
        store.executescript("""
            CREATE TABLE IF NOT EXISTS ledger(artifact TEXT,kind TEXT,batch TEXT,utc TEXT,body TEXT,
                PRIMARY KEY(artifact,kind,batch));
            CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON ledger
                BEGIN SELECT RAISE(ABORT,'append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON ledger
                BEGIN SELECT RAISE(ABORT,'append-only'); END;
        """)
        store.execute("BEGIN IMMEDIATE")
        db.execute("BEGIN")
        now = utcnow()
        if args.cmd == "fit":
            return fit(db,store,args,now)
        model = load(store,args.artifact,"model")
        require(model["method"] == METHOD and model["gate"] == GATE, "Ripristinare la versione congelata")
        require(stamp(model["fit_utc"]) <= now, "Orologio incoerente con il fit")
        if args.cmd == "show":
            return model
        if args.cmd == "reserve":
            return reserve(db,store,args,model,now)
        contest = load(store,args.artifact,"contest")
        require(contest["model_sha256"] == digest(model) and stamp(contest["reserved_utc"]) <= now,
                "Modello o orologio incoerente")
        if args.cmd == "freeze":
            return freeze(db,store,args,model,contest,now)
        return evaluate(db,store,model,contest,now)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd",required=True)
    for cmd in ("fit","show","reserve","freeze","evaluate"):
        s = sub.add_parser(cmd)
        s.add_argument("--artifact",required=True)
        s.add_argument("--launch-dir")
        if cmd == "fit":
            s.add_argument("--context",required=True)
            s.add_argument("--metric",required=True)
            s.add_argument("--threshold",type=int,required=True)
        if cmd == "reserve":
            s.add_argument("--batches",nargs="+",required=True)
        if cmd == "freeze":
            s.add_argument("--batch",required=True)
    try:
        print(encode(run(p.parse_args())))
    except (OSError,ValueError,TypeError,sqlite3.Error,KeyError) as e:
        print(f"demo_challenger: {e}",file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
