#!/usr/bin/env python3
"""Plain-Italian explanations and internal links for the HTML reports (status_page.py, report_html.py).

Two things, applied to the text of a page (never to code, links, buttons, headings, summaries, SVG):
  1. a short explanation of a term the first time it appears in each section, shown as a tooltip on hover, keyboard focus or tap
     (<abbr class="g" tabindex="0" data-def="...">), and collected in a "Glossario" at the end of the page with only the terms used;
  2. a link to the section of the page that deals with the thing mentioned ("creator" -> the creators section), once per section,
     never to the section you are already in.
The explanations are deliberately simple and carry no figures that go out of date. Text already inside an <abbr> or <a> is skipped. Apply it once to each section.
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser

# key: (regex of the words in the text, plain explanation or None, link target or None)
TERMS: dict = {
    "wishlist": (r"wishlist|lista desideri", "La lista dei desideri di Steam: chi ci mette il gioco riceve un avviso all'uscita. È il segnale di interesse più usato prima del lancio.", "trend"),
    "gate": (r"gate(?: [0abc])?|cancell[oi](?: go ?/ ?no-go)?|go ?/ ?no-go", "Un controllo da superare prima di andare avanti o di spendere soldi. Se non passa, si sistema e si ripete.", "gates"),
    "ice": (r"\bICE\b", "Un modo per ordinare le idee: Impatto, Confidenza e Facilità, ognuno da 1 a 10. Si fa la media e vince il punteggio più alto.", None),
    "premortem": (r"pre-?mortem", "Si immagina che il gioco sia già un flop e si scrive perché. Serve a vedere i problemi prima che succedano.", "premortem"),
    "tripwire": (r"tripwire|segnali? d'allarme", "Un segnale d'allarme con una soglia e una data: se scatta, si cambia piano.", None),
    "breakeven": (r"break-?even|punto di pareggio", "Quante copie bisogna vendere per coprire i costi. Da lì in poi si guadagna.", "economy"),
    "conversione": (r"conversione|tasso di conversione", "Quanti di quelli che hanno messo il gioco in wishlist lo comprano davvero.", None),
    "percentile": (r"percentile", "Dice dove ti trovi rispetto agli altri: il 60° percentile vuol dire meglio del 60% dei giochi.", None),
    "mediana": (r"mediana", "Il valore di mezzo: metà dei giochi sta sotto e metà sopra. Inganna meno della media.", None),
    "codaalta": (r"coda alta", "I giochi più venduti o recensiti. Non rappresentano il gioco normale: dicono cosa serve per farsi vedere, non cosa aspettarsi.", None),
    "focusgroup": (r"focus group|panel|tester simulati", "Tester inventati, con gusti diversi, che giudicano il gioco. Servono a ordinare i problemi, non a prevedere le vendite.", "waves"),
    "ondata": (r"ondat[ae]", "Un giro completo del focus group. Si ripete dopo le modifiche con gli stessi tester per vedere cosa è cambiato.", "waves"),
    "hook": (r"\bhook\b|gancio", "I primi secondi in cui il giocatore capisce cosa fai e decide se gli interessa.", None),
    "capsule": (r"capsule", "L'immagine del gioco negli elenchi dei negozi, quella piccola che si vede mentre si scorre. Deve spiegarsi in un attimo.", None),
    "nextfest": (r"next ?fest", "Il festival delle demo di Steam: per alcuni giorni tanti giocatori provano demo gratuite. È una grande occasione di visibilità.", None),
    "steamdirect": (r"steam direct", "La quota che si paga a Steam per poter pubblicare un gioco. L'importo si verifica sul sito ufficiale.", None),
    "comparabili": (r"comparabil[ei]|\bcomps\b", "Giochi simili al tuo per genere e pubblico. Servono a capire cosa aspettarsi e cosa funziona.", "competitors"),
    "posizionamento": (r"posizionamento", "Come presenti il gioco e cosa lo rende diverso dagli altri simili. Se non è chiaro, il resto conta poco.", None),
    "benchmark": (r"benchmark", "Un confronto con i numeri di altri giochi, per sapere se i tuoi sono alti o bassi.", None),
    "dealbreaker": (r"dealbreaker", "Un difetto che da solo fa dire no al giocatore.", None),
    "boxleiter": (r"boxleiter", "Un metodo per stimare le vendite partendo dal numero di recensioni. È approssimato.", None),
    "steamspy": (r"steamspy", "Un sito di terzi che stima proprietari e giocatori dei giochi Steam. I numeri sono approssimati: servono per le tendenze.", None),
    "steamdb": (r"steamdb", "Un sito che mostra dati pubblici di Steam: follower, picchi di giocatori, prezzi nel tempo.", "steamdb"),
    "verticalslice": (r"vertical slice", "Un pezzo del gioco rifinito bene, che fa vedere com'è il gioco finito.", None),
    "build": (r"\bbuild\b", "La versione del gioco che si può avviare e provare.", None),
    "playtest": (r"playtest", "Una prova del gioco fatta da persone vere, per vedere dove si bloccano o si annoiano.", None),
    "rimborso": (r"rimbors[oi]|refund", "Il giocatore compra e poi chiede i soldi indietro. Una quota alta dice che il gioco non mantiene la promessa.", None),
    "roster": (r"roster", "L'elenco dei tester simulati, ognuno con un codice fisso, così sono sempre gli stessi a ogni ondata.", None),
    "convergenza": (r"convergenza", "Quando due gruppi che non si sono visti arrivano alla stessa conclusione: è un buon segno che il problema è vero.", None),
    "puntwl": (r"punteggio wishlist", "Il voto del focus group: più è alto, più tester metterebbero il gioco in wishlist. Non è una percentuale.", None),
    "netto": (r"netto per copia", "Quanto resta a te per ogni copia venduta, dopo tasse, commissione di Steam e rimborsi.", "economy"),
    "contingenza": (r"contingenz[ae]|se… ?allora|se\.\.\. ?allora", "Un piano già pronto per cosa fare se qualcosa va male, con segnale, soglia e prima azione.", "contingencies"),
    "creator": (r"creator|streamer|influencer|outreach", "Chi fa video o dirette e può far conoscere il gioco. Outreach vuol dire contattarli.", "creators"),
    "proxy": (r"\bproxy\b", "Un numero che sta al posto di un altro che non si può avere: le recensioni, per esempio, al posto delle vendite.", None),
    "euristica": (r"euristic[ao]", "Una regola pratica che dà un'idea, non una misura esatta.", None),
    "pilastri": (r"pilastr[oi]", "Le cose che un gioco di questo genere deve fare bene per piacere. Ogni pilastro prende PASS, MARGINAL o FAIL.", "product"),
    "calendario": (r"calendario a passi|passi in ordine", "L'elenco dei passi da fare, in ordine, ognuno con chi lo fa (tu o Claude) e la scadenza.", "steps"),
    "window": (r"finestra di lancio", "Il periodo attorno alla data di uscita: contano i concorrenti, i festival e i saldi che ci cadono vicino.", "window"),
    "storekit": (r"pagin[ae] steam|pagin[ae] itch|kit pagine|store kit", "I testi, i tag e le immagini delle pagine dei negozi, pronti da copiare.", "storekit"),
    "fullgame": (r"gioco completo", "La versione finale del gioco, non la beta.", "fullgame"),
    "todo": (r"\bTODO\b|prossime azioni", "L'elenco delle cose da fare, con scadenza e ore stimate.", "todo"),
    "intentions": (r"profilo decisionale|intenzioni", "Ciò che vuoi davvero (obiettivo, tempo, budget, rischio): guida le soglie e il piano.", "intentions"),
}
LABEL = {"wishlist": "Wishlist", "gate": "Gate (cancello)", "ice": "ICE", "premortem": "Pre-mortem", "tripwire": "Tripwire (segnale d'allarme)", "breakeven": "Break-even", "conversione": "Conversione",
         "percentile": "Percentile", "mediana": "Mediana", "codaalta": "Coda alta", "focusgroup": "Focus group simulato", "ondata": "Ondata", "hook": "Hook (gancio)", "capsule": "Capsule", "nextfest": "Next Fest",
         "steamdirect": "Steam Direct", "comparabili": "Comparabili", "posizionamento": "Posizionamento", "benchmark": "Benchmark", "dealbreaker": "Dealbreaker", "boxleiter": "Boxleiter", "steamspy": "SteamSpy",
         "steamdb": "SteamDB", "verticalslice": "Vertical slice", "build": "Build", "playtest": "Playtest", "rimborso": "Rimborso", "roster": "Roster", "convergenza": "Convergenza", "puntwl": "Punteggio wishlist",
         "netto": "Netto per copia", "contingenza": "Piani se… allora", "creator": "Creator e outreach", "proxy": "Proxy", "euristica": "Euristica", "pilastri": "Pilastri", "calendario": "Calendario a passi",
         "window": "Finestra di lancio", "storekit": "Pagine dei negozi", "fullgame": "Gioco completo", "todo": "TODO", "intentions": "Profilo decisionale"}
SECTION_RX = {  # link target -> regex on the section heading
    "trend": r"andamento|wishlist", "gates": r"cancelli|gate", "premortem": r"pre-?mortem", "economy": r"economia|prezz|economi", "waves": r"ondate del focus|critiche e ondate|focus group",
    "steamdb": r"steamdb", "creators": r"^creator|creator e community", "contingencies": r"se… allora|se\.\.\. allora|contingenz|piani", "product": r"audit|pilastr|quadro d'insieme",
    "steps": r"passi in ordine|piattaforme|calendario", "window": r"finestra di lancio", "storekit": r"pagine store|pagina steam|testi dello store|kit", "fullgame": r"beta oggi|gioco completo",
    "todo": r"prossime azioni|todo", "intentions": r"profilo decisionale|intenzioni", "competitors": r"concorrenti e comparabili|mercato|comparabil"}
SKIP = {"script", "style", "svg", "code", "pre", "a", "button", "abbr", "textarea", "summary", "nav", "title", "select", "option", "h1", "h2", "h3", "head"}
VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}
_RX = re.compile("|".join(f"(?P<{k}>{v[0]})" for k, v in sorted(TERMS.items(), key=lambda kv: -len(kv[1][0]))), re.I)
_RX = re.compile(r"(?<![\w-])(?:" + _RX.pattern + r")(?![\w-])", re.I)

CSS = """
abbr.g{text-decoration:underline dotted var(--muted);text-underline-offset:3px;cursor:help;position:relative}
abbr.g:hover::after,abbr.g:focus::after{content:attr(data-def);position:absolute;left:var(--dx,0);top:calc(100% + 6px);z-index:30;width:max-content;max-width:min(300px,78vw);background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:8px 10px;font-size:.85rem;font-weight:400;line-height:1.4;text-align:left;white-space:normal;box-shadow:0 4px 14px rgba(0,0,0,.18)}
a.xl{color:inherit;text-decoration:underline dashed var(--s1);text-underline-offset:3px}a.xl:hover,a.xl:focus{color:var(--s1)}
dl.gl dt{font-weight:600;margin-top:10px}dl.gl dd{margin:2px 0 0;color:var(--ink2)}
@media print{abbr.g::after{display:none!important}}
"""
JS = """
(function(){document.querySelectorAll('abbr.g').forEach(function(a){function fit(){var r=a.getBoundingClientRect(),w=Math.min(300,innerWidth*0.78),dx=Math.min(0,innerWidth-12-r.left-w);a.style.setProperty('--dx',dx+'px');}
a.addEventListener('mouseenter',fit);a.addEventListener('focus',fit);});})();
"""


class _Enricher(HTMLParser):
    def __init__(self, anchors: dict, own: set, used: set, gloss: bool, links: bool):
        super().__init__(convert_charrefs=False)
        self.out, self.skip, self.anchors, self.own, self.used, self.gloss, self.links = [], 0, anchors, own, used, gloss, links
        self.seen_gloss: set = set()
        self.seen_link: set = set()

    def handle_starttag(self, tag, attrs):
        self.out.append(self.get_starttag_text())
        if tag in SKIP and tag not in VOID:
            self.skip += 1

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")
        if tag in SKIP and self.skip:
            self.skip -= 1

    def handle_entityref(self, name):
        self.out.append(f"&{name};")

    def handle_charref(self, name):
        self.out.append(f"&#{name};")

    def handle_comment(self, data):
        self.out.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.out.append(f"<!{decl}>")

    def handle_data(self, data):
        if self.skip or not data.strip():
            self.out.append(data)
            return
        self.out.append(_RX.sub(self._sub, data))

    def _sub(self, m):
        key, text = m.lastgroup, m.group(0)
        _, definition, target = TERMS[key]
        inner = text
        if self.gloss and definition and key not in self.seen_gloss:
            self.seen_gloss.add(key)
            self.used.add(key)
            inner = f'<abbr class="g" tabindex="0" data-def="{html.escape(definition, quote=True)}">{text}</abbr>'
        if self.links and target and target in self.anchors and self.anchors[target] not in self.own and target not in self.seen_link:
            self.seen_link.add(target)
            inner = f'<a class="xl" href="#{self.anchors[target]}" title="Vai alla sezione">{inner}</a>'
        return inner


def enrich(chunk: str, anchors: dict | None = None, own: set | None = None, used: set | None = None, *, gloss: bool = True, links: bool = True) -> str:
    """Add tooltips and internal links to the HTML of one section. `anchors` maps a link target (see SECTION_RX) to an element id,
    `own` holds the ids of the sections contained in `chunk` (no self-links), `used` collects the glossary keys explained."""
    p = _Enricher(anchors or {}, own or set(), used if used is not None else set(), gloss, links)
    p.feed(chunk)
    p.close()
    return "".join(p.out)


def anchors_for(headings: list[tuple[str, str]]) -> dict:
    """[(id, heading text)] -> {link target: id of the first heading that matches}."""
    out = {}
    for target, rx in SECTION_RX.items():
        for hid, text in headings:
            if re.search(rx, text, re.I):
                out[target] = hid
                break
    return out


def glossary_html(used: set) -> str:
    if not used:
        return ""
    items = sorted(used, key=lambda k: LABEL.get(k, k).lower())
    rows = "".join(f"<dt>{html.escape(LABEL.get(k, k))}</dt><dd>{html.escape(TERMS[k][1])}</dd>" for k in items)
    return f'<details class="card doc"><summary><strong>Glossario: le parole usate in questa pagina</strong></summary><dl class="gl">{rows}</dl></details>'
