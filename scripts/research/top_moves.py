#!/usr/bin/env python3
"""The 3 moves with the most impact right now, computed from the data and written into TODO.md and calendar.md.

Candidates (each with the reason, the expected effect, the hours and who does it):
  issues   open focus-group issues without a closed decision: severity x share of testers (SIMULATO)
  recipe   steps of the real B-tier winners (calibration.json -> marketing.recipe) that the game does not have yet:
           share in winners minus share in losers ([FATTO] on the sample, correlation, not a guarantee)
  metro    the levers of the objective metric (launch/_raw/metro.json): how many points of P(>= 1,000 copies) each missing
           factor adds [STIMA]; merged with the recipe step of the same thing (one move, the stronger reason)
  todo     open TODO.md items and calendar steps that are overdue or due within 14 days
  fest     Steam event registrations closing soon (launch/_raw/steam_events_deadlines.json from steam_events.py deadlines):
           "register for fest X by date Y"; 50 within 21 days, 35 within 45 days [FATTO: Valve's dates]
  cases    from the Reddit cases (references/09-reddit-casi.md): "send the trailer to the aggregators" when the trailer is done and
           no TODO / calendar line mentions aggregators (32: the lever most often tied to a jump, 14 confirm / 3 contradict);
           the heaviest failed items of launch/_raw/flopcheck.json (social_content.py flopcheck): score 10 + 6 x weight (1-5,
           how often flop threads blame that factor) [OPINIONE of the commenters, counted]
  promo    the nearest high-priority feasible (not long-shot) online showcase / third-party fest application (launch/_raw/promo_events_deadlines.json
           from promo_events.py deadlines): 40 within 21 days, 30 within 45 days [OPINIONE: value score]
Score (0-100, rules not magic): issue = weight(alta 3, media 2, bassa 1) / 3 x % testers; recipe = winners% - losers%
(only if the gap is >= 10 points and both groups have >= 5 games); metro = 2 x points gained (>= 2 points); todo = 45 overdue, 35 within 7 days, 25 within 14 (being late is not the same as having impact).
At most 2 moves from the same source. Ties: earlier deadline first.

`apply` (run on every skill run, before status_page.py):
  - removes the old "⭐ mossa top" marks from TODO.md and calendar.md;
  - for each move: if an open TODO line matches, marks it "⭐ mossa top"; otherwise adds it to the TODO section
    "⭐ Le 3 mosse a più impatto"; same in calendar.md: marks a matching open step, otherwise adds a dated step
    (👤 / 🤖) to the phase "### ⭐ Mosse a più impatto" with the next free number. Nothing is ever duplicated; the files are
    written only when something changes.
  - writes launch/_raw/top_moves.json (read by STATUS.html).

  top_moves.py show  [--launch-dir launch] [--calibration PATH]
  top_moves.py apply [--launch-dir launch] [--calibration PATH] [--today D]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re

import common
import plan_steps as ps
import todo_track as tt

MARK = "⭐ mossa top · "
SEV_W = {"alta": 3, "media": 2, "bassa": 1}
STEP_WORDS = {"playtest": ["playtest"], "trailer": ["trailer"], "demo": ["demo"], "festival": ["festival", "vetrina", "showcase"],
              "next_fest": ["next fest", "nextfest"], "creators": ["creator", "youtuber", "streamer", "influencer"],
              "updates": ["aggiornament", "patch", "roadmap", "update"], "aggregators": ["aggregator", "indie games hub", "gametrailers", "ign indie"]}
STEP_HOURS = {"playtest": "3-6 h", "trailer": "10-20 h", "demo": "20-40 h", "festival": "2-4 h per candidatura", "next_fest": "4-8 h (iscrizione, pagina, stream)",
              "creators": "6-10 h (lista e email)", "updates": "pianificazione 2 h"}
METRO_STEP = {"trailer": "trailer", "demo_pre": "demo", "nextfest_pre": "next_fest", "playtest_pre": "playtest"}
METRO_WORDS = {"trailer": ["trailer"], "demo_pre": ["demo"], "nextfest_pre": ["next fest"], "playtest_pre": ["playtest"], "langs_log": ["lingue", "traduz"],
               "comingsoon_log": ["coming soon"], "news_pre_log": ["notizi", "devlog", "news"], "gif": ["gif"], "screens": ["screenshot"]}
STEP_OWNER = {"trailer": "👤+🤖", "demo": "👤+🤖", "creators": "👤+🤖", "playtest": "👤", "festival": "👤", "next_fest": "👤", "updates": "👤+🤖"}


def words(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-zàèéìòù]{5,}", (s or "").lower()) if w not in ("della", "delle", "nella", "sulla", "questo", "quella", "prima", "dopo", "senza")]


def our_status(root: str) -> dict[str, str]:
    """done / planned / missing for every recipe step, from TODO.md and calendar.md."""
    t = tt.parse(os.path.join(root, "TODO.md"))
    cal = os.path.join(root, "calendar.md")
    plan = ps.parse(open(cal, encoding="utf-8").read()) if os.path.exists(cal) else dict(phases=[])
    lines = [((x["action"] + " " + t["lines"][x["line"]]).lower(), x["done"]) for x in (t or {}).get("items", []) if not x["dropped"]]
    lines += [(s["text"].lower(), s["done"]) for s in ps.all_steps(plan)]
    out = {}
    for k, ws in STEP_WORDS.items():
        hits = [d for txt, d in lines if any(w in txt for w in ws)]
        # done only when every line about it is ticked: a ticked "decide the demo plan" does not make the demo done
        out[k] = "manca" if not hits else ("fatto" if all(hits) else "pianificato")
    return out


def load_cal(path: str | None) -> dict | None:
    p = path or common.user_dir("calibration.json")
    return common.load_json(p) if os.path.exists(p) else None


def candidates(root: str, today: dt.date, cal: dict | None) -> list[dict]:
    out = []
    # ---- open issues (SIMULATO)
    try:
        import criticita as cr
        st = common.load_json(os.path.join(root, "status.json")) if os.path.exists(os.path.join(root, "status.json")) else {}
        _, data = cr.build(root, st)
        for x in (data or {}).get("issues", []):
            if not x.get("now"):
                continue
            pct = x.get("last_pct") or 0
            out.append(dict(source="issue", key=x.get("key"), title=f"Risolvi: {x.get('label')}", score=round(SEV_W.get(x.get("severity"), 2) / 3 * pct, 1),
                            why=f"segnalato dal {pct:.0f} % dei tester simulati nell'ultima ondata, gravità {x.get('severity')} (SIMULATO)",
                            effect="meno abbandoni e più wishlist nella prossima ondata; da verificare con i tester veri",
                            hours=None, owner="🤖", due=None, match=words(x.get("label"))[:4]))
    except Exception as e:  # noqa: BLE001
        common.log(f"WARN issues not read: {e}")
    # ---- winners' recipe ([FATTO] on the sample)
    rec = ((cal or {}).get("marketing") or {}).get("recipe") or []
    mine = our_status(root)
    for r in rec:
        w, l_ = r.get("winners"), r.get("losers")
        if w is None or l_ is None or r.get("n_winners", 0) < 5 or r.get("n_losers", 0) < 5:
            continue
        gap = w - l_
        if gap >= 10 and mine.get(r["step"]) != "fatto":
            when = r.get("median_days_before")
            out.append(dict(source="recipe", key=r["step"], title=f"{r['label']}" + (f" (i B vincenti: circa {int(when)} giorni prima dell'uscita)" if when and when > 0 else ""),
                            score=round(gap, 1), why=f"c'è nel {w:.0f} % dei B vincenti e nel {l_:.0f} % dei perdenti (n = {r['n_winners']} / {r['n_losers']}, dati del {cal.get('generated_on')}); da noi: {mine.get(r['step'])}",
                            effect="correlazione con le vendite dei giochi della nostra fascia, non una garanzia [FATTO sul campione]",
                            hours=STEP_HOURS.get(r["step"]), owner=STEP_OWNER.get(r["step"], "👤"), due=None, match=STEP_WORDS.get(r["step"], [])))
    # ---- metro levers ([STIMA]); same step as a recipe move -> one move
    met = common.load_json(os.path.join(root, "_raw", "metro.json")) if os.path.exists(os.path.join(root, "_raw", "metro.json")) else None
    for lv in ((met or {}).get("score") or {}).get("levers") or []:
        if lv["delta_p1k_pp"] < 2:
            continue
        step = METRO_STEP.get(lv["feature"])
        sc = min(100.0, 2 * lv["delta_p1k_pp"])
        why = f"il metro oggettivo stima +{lv['delta_p1k_pp']} punti di probabilità di superare 1.000 copie [STIMA, {((met or {}).get('metro') or {}).get('strength', 'non verificato')}]"
        twin = next((c for c in out if c["source"] == "recipe" and c["key"] == step), None) if step else None
        if twin:
            twin["why"] += "; " + why
            twin["score"] = max(twin["score"], sc)
            continue
        out.append(dict(source="metro", key=lv["feature"], title=lv["label"], score=round(sc, 1), why=why, effect=f"P(≥1.000 copie) da {round(100 * (met['score']['p1k']))} % a {round(100 * lv['p1k_after'])} % [STIMA]",
                        hours=STEP_HOURS.get(step) if step else None, owner=STEP_OWNER.get(step, "👤+🤖") if step else "👤+🤖", due=None, match=METRO_WORDS.get(lv["feature"], [])))
    # ---- Steam events: registrations that close soon (steam_events.py deadlines -> _raw/steam_events_deadlines.json) [FATTO Valve]
    fest_dates = set()
    sev = common.load_json(os.path.join(root, "_raw", "steam_events_deadlines.json")) if os.path.exists(os.path.join(root, "_raw", "steam_events_deadlines.json")) else None
    for st in (sev or {}).get("steps") or []:
        if st.get("kind") != "registrazione" or not st.get("deadline"):
            continue
        days = (dt.date.fromisoformat(st["deadline"]) - today).days
        sc = 50 if 0 <= days <= 21 else 35 if 0 <= days <= 45 else 0
        if not sc:
            continue
        fest_dates.add(st["deadline"])
        est = " (data stimata: ~6 settimane prima dell'evento [DA VERIFICARE])" if st.get("estimated") else ""
        out.append(dict(source="fest", key=st.get("key"), title=f"Iscriviti a {st['event']} entro il {st['deadline']}", score=sc,
                        why=f"la scadenza Valve è tra {days} giorni{est}; dopo non si entra più: visibilità gratis persa",
                        effect="una vetrina ufficiale di Steam in più (sezione del fest per Coming Soon e demo) [FATTO regole Valve]",
                        hours="0,5-1 h", owner="👤", due=st.get("due") or st["deadline"], match=[w for w in words(st["event"]) if w not in ("steam",)][:2] or ["fest"]))
    # ---- online showcases and third-party fests (promo_events.py deadlines -> _raw/promo_events_deadlines.json): only the
    # nearest high-value application, so the plan never fills up with showcase forms [OPINIONE on the value score]
    promo_keys = set()
    pev = common.load_json(os.path.join(root, "_raw", "promo_events_deadlines.json")) if os.path.exists(os.path.join(root, "_raw", "promo_events_deadlines.json")) else None
    near = []
    for st in (pev or {}).get("steps") or []:
        if st.get("kind") != "candidatura" or not st.get("deadline") or st.get("priority") != "alta" or st.get("tier") != "fattibile":
            continue
        days = (dt.date.fromisoformat(st["deadline"]) - today).days
        if 0 <= days <= 45:
            near.append((days, -(st.get("score") or 0), st))
    if near:
        days, _, st = min(near, key=lambda x: (x[0], x[1]))
        promo_keys.add(st["key"])
        est = " (data stimata dai mesi abituali [DA VERIFICARE])" if st.get("estimated") else ""
        out.append(dict(source="promo", key=st["key"], title=f"Candidati a {st['event']} entro il {st['deadline']}", score=40 if days <= 21 else 30,
                        why=f"la candidatura chiude tra {days} giorni{est}; valore {st.get('score')}/18, possibilità reale di essere presi [OPINIONE]",
                        effect="uno spazio in uno showcase o fest online (pagina del fest, segmento in diretta) [STIMA: dipende dalla selezione]",
                        hours="0,5-1 h", owner="👤", due=st.get("due") or st["deadline"], match=[w for w in re.findall(r"[a-zà-ù]{3,}", st["event"].lower()) if w not in ("the", "and", "fest", "show", "games", "game", "showcase")][:2] or ["candidati"]))
    # ---- social (social_content.py): repeat what works for THIS game [FATTO on our posts]; keep recording numbers
    sl = common.load_json(os.path.join(root, "_raw", "social_learn.json")) if os.path.exists(os.path.join(root, "_raw", "social_learn.json")) else None
    for w in ((sl or {}).get("winners") or [])[:1]:
        out.append(dict(source="social", key=f"social-win-{w['key']}", title=f"Rifai 3 post con {w['field']} {w['key']} (rende {w['lift']}× la nostra mediana)", score=30,
                        why=f"sui nostri post registrati {w['key']} fa {w['lift']}× le visualizzazioni mediane (n = {w['n']}) [FATTO, campione piccolo]",
                        effect="più visualizzazioni a parità di ore; le wishlist si leggono il giorno dopo in Steamworks", hours="2-3 h", owner="👤", due=None, match=["post", w["key"].lower()]))
    spl = common.load_json(os.path.join(root, "_raw", "social_plan.json")) if os.path.exists(os.path.join(root, "_raw", "social_plan.json")) else None
    if spl:
        posted = [p_ for p_ in spl.get("posts", []) if p_.get("date") and p_["date"] <= today.isoformat()]
        if len(posted) >= 3 and (not sl or (sl.get("n") or 0) < len(posted) // 2):
            out.append(dict(source="social", key="social-track", title="Registra i numeri dei post usciti (social_content.py track)", score=22,
                            why=f"{len(posted)} post del piano sono già passati ma i numeri registrati sono {(sl or {}).get('n') or 0}: senza numeri non si capisce cosa rifare",
                            effect="il piano impara quali momenti e ganci tenere", hours="15 min", owner="👤", due=today.isoformat(), match=["numeri", "post"]))
    # ---- Reddit cases (references/09-reddit-casi.md): aggregators once the trailer exists; heaviest flop-checklist failures
    stt = our_status(root)
    if stt.get("trailer") == "fatto" and stt.get("aggregators") == "manca":
        out.append(dict(source="cases", key="cases-aggregators", title="Manda il trailer agli aggregatori (Indie Games Hub, GameTrailers, IGN Indie)", score=32,
                        why="nei casi Reddit 2026 è la leva più spesso legata a un salto (14 casi la confermano, 3 la smentiscono); YouTube converte 10-35 wishlist ogni 1.000 view [FATTO sui casi, auto-dichiarati]",
                        effect="un repost visto da 20-200k persone (Pennants of Glory 70.949 view su Indie Games Hub, Koromi 229.045 su GameTrailers) [STIMA per noi]",
                        hours="1 h (mail o modulo)", owner="👤", due=None, match=["aggregator", "indie games hub"]))
    fcp = os.path.join(root, "_raw", "flopcheck.json")
    fc = common.load_json(fcp) if os.path.exists(fcp) else None
    for x in [i for i in (fc or {}).get("items", []) if i.get("status") == "fail"][:2]:
        out.append(dict(source="cases", key=f"flopcheck-{x['id']}", title=f"Sistema: {x['fix']}", score=10 + 6 * x["weight"],
                        why=f"controllo 'perché floppa' ({x['id']}, peso {x['weight']}/5): {x.get('evidence', '')} [OPINIONE dei commentatori, contata]",
                        effect="toglie una delle cause di flop più citate nei commenti dei casi reali", hours=None, owner="👤+🤖", due=None,
                        match=[w for w in re.findall(r"[a-zà-ù]{5,}", x["fix"].lower())][:2]))
    # ---- publisher (publisher_scout.py): the owner said yes / don't know and someone is realistic now
    pub = common.load_json(os.path.join(root, "_raw", "publisher_scout.json")) if os.path.exists(os.path.join(root, "_raw", "publisher_scout.json")) else None
    if pub and pub.get("publisher_question") in ("yes", "dont_know") and (pub.get("counts") or {}).get("realistic_now"):
        top = [r["name"] for r in pub["rows"] if r["tier"] == "realistic_now"][:5]
        out.append(dict(source="publisher", key="publisher-pitch", title=f"Manda la proposta a {len(top)} publisher realistici ({', '.join(top[:3])}…)", score=18,
                        why=f"realistici adesso secondo publisher_scout.py; probabilità di almeno un'offerta ≤ {round(100 * pub['pitch_top']['p_any'])} % [STIMA]",
                        effect="un'opzione in più senza fermare il piano da soli", hours="4-6 h (deck + mail)", owner="👤+🤖", due=None, match=["publisher", "proposta"]))
    # ---- deadlines
    t = tt.parse(os.path.join(root, "TODO.md"))
    for x in (t or {}).get("items", []):
        if x["done"] or x["dropped"] or not x["due_date"]:
            continue
        if any(d in t["lines"][x["line"]] for d in fest_dates):
            continue                     # the same registration is already a "fest" move
        if any(f"[id promo:{k}]" in t["lines"][x["line"]] for k in promo_keys):
            continue                     # the same application is already a "promo" move
        days = (x["due_date"] - today).days
        sc = 45 if days < 0 else 35 if days <= 7 else 25 if days <= 14 else 0
        if sc:
            out.append(dict(source="todo", key=f"todo-{x['n']}", title=re.sub(r"[*`]", "", x["action"]).replace(MARK.strip(), "").strip(" ·"), score=sc,
                            why=("in ritardo dal " if days < 0 else "scade il ") + x["due_date"].isoformat(), effect=x.get("metric") or "voce del piano",
                            hours=x.get("hours") or None, owner={"me": "👤", "claude": "🤖", "both": "👤+🤖"}.get(x["owner"], "👤"), due=x["due_date"].isoformat(),
                            match=[], todo_line=x["line"]))
    return out


def pick(cands: list[dict], k: int = 3) -> list[dict]:
    chosen, per = [], {}
    seen_titles = set()
    for c in sorted(cands, key=lambda c: (-c["score"], c.get("due") or "9999")):
        if per.get(c["source"], 0) >= 2 or c["title"].lower() in seen_titles:
            continue
        chosen.append(c); per[c["source"]] = per.get(c["source"], 0) + 1; seen_titles.add(c["title"].lower())
        if len(chosen) == k:
            break
    return chosen


def compute(root: str, today: dt.date, cal_path: str | None = None) -> list[dict]:
    return pick(candidates(root, today, load_cal(cal_path)))


def _strip_marks(lines: list[str]) -> list[str]:
    return [ln.replace(MARK, "") for ln in lines]


def action_of(line: str) -> str:
    """The action of a TODO line or calendar step: the **bold** part if any, else the text before the first " — " or " · "."""
    m = re.search(r"\*\*(.+?)\*\*", line)
    if m:
        return m.group(1)
    body = re.sub(r"^\s*(?:[-*]|\d+\.)\s*\[.\]\s*", "", line)
    return re.split(r" — | \| | · 📅", body)[0]


def _match_line(lines: list[str], idxs: list[int], m: dict) -> int | None:
    if m.get("todo_line") is not None:
        return m["todo_line"]
    ws = m.get("match") or []
    if not ws:
        return None
    for i in idxs:
        low = action_of(lines[i]).lower()   # only the action itself, not the notes or the metric of the line
        hit = sum(1 for w in ws if w in low)
        if hit >= (1 if m["source"] == "recipe" else min(2, len(ws))):
            return i
    return None


def _mark(line: str) -> str:
    m = re.match(r"^(\s*(?:[-*]|\d+\.)\s*\[ \]\s*(?:👤\s*\+\s*🤖|👤|🤖)?\s*)(.*)$", line)
    return (m.group(1) + MARK + m.group(2)) if m else line


def apply(root: str, today: dt.date, moves: list[dict]) -> dict:
    res = dict(todo_marked=0, todo_added=0, cal_marked=0, cal_added=0)
    # ---- TODO.md
    tp = os.path.join(root, "TODO.md")
    if os.path.exists(tp):
        raw = open(tp, encoding="utf-8").read()
        lines = _strip_marks(raw.splitlines())
        t = tt.parse(tp)
        open_idx = [x["line"] for x in t["items"] if not x["done"] and not x["dropped"]]
        to_add = []
        for m in moves:
            i = _match_line(lines, open_idx, m)
            if i is not None:
                lines[i] = _mark(lines[i]); res["todo_marked"] += 1; m["todo"] = "segnata"
            else:
                to_add.append(m)
        new = "\n".join(lines) + ("\n" if raw.endswith("\n") else "")
        if new != raw:
            with open(tp, "w", encoding="utf-8", newline="\n") as f:
                f.write(new)
        for m in to_add:
            due = m.get("due") or (today + dt.timedelta(days=14)).isoformat()
            tt.add(tp, "⭐ Le 3 mosse a più impatto", f"{m['owner']} {MARK}**{m['title']}** — {due} — {m.get('hours') or 'da stimare'} — nessuna — {m['effect']}", today)
            res["todo_added"] += 1; m["todo"] = "aggiunta"
    # ---- calendar.md
    cp = os.path.join(root, "calendar.md")
    if os.path.exists(cp):
        raw = open(cp, encoding="utf-8").read()
        lines = _strip_marks(raw.replace("\r", "").split("\n"))
        plan = ps.parse("\n".join(lines))
        if plan["phases"]:
            open_idx = [plan["line_of"][s["n"]] for s in ps.all_steps(plan) if not s["done"]]
            nmax = max((s["n"] for s in ps.all_steps(plan)), default=0)
            add_steps = []
            for m in moves:
                i = _match_line(lines, open_idx, {**m, "todo_line": None, "match": m.get("match") or words(m["title"])[:3]})
                if i is not None:
                    lines[i] = _mark(lines[i]); res["cal_marked"] += 1; m["calendar"] = "segnato"
                else:
                    nmax += 1
                    due = m.get("due") or (today + dt.timedelta(days=14)).isoformat()
                    add_steps.append(f"{nmax}. [ ] {m['owner']} {MARK}**{m['title']}** ({m.get('hours') or 'ore da stimare'}). · 📅 {due}")
                    res["cal_added"] += 1; m["calendar"] = "aggiunto"
            if add_steps:
                head = next((k for k, ln in enumerate(lines) if ln.startswith("### ⭐ Mosse a più impatto")), None)
                if head is None:
                    sec = next(k for k, ln in enumerate(lines) if ps.SECTION.match(ln))
                    first_phase = next(k for k in range(sec + 1, len(lines)) if lines[k].startswith("### "))
                    lines[first_phase:first_phase] = [f"### ⭐ Mosse a più impatto (calcolate da top_moves.py, aggiornate il {today.isoformat()})"] + add_steps
                else:
                    lines[head] = f"### ⭐ Mosse a più impatto (calcolate da top_moves.py, aggiornate il {today.isoformat()})"
                    end = next((k for k in range(head + 1, len(lines)) if lines[k].startswith("#")), len(lines))
                    lines[end:end] = add_steps
            new = "\n".join(lines)
            if new != raw.replace("\r", ""):
                with open(cp, "w", encoding="utf-8", newline="\n") as f:
                    f.write(new)
    os.makedirs(os.path.join(root, "_raw"), exist_ok=True)
    with open(os.path.join(root, "_raw", "top_moves.json"), "w", encoding="utf-8") as f:
        json.dump(dict(computed_on=today.isoformat(), moves=moves, result=res), f, ensure_ascii=False, indent=1)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["show", "apply"]); ap.add_argument("--launch-dir", default="launch")
    ap.add_argument("--calibration"); ap.add_argument("--today")
    a = ap.parse_args(argv)
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    moves = compute(a.launch_dir, today, a.calibration)
    for i, m in enumerate(moves, 1):
        print(f"{i}. [{m['source']}, {m['score']}] {m['title']}\n   perché: {m['why']}\n   effetto: {m['effect']} · ore: {m.get('hours') or 'da stimare'} · {m['owner']}")
    if a.cmd == "apply":
        r = apply(a.launch_dir, today, moves)
        print(f"TODO.md: {r['todo_marked']} segnate, {r['todo_added']} aggiunte · calendar.md: {r['cal_marked']} segnati, {r['cal_added']} aggiunti")


if __name__ == "__main__":
    main()
