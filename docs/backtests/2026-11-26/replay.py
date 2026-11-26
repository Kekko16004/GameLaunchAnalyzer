"""Offline retrospective: prepare -> two independent ballots -> freeze -> reveal."""
import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import random
import re
import statistics as st


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, item):
    with path.open("x", encoding="utf-8") as f:
        json.dump(item, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source():
    ds = Path(os.getenv("GLS_HOME") or Path.home()/".game-launch-strategist")/"cohorts"
    return ds/"cohort_2026-07-15_2026-07-21.csv"


def prepare(out):
    src = source()
    work = Path(src.with_suffix(".source").read_text(encoding="utf-8-sig").strip())
    rows, pitches = [], []
    perf = re.compile(r'\b(review(?:ed|s)?|wishlist\w*|acclaimed|award\w*|bestsell\w*|best.sell\w*|best.?selling|sold|million|sequel to|players worldwide|steam|kickstarter|followers?)\b|https?://|www\.', re.I)
    # No label columns are projected, reported or used by this stage.
    with src.open(encoding="utf-8-sig", newline="") as f:
        index = [{k:r.get(k) for k in ("appid","release_date","price")} for r in csv.DictReader(f)]
    for r in index:
        rel = r["release_date"] or ""
        if not "2026-07-15" <= rel <= "2026-07-21" or float(r["price"] or 0) <= 0:
            continue
        path = work/"apps"/(r["appid"]+".json")
        if not path.is_file():
            continue
        cache = read(path)
        page = cache.get("details") or {}
        if page.get("type") != "game" or page.get("is_free") is not False:
            continue
        news = cache.get("news")
        entry = dict(appid=r["appid"], release=rel, simple=None, strict=None)
        rows.append(entry)
        if not isinstance(news,list) or len(news)>=100 or any(not n.get("date") for n in news):
            continue
        pre = [n for n in news if n["date"] < rel and n.get("official")]
        kinds = {k for n in pre for k in n.get("kinds",[])}
        entry["simple"] = int(bool(kinds & {"demo","next_fest"}))
        entry["strict"] = int(entry["simple"] and len({n["date"] for n in pre})>=2)
        if "demo" not in kinds:
            continue
        text = html.unescape(re.sub(r"<[^>]*>", " ",page.get("short_description") or ""))
        text = " ".join(text.split())
        for ident in [page.get("name"),*(page.get("developers") or []),*(page.get("publishers") or [])]:
            if ident and ident.strip():
                text = re.sub(re.escape(ident.strip()),"[title]",text,flags=re.I)
        text = " ".join(s for s in re.split(r"(?<=[.!?])\s+",text) if not perf.search(s))
        if len(text)>=35:
            pitches.append((digest(("gls-july-pitch-20261126:"+r["appid"]).encode()),entry,text))
    pack = {}
    for i, (_,entry,text) in enumerate(sorted(pitches,key=lambda x:x[0])[:48],1):
        entry["alias"]=f"P{i:02d}"
        pack[entry["alias"]]=text
    out.mkdir(parents=True,exist_ok=True)
    save(out/"curator.json",rows)
    save(out/"pitches.json",pack)
    print("Candidati",len(rows),"regole datate",sum(x["simple"] is not None for x in rows),"pitch eleggibili",len(pitches),"selezionati",len(pack))


def freeze(out, ballots):
    cases = read(out/"pitches.json")
    a,b=(read(p) for p in ballots)
    if not set(a)==set(b)==set(cases):
        raise ValueError("Ballot mismatch")
    preds={}
    for k in cases:
        x,y=a[k],b[k]
        if x is not None and (type(x) not in (int,float) or x*2!=int(x*2) or not 1<=x<=5):
            raise ValueError(k)
        if y is not None and (not isinstance(y,list) or len(y)!=4 or any(type(v) is not int or not 1<=v<=5 for v in y)):
            raise ValueError(k)
        preds[k]=[x,st.mean(y) if y is not None else None]
    paths=[Path(__file__),Path(__file__).with_name("protocol.md"),out/"curator.json",out/"pitches.json",*ballots]
    save(out/"frozen.json",dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                                sha256={p.name:digest(p.read_bytes()) for p in paths},scores=preds))
    print("SHA256 congelato:",digest((out/"frozen.json").read_bytes()))


def binary(y,call):
    tp=sum(v and c for v,c in zip(y,call)); tn=sum(not v and not c for v,c in zip(y,call))
    fp=sum(call)-tp; fn=sum(y)-tp
    return dict(n=len(y),tp=tp,tn=tn,fp=fp,fn=fn,accuracy=(tp+tn)/len(y),
                precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None)


def auc(y, scores):
    pos=[s for s,v in zip(scores,y) if v]; neg=[s for s,v in zip(scores,y) if not v]
    return sum((a>b)+0.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg)) if pos and neg else None


def reveal(out,seal):
    frozen=read(out/"frozen.json")
    if digest((out/"frozen.json").read_bytes())!=seal: raise ValueError("Invalid seal")
    for n,h in frozen["sha256"].items():
        p=Path(__file__).with_name(n) if n in ("protocol.md","replay.py") else out/n
        if digest(p.read_bytes())!=h: raise ValueError("File changed: "+n)
    cases=read(out/"curator.json")
    # Only now read target labels, date-bounded and never imputed.
    y={}
    with source().open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            if r.get("reviews_d30","").isdigit() and r.get("release_date") and r.get("checked_d30"):
                if dt.date.fromisoformat(r["release_date"])+dt.timedelta(days=30)<=dt.date.fromisoformat(r["checked_d30"])<=dt.date(2026,11,26):
                    y[r["appid"]]=int(int(r["reviews_d30"])>=30)
    matched=[c for c in cases if c["appid"] in y and c["simple"] is not None]
    truth=[y[c["appid"]] for c in matched]
    result=dict(seal=seal,threshold="reviews_d30>=30",population=len(cases),market_scored=sum(c["simple"] is not None for c in cases),market={k:binary(truth,[c[k] for c in matched]) for k in ("simple","strict")})
    result["market"]["always_no"]=binary(truth,[0]*len(truth))
    pair=[(c["alias"],y[c["appid"]],*frozen["scores"][c["alias"]]) for c in matched if c.get("alias") and None not in frozen["scores"][c["alias"]]]
    truth=[r[1] for r in pair]; panel={}
    calls=[]; errors=[]
    for i,key in enumerate(("intuitive","structured"),2):
        scores=[r[i] for r in pair]; yes=[int(s>=3.5) for s in scores]; losses=[(0.5+(s-3)/8-v)**2 for s,v in zip(scores,truth)]
        panel[key]=dict(**binary(truth,yes),auc=auc(truth,scores),brier=st.mean(losses))
        calls.append(yes);errors.append(losses)
    panel["always_no"]=binary(truth,[0]*len(truth))
    rng=random.Random(1126)
    deltas=[int(b==v)-int(a==v) for a,b,v in zip(*calls,truth)]; loss_delta=[a-b for a,b in zip(*errors)]
    for name,values in (("accuracy_change",deltas),("brier_gain",loss_delta)):
        means=sorted(sum(rng.choices(values,k=len(values)))/len(values) for _ in range(10000))
        panel[name]=dict(mean=st.mean(values),ci95=[means[249],means[9749]])
    result["pitch"]=panel
    result["pitch_selected"]=len(frozen["scores"])
    result["abstentions"]={k:sum(v[i] is None for v in frozen["scores"].values()) for i,k in enumerate(("intuitive","structured"))}
    result["pitch_matched"]=[dict(alias=k,outcome=v,intuitive=a,structured=b) for k,v,a,b in pair]
    save(out/"results.json",result)
    print(json.dumps({k:v for k,v in result.items() if k!="pitch_matched"},indent=1))


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("phase",choices=["prepare","freeze","reveal"]); cli.add_argument("out",type=Path)
    cli.add_argument("--seal"); cfg=cli.parse_args()
    if cfg.phase=="prepare": prepare(cfg.out)
    elif cfg.phase=="freeze": freeze(cfg.out,[cfg.out/"a.json",cfg.out/"b.json"])
    else: reveal(cfg.out,cfg.seal)
