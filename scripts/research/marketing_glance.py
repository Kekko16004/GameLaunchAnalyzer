#!/usr/bin/env python3
"""The top of the "Marketing e social" tab of STATUS.html: everything the owner needs at a glance, then the rest folded.

At a glance (only what exists in launch/ is shown):
  1. Cosa fare adesso      the 3 moves of top_moves.py (_raw/top_moves.json) with deadline and owner (👤 / 🤖), falling back to the next open steps of calendar.md
  2. Canali                Steam, itch.io, TikTok, Shorts, Reels, Reddit, X, YouTube creators: pronto / da collegare / non usare (clips.json, social_kit.json,
                           social_learn.json, creators.csv, store_kit.json) with the case reference "wishlist ogni 1.000 visualizzazioni"
  3. Numeri contro i casi  wishlist, next threshold, wishlist at launch, Next Fest, store page text and languages, social conversion,
                           each against the real Reddit cases (data/social_patterns.json -> case_benchmarks): sopra / sotto / da misurare
  4. Perché floppa         the flop checklist (social_content.flopcheck) as a traffic light, one action per item. Answers: _raw/flopcheck_answers.json;
                           a ready _raw/flopcheck.json wins; a few items are filled from the plan when the fact is in launch/ (store text, languages, timing, wishlists)
Below, folded: social plan week by week, hooks, subreddit rules, evidence and sources, linked real cases.
No network: every file is local. All text is escaped. Plain Italian on screen, no file keys.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import os
import re

MONTHS = "gen feb mar apr mag giu lug ago set ott nov dic".split()
NAMES = {"steam": "Pagina Steam", "itch": "Pagina itch.io", "tiktok": "TikTok", "youtube_shorts": "YouTube Shorts", "instagram": "Instagram Reels",
         "reddit": "Reddit", "x": "X (Twitter)", "youtube": "Creator su YouTube"}
OWN = {"me": "👤 Tu", "claude": "🤖 Claude", "both": "👤+🤖 Insieme"}


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def _j(root: str, *p):
    path = os.path.join(root, *p)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def fmt_date(s) -> str:
    try:
        d = dt.date.fromisoformat(str(s)[:10])
        return f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    except ValueError:
        return esc(s)


def n_it(x, nd=0) -> str:
    if x is None:
        return "n/d"
    s = f"{x:,.{nd}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return s


FIELDS = {"languages": "lingue", "desc_chars": "caratteri della descrizione", "wishlists": "wishlist", "trailers": "trailer", "short_desc_chars": "caratteri della descrizione breve", "screenshots": "screenshot"}


def plain(t: str) -> str:
    """Strip Markdown links, file names and bracket labels: the glance speaks plain Italian (details keep the full text)."""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t or "")
    t = re.sub(r"\s*\([^()]*\.(?:md|json|csv|py)[^()]*\)", "", t)
    t = re.sub(r"\s+(?:con|in|da|via)\s+[\w./-]+\.(?:py|md|json|csv)(?:\s+[a-z]+)?", "", t)
    t = re.sub(r"\s*\(p [\d.,]+\)", "", t)
    t = re.sub(r";\s*\)", ")", t)
    for k, v in FIELDS.items():
        t = re.sub(rf"{k} = ([\d.,]+), soglia (>=|<=|>|<) ([\d.,]+)", lambda m, v=v: f"{v}: {m.group(1)}, " + {">=": "serve almeno", "<=": "serve al massimo", ">": "serve più di", "<": "serve meno di"}[m.group(2)] + f" {m.group(3)}", t)
    t = re.sub(r"\s*\[(?:STIMA|FATTO|OPINIONE|DA VERIFICARE)[^\]]*\]", "", t)
    return re.sub(r"`([^`]+)`", r"\1", t).strip()


def dot(kind: str, label: str) -> str:
    """Status pill, one palette for the whole page: ok (green, done), prog (orange, in progress), todo (grey outline, to do), bad (red, overdue or a problem), off (light grey, not used / not applicable yet)."""
    return f'<span class="spill {kind}"><i aria-hidden="true"></i>{esc(label)}</span>'


# ---------------------------------------------------------------- 1. moves
def owner_of(raw: str) -> str:
    raw = raw or ""
    return "both" if ("👤" in raw and "🤖" in raw) or raw in ("both",) else "claude" if ("🤖" in raw or raw == "claude") else "me"


def why_plain(why: str, title: str = "") -> str:
    """"c'è nel 84 % dei B vincenti e nel 33 % dei perdenti (n = …); da noi: …" -> one everyday sentence; a bare deadline note is dropped (the date is shown)."""
    m = re.search(r"nel (\d+) % dei B vincenti e nel (\d+) % dei perdenti", why or "")
    if m:
        days = re.search(r"circa (\d+) giorni prima", title or "")
        return (f"Lo ha fatto il {m.group(1)} % dei giochi simili andati bene e solo il {m.group(2)} % di quelli andati male"
                + (f", di solito circa {days.group(1)} giorni prima dell'uscita." if days else "."))
    if re.fullmatch(r"\s*scade il [\d-]+\s*", why or ""):
        return ""
    return plain(why)


def moves(root: str, plan: dict, today: dt.date, ps=None) -> list[dict]:
    """[{title, owner, due, hours, why, step}] at most 3: top_moves.json first, then the next open steps."""
    steps = [s for p in (plan or {}).get("phases", []) for s in p["steps"]]
    out = []
    tm = _j(root, "_raw", "top_moves.json") or {}
    for m in (tm.get("moves") or [])[:3]:
        due, step = m.get("due"), None
        words = [w.lower() for w in (m.get("match") or []) if w]
        for s in steps:
            if s["done"] or not words:
                continue
            if any(w in s["text"].lower() for w in words):
                step = s["n"]
                due = due or s.get("due")
                break
        out.append(dict(title=plain(re.sub(r"\s*\(i B vincenti[^)]*\)", "", m.get("title", ""))), owner=owner_of(m.get("owner")), due=due, hours=m.get("hours"),
                        why=why_plain(m.get("why", ""), m.get("title", "")), step=step))
    if len(out) < 3 and ps and steps:
        have = {o["step"] for o in out}
        for s in ps.next_steps(plan, None, 6, today):
            if len(out) >= 3:
                break
            if s["n"] in have:
                continue
            t = re.sub(r"\*\*", "", s["text"])
            out.append(dict(title=plain(t.split(":")[0] if len(t) > 90 else t), owner=s.get("owner") if s.get("owner") in OWN else "me", due=s.get("due"), hours=None, why="", step=s["n"]))
    return out


def due_html(due, today: dt.date) -> str:
    if not due:
        return '<span class="due none">senza data</span>'
    try:
        d = dt.date.fromisoformat(str(due)[:10])
    except ValueError:
        return f'<span class="due">{esc(due)}</span>'
    n = (d - today).days
    rel = "oggi" if n == 0 else f"tra {n} g" if n > 0 else f"scaduta da {-n} g"
    cls = "late" if n < 0 else "soon" if n <= 7 else ""
    return f'<span class="due {cls}">entro il {fmt_date(d.isoformat())} · {rel}</span>'


def moves_html(ms: list[dict], today: dt.date) -> str:
    if not ms:
        return '<p class="note">Nessuna mossa calcolata: Claude le calcola con il giro delle 3 mosse.</p>'
    li = []
    for k, m in enumerate(ms, 1):
        link = f' <a class="more" href="#step-{m["step"]}">vedi il passo {m["step"]}</a>' if m.get("step") else ""
        meta = f'<span class="who {m["owner"]}">{OWN.get(m["owner"], "👤 Tu")}</span>{due_html(m.get("due"), today)}' + (f'<span class="hrs">{esc(m["hours"])}</span>' if m.get("hours") else "")
        why = f'<p class="mv-why">{esc(m["why"][:220])}{"…" if len(m["why"]) > 220 else ""}</p>' if m.get("why") else ""
        li.append(f'<li><span class="mv-n">{k}</span><div><p class="mv-t">{esc(m["title"])}{link}</p><div class="mv-meta">{meta}</div>{why}</div></li>')
    return f'<ol class="moves">{"".join(li)}</ol>'


# ---------------------------------------------------------------- 2. channels
def channels(root: str, db: dict, today: dt.date) -> list[dict]:
    clips = _j(root, "clips.json") or {}
    kits = (_j(root, "social_kit.json") or _j(root, "_raw", "social_kit.json") or {}).get("kits") or []
    learn = {p["platform"]: p for p in ((_j(root, "_raw", "social_learn.json") or {}).get("platforms") or [])}
    plan_social = _j(root, "_raw", "social_plan.json") or {}
    kit = _j(root, "store_kit.json") or {}
    wlp = _j(root, "_raw", "wl_plan.json") or {}
    conv = ((db or {}).get("case_benchmarks") or {}).get("wishlists_per_1k_views") or {}
    planned = {s["platform"] for k in kits for p in k.get("posts", []) for s in p.get("slots", [])} | {p.get("platform") for p in plan_social.get("posts", []) if p.get("platform")}
    if any(p.get("kind") != "video" for k in kits for p in k.get("posts", [])) or clips.get("reddit"):
        planned.add("reddit")
    rows = []
    # store pages
    if clips.get("steam_url") or clips.get("page_live"):
        rows.append(dict(key="steam", kind="ok", label="Online", note="La pagina c'è: ogni post porta lì."))
    elif kit.get("steam"):
        when = f" (prevista il {fmt_date(wlp['start'])})" if wlp.get("start") else ""
        rows.append(dict(key="steam", kind="todo", label="Da collegare", note=f"Testi pronti da copiare; la pagina non è ancora online{when}."))
    if clips.get("itch_live"):
        rows.append(dict(key="itch", kind="ok", label="Online", note="Pagina itch.io pubblicata."))
    elif kit.get("itch"):
        rows.append(dict(key="itch", kind="todo", label="Da collegare", note="Testi pronti; la pagina non è ancora pubblicata."))
    for key in ("tiktok", "youtube_shorts", "instagram", "reddit", "x"):
        ref = conv.get(key)
        refs = f"Nei casi: {n_it(ref['median'], 1)} wishlist ogni 1.000 visualizzazioni (n {ref['n']})." if ref else ""
        if key in learn:
            p = learn[key]
            rows.append(dict(key=key, kind="ok", label="Attivo", note=f"{p['n']} post misurati. {refs}".strip()))
        elif key in planned:
            extra = " Regole dei subreddit da leggere a mano." if key == "reddit" and any("VERIFICARE" in str(r.get("flair", "")) for r in clips.get("reddit") or []) else ""
            rows.append(dict(key=key, kind="todo", label="Da collegare", note=f"Nel piano, nessun post misurato ancora.{extra} {refs}".strip()))
        elif ref:
            rows.append(dict(key=key, kind="off", label="Non usare per ora", note=f"Fuori dal piano. {refs}".strip()))
    cr_path = os.path.join(root, "creators.csv")
    if os.path.exists(cr_path):
        try:
            with open(cr_path, encoding="utf-8-sig", newline="") as f:
                cr = list(csv.DictReader(f))
        except OSError:
            cr = []
        if cr:
            a = sum(1 for r in cr if (r.get("priorita") or "").strip().upper().startswith("A"))
            ref = conv.get("youtube")
            rows.append(dict(key="youtube", kind="todo", label="Da contattare", note=f"{len(cr)} creator in lista, {a} con priorità A."
                             + (f" Nei casi un video di creator rende {n_it(ref['median'], 1)} wishlist ogni 1.000 visualizzazioni." if ref else "")))
    return rows


def channels_html(rows: list[dict]) -> str:
    if not rows:
        return '<p class="note">Nessun canale nel piano.</p>'
    return '<ul class="chan">' + "".join(f'<li><span class="cn">{esc(NAMES.get(r["key"], r["key"]))}</span>{dot(r["kind"], r["label"])}<span class="cnote">{esc(r["note"])}</span></li>' for r in rows) + "</ul>"


# ---------------------------------------------------------------- 3. numbers against the cases
def meter(value, lo, hi, lo_lab="flop", hi_lab="successi") -> str:
    """Track with the flop median (red tick), the success median (green tick) and our value (dot)."""
    if value is None or lo is None or hi is None:
        return ""
    top = max(value, lo, hi) * 1.15 or 1
    x = lambda v: f"{min(max(v / top * 100, 0), 100):.1f}%"
    return (f'<div class="meter" role="img" aria-label="Noi {n_it(value)}; {lo_lab} {n_it(lo)}; {hi_lab} {n_it(hi)}"><span class="tick lo" style="left:{x(lo)}" title="{esc(lo_lab)}: {n_it(lo)}"></span>'
            f'<span class="tick hi" style="left:{x(hi)}" title="{esc(hi_lab)}: {n_it(hi)}"></span><span class="me" style="left:{x(value)}"></span></div>')


def numbers(root: str, db: dict, today: dt.date, wl_a: dict | None) -> list[dict]:
    """[{label, ours, ref, kind, verdict, meter}]: kind ok = sopra, bad = sotto, prog = a metà, todo = da misurare."""
    cb = (db or {}).get("case_benchmarks") or {}
    wlp = _j(root, "_raw", "wl_plan.json") or {}
    kit = _j(root, "store_kit.json") or {}
    cur = (wl_a or {}).get("current")
    out = []
    f5 = (cb.get("first_5_weeks_from_zero") or {})
    bo = f5.get("by_outcome") or {}
    if f5.get("all"):
        ref = f"Prime 5 settimane da zero, nei casi: mediana {n_it(f5['all']['median'])}" + (f" (successi {n_it(bo['success']['median'])}, flop {n_it(bo['flop']['median'])})" if bo.get("success") and bo.get("flop") else "")
        if cur is None:
            page = f"la pagina Steam apre il {fmt_date(wlp['start'])}" if wlp.get("start") else "nessun dato registrato"
            out.append(dict(label="Wishlist", ours="—", sub=page, ref=ref, kind="todo", verdict="Da misurare", meter=""))
        else:
            hi, lo = (bo.get("success") or {}).get("median"), (bo.get("flop") or {}).get("median")
            kind = "ok" if hi and cur >= hi else "bad" if lo and cur <= lo else "prog"
            vel = (wl_a or {}).get("velocity_4w")
            out.append(dict(label="Wishlist", ours=n_it(cur), sub=f"{'+' if vel and vel > 0 else ''}{n_it(vel)} a settimana" if vel is not None else "", ref=ref, kind=kind,
                            verdict={"ok": "Sopra i successi", "bad": "Sotto i flop", "prog": "Tra flop e successi"}[kind], meter=meter(cur, lo, hi)))
    nxt = next((t for t in sorted(wlp.get("tripwires") or [], key=lambda t: t["date"]) if dt.date.fromisoformat(t["date"]) >= today), None)
    if nxt:
        kind, verdict = ("todo", "Da misurare") if cur is None else (("ok", "Sopra la soglia") if cur >= nxt["min_wishlists"] else ("bad", "Sotto la soglia"))
        out.append(dict(label="Prossima soglia", ours=n_it(nxt["min_wishlists"]), sub=f"entro il {fmt_date(nxt['date'])}: {plain(nxt.get('label', ''))}",
                        ref=f"Se manca: {plain(nxt.get('emergency', ''))}" if nxt.get("emergency") else "", kind=kind, verdict=verdict, meter=""))
    lw = cb.get("launch_wishlists") or {}
    base = (wlp.get("targets") or {}).get("base")
    if base and lw.get("threshold_ok"):
        ok, alarm = lw["threshold_ok"], lw.get("threshold_alarm")
        kind = "ok" if base >= ok else "bad" if alarm and base < alarm else "prog"
        out.append(dict(label="Wishlist all'uscita (obiettivo base)", ours=n_it(base), sub=f"uscita il {fmt_date(wlp['launch'])}" if wlp.get("launch") else "",
                        ref=f"Nei casi: sotto {n_it(alarm)} si vende pochissimo, da {n_it(ok)} in su si entra tra i più attesi", kind=kind,
                        verdict={"ok": "Sopra la soglia dei casi", "bad": "Sotto la soglia d'allarme", "prog": "Tra allarme e soglia buona"}[kind], meter=meter(base, alarm, ok, "allarme", "soglia buona")))
    nf = cb.get("next_fest_by_entry") or []
    entry = next((t["min_wishlists"] for t in (wlp.get("tripwires") or []) if "next fest" in t.get("label", "").lower() and "ingresso" in t.get("label", "").lower()), None)
    if nf and entry is not None:
        band = nf[0] if entry < 1000 else nf[1] if entry < 10000 and len(nf) > 1 else nf[-1]
        g = band["gain"]
        out.append(dict(label="Next Fest", ours=f"+{n_it(g['median'])}", sub=f"entrando con {n_it(entry)} wishlist (soglia del piano)",
                        ref=f"Nei casi con entrata {band['band']}: +{n_it(g['p25'])}…+{n_it(g['p75'])} wishlist (n {g['n']})", kind="info", verdict="Cosa aspettarsi", meter=""))
    spm = cb.get("store_page_measured") or {}
    st = kit.get("steam") or {}
    if st.get("long_description", {}).get("blocks") and spm.get("desc_chars"):
        try:
            import store_kit as sk
            n = len(sk.assemble(st["long_description"]))
        except Exception:  # noqa: BLE001
            n = None
        d = spm["desc_chars"]
        if n is not None:
            kind = "ok" if n >= d["success_median"] else "bad" if n <= d["flop_median"] else "prog"
            out.append(dict(label="Descrizione Steam", ours=f"{n_it(n)} caratteri", sub="dal testo pronto da copiare", ref=f"Mediana nei casi: successi {n_it(d['success_median'])}, flop {n_it(d['flop_median'])}",
                            kind=kind, verdict={"ok": "Sopra i successi", "bad": "Come i flop", "prog": "Tra flop e successi"}[kind], meter=meter(n, d["flop_median"], d["success_median"])))
    langs = languages(kit)
    if langs and spm.get("languages"):
        d = spm["languages"]
        kind = "ok" if langs >= d["success_median"] else "bad" if langs <= d["flop_median"] else "prog"
        out.append(dict(label="Lingue della pagina", ours=str(langs), sub="lingue dichiarate", ref=f"Mediana nei casi: successi {n_it(d['success_median'])}, flop {n_it(d['flop_median'], 1)}",
                        kind=kind, verdict={"ok": "Come i successi", "bad": "Come i flop", "prog": "Tra flop e successi"}[kind], meter=meter(langs, d["flop_median"], d["success_median"])))
    conv = cb.get("wishlists_per_1k_views") or {}
    learn = (_j(root, "_raw", "social_learn.json") or {}).get("platforms") or []
    measured = [p for p in learn if p.get("wishlists_per_1k") is not None and conv.get(p["platform"])]
    if measured:
        for p in measured:
            r = conv[p["platform"]]
            v = float(p["wishlists_per_1k"])
            kind = "ok" if v >= r["median"] else "bad" if v < r["p25"] else "prog"
            out.append(dict(label=f"Wishlist ogni 1.000 visualizzazioni · {NAMES.get(p['platform'], p['platform'])}", ours=n_it(v, 1), sub=f"{p.get('n')} post",
                            ref=f"Nei casi: mediana {n_it(r['median'], 1)} ({n_it(r['p25'], 1)}…{n_it(r['p75'], 1)})", kind=kind,
                            verdict={"ok": "Sopra la mediana", "bad": "Sotto i casi", "prog": "Nella forchetta"}[kind], meter=meter(v, r["p25"], r["median"], "quartile basso", "mediana")))
    elif conv:
        best = sorted(conv.items(), key=lambda kv: -kv[1]["median"])
        out.append(dict(label="Wishlist ogni 1.000 visualizzazioni", ours="—", sub="nessun post misurato", kind="todo", verdict="Da misurare",
                        ref="Nei casi: " + ", ".join(f"{NAMES.get(k, k.replace('_', ' '))} {n_it(v['median'], 1)}" for k, v in best[:5]), meter=""))
    return out


def languages(kit: dict) -> int | None:
    for s in (kit.get("steam") or {}).get("settings") or []:
        if str(s.get("label", "")).lower().startswith("languages") or str(s.get("label", "")).lower().startswith("lingue"):
            v = [x for x in re.split(r"[,;/]", str(s.get("value") or "")) if x.strip()]
            return len(v) or None
    return None


def numbers_html(rows: list[dict]) -> str:
    if not rows:
        return '<p class="note">Nessun numero confrontabile ancora.</p>'
    kinds = {"ok": "ok", "bad": "bad", "prog": "off", "todo": "todo", "info": "off"}  # the middle of a range is not "in progress": neutral
    body = "".join(f'<div class="num"><div class="nl">{esc(r["label"])}</div><div class="nv">{esc(r["ours"])}</div><div class="ns">{esc(r.get("sub", ""))}</div>'
                   f'{dot(kinds[r["kind"]], r["verdict"])}{r.get("meter", "")}<div class="nr">{esc(r.get("ref", ""))}</div></div>' for r in rows)
    has_meter = any(r.get("meter") for r in rows)
    how = ('<p class="how"><strong>Come si legge:</strong> il pallino è il nostro numero; la tacca rossa è la mediana dei giochi andati male, quella verde dei giochi andati bene '
           '(o la soglia d\'allarme e quella buona). I casi sono post pubblici di sviluppatori: numeri dichiarati da loro, più spesso successi che flop.</p>') if has_meter else ""
    return f'<div class="nums">{body}</div>{how}'


# ---------------------------------------------------------------- 4. flop check
def flop(root: str, db: dict, today: dt.date, wl_a: dict | None):
    """The flop checklist on our game: the saved result wins (unless the answers are newer); otherwise answers + facts read from launch/."""
    ready = _j(root, "_raw", "flopcheck.json")
    ans_path = os.path.join(root, "_raw", "flopcheck_answers.json")
    ready_path = os.path.join(root, "_raw", "flopcheck.json")
    fresh = not (os.path.exists(ans_path) and os.path.exists(ready_path) and os.path.getmtime(ans_path) > os.path.getmtime(ready_path) + 1)
    if ready and ready.get("items") and fresh:
        return ready
    if not (db or {}).get("flop_checklist"):
        return None
    import social_content as sc
    facts, auto = sc.launch_facts(root)
    answers = dict(auto, **(_j(root, "_raw", "flopcheck_answers.json") or {}))
    if (wl_a or {}).get("current") is not None:
        facts["wishlists"] = wl_a["current"]
    fc = sc.flopcheck(db, facts, answers)
    for it in fc["items"]:
        if it["status"] != "todo" and not it.get("how"):
            it["how"] = "dalle tue risposte o dal piano"
    return fc


def flop_label(db: dict, code: str) -> str:
    lab = (((db or {}).get("factor_weights") or {}).get("factors") or {}).get(code, {}).get("label") or code.replace("_", " ")
    return lab[:1].upper() + lab[1:]


def flop_html(fc: dict | None, db: dict) -> str:
    if not fc:
        return ""
    order = {"fail": 0, "todo": 1, "ok": 2, "na": 3}
    items = sorted(fc["items"], key=lambda x: (order.get(x["status"], 4), -x["weight"]))
    n = {k: sum(1 for x in items if x["status"] == k) for k in ("ok", "fail", "todo", "na")}
    pill = {"ok": ("ok", "Superato"), "fail": ("bad", "Da sistemare"), "todo": ("todo", "Da verificare"), "na": ("off", "Non applicabile ancora")}
    li = []
    for x in items:
        k, lab = pill.get(x["status"], ("todo", "Da verificare"))
        act = x.get("action") or (x["fix"] if x["status"] != "ok" else "Niente da fare: tienilo così.")
        how = f' <span class="note">({esc(plain(x["how"]))})</span>' if x.get("how") and x["status"] not in ("todo",) and x["how"] != "risposta" and not x.get("why") else ""
        why = (f'<p class="fw"><strong>Motivo:</strong> {esc(x["why"])}' + (f' <span class="proof">Prova: {esc(x["proof"])}</span>' if x.get("proof") else "") + "</p>") if x.get("why") else ""
        li.append(f'<li class="fl {x["status"]}">{dot(k, lab)}<div><p class="ft">{esc(flop_label(db, x["code"]))} <span class="w" title="Peso: quanto spesso i commenti dei flop citano questa causa (5 = la più citata)">peso {x["weight"]}/5</span></p>'
                  f'<p class="fq">{esc(plain(x["q"]))}{how}</p>{why}<p class="fa"><strong>Azione:</strong> {esc(plain(act))}</p></div></li>')
    head = (f'<div class="flsum">{dot("ok", str(n["ok"]) + " superati")}{dot("bad", str(n["fail"]) + " da sistemare")}'
            + (f'{dot("todo", str(n["todo"]) + " da verificare")}' if n["todo"] else "")
            + (f'{dot("off", str(n["na"]) + " non applicabili ancora")}' if n["na"] else "") + "</div>")
    return (head + f'<ul class="flops">{"".join(li)}</ul><p class="how"><strong>Come si legge:</strong> le domande vengono dai commenti più votati sotto i post di giochi andati male; '
            'il peso dice quanto spesso quella causa viene citata. Sono opinioni contate, non leggi: dicono cosa guardare per primo. '
            '«Non applicabile ancora» vuol dire che la cosa non esiste (per esempio il trailer): non conta come bocciata finché non c\'è. '
            'Claude segna le risposte con il motivo e la prova; alcune voci si controllano da sole sui dati del piano.</p>')


# ---------------------------------------------------------------- folded details
def plan_weeks_html(root: str) -> str:
    """The calendar of social_content.py plan (_raw/social_plan.json): every platform, week by week, with the two opening texts of the A/B test."""
    pl = _j(root, "_raw", "social_plan.json") or {}
    posts = pl.get("posts") or []
    if not posts:
        return ""
    weeks: dict = {}
    for x in posts:
        try:
            d = dt.date.fromisoformat(x["date"])
        except (KeyError, ValueError):
            continue
        weeks.setdefault(d - dt.timedelta(days=d.weekday()), []).append(x)
    per = pl.get("per_week") or {}
    intro = ("<p class=\"note\">Post a settimana: " + ", ".join(f"{esc(NAMES.get(p, p))} {n}" for p, n in per.items()) + ". "
             "Lo stesso momento esce su più piattaforme a 1-2 giorni di distanza; ogni riga ha due testi d'apertura per la prova A/B.</p>") if per else ""
    out = [intro]
    for wk, xs in sorted(weeks.items()):
        rows = []
        for x in sorted(xs, key=lambda x: x["date"]):
            where = esc(NAMES.get(x["platform"], x["platform"])) + (f' · {esc(x["subreddit"])}' if x.get("subreddit") else "")
            rows.append(f'<tr><td>{fmt_date(x["date"])}</td><td>{where}</td><td>{esc(x.get("moment"))} {esc(str(x.get("moment_label", ""))[:60])}</td>'
                        f'<td>A: {esc(x.get("hook_a"))}<br>B: {esc(x.get("hook_b"))}</td><td>{esc(x.get("caption", ""))}</td><td>{esc(x.get("cta", ""))}</td></tr>')
        out.append(f'<h3>Settimana del {fmt_date(wk.isoformat())}</h3><div class="wrap"><table><thead><tr><th>Giorno</th><th>Dove</th><th>Momento</th><th>Testo di apertura</th><th>Didascalia</th><th>Fine del video</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    return "".join(out)


def weeks_html(root: str) -> str:
    plan_part = plan_weeks_html(root)
    kits = (_j(root, "_raw", "social_kit.json") or {}).get("kits") or []
    if not kits:
        return plan_part
    parts = [plan_part + "<h3>Kit pronto da pubblicare (clip e storyboard)</h3>" if plan_part else ""]
    for k in kits:
        rows = []
        for p in k.get("posts", []):
            if p.get("kind") == "video":
                when = "; ".join(f'{NAMES.get(s["platform"], s["platform"])} {fmt_date(s["date"])} {esc(s.get("time", ""))}' for s in p.get("slots", []))
                rows.append(f'<tr><td>{esc(p.get("clip"))} {esc(p.get("title"))}</td><td>{esc((p.get("hooks") or [""])[p.get("use_hook", 0)] if p.get("hooks") else "")}</td><td>{when}</td><td>{esc(p.get("caption", ""))}</td></tr>')
            else:
                rows.append(f'<tr><td>Reddit {esc(p.get("subreddit"))}</td><td>{esc(p.get("title"))}</td><td>{fmt_date(p.get("date"))} {esc(p.get("time", ""))}</td><td>{esc(p.get("body", "") or p.get("note", ""))}</td></tr>')
        parts.append(f'<h3>Settimana del {fmt_date(k["week"])}</h3><div class="wrap"><table><thead><tr><th>Post</th><th>Testo d\'apertura</th><th>Dove e quando</th><th>Didascalia</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    return "".join(parts)


def hooks_html(root: str) -> str:
    kits = (_j(root, "_raw", "social_kit.json") or {}).get("kits") or []
    seen, li = set(), []
    for x in (_j(root, "_raw", "social_plan.json") or {}).get("posts") or []:
        for lab, h in (("A", x.get("hook_a")), ("B", x.get("hook_b"))):
            if h and h not in seen:
                seen.add(h)
                li.append(f'<li>{dot("ok" if lab == "A" else "off", "In uso" if lab == "A" else "Di riserva")}<span>«{esc(h)}» <span class="note">{esc(NAMES.get(x["platform"], x["platform"]))}, momento {esc(x.get("moment"))}</span></span></li>')
    for k in kits:
        for p in k.get("posts", []):
            for i, h in enumerate(p.get("hooks") or []):
                if h in seen:
                    continue
                seen.add(h)
                used = i == p.get("use_hook", 0)
                li.append(f'<li>{dot("ok" if used else "off", "In uso" if used else "Di riserva")}<span>«{esc(h)}» <span class="note">clip {esc(p.get("clip"))}</span></span></li>')
    return f'<ul class="clean">{"".join(li)}</ul><p class="note">Il testo che compare nei primi 2 secondi del video. Quello «in uso» va nel post di questa settimana; gli altri servono per la prova A/B.</p>' if li else ""


def flair(v) -> str:
    return re.sub(r"\[DA VERIFICARE[^\]]*\]", "da verificare", str(v or "")).strip() or "—"


def subreddits_html(root: str, db: dict) -> str:
    clips = _j(root, "clips.json") or {}
    out = []
    for r in clips.get("reddit") or []:
        out.append(f'<div class="srule"><p><strong>{esc(r.get("sub"))}</strong> <span class="note">flair: {esc(flair(r.get("flair")))} · un post ogni {esc(r.get("cooldown_days", "?"))} giorni al massimo</span></p>'
                   + "<ul>" + "".join(f"<li>{esc(plain(x))}</li>" for x in r.get("rules_check") or []) + "</ul></div>")
    ours = {str(r.get("sub", "")).lower() for r in clips.get("reddit") or []}
    other = [s for s in (db or {}).get("subreddits") or [] if s.get("sub", "").lower() not in ours]
    if other:
        out.append("<h3>Altri subreddit nella base dati</h3><ul class=\"clean\">" + "".join(
            f'<li><span><strong>{esc(s["sub"])}</strong> <span class="note">circa {n_it(s.get("subscribers_approx"))} iscritti'
            + "".join(f' · <a href="{esc(u["url"])}" rel="noopener noreferrer">fonte</a>' for u in (s.get("sources") or [])[:2] if str(u.get("url", "")).startswith("https://"))
            + "</span></span></li>" for s in other) + "</ul>")
    return "".join(out)


def _a(url: str, text: str) -> str:
    return f'<a href="{esc(url)}" rel="noopener noreferrer">{esc(text)}</a>' if str(url or "").startswith("https://") else esc(text)


def evidence_html(db: dict) -> str:
    cb = (db or {}).get("case_benchmarks") or {}
    if not cb:
        return ""
    out = [f'<p class="note">{esc(cb.get("note", ""))} Aggiornati il {fmt_date(cb.get("generated", ""))}.</p>']
    conv = cb.get("wishlists_per_1k_views") or {}
    if conv:
        out.append('<h3>Wishlist ogni 1.000 visualizzazioni, per canale</h3><div class="wrap"><table><thead><tr><th>Canale</th><th class="n">Mediana</th><th class="n">Forchetta</th><th class="n">Casi</th><th>Esempi</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{esc(NAMES.get(k, k.replace("_", " ")))}</td><td class="n">{n_it(v["median"], 1)}</td><td class="n">{n_it(v["p25"], 1)}…{n_it(v["p75"], 1)}</td><td class="n">{v["n"]}</td>'
                             f'<td>{"; ".join(_a(e.get("url"), e.get("case", "")) for e in (v.get("examples") or [])[:2])}</td></tr>' for k, v in sorted(conv.items(), key=lambda kv: -kv[1]["median"]))
                   + "</tbody></table></div>")
    wb = cb.get("weekly_wishlists_by_band") or []
    if wb:
        out.append('<h3>Wishlist a settimana, per quante ne hai</h3><div class="wrap"><table><thead><tr><th>Partenza</th><th class="n">Mediana a settimana</th><th class="n">Forchetta</th><th class="n">Casi</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{esc(b["band"])}</td><td class="n">{n_it(b["median"])}</td><td class="n">{n_it(b["p25"])}…{n_it(b["p75"])}</td><td class="n">{b["n"]}</td></tr>' for b in wb) + "</tbody></table></div>")
    ads = cb.get("ads_cost_per_wishlist") or {}
    if ads.get("items"):
        out.append(f'<h3>Pubblicità: costo per wishlist (mediana {n_it(ads.get("median_usd"), 2)} $)</h3><ul class="clean">'
                   + "".join(f'<li><span>{_a(i.get("url"), i.get("channel", ""))}: {n_it(i.get("spend_usd"))} $ → {n_it(i.get("wishlists"))} wishlist ({n_it(i.get("usd_per_wishlist"), 2)} $ l\'una)</span></li>' for i in ads["items"]) + "</ul>")
    spm = cb.get("store_page_measured") or {}
    if spm:
        out.append(f'<h3>Pagine Steam: cosa distingue i successi dai flop</h3><p class="note">{esc(spm.get("note", ""))}</p><ul class="clean">'
                   + "".join(f'<li><span>{esc(lab)}: successi {esc(n_it(v.get("success_median"), 0) if "success_median" in v else str(round(100 * v.get("success_share", 0))) + " %")}, '
                             f'flop {esc(n_it(v.get("flop_median"), 1) if "flop_median" in v else str(round(100 * v.get("flop_share", 0))) + " %")}'
                             f'{" · differenza netta" if (v.get("p") or 1) < 0.05 else " · differenza non netta"}{(" · " + esc(v["note"])) if v.get("note") else ""}</span></li>'
                             for k, lab in (("languages", "Lingue"), ("desc_chars", "Caratteri della descrizione"), ("short_desc_chars", "Caratteri della descrizione breve"), ("has_demo", "Con demo"), ("screenshots", "Screenshot"), ("trailers", "Trailer"))
                             if isinstance((v := spm.get(k)), dict)) + "</ul>")
    fw = (db or {}).get("factor_weights") or {}
    if fw.get("method"):
        out.append(f'<h3>Come sono stati pesati i motivi dei flop</h3><p class="note">{esc(fw["method"])}</p>')
    return "".join(out)


def cases_html(db: dict) -> str:
    cb = (db or {}).get("case_benchmarks") or {}
    fw = ((db or {}).get("factor_weights") or {}).get("factors") or {}
    out = []
    if fw:
        out.append("<h3>Cosa dicono i commenti, motivo per motivo</h3>")
        for code, v in sorted(fw.items(), key=lambda kv: -kv[1].get("flop_share", 0)):
            ex = v.get("examples") or []
            if not ex:
                continue
            out.append(f'<p><strong>{esc(v.get("label", code)[:1].upper() + v.get("label", code)[1:])}</strong> <span class="note">citato in {v.get("flop_threads_blaming", 0)} flop e come merito in {v.get("success_threads_crediting", 0)} successi</span></p><ul>'
                       + "".join(f'<li>{_a(e.get("url"), e.get("it", ""))} <span class="note">{esc(e.get("case", ""))} · {e.get("votes", 0)} voti</span></li>' for e in ex[:4]) + "</ul>")
    nfc = cb.get("next_fest_cases") or []
    if nfc:
        out.append("<h3>Next Fest: casi reali</h3><ul class=\"clean\">" + "".join(f'<li><span>{_a(c.get("url"), c.get("case", ""))}: entrato con {n_it(c.get("entry"))} wishlist, +{n_it(c.get("gain"))}{(" · " + esc(c["note"])) if c.get("note") else ""}</span></li>' for c in nfc) + "</ul>")
    lw = cb.get("launch_wishlists") or {}
    if lw.get("note"):
        out.append(f'<h3>Uscite con poche wishlist</h3><p>{esc(plain(lw["note"]))}</p>')
    return "".join(out)


# ---------------------------------------------------------------- page block
def fold(title: str, body: str, count: str = "", open_: bool = False, anchor: str = "") -> str:
    if not body:
        return ""
    return (f'<details class="fold"{" open" if open_ else ""}{f" id={chr(34)}{anchor}{chr(34)}" if anchor else ""}><summary><h2>{esc(title)}</h2>'
            + (f'<span class="count">{esc(count)}</span>' if count else "") + f'</summary><div class="card">{body}</div></details>')


def wrap_fold(chunk: str | None, count: str = "") -> str | None:
    """An existing section ("<h2>Title</h2>…") turned into a closed details with the same heading."""
    if not chunk:
        return chunk
    m = re.match(r"\s*<h2>(.*?)</h2>(.*)$", chunk, re.S)
    if not m:
        return chunk
    return f'<details class="fold"><summary><h2>{m.group(1)}</h2>' + (f'<span class="count">{esc(count)}</span>' if count else "") + f"</summary>{m.group(2)}</details>"


def has_data(root: str) -> bool:
    return any(os.path.exists(os.path.join(root, *p)) for p in (("_raw", "top_moves.json"), ("clips.json",), ("_raw", "social_kit.json"), ("_raw", "social_plan.json"), ("_raw", "flopcheck.json"),
                                                                ("_raw", "flopcheck_answers.json")))


def glance(root: str, plan: dict, today: dt.date, wl_a: dict | None, db: dict | None = None, ps=None) -> tuple[str, list[str]] | None:
    """(top block html, [folded sections html]) or None when the game has no marketing data yet."""
    if not has_data(root):
        return None
    if db is None:
        try:
            import social_content as sc
            db = sc.load_db()
        except Exception:  # noqa: BLE001
            db = {}
    ms = moves(root, plan, today, ps)
    ch = channels(root, db, today)
    nums = numbers(root, db, today, wl_a)
    fc = flop(root, db, today, wl_a)
    top = ('<h2>A colpo d\'occhio</h2><div class="glance"><section class="card g-now"><h3>Cosa fare adesso</h3>' + moves_html(ms, today) + "</section>"
           + '<section class="card g-chan"><h3>Canali</h3>' + channels_html(ch) + "</section>"
           + '<section class="card g-num"><h3>I nostri numeri contro i casi reali</h3>' + numbers_html(nums) + "</section>"
           + ('<section class="card g-flop"><h3>Perché i giochi floppano: il nostro controllo</h3>' + flop_html(fc, db) + "</section>" if fc else "") + "</div>")
    kits = (_j(root, "_raw", "social_kit.json") or {}).get("kits") or []
    clips = _j(root, "clips.json") or {}
    n_weeks = len({(dt.date.fromisoformat(x["date"]) - dt.timedelta(days=dt.date.fromisoformat(x["date"]).weekday())) for x in (_j(root, "_raw", "social_plan.json") or {}).get("posts") or [] if x.get("date")}) or len(kits)
    folds = [fold("Piano social, settimana per settimana", weeks_html(root), f"{n_weeks} settimane"),
             fold("Ganci: i testi dei primi 2 secondi", hooks_html(root)),
             fold("Regole dei subreddit", subreddits_html(root, db), f"{len(clips.get('reddit') or [])} nel piano"),
             fold("Prove e fonti", evidence_html(db)),
             fold("Casi reali collegati", cases_html(db))]
    return top, [f for f in folds if f]


CSS = """
.glance{display:grid;gap:16px;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr)}.glance .g-num,.glance .g-flop{grid-column:1/-1}
.glance h3{margin:0 0 12px;font-size:var(--fs-2)}
ol.moves{list-style:none;margin:0;padding:0;display:grid;gap:14px}ol.moves li{display:grid;grid-template-columns:2rem minmax(0,1fr);gap:12px}
.mv-n{width:2rem;height:2rem;border-radius:50%;display:grid;place-items:center;font-weight:700;background:var(--acc-soft);color:var(--acc)}
.mv-t{margin:0;font-weight:600;font-size:var(--fs-2);line-height:1.35}.mv-t .more{font-weight:400;font-size:var(--fs-0);margin-left:6px;white-space:nowrap}
.mv-meta{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 0}.mv-meta>span{font-size:var(--fs-0);border:1px solid var(--rule);border-radius:999px;padding:1px 9px;color:var(--ink2);background:var(--surface)}
.mv-meta .who{color:var(--ink);font-weight:600}.mv-meta .who.claude{border-color:#2a78d6}.mv-meta .who.me{border-color:#8a63d2}.mv-meta .who.both{border-color:#0e8fa8}
.mv-meta .due.late{border-color:var(--crit);color:var(--crit);font-weight:600}.mv-meta .due.soon{border-color:var(--warn);color:var(--ink)}.mv-meta .due.none{color:var(--muted)}
.mv-why{margin:6px 0 0;color:var(--ink2);font-size:var(--fs-0)}
.spill{display:inline-flex;align-items:center;gap:6px;font-size:var(--fs-0);font-weight:600;white-space:nowrap;line-height:1.4}.spill i{width:10px;height:10px;border-radius:50%;flex:none;display:inline-block}
.spill.ok i{background:var(--good)}.spill.prog i{background:var(--warn)}.spill.bad i{background:var(--crit)}.spill.todo i{border:2px solid var(--muted);width:8px;height:8px}.spill.off i{background:var(--axis);border:0}
.spill.ok{color:var(--goodtext)}.spill.bad{color:var(--crit)}.spill.todo{color:var(--ink2)}.spill.off{color:var(--muted)}
ul.chan{list-style:none;margin:0;padding:0}ul.chan li{display:grid;grid-template-columns:9.5em 10.5em minmax(0,1fr);gap:4px 12px;align-items:baseline;padding:8px 0;border-top:1px solid var(--rule)}ul.chan li:first-child{border-top:0}
.cn{font-weight:600}.cnote{color:var(--ink2);font-size:var(--fs-0)}
.nums{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(250px,100%),1fr))}.num{border:1px solid var(--rule);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:4px;min-width:0}
.nl{font-size:var(--fs-0);color:var(--ink2);font-weight:600}.nv{font-size:var(--fs-3);font-weight:700;letter-spacing:-.01em;font-variant-numeric:tabular-nums;line-height:1.15}.ns,.nr{font-size:var(--fs-0);color:var(--ink2)}.nr{color:var(--muted)}
.meter{position:relative;height:6px;border-radius:3px;background:var(--surface2);margin:10px 0 6px}.meter .tick{position:absolute;top:-4px;width:2px;height:14px;border-radius:1px;transform:translateX(-1px)}
.meter .tick.lo{background:var(--crit)}.meter .tick.hi{background:var(--good)}.meter .me{position:absolute;top:50%;width:12px;height:12px;border-radius:50%;background:var(--acc);border:2px solid var(--surface);transform:translate(-6px,-50%)}
p.how{margin:12px 0 0;font-size:var(--fs-0);color:var(--ink2)}
.flsum{display:flex;gap:18px;flex-wrap:wrap;margin:0 0 10px}
ul.flops{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(420px,100%),1fr));gap:0 24px}
ul.flops li{display:grid;grid-template-columns:12.5em minmax(0,1fr);gap:10px;align-items:start;padding:10px 0;border-top:1px solid var(--rule)}
.ft{margin:0;font-weight:600}.ft .w{font-weight:400;color:var(--muted);font-size:var(--fs-0);margin-left:6px}.fq{margin:2px 0 0;color:var(--ink2);font-size:var(--fs-0)}.fa{margin:4px 0 0;font-size:var(--fs-0)}
li.fl.ok .fa,li.fl.na .fa{color:var(--muted)}li.fl.na .ft,li.fl.na .fq{color:var(--ink2)}.fw{margin:4px 0 0;font-size:var(--fs-0)}.fw .proof{display:block;color:var(--muted);overflow-wrap:anywhere}
details.fold{margin-top:12px}details.fold>summary{padding:4px 0}details.fold>summary h2{margin:16px 0 8px;display:inline-flex}details.fold>summary .count{color:var(--muted);font-size:var(--fs-0)}
details.fold>.card{margin-top:4px}.srule{margin-bottom:12px}.srule ul{margin:4px 0 0}
@media (max-width:760px){.glance{grid-template-columns:1fr}ul.chan li{grid-template-columns:1fr auto}ul.chan .cnote{grid-column:1/-1}ul.flops li{grid-template-columns:1fr}}
"""
