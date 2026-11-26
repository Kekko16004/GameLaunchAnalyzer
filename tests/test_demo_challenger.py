"""Challenger v2: synthetic ledger in temp, real CLI entrypoints, clock mocked only in tests."""
from contextlib import closing, redirect_stderr, redirect_stdout
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import os
import sqlite3
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

R = Path(__file__).resolve().parents[1]/"scripts"/"research"
sys.path.insert(0,str(R))
import demo_blind as primary
import demo_challenger as ch


METRIC = "demo_returns_first20_d7"
CONTEXT = dict(version=primary.VERSION,frame_kind="private",country=None,model="fixture.ai",
               setup="same timed trace",sampling="consecutive internal builds",baseline_method="naive")
T = timedelta(days=1)


def at(d,h=12):
    return datetime.combine(d,time(h),tzinfo=timezone.utc)


def suite(tmp):
    root = Path(tmp)
    ctx = root/"context.json"
    ctx.write_text(json.dumps(CONTEXT), encoding="utf8")
    v1 = root/"demo-blind.sqlite3"
    db = sqlite3.connect(v1)
    primary.setup(db)
    fit_day = date(2021,3,1)
    def ev(b,k,t,x,id="",metric=""):
        db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)",
                   (b,k,id,metric,str(t.date()),t.isoformat(),json.dumps(x)))
        db.commit()
    def plan(b,d,mode="prospective",when=None):
        when = when or d-2*T
        p = dict(CONTEXT,batch=b,start=str(d),end=str(d),mode=mode,train_through=str(when-T),
                 targets=[dict(metric=METRIC,threshold=10,history=[],baseline=.5)])
        del p["baseline_method"]
        ev(b,"plan",at(when),p)
    def intake(b,d,n,special=False,crossover=False):
        cases = []
        for idx in range(n):
            i, g = f"D{idx+1:04}", f"{b}-{idx}"
            if idx == 4 and crossover:
                g = "train1-1"
            status = "unplayable" if special and idx == n-1 else "ready"
            cases.append(dict(id=i,group=g,released=str(d),status=status))
        ev(b,"intake",at(d+T,7),{"cases":cases})
        for idx,c in enumerate(cases):
            if c["status"] == "ready":
                x = (5,1,3,3,3) if idx%2 else (1,5,3,3,3)
                j = dict(status="scored",scores={k:{"value":v} for k,v in zip(primary.RUBRIC,x)},
                         probabilities={METRIC:.5})
                ev(b,"judge",at(d+T,8),j,c["id"])
        ev(b,"seal",at(d+T,9),{"seal_sha256":hashlib.sha256(b.encode()).hexdigest()})
    def outcomes(b,d,n,special=False,reverse=False,recorded=None,oneclass=False):
        for idx in range(n):
            observed = not (special and idx == 0)
            value = 15 if oneclass or bool(idx%2)^reverse else 5
            o = dict(status="observed" if observed else "missing",value=value if observed else None,
                     as_of=str(d+7*T),evidence="synthetic fixture only")
            ev(b,"outcome",at(recorded or d+8*T),o,f"D{idx+1:04}",METRIC)
    def cli(cmd, when, *args, artifact="v2",ok=True):
        out, err = io.StringIO(), io.StringIO()
        primary_sha = hashlib.sha256(v1.read_bytes()).digest()
        argv = ["demo_challenger.py",cmd,"--artifact",artifact,*map(str,args)]
        with patch.object(sys,"argv",argv), patch.object(ch,"utcnow",return_value=at(when)), \
             redirect_stdout(out), redirect_stderr(err):
            rc = ch.main()
        assert (rc==0)==ok, (argv,out.getvalue(),err.getvalue())
        assert hashlib.sha256(v1.read_bytes()).digest()==primary_sha, "Challenger wrote v1!"
        return json.loads(out.getvalue()) if ok else err.getvalue()
    fit = ("--metric",METRIC,"--threshold","10","--context",ctx)
    for b,d,n,mode in [("train1",date(2021,1,1),20,"prospective"),
                        ("dry",date(2021,1,2),60,"rehearsal")]:
        plan(b,d,mode)
        intake(b,d,n)
        outcomes(b,d,n)
    r = cli("fit",fit_day,*fit)
    assert r["status"]=="non addestrabile" and r["summary"]["paired"]==20
    cli("show",fit_day,ok=False)
    d = date(2021,1,9)
    plan("train2",d)
    intake("train2",d,20)
    outcomes("train2",d,19)
    assert cli("fit",fit_day,*fit)["summary"]["paired"]==20  # not a cherry-picked partial cohort
    ev("train2","outcome",at(d+8*T),dict(status="observed",value=18,as_of=str(d+7*T)),"D0020",METRIC)
    # One full cohort revealed on fit day, not BEFORE fit day.
    d = date(2021,2,15)
    plan("late",d)
    intake("late",d,36)
    outcomes("late",d,36,recorded=fit_day)
    r = cli("fit",fit_day,*fit)
    assert r["status"].startswith("addestrato") and r["summary"]["paired"]==40
    assert r["summary"]["omitted_windows"][0]["batch"]=="late"
    model = cli("show",fit_day)
    assert model["weights"][0] > 0 and model["weights"][1] < 0 and model["cutoff_exclusive"]==str(fit_day)
    assert len(model["training"])==2 and model["training"][0]["paired"][0]["judge_sha256"]
    cli("fit",fit_day,*fit,ok=False)
    independent = dict(CONTEXT, model="second-model")
    ctx.write_text(json.dumps(independent), encoding="utf8")
    for suffix in (1,2):
        d = date(2020,11,1)+T*suffix*10
        b = f"oneclass{suffix}"
        p = dict(independent,batch=b,start=str(d),end=str(d),mode="prospective",train_through=str(d-5*T),
                 targets=[dict(metric=METRIC,threshold=10,history=[],baseline=.5)])
        del p["baseline_method"]
        ev(b,"plan",at(d-2*T),p)
        intake(b,d,20)
        outcomes(b,d,20,oneclass=True)
    only_positive = cli("fit",fit_day,*fit,artifact="no-negatives")
    assert only_positive["status"] == "non addestrabile" and only_positive["summary"]["negatives"] == 0
    ctx.write_text(json.dumps(CONTEXT), encoding="utf8")
    rare = cli("fit",fit_day,"--metric",METRIC,"--threshold",11,"--context",ctx,artifact="wrong_threshold")
    assert rare["status"]=="non addestrabile" and rare["summary"]["paired"]==0
    cli("reserve",fit_day,"--batches","train1",ok=False)
    days = [fit_day+i*T for i in (4,8,12)]
    names = ["test1","test2","test3"]
    for b,d in zip(names,days):
        plan(b,d,when=fit_day)
    cli("reserve",fit_day,"--batches","test1","test1",ok=False)
    cli("reserve",fit_day,"--batches",*names)
    cli("reserve",fit_day,"--batches","test1",ok=False)
    cli("fit",fit_day,*fit,artifact="another")
    cli("reserve",fit_day,"--batches","test1",artifact="another",ok=False)
    assert cli("evaluate",fit_day)["coverage"] is None
    for i,(b,d) in enumerate(zip(names,days)):
        intake(b,d,16,special=i==0,crossover=i==0)
        cli("freeze",d+4*T,"--batch",b,ok=False)  # can't retroactively score before reveal
        predictions = cli("freeze",d+T,"--batch",b)["predictions"]
        if not i:
            assert predictions[4]["status"] == "crossover" and predictions[-1]["status"]=="unplayable"
        assert predictions[1]["v2"]>.5 and predictions[1]["baseline"]==predictions[1]["v1"]==.5
        cli("freeze",d+T,"--batch",b,ok=False)
    before = cli("evaluate",days[-1]+T)
    assert before["paired"]==0 and before["brier"]["v2"] is None and before["decision"]=="non promuovere"
    for i,(b,d) in enumerate(zip(names,days)):
        outcomes(b,d,16,special=i==0)
        r = cli("evaluate",days[-1]+9*T)
        if i<2:
            assert r["decision"]=="non promuovere"
    assert r["windows"][0]["outcomes"]["missing"]==1
    assert r["paired"]==45 and r["coverage"]==45/48 and r["brier"]["v1"]==r["brier"]["baseline"]==.25
    assert r["brier"]["v2"] < .24 and r["decision"]=="candidato a revisione umana" and r["primary_unchanged"]
    ev("test3","quarantine",at(days[-1]+10*T),{"reason":"recognized"},"D0001")
    assert cli("evaluate",days[-1]+11*T)["decision"]=="non promuovere"
    ev("train1","quarantine",at(days[-1]+11*T),{"reason":"recognized"},"D0001")
    assert cli("evaluate",days[-1]+12*T)["training_quarantined_after_fit"]

    # New contest: fail closed if someone already opened ANY target before prediction.
    b,d = "broken",date(2021,5,1)
    plan(b,d,when=fit_day)
    cli("reserve",fit_day,"--batches",b,artifact="another")
    intake(b,d,4)
    ev(b,"outcome",at(d+T,10),{"status":"observed"},"D0001","unrelated_target")
    cli("freeze",d+T,"--batch",b,artifact="another",ok=False)
    r = cli("evaluate",d+20*T,artifact="another")
    assert r["windows"][0]["state"]=="freeze_mancante" and r["coverage"]==0 and r["paired"]==0
    with closing(sqlite3.connect(root/"demo-challenger.sqlite3")) as store:
        for sql in ("UPDATE ledger SET body='{}'","DELETE FROM ledger"):
            try:
                store.execute(sql)
            except sqlite3.IntegrityError:
                continue
            raise AssertionError("sidecar mutable")
    db.close()


if __name__ == "__main__":
    with TemporaryDirectory() as tmp, patch.dict(os.environ,GLS_HOME=tmp,HOME=tmp,USERPROFILE=tmp):
        suite(tmp)
    print("OK demo challenger: mature-only fit, immutable artifacts, prospective freezes, paired holdout gate")
