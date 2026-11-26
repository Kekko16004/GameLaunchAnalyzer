"""Prospective and rehearsal blind-demo CLIs, no network/home, fixed outcomes with hand-checked losses."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory

RESEARCH = Path(__file__).resolve().parents[1] / "scripts" / "research"
sys.path.insert(0, str(RESEARCH))
INTAKE = Path(importlib.util.find_spec("demo_intake").origin)
DB = RESEARCH / "demo_blind.py"


def suite(tmp):
    d = Path(tmp)
    env = dict(os.environ, GLS_HOME=str(d/"private"), HOME=str(d/"isolated"),
               USERPROFILE=str(d/"isolated"), PYTHONPATH=os.pathsep.join(
                   [str(RESEARCH), str(INTAKE.parent)]), GLS_REACH="off", PYTHONUTF8="1")
    def call(*args, ok=True, script=DB):
        p = subprocess.run([sys.executable, "-B", str(script), *args], cwd=d, env=env,
                           capture_output=True, text=True, encoding="utf8")
        assert (p.returncode == 0) == ok and "Traceback" not in p.stderr, (args, p.stdout, p.stderr)
        return json.loads(p.stdout) if ok and script == DB else p.stdout + p.stderr

    def write(name, data):
        (d/name).write_text(json.dumps(data), encoding="utf-8")
        return name

    def dated(cmd, when, *args, ok=True, batch="w1"):
        return call(cmd, "--as-of", when, *(["--batch", batch] if cmd != "plan" else []), *args, ok=ok)

    def admit(*args, ok=True):
        return dated("intake", "2020-02-03", "--manifest", "snap", "--input", "roster", *args, ok=ok)

    plan = {"batch":"w1", "mode":"rehearsal", "start":"2020-02-02", "end":"2020-02-02",
            "train_through":"2020-01-29", "frame_kind":"steam_listed", "country":"US",
            "sampling":"Censimento consecutivo US", "model":"modello-test", "setup":"prima run",
            "targets":[{"metric":"demo_reviews_d14","threshold":10,"history":[]},
                       {"metric":"game_units_d30","threshold":100,"history":[
                           {"group":"history1","observed":"2020-01-02","value":0,"evidence":"receipt-old"}]}]}
    today = datetime.now(timezone.utc).date()
    assert call("series") == [] and call("batches") == [] and not (d/"private").exists()
    future = str(today + timedelta(days=2))
    prospective = dict(plan, batch="real1", start=future, end=future, mode="prospective")
    write("plan", prospective)
    call("plan", "--input", "plan", "--as-of", "2020-01-31", ok=False)
    call("plan", "--input", "plan")
    call("intake", "--batch", "real1", "--input", "nothing", "--as-of", future, ok=False)
    write("plan", dict(plan, mode="prospective"))
    call("plan", "--input", "plan", ok=False)  # No historical runs passed as empirical
    for p in [dict(plan, train_through="2020-02-01"), dict(plan, start="2020-02-30"),
              dict(plan, end="2020-02-05"), dict(plan, start="2020-01-31"),
               dict(plan, targets=[dict(plan["targets"][1], metric="estimated_sales")]),
               dict(plan, targets=[{"metric":"demo_returns_first20_d7","threshold":21,"history":[]}]),
               dict(plan, targets=[{"metric":"demo_returns_first20_d7","threshold":5,"history":[
                   {"group":"h","observed":"2020-01-02","value":21,"evidence":"wrong denominator"}]}])]:
        dated("plan", "2020-01-31", "--input", write("plan", p), ok=False)
    dated("plan", "2020-01-31", "--input", write("plan", plan))
    dated("plan", "2020-01-31", "--input", write("plan", dict(plan,batch="retry")), ok=False)

    snap = {"source":"Steam search: listed demos, release date (category1=10)", "country":"US",
            "window":[plan["start"],plan["end"]], "observed_at":"2020-02-03T00:05:00+00:00",
            "complete":True, "warnings":[], "candidates":[{"appid":i,"release_date":"2020-02-02"}
                                                         for i in range(101,107)]}
    write("snap", snap)
    call("--prepare-roster", "snap", "--out", "draft", script=INTAKE)
    roster = json.loads((d/"draft").read_text())
    rows = roster["cases"]
    # Six consecutive cases: two viable traces, a failed build, one insufficient,
    # one contaminated, and one abstention after reading a pack.
    for r in [rows[0],rows[1],rows[5]]:
        r.update(status="ready",reason="",trace=["00:41 biforcazione osservata", "02:12 nuovo loop",
                                                 "07:03 seconda strategia"])
    rows[0]["media"] = ["RealTitle-watermarked-original-name.mp4"]
    (d/rows[0]["media"][0]).write_bytes(b"sanitized generic bytes in a synthetic fixture")
    rows[2].update(status="unplayable", reason="crash a freddo")
    rows[4].update(status="contaminated", reason="identità riconosciuta")
    write("roster", roster)
    for s in [dict(snap, complete=False), dict(snap,country="IT"), dict(snap,observed_at="2020-02-01T12:00:00Z"),
              dict(snap, candidates=list(reversed(snap["candidates"]))), dict(snap,window=["2020-01-31",plan["end"]])]:
        write("snap",s)
        admit(ok=False)
    write("snap",snap)
    for bad in [dict(roster,snapshot="f"*64),dict(roster,cases=rows[1:]),dict(roster,cases=rows[::-1]),
                dict(roster,cases=[dict(rows[0],trace=["3000 reviews su Steam"]),*rows[1:]]),
                dict(roster,cases=[dict(rows[0],title="leak"),*rows[1:]])]:
        write("roster",bad)
        admit(ok=False)
    write("roster",roster)
    assert admit()["cases"] == 6
    admit(ok=False)
    media = d / rows[0]["media"][0]
    original = media.read_bytes()
    media.write_bytes(original + b" changed")
    dated("pack","2020-02-03","--case","D0001","--out","bad",ok=False)
    assert not (d/"bad").exists()
    media.write_bytes(original)
    dated("pack","2020-02-03","--case","D0001","--out","handoff")
    files = sorted(x.name for x in (d/"handoff").iterdir())
    assert files == ["clip-01.mp4","dossier.json"]
    dossier = json.loads((d/"handoff"/files[1]).read_text())
    assert set(dossier) == {"id","media","rubric","targets","trace"}
    assert all(x not in json.dumps(dossier) for x in [rows[0]["group"], "RealTitle", "history1",
                                                       "receipt-old", "2020-02-02","baseline","appid"])
    dated("pack","2020-02-03","--case","D0001","--out","handoff",ok=False)
    dated("pack","2020-02-03","--case","D0003","--out","other",ok=False)

    def judgment(case, score):
        step = dict(evidence="trace:1", observation="Due corsie.", response="Proverei a sinistra.")
        return {"id":case,"status":"scored","basis":"trace","uncertainty":"Durata corta",
                "run":{k:step for k in ["first_decision","repeated_loop","return_choice"]},
                "scores":{k:dict(value=score,evidence="trace:2",why="Cambia il secondo percorso")
                          for k in ["gameplay","hook","variety","readability","replay"]}}
    def judge(r, case, ok=True):
        return dated("judge","2020-02-03","--case",case,"--input",write("judge",r),ok=ok)
    r = judgment("D0001",5)
    r["scores"]["gameplay"]["value"] = True
    judge(r, "D0001", ok=False)
    r = judgment("D0001",5)
    r["run"]["return_choice"]["evidence"] = "clip-99.mp4"
    judge(r, "D0001", ok=False)
    r = judgment("D0001",5)
    assert judge(r, "D0001")["probabilities"] == {"demo_reviews_d14":0.75, "game_units_d30":0.25}
    judge(judgment("D0001",1), "D0001", ok=False)  # no replacing a losing forecast
    assert judge(judgment("D0002",1),"D0002")["probabilities"]["demo_reviews_d14"] == 0.25
    assert "seal" in dated("reveal","2020-02-03","--case","D0001","--input","does-not-exist",ok=False)
    dated("seal","2020-02-03",ok=False)
    judge(dict(id="D0006",status="insufficient",reason="Il secondo loop non si vede"),"D0006")
    receipt = dated("seal","2020-02-03")["seal_sha256"]
    dated("seal","2020-02-03",ok=False)
    assert len(receipt) == 64
    empty = dated("report","2020-02-03")
    assert empty["targets"]["game_units_d30"]["coverage_scored"] == 0
    assert empty["targets"]["game_units_d30"]["brier"] is None

    def reveal(id, asof="2020-02-17", ok=True, **over):
        obs = dict(id=id,metric="demo_reviews_d14",status="observed",source="demo_review_snapshot",
                   as_of="2020-02-16",value=10,game_release=None,evidence="archived test receipt")
        obs.update(over)
        return dated("reveal",asof,"--case",id,"--input",write("out",obs),ok=ok)
    reveal("D0001","2020-02-16",ok=False)  # day not over yet
    reveal("D0001",as_of="2020-02-17",ok=False)
    reveal("D0001",metric="game_units_d30",source="estimated_owners",ok=False)
    reveal("D0001",value=True,ok=False)
    reveal("D0001",status="missing",value=0,ok=False)
    reveal("D0001")
    reveal("D0001",value=0,ok=False)
    reveal("D0002")  # a false negative
    reveal("D0003",status="missing",value=None)
    r = dated("report","2020-02-17")
    assert not r["out_of_time"] and r["frame"] == "verified_listed_census"
    assert r["seal_sha256"] == receipt and r["enrolled"] == 6
    assert r["dispositions"] == {"insufficient":2,"scored":2,"contaminated":1,"unplayable":1}
    m = r["targets"]["demo_reviews_d14"]
    assert m["outcomes_all_enrolled"] == {"observed":2,"pending":3,"missing":1}
    assert m["brier"] == (.25**2+.75**2)/2 and m["baseline_brier_same_cases"] == .25
    assert m["brier_gain"] == -.0625 and m["coverage_enrolled"] == 2/6 and m["coverage_scored"] == 1
    assert m["calibration"][1] == dict(lower=.2,upper=.4,n=1,mean_p=.25,frequency=1.0)
    assert m["largest_errors"][0]["id"] == "D0002"
    dated("quarantine","2020-02-17","--case","D0002","--reason","Riconosciuto nel video")
    m = dated("report","2020-02-17")["targets"]["demo_reviews_d14"]
    assert m["paired"] == 1 and m["all_frozen_including_quarantine"]["brier"] == .3125
    game = dict(metric="game_units_d30",source="owner_net_paid_units",as_of="2020-04-09",
                game_release="2020-03-10",value=113)
    reveal("D0001", "2020-04-10", **dict(game,source="estimated_owners"), ok=False)
    reveal("D0001", "2020-04-10", **dict(game,game_release="2020-02-01"), ok=False)
    reveal("D0001", "2020-04-10", **game)
    reveal("D0002", "2020-08-01", **dict(game,game_release=None,value=None,as_of="2020-07-31",status="not_released"))
    r = dated("report","2020-08-01")["targets"]["game_units_d30"]
    assert r["paired"] == 1 and r["brier"] == .75**2 and r["baseline_brier_same_cases"] == 1
    assert r["outcomes_all_enrolled"]["not_released"] == 1

    # Private projects: separate frame pinned before inspection; overlap cannot be scored;
    # missed deadlines stay enrolled. Empty/missed census does not invent a coverage ratio.
    priv = dict(plan,batch="p1",frame_kind="private",country=None,targets=[plan["targets"][1]])
    dated("plan","2020-01-31","--input",write("private-plan",priv))
    frame = {"complete":True,"cases":[dict(group="history1",released=plan["start"]),
                                     dict(group="new1",released=plan["start"])]}
    receipt = dated("frame","2020-02-03","--input",write("frame",frame),batch="p1")["snapshot"]
    assert receipt == hashlib.sha256((d/"frame").read_bytes()).hexdigest()
    items = [dict(x,trace=["00:10 azione"],media=[],reason="",status="ready") for x in frame["cases"]]
    private_roster = dict(snapshot=receipt,complete=True,cases=items)
    args = ("intake","2020-02-03","--input","p")
    write("p",private_roster)
    dated(*args,batch="p1",ok=False)
    items[0].update(status="contaminated",trace=[],reason="Nel training")
    write("p",private_roster)
    dated(*args,batch="p1")
    dated("judge","2020-02-06","--case","D0002","--input",write("judge",judgment("D0002",3)),batch="p1",ok=False)
    dated("seal","2020-02-06",batch="p1")
    r = dated("report","2020-02-06",batch="p1")
    assert r["frame"] == "self_declared" and r["dispositions"] == {"contaminated":1,"missed_deadline":1}
    dated("plan","2020-02-09","--input",write("p2",dict(priv,batch="p2",start="2020-02-10",end="2020-02-10")))
    groups = call("series")
    private = next(x for x in groups if x["config"]["frame_kind"] == "private")
    assert private["coverage"] is None and private["unknown_census"] == 1 and len(private["windows"]) == 2
    assert len(call("batches")) == 4
    isolated = dict(plan,batch="project1",frame_kind="private",country=None)
    dated("plan","2020-01-31","--input",write("iso",isolated),"--launch-dir","launch")
    assert len(call("batches","--launch-dir","launch")) == 1
    with sqlite3.connect(d/"private"/"demo-blind.sqlite3") as conn:
        for sql in ("DELETE FROM events", "UPDATE events SET id=id"):
            try:
                conn.execute(sql)
            except sqlite3.IntegrityError:
                pass
            else:
                raise AssertionError(sql)


if __name__ == "__main__":
    with TemporaryDirectory() as tmp:
        suite(tmp)
    print("OK blind-demo CLI: roster/pack, blind score, freeze, windows, calibration, missingness, series")
