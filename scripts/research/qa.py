#!/usr/bin/env python3
"""Questions and answers ("domande e risposte") for STATUS.html.

Three groups, filterable by text and by topic:
  * "Le tue domande": the questions the owner asked during the work, with the answer given, saved in launch/qa.json (qa.py add) or in
    status.json -> qa (entries with "custom": true). Each can carry a topic, a wave and a gate so you see what it belongs to.
  * "Domande frequenti, con le risposte di oggi": generic questions answered from the CURRENT data (verdict and its reasons, what to
    do now, what changed since the last wave, the worst open criticalities, can I pay Steam Direct, when to launch, how many copies to
    break even, where the wishlists are, what happens if things go badly, does the full game hold) plus a few fixed explanations
    (what the focus-group score means, whether it predicts sales, how to record wishlists). They change when the data changes.
  * "Domande che conviene farti adesso": questions suggested by the state of the project (a gate not passed, a serious open
    criticality, a crowded launch week...) and a few that always help before a launch.
Answers use simple Italian. Links inside answers are written [[target|text]] and turned into links to the section that deals with it.

  qa.py add --q "Perché non pago Steam adesso?" --a "Perché il Gate B non è superato..." [--topic Cancelli] [--wave 2] [--gate B] [--source "dal piano"]
  qa.py list
  qa.py rm 3
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re

import common  # noqa: F401  (side effect: UTF-8 stdout, so accents do not crash on a Windows console)

CSS = """
.qa input[type=search]{width:100%;padding:8px 10px;border:1px solid var(--ring);border-radius:8px;background:var(--surface);color:var(--ink);font:inherit;margin-bottom:8px}
.qa details.q{border-top:1px solid var(--grid);padding:8px 0}.qa details.q[hidden]{display:none}.qa details.q>div{margin:6px 0 2px;color:var(--ink2)}.qa h3{margin:18px 0 4px}
.qa .tags{display:inline-flex;gap:6px;margin-left:8px;vertical-align:middle}.qa ul.sug{margin:6px 0 0;padding-left:20px}.qa ul.sug li{margin:4px 0}.qa .empty{color:var(--muted);display:none}
"""
JS = """
(function(){document.querySelectorAll('[data-qa]').forEach(function(box){var q=box.querySelector('input[type=search]'),bs=box.querySelectorAll('.filters button'),ds=box.querySelectorAll('details.q'),em=box.querySelector('.empty'),topic='all';
function run(){var t=(q.value||'').toLowerCase().trim(),n=0;ds.forEach(function(d){var ok=(topic==='all'||d.getAttribute('data-topic')===topic)&&(!t||d.textContent.toLowerCase().indexOf(t)>-1);d.hidden=!ok;if(ok)n++;});if(em)em.style.display=n?'none':'block';}
q.addEventListener('input',run);bs.forEach(function(b){b.addEventListener('click',function(){topic=b.getAttribute('data-t');bs.forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});run();});});});})();
"""


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def resolve_links(text: str, anchors: dict) -> str:
    """[[target|text]] -> link to the section (class xl) when it exists on the page, plain text otherwise."""
    return re.sub(r"\[\[(\w+)\|([^\]]+)\]\]", lambda m: f'<a class="xl" href="#{anchors[m.group(1)]}" title="Vai alla sezione">{m.group(2)}</a>' if m.group(1) in anchors else m.group(2), text)


def _fmt(n) -> str:
    return "n/d" if n is None else f"{int(round(n)):,}".replace(",", ".")


# ---------------------------------------------------------------- stored entries
def read_log(root: str) -> list[dict]:
    p = os.path.join(root, "qa.json")
    try:
        data = json.load(open(p, encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    return [x for x in data if isinstance(x, dict) and x.get("q")] if isinstance(data, list) else []


def stored(root: str, st: dict) -> list[dict]:
    """The owner's questions: launch/qa.json plus status.json -> qa, normalised."""
    out = []
    for src in (read_log(root), [x for x in (st.get("qa") or []) if isinstance(x, dict) and x.get("q")]):
        for x in src:
            out.append(dict(q=str(x["q"]), a=str(x.get("a") or ""), topic=str(x.get("topic") or "Generale"), custom=bool(x.get("custom", x.get("by", "utente") != "generica")),
                            date=str(x.get("date") or ""), wave=x.get("wave"), gate=x.get("gate"), source=str(x.get("source") or "")))
    return out


# ---------------------------------------------------------------- answers from the current data
def faq(ctx: dict) -> list[tuple]:
    """[(topic, question, answer html)]. Only the questions that the data can answer today are returned."""
    st, wl, econ, win, crit, plan, today = ctx.get("st") or {}, ctx.get("wl_a") or {}, ctx.get("econ"), ctx.get("window"), ctx.get("crit"), ctx.get("plan") or {}, ctx["today"]
    out = []
    v = st.get("verdict") or {}
    gates = st.get("gates") or {}
    names = ctx.get("gate_names") or {}
    if v:
        word = str(v.get("color", "")).capitalize() or "n/d"
        notpass = [names.get(k, f"Gate {k}") for k, g in gates.items() if g.get("state") != "pass"]
        a = esc(v.get("summary", "")) + (f' Rischi principali: {esc("; ".join(v.get("risks", [])[:3]))}.' if v.get("risks") else "") + (f' Cancelli non ancora superati: {esc(", ".join(notpass))} ([[gates|vedi i cancelli]]).' if notpass else "")
        out.append(("Verdetto", f"Perché il verdetto è {word.lower()}?", a))
    if plan.get("phases"):
        import plan_steps as ps
        mine = ps.next_steps(plan, "me", 3, today)
        out.append(("Cosa fare", "Cosa devo fare adesso?", ("<ol>" + "".join(f'<li>{esc(re.sub(r"[*`]", "", s["text"]))}' + (f' (entro {esc(s["due"])})' if s.get("due") else "") + "</li>" for s in mine) + "</ol>Il resto è nel [[steps|calendario a passi]]." if mine else "Niente in sospeso per te: tocca a Claude o aspetti una data ([[steps|calendario a passi]]).")))
    if crit and crit.get("panels"):
        panels = crit["panels"]
        last = panels[-1]
        if len(panels) > 1:
            prev = panels[-2]["wave"]
            d = last["wave"]["score"] - prev["score"] if isinstance(last["wave"]["score"], (int, float)) and isinstance(prev["score"], (int, float)) else None
            parts = [f'Punteggio {last["wave"]["score"]}' + (f' ({d:+.1f} rispetto all\'ondata {prev["n"]})' if d is not None else "")]
            new = [r["label"] for r in last["rows"] if r["status"] in ("nuova", "ricomparsa")]
            up = [r["label"] for r in last["rows"] if r["status"] == "in aumento"]
            if last["resolved"]:
                parts.append("risolte: " + ", ".join(r["label"] for r in last["resolved"]))
            if new:
                parts.append("nuove: " + ", ".join(new))
            if up:
                parts.append("in aumento: " + ", ".join(up))
            a = esc(". ".join(parts)) + ". Il dettaglio è in [[critiche|Criticità]]."
        else:
            a = "È la prima ondata: non c'è ancora un confronto. Dalla prossima vedrai cosa migliora e cosa peggiora in [[critiche|Criticità]]."
        out.append(("Ondate", "Cosa è cambiato rispetto all'ultima ondata?", a))
    if crit and crit.get("issues"):
        opened = [x for x in crit["issues"] if x["open"]][:3] + []
        reg = [m for m in crit.get("register", []) if m["status"] != "risolta"]
        lines = [f'<li><strong>{esc(x["label"])}</strong>, gravità {esc(x["severity"])}' + (f', {x["last_pct"]:g}% dei tester' if x.get("last_pct") is not None else "") + (f', cancello {esc(x["gate"])}' if x.get("gate") else "") + "</li>" for x in opened]
        lines += [f'<li><strong>{esc(m["label"])}</strong>, gravità {esc(m["severity"])}, da {esc(m["source"])}</li>' for m in reg[:max(0, 3 - len(lines))]]
        out.append(("Ondate", "Quali sono le criticità aperte più gravi?", ("<ul>" + "".join(lines) + "</ul>Tutte, ondata per ondata, in [[critiche|Criticità]]." if lines else "Nessuna criticità aperta nell'ultima ondata.")))
    if gates:
        nopass = [(k, g) for k, g in gates.items() if g.get("state") != "pass"]
        if nopass:
            a = "Non ancora: restano da superare " + esc(", ".join(names.get(k, f"Gate {k}") for k, _ in nopass)) + ". " + esc(next((g.get("note") for _, g in nopass if g.get("note")), "")) + " Pagare prima di aver superato i cancelli vuol dire spendere senza prove ([[gates|cancelli]])."
        else:
            a = "I cancelli sono tutti superati. Resta da controllare il resto: soldi disponibili, accordo tra soci e commercialista ([[gates|cancelli]])."
        out.append(("Cancelli", "Posso pagare Steam Direct adesso?", a))
        first = next((g for _, g in nopass if g.get("note")), None)
        if first:
            out.append(("Cancelli", "Cosa serve per superare il prossimo cancello?", esc(first.get("note")) + " ([[gates|cancelli]])"))
    if win and win.get("chosen"):
        ch = win["chosen"]
        best = win["best"][0] if win.get("best") else None
        a = f'La settimana scelta ({esc(win["launch"])}) risulta <strong>{esc(ch["verdict"])}</strong>: il {ch["quieter_weeks_pct"]}% delle settimane candidate è più tranquillo.' + (f' La più tranquilla in lista è quella dal {esc(best["week"])}.' if best else "") + " Conta solo ciò che è in lista ([[window|finestra di lancio]])."
        out.append(("Lancio", "Quando conviene uscire?", a))
    if econ:
        be = econ["breakeven"]
        sc = econ.get("scenarios") or []
        a = f'Servono circa <strong>{_fmt(be["copies_with_time"])}</strong> copie per coprire soldi e ore (solo i soldi spesi: {_fmt(be.get("copies_cash"))}). Per ogni copia restano {econ["net_per_copy"]:.2f}.' + (" Gli scenari vendono " + ", ".join(f'{esc(s["name"])}: {_fmt(s["copies"])}' for s in sc) + "." if sc else "") + " ([[economy|economia]])"
        out.append(("Economia", "Quante copie servono per coprire i costi?", a))
    if wl.get("current") is not None:
        vel = wl.get("velocity_4w")
        a = f'Oggi {_fmt(wl["current"])} wishlist' + (f', circa {_fmt(vel)} a settimana nelle ultime 4' if vel is not None else "") + (f'; mancano {_fmt(wl["days_to_launch"])} giorni al lancio' if "days_to_launch" in wl else "") + "."
        alerts = [x["text"] for x in wl.get("alerts", []) if x.get("level") in ("ALARM", "ATTENZIONE")]
        out.append(("Wishlist", "A che punto sono le wishlist?", esc(a) + (" Attenzione: " + esc(alerts[0]) if alerts else "") + " ([[trend|andamento]])"))
    out.append(("Ondate", "Cosa significa il punteggio del focus group?", "È un voto che dà il gruppo di tester simulati: più è alto, più tester metterebbero il gioco in wishlist. Non è una percentuale (va da -80 a 100) e serve a confrontare un'ondata con l'altra e con la soglia del cancello A. Differenze di pochi punti sono rumore."))
    out.append(("Ondate", "Il focus group prevede le vendite?", "No. I tester sono simulati: ordinano i problemi e dicono cosa sistemare per primo, ma non sono dati di mercato. Le critiche reali vengono dalle recensioni vere e dal test con persone vere."))
    out.append(("Wishlist", "Come registro le wishlist?", "Una volta a settimana copia il totale da Steamworks e dillo a Claude, oppure esegui <code>wl_track.py add --wishlists N</code>. Steam non rende pubbliche le wishlist, quindi non si possono leggere da fuori."))
    cont = ctx.get("contingencies")
    if cont:
        out.append(("Se va male", "E se qualcosa va male?", "Sono già pronti dei piani «se… allora»: " + ", ".join(esc(s.get("title", "")) for s in cont[:4]) + ". Ognuno ha un segnale, una soglia e cosa fare ([[contingencies|piani se… allora]])."))
    fg = st.get("full_game")
    if fg and fg.get("summary"):
        out.append(("Gioco completo", "Il gioco completo regge?", esc(fg["summary"]) + " ([[fullgame|dettaglio]])"))
    if (st.get("product") or {}).get("kind") in ("beta", "demo", "vertical_slice"):
        out.append(("Gioco completo", "Perché la beta si giudica in modo diverso dal gioco completo?", "Una beta mostra solo una parte: il contenuto che manca non è un difetto, è un gap da colmare. Se è gratuita deve soprattutto far venire voglia di comprare il gioco finito, quindi guardiamo anche quanti tester pagherebbero."))
    return out


def suggested(ctx: dict) -> list[tuple]:
    """[(question, why)]: questions worth asking now, from the state of the project, then the ones that always help."""
    st, crit, win = ctx.get("st") or {}, ctx.get("crit"), ctx.get("window")
    names = ctx.get("gate_names") or {}
    out = []
    for k, g in (st.get("gates") or {}).items():
        if g.get("state") != "pass":
            out.append((f"Cosa manca per superare il {names.get(k, 'Gate ' + k)}?", "Un cancello non superato blocca il pagamento di Steam: meglio sapere cosa serve e quando rifare la prova."))
            break
    if crit:
        top = next((x for x in crit.get("issues", []) if x["open"] and x["severity"] == "alta"), None)
        if top:
            out.append((f"Quanto costa sistemare «{top['label']}» e ho le ore per farlo?", "È una criticità grave ancora aperta: conviene sapere ore, scadenza e cosa si sposta se la risolvi."))
    if win and win.get("chosen", {}).get("verdict") == "affollata":
        out.append(("Sposto la data di lancio o resto dov'è?", "La settimana scelta ha molta concorrenza vicino: conviene decidere ora, con le alternative sotto mano."))
    out += [("Cosa taglieresti se le ore non bastassero?", "Decidere i tagli prima evita di farli di corsa all'ultimo."), ("Cosa succede se la prima settimana va male?", "I piani «se… allora» servono a questo: avere già soglie e azioni."),
            ("Chi, fuori dal team, può provare il gioco prima del lancio?", "I tester veri trovano ciò che i simulati non vedono."), ("C'è qualcosa che non vuoi assolutamente cambiare?", "Le tue linee rosse guidano il piano: meglio dirle presto.")]
    return out[:7]


# ---------------------------------------------------------------- html
def _item(topic: str, q: str, a: str, tags: str = "") -> str:
    return f'<details class="q" data-topic="{esc(topic)}"><summary><strong>{esc(q)}</strong>{tags}</summary><div>{a}</div></details>'


def build(root: str, ctx: dict) -> str | None:
    """The whole section (with its h2) or None when there is nothing to show."""
    st = ctx.get("st") or {}
    mine = stored(root, st)
    custom = [x for x in mine if x["custom"]]
    others = [x for x in mine if not x["custom"]]
    gen = faq(ctx)
    sug = suggested(ctx)
    topics = sorted({x["topic"] for x in mine} | {t for t, _, _ in gen})
    if not (custom or others or gen):
        return None
    def tags(x):
        t = ""
        if x.get("wave"):
            t += f'<span class="pill new">Ondata {esc(x["wave"])}</span>'
        if x.get("gate"):
            t += f'<span class="pill mute">Cancello {esc(x["gate"])}</span>'
        if x.get("date"):
            t += f'<span class="note">{esc(x["date"])}</span>'
        return f'<span class="tags">{t}</span>' if t else ""
    def body(x):
        return esc(x["a"]).replace("\n", "<br>") + (f'<p class="note">{esc(x["source"])}</p>' if x["source"] else "")
    chips = '<div class="filters" role="group" aria-label="Filtra per argomento"><button type="button" data-t="all" aria-pressed="true">Tutte</button>' + "".join(f'<button type="button" data-t="{esc(t)}" aria-pressed="false">{esc(t)}</button>' for t in topics) + "</div>"
    parts = ['<h2>Domande e risposte</h2><div class="card qa" data-qa>', '<input type="search" placeholder="Cerca una domanda o una parola…" aria-label="Cerca nelle domande">', chips]
    if custom:
        parts.append("<h3>Le tue domande</h3>" + "".join(_item(x["topic"], x["q"], body(x), tags(x)) for x in sorted(custom, key=lambda x: x["date"], reverse=True)))
    if others:
        parts.append("<h3>Altre domande con risposta</h3>" + "".join(_item(x["topic"], x["q"], body(x), tags(x)) for x in others))
    if gen:
        parts.append("<h3>Domande frequenti, con le risposte di oggi</h3>" + "".join(_item(t, q, a) for t, q, a in gen))
    parts.append('<p class="empty">Nessuna domanda corrisponde: prova con un\'altra parola.</p>')
    if sug:
        parts.append("<h3>Domande che conviene farti adesso</h3><ul class=\"sug\">" + "".join(f"<li><strong>{esc(q)}</strong><br><span class=\"note\">{esc(w)}</span></li>" for q, w in sug) + "</ul><p class=\"note\">Falle a Claude: le risposte che contano le salva qui, nelle tue domande.</p>")
    parts.append("</div>")
    return "".join(parts)


# ---------------------------------------------------------------- log CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", default="launch/qa.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add"); p.add_argument("--q", required=True); p.add_argument("--a", required=True); p.add_argument("--topic", default="Generale"); p.add_argument("--wave"); p.add_argument("--gate")
    p.add_argument("--source", default=""); p.add_argument("--by", choices=["utente", "generica"], default="utente"); p.add_argument("--date", default=dt.date.today().isoformat())
    p = sub.add_parser("rm"); p.add_argument("id", type=int)
    sub.add_parser("list")
    a = ap.parse_args()
    data = []
    if os.path.exists(a.json):
        try:
            data = json.load(open(a.json, encoding="utf-8-sig"))
        except ValueError:
            raise SystemExit(f"{a.json} is not valid JSON")
    if a.cmd == "add":
        same = next((x for x in data if x.get("q", "").strip().lower() == a.q.strip().lower()), None)
        entry = dict(id=(same or {}).get("id") or max([x.get("id", 0) for x in data] + [0]) + 1, date=a.date, q=a.q, a=a.a, topic=a.topic, by=a.by, source=a.source)
        if a.wave:
            entry["wave"] = a.wave
        if a.gate:
            entry["gate"] = a.gate.upper()
        data = [x for x in data if x is not same] + [entry]      # the same question is updated, not duplicated
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        json.dump(sorted(data, key=lambda x: x.get("id", 0)), open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"saved question {entry['id']} in {a.json}")
    elif a.cmd == "rm":
        n = len(data)
        data = [x for x in data if x.get("id") != a.id]
        if len(data) == n:
            raise SystemExit(f"question {a.id} not found")
        json.dump(data, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"removed question {a.id}")
    else:
        print("\n".join(f"{x.get('id'):3} {x.get('date', '')} [{x.get('topic', '')}] {x.get('q')}" for x in data) or "no questions saved")


if __name__ == "__main__":
    main()
