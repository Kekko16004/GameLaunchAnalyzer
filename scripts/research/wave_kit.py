#!/usr/bin/env python3
"""Wave kit: prepare and check the MANDATORY material of a focus-group wave (the "wave 9 method").

Before the panel judges, every wave gets six preparation files built from the real game (code, data, telemetry,
real reviews), for any engine (Unity, Unreal, Godot, custom), in launch/fg/waves/:

  wNN-brief.md              what is judged, tester questions (standard + extra), outputs
  wNN-mappa-gioco.md        TOTAL map of the game from the code, with file references (path or path:line)
  wNN-schermate.md          every screen/menu: how you reach it, when, whether the game tells you, grade
                            evidente (ovvia) / trovabile / nascosta
  wNN-runs.md               3+ simulated typical runs with timestamps (mm:ss): new player, one who understood,
                            first win; dead spots, fun peaks, frustration, quit points, too much UI, unclear moments
  wNN-mercato.md            real reviews of comparables (review_corpus.py) and demo-length market data, with sources
  wNN-proposte-gameplay.md  gameplay proposals (evidence, hours, risk) + a separate "Riapre la decisione" section
  wNN-limite-beta.md        (optional) what to cut / limit in a free demo or beta
  wNN-sintesi.md            (output, filled after the panel) every row with the issue key and the proposal ID P-wNN-n

Link with game-developer (references/dev-link.md, contract gdl-v2). When the game project has docs/design-review/:
  - the brief gets a "Da ricontrollare" section filled from docs/design-review/changes-since-wMM.md (the risks the
    development gates introduced, the design choices they changed); MM = the previous wave;
  - wNN-mappa-gioco.md, wNN-schermate.md, wNN-runs.md start from game-map.md, screen-map.md, runs.md (copied as they are,
    to verify on the code); the screens file always carries the shared ```screens block, the runs use times from the start
    of the run and the shared tags [MORTO] [TOP] [FRUSTRA] [ABBANDONO] [CONFUSO] [TROPPA-UI:n] [SPIRALE];
  - `fixes` copies the changes-since `fixes` block as it is (or `gate_link.py since --json`) into the wave JSON.
Without game-developer everything works the same: the templates are filled from the code by hand.

Commands:
  init  --launch-dir launch --wave N [--date YYYY-MM-DD] [--game NAME] [--project ROOT]
                                     write the templates, never overwrite (ROOT default: the folder above launch/)
  check --launch-dir launch --wave N [--json] [--project ROOT]
                                     Italian checklist; exit 1 if a required item is missing (limite-beta, the
                                     contract items and the sintesi only warn)
  fixes --launch-dir launch --wave N [--from FILE] [--write WAVE.json] [--project ROOT]
                                     the `fixes` array from changes-since (.md) or `gate_link.py since --json` (.json);
                                     --write appends the missing ones to the wave JSON (never removes or edits a fix)

The checker accepts the real wave-9 formats (it is the reference): headings are matched by meaning, not by exact text.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import re
import sys

from common import setup_stdio  # noqa: F401  (importing common already switches stdout/stderr to UTF-8)

PLACEHOLDER = "(da compilare)"

# ---------------------------------------------------------------------------------------------- game-developer link
REVIEW_DIR = ("docs", "design-review")
REVIEW_SRC = {"mappa-gioco": "game-map.md", "schermate": "screen-map.md", "runs": "runs.md"}
SHARED_TAGS = ("MORTO", "TOP", "FRUSTRA", "ABBANDONO", "CONFUSO", "SPIRALE")   # + [TROPPA-UI:n] (dev-link.md §9)
TAG_RX = re.compile(r"\[(?:" + "|".join(SHARED_TAGS) + r"|TROPPA-UI\s*:\s*\d+)\]", re.I)
RUN_TIME = re.compile(r"^\s*(\d+):(\d{2})(?:\s*[-–]\s*(\d+):(\d{2}))?")       # same as design_review.py
PID_RX = re.compile(r"\bP-w\d{2,}-\d+\b")
REOPEN_RX = re.compile(r"Riapre la decisione:\s*[^—\n]+—\s*prove:[^—\n]+—\s*proposta:[^—\n]+—\s*costo:", re.I)


def project_root(launch_dir: str, project: str | None = None) -> str:
    return os.path.abspath(project) if project else os.path.dirname(os.path.abspath(launch_dir))


def review_file(root: str, name: str) -> str:
    return os.path.join(root, *REVIEW_DIR, name)


def find_changes_since(root: str, n: int, launch_dir: str | None = None) -> str | None:
    """docs/design-review/changes-since-wMM.md that describes the state judged by wave n: MM = the latest wave before n
    found in launch/fg/waves, else n-1. None when the developer side has not written it."""
    prev = n - 1
    if launch_dir:
        nums = {int(m.group(1)) for p in glob.glob(os.path.join(wave_dir(launch_dir), "w[0-9]*"))
                for m in [re.match(r"w(\d+)-", os.path.basename(p))] if m and int(m.group(1)) < n}
        prev = max(nums) if nums else prev
    for mm in (prev, n - 1):
        p = review_file(root, f"changes-since-w{mm:02d}.md")
        if mm >= 1 and os.path.exists(p):
            return p
    return None


def parse_changes_since(text: str) -> dict:
    """The file written by game-developer's `gate_link.py since --out`: gates, touched keys, risks to re-check, design
    changes, things to try, and the `fixes` block (kept as it is)."""
    out = {"gates": [], "touched": [], "risks": [], "changes": [], "tries": [], "fixes": []}
    for m in re.finditer(r"^- \*\*Gate (\d+)\*\* \(([^,]*), ([^)]*)\): (.*?)(?: — `([^`]+)`)?\s*$", text, re.M):
        out["gates"].append({"gate": int(m.group(1)), "date": m.group(2).strip(), "status": m.group(3).strip(),
                             "title": m.group(4).strip(), "path": m.group(5) or ""})
    tbl = body_until_next(text, r"criticit[àa] toccate") or ""
    for ln in tbl.splitlines():
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) >= 4 and c[0].startswith("`") and c[2].isdigit():
            out["touched"].append({"issue": c[0].strip("`"), "status": c[1], "gate_dev": int(c[2]), "what": " | ".join(c[3:])})

    def bullets(rx: str, field: str) -> list:
        res = []
        for ln in (body_until_next(text, rx) or "").splitlines():
            m = re.match(r"^\s*-\s*gate\s+(\d+)\s*:\s*(.+)$", ln, re.I)
            if m:
                res.append({"gate_dev": int(m.group(1)), field: m.group(2).strip()})
        return res
    out["risks"] = bullets(r"rischi", "risk")
    out["changes"] = bullets(r"scelte di design", "change")
    out["tries"] = bullets(r"da provare", "try")
    blk = body_until_next(text, r"`?fixes`?") or ""
    m = re.search(r"```(?:json)?\s*\n(.*?)```", blk, re.S)
    if m:
        try:
            fx = json.loads(m.group(1))
            out["fixes"] = [f for f in fx if isinstance(f, dict)] if isinstance(fx, list) else []
        except ValueError:
            out["fixes_error"] = "blocco `fixes` non leggibile (JSON)"
    by = {(t["issue"], t["what"]): t["gate_dev"] for t in out["touched"]}
    for f in out["fixes"]:   # issue/what stay as they are; the gate number comes from the same file's table
        g = by.get((f.get("issue"), f.get("what")))
        if g is not None and "gate_dev" not in f:
            f["gate_dev"] = g
    return out


def load_changes_since(root: str, n: int, launch_dir: str | None = None) -> tuple[str | None, dict | None]:
    p = find_changes_since(root, n, launch_dir)
    if not p:
        return None, None
    with open(p, encoding="utf-8", errors="replace") as f:
        return p, parse_changes_since(f.read())


def _rel(root: str, p: str) -> str:
    return os.path.relpath(p, root).replace("\\", "/")


def _recheck_section(n: int, root: str | None, launch_dir: str | None) -> str:
    head = "## Da ricontrollare (rischi introdotti dai gate di sviluppo dopo l'ultima ondata)\n"
    p, cs = load_changes_since(root, n, launch_dir) if root else (None, None)
    if not cs:
        return (head + "> Se il gioco lo sviluppa `game-developer`: prima dell'ondata `gate_link.py since --out docs/design-review/changes-since-wNN.md` "
                "e rilancia `wave_kit.py init` su un brief nuovo (o copia qui i rischi). Altrimenti scrivi cosa può essere peggiorato con i cambi fatti, "
                "o \"niente da ricontrollare\". I tester commentano apposta ogni voce (regola di regressione, `references/dev-link.md` §8).\n"
                f"{PLACEHOLDER}\n")
    gates = ", ".join(f"gate {g['gate']}" for g in cs["gates"]) or "nessun gate nuovo"
    lines = [head + f"> Da `{_rel(root, p)}` ({gates}). I tester guardano apposta ogni voce e dicono se il problema c'è; sono punti da guardare, "
                    "non un elenco di fix (anti-ancoraggio). Un problema nuovo nato da un gate entra nel JSON con una **chiave nuova** e `\"from_gate_dev\": NN`; "
                    "una chiave `risolto` che torna riapre come \"ricomparso dopo il gate NN\" (`references/dev-link.md` §8)."]
    lines += [f"- [gate {r['gate_dev']}] {r['risk']}" for r in cs["risks"]]
    lines += [f"- [gate {c['gate_dev']}, scelta di design cambiata] {c['change']}" for c in cs["changes"]]
    if not cs["risks"] and not cs["changes"]:
        lines.append(f"- niente da ricontrollare: i gate ({gates}) non dichiarano rischi")
    return "\n".join(lines) + "\n"


def _from_review(n: int, date: str, title: str, root: str, src: str, extra: str = "") -> str:
    """A wave file that starts from the developer's design-review file, copied as it is (without its H1)."""
    with open(src, encoding="utf-8", errors="replace") as f:
        text = f.read().lstrip("﻿")
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    g = re.search(r"aggiornat[ao]\s+al\s+gate\s+(\d+)(?:\s*\(([^)]*)\))?", text, re.I)
    when = f" (aggiornata al gate {g.group(1)}" + (f", {g.group(2)}" if g.group(2) else "") + ")" if g else " (gate non indicato)"
    body = "\n".join(lines).strip("\n")
    return (f"# Ondata {n} — {title} ({date})\n\n"
            f"> **Partita da `{_rel(root, src)}`**{when}, scritta da game-developer (`references/dev-link.md` §6.2 e §9). Copiata così com'è: "
            "**verificala sul codice** prima del panel, correggi dove la build è cambiata, cita il gate e lascia **[DA VERIFICARE]** dove non hai controllato.\n\n"
            + body + "\n" + extra)


SCREENS_BLOCK = """
## 3. Blocco `screens` (stesso formato di `design_review.py` di game-developer)
> Una riga per cosa: `root:` (dove parte il gioco), `screen: Nome | file | hidden-ok: motivo e fonte` (solo per quelle nascoste per scelta),
> `A -> B : come` (`auto` = la apre il gioco da solo). Servono per contare orfani, clic dalla radice e posti con un solo ingresso.

```screens
# root: Menu
# screen: Negozio | UI/Shop.uxml
# Menu -> Opzioni : clic Opzioni
```
"""


# ---------------------------------------------------------------------------------------------- templates
def _t_brief(n: int, date: str, game: str, root: str | None = None, launch_dir: str | None = None) -> str:
    w = f"w{n:02d}"
    return f"""# Ondata {n} — Brief ({date})

> **SIMULATO.** Stessi tester del roster (gruppi A e B in contesti separati), anti-ancoraggio: vedono solo lo stato attuale di {game}. Punteggi con `fg_waves.py`. Le decisioni prese dal proprietario non contano come problemi.
> Prima del panel si preparano (e si controllano con `wave_kit.py check`) i file di preparazione elencati sotto.

## Cosa si valuta
> Tipo di prodotto (beta / demo / gioco completo), build, cosa è cambiato per il proprietario, materiali (pagina store, trailer, capsule).
{PLACEHOLDER}

{_recheck_section(n, root, launch_dir)}
## Preparazione dell'ondata (obbligatoria, prima dei giudizi)
- `{w}-mappa-gioco.md`: mappa totale del gioco dal codice, con i file;
- `{w}-schermate.md`: tutte le schermate, come ci arrivi e se lo scopri (evidente / trovabile / nascosta);
- `{w}-runs.md`: almeno 3 run simulate con i tempi (nuovo giocatore, chi ha capito, prima vittoria);
- `{w}-mercato.md`: recensioni vere dei simili (`review_corpus.py`) e durata delle demo;
- `{w}-proposte-gameplay.md`: proposte con prove, ore e rischio + sezione "Riapre la decisione";
- `{w}-limite-beta.md` (se c'è una demo o beta gratuita): cosa tagliare o limitare.

## Domande ai tester
Oltre a quelle solite (verdetto, click sulla capsule, pitch capito, pagheresti il prezzo previsto):
1. Spiega il gioco a un amico in **una frase**: arriva il gancio? (`hook_lands`)
2. Dopo **quante run** (o partite) smetti, e perché? (`q_stop_after_runs`)
3. **Quanto pagheresti** il gioco completo? Dai una cifra. (`q_price_full`)
4. Quale **momento** ricordi di più? (`q_memorable`)
5. La **co-op / il multiplayer** ti serve per comprarlo? (`q_coop_needed`)
6. **In quale minuto** ti annoi per la prima volta, e cosa stavi facendo? (`q_bored_minute`)
7. Finita la demo/beta, cosa fai: wishlist, la consigli, la disinstalli? Cosa ti farebbe tornare? (`q_after_demo`)
8. Lo **guarderesti giocare** da un creator o lo giocheresti tu? Quale momento condivideresti come clip? (`q_watch_or_play`)
9. In quale momento **non sapevi cosa fare**, o c'erano **troppe cose a schermo**? (`q_lost_moment`)

## Limite della demo/beta
> Solo se c'è una demo o beta gratuita: cosa devono proporre i tester (durata, contenuti, fine). Altrimenti scrivi "non serve".
{PLACEHOLDER}

## Uscite
- `{w}-group-a.md`, `{w}-group-b.md`, `{w}-debate.md`;
- `{w}-AAAA-MM-GG.json` (o `-beta.json` / `-full.json`), `{w}-metrics-*`, `{w}-delta-*`; `fixes` da `wave_kit.py fixes` se c'è il file `changes-since`;
- `{w}-sintesi.md` per il proprietario, in italiano semplice: ogni riga con la **chiave** e l'ID della proposta `P-{w}-n`;
- poi `timeline.md`, `TODO.md` (con `todo_track.py`: righe 🤖 con `P-{w}-n` e `key:<chiave>`), `issue_status.json`, `STATUS.html`, `predictions.py sync`.
"""


def _t_mappa(n: int, date: str, game: str, root: str | None = None, launch_dir: str | None = None) -> str:
    sec = [
        ("1. Il giro del gioco (loop) in una riga", "Dal menu alla fine di una partita, con i file che lo governano."),
        ("2. Livelli, durate, obiettivi", "Ogni livello/piano/missione: durata, obiettivo, numeri, asset o dati (`percorso`)."),
        ("3. Sistemi e regole (con i numeri)", "Vita/umore/punteggio, condizioni di sconfitta e vittoria, ogni valore con il file (`percorso:riga`)."),
        ("4. Economia (valute, ricompense, prezzi)", "Da dove entrano e dove escono soldi, punti, mance; tabella Fonte | Valore | File."),
        ("5. Progressione, sblocchi e meta", "Cosa si sblocca, quando, a che prezzo; cosa resta tra una partita e l'altra."),
        ("6. Oggetti, potenziamenti, perk", "Elenco completo con effetto e file; segna cosa c'è nella demo/beta e cosa no."),
        ("7. Ostacoli, nemici, disturbi", "Ogni pericolo: quando arriva, cosa fa, come si evita."),
        ("8. Eventi", "Eventi a tempo o casuali, con finestra e ricompensa."),
        ("9. HUD e testi a schermo", "Ogni elemento dell'HUD, notifiche, marker, fumetti."),
        ("10. Comandi", "Tastiera, mouse, pad, touch; rimappatura."),
        ("11. Accessibilità", "Opzioni reali presenti nel codice."),
        ("12. Audio", "Musica, effetti, mixer, cosa manca."),
        ("13. Telemetria, piattaforme, lingue", "Cosa si misura, dove gira, quali lingue."),
        ("14. Cosa NON c'è (deciso o rimandato)", "Così i tester non lo contano come difetto."),
    ]
    src = review_file(root, REVIEW_SRC["mappa-gioco"]) if root else None
    if src and os.path.exists(src):
        return _from_review(n, date, "Mappa totale del gioco", root, src)
    body = "\n\n".join(f"## {h}\n> {g}\n{PLACEHOLDER}" for h, g in sec)
    return f"""# Ondata {n} — Mappa totale del gioco ({date})

> Tutto quello che c'è nella build di oggi di {game}, letto dal codice e dai dati, **con il file di riferimento** (`percorso` o `percorso:riga`). Motore qualsiasi: script, asset di dati, scene, file di configurazione, editor via MCP se c'è.
> Etichette: **[FATTO]** = letto nel codice o negli asset · **[DA VERIFICARE]** = scritto nel design ma non controllato giocando. È un inventario: niente giudizi.

{body}
"""


def _t_schermate(n: int, date: str, game: str, root: str | None = None, launch_dir: str | None = None) -> str:
    src = review_file(root, REVIEW_SRC["schermate"]) if root else None
    if src and os.path.exists(src):
        with open(src, encoding="utf-8", errors="replace") as f:
            has_block = "```screens" in f.read()
        return _from_review(n, date, "Mappa di tutte le schermate: come ci arrivi e se lo scopri", root, src, "" if has_block else SCREENS_BLOCK)
    return f"""# Ondata {n} — Mappa di tutte le schermate: come ci arrivi e se lo scopri ({date})

> Letto nel codice, nei file della UI e negli asset. **Voto di scoperta:** **evidente** (te la mette davanti il gioco) · **trovabile** (c'è un pulsante visibile, ma nessuno te lo dice) · **nascosta** (serve sapere che esiste, o non si apre mai).

## 1. Tabella completa
> Una riga per ogni schermata, menu, scheda, popup. Tasti e clic esatti.

| # | Schermata (file) | Come ci arrivi (tasti / clic) | Quando diventa raggiungibile | Il gioco te lo dice? | Voto |
|---|---|---|---|---|---|
{PLACEHOLDER}

## 2. Cosa resta nascosto o poco chiaro
> Schermate nascoste, doppie porte, schermate belle ma irraggiungibili; cosa unire, spostare o mostrare al momento giusto.
{PLACEHOLDER}
{SCREENS_BLOCK}"""


def _t_runs(n: int, date: str, game: str, root: str | None = None, launch_dir: str | None = None) -> str:
    src = review_file(root, REVIEW_SRC["runs"]) if root else None
    if src and os.path.exists(src):
        return _from_review(n, date, "Run tipiche, trascritte a tempi", root, src)

    def run(k: int, title: str, hint: str) -> str:
        return f"""## RUN {k} — {title}
> {hint}

| Tempo | Dove | Cosa fa il giocatore | Numeri | A schermo e segni |
|---|---|---|---|---|
{PLACEHOLDER}"""
    runs = "\n\n".join([
        run(1, "Giocatore nuovo", "Profilo vuoto: avvio, menu, tutorial, primo livello, prima sconfitta o fine."),
        run(2, "Giocatore che ha capito", "Qualche partita alle spalle; estrazioni ed eventi diversi dalla run 1."),
        run(3, "Prima vittoria (o quasi)", "Boss/finale, sblocchi, schermata di fine."),
    ])
    return f"""# Ondata {n} — Run tipiche, trascritte a tempi ({date})

> **SIMULATO.** Run ricostruite dai numeri veri del codice, dei dati e della telemetria (se c'è); dove il tempo dipende dal giocatore scrivi **[STIMA]**.
> Formato a tempi: ogni riga della tabella **comincia con il tempo dall'inizio della run** (`m:ss` o `m:ss-m:ss`, mai azzerato per livello): stanze, azioni, numeri, notifiche, schermate, caricamenti.
> Segni nella riga (gli stessi di `design_review.py` di game-developer): **[MORTO]** punto morto (dura fino alla riga dopo o al range) · **[TOP]** punto divertente (clip) · **[FRUSTRA]** frustrazione · **[ABBANDONO]** abbandono probabile · **[CONFUSO]** non si capisce cosa fare · **[TROPPA-UI:n]** troppe UI insieme (n pannelli o avvisi) · **[SPIRALE]** un fallimento che ne porta un altro senza spiegazione.
> Esempio: `| 0:40-0:52 | corridoio | camminata vuota col carico | — | [MORTO] |`

## 0. I numeri veri su cui si basano le run
> Durate, obiettivi, valori dal codice (`percorso`), telemetria vera se c'è.
{PLACEHOLDER}

{runs}

## 4. Riepilogo per i tester
> I punti morti più grandi, i punti divertenti più grandi, dove si perde il filo.
{PLACEHOLDER}
"""


def _t_mercato(n: int, date: str, game: str, root: str | None = None, launch_dir: str | None = None) -> str:
    return f"""# Ondata {n} — {game} contro il mercato reale del genere ({date})

> Dati veri, con fonte (URL o file). Recensioni **parafrasate**, citazioni sotto le 15 parole, nessun nome di recensore. **[FATTO]** / **[STIMA]** / **[OPINIONE]**.

## 1. Le fonti usate
> `review_corpus.py --comps ... --genre-tag ... --my-features ... -o launch/_raw/corpus-{n:02d}.json --md ...`, comparabili, calibrazione, ricerche web con data.
{PLACEHOLDER}

## 2. Cosa premiano e cosa puniscono le recensioni vere
> Temi puniti e premiati, e cosa dicono delle caratteristiche del tuo gioco.
{PLACEHOLDER}

## 3. Dove sta il gioco
{PLACEHOLDER}

## 4. Durata delle demo (dati di mercato)
> Mediana di gioco delle demo che vendono, esempi di demo che "regalano troppo", con URL.
{PLACEHOLDER}

## 5. Limiti di questo confronto
{PLACEHOLDER}
"""


def _t_proposte(n: int, date: str, game: str, root: str | None = None, launch_dir: str | None = None) -> str:
    return f"""# Ondata {n} — Proposte di gameplay ({date})

> **SIMULATO / da discutere.** Ogni proposta ha: cosa cambia · perché · prova di mercato (gioco reale, fonte) · ore **[STIMA]** · rischio. Il proprietario sceglie cosa costruire.
> Fonti: `w{n:02d}-runs.md`, `w{n:02d}-schermate.md`, `w{n:02d}-mappa-gioco.md`, `w{n:02d}-mercato.md`.

> Ogni proposta ha un **ID `P-w{n:02d}-n`** (numerato da 1, non cambia più) e le **chiavi** delle criticità che chiude (le stesse di `issue_status.json` e del JSON dell'ondata): il piano dei gate di game-developer e le righe 🤖 della TODO le citano così (`references/dev-link.md` §5).

## 1. Proposte (dai dati delle run e del mercato)
> Una riga per proposta (dettagli in una sottosezione `### P-w{n:02d}-n — titolo` se servono). Rischio = cosa può peggiorare e per chi.

| ID | Chiave | Proposta (cosa cambia) | Perché | Prova di mercato (fonte) | Ore [STIMA] | Rischio |
|---|---|---|---|---|---|---|
{PLACEHOLDER}

## 2. Proposte dei tester e della giuria
> Si aggiunge dopo il panel, ordinata per impatto diviso ore, con ID e chiave come sopra (continua la numerazione).

| ID | Chiave | Proposta | Chi la chiede | Ore [STIMA] | Rischio |
|---|---|---|---|---|---|
{PLACEHOLDER}

## 3. Riapre la decisione (a parte: non abbassa il punteggio, non conta come problema)
> Solo con prove di mercato forti, una riga per decisione, in questo formato (contratto `references/dev-link.md` §4.3):
> `Riapre la decisione: <D-NNN o testo> — prove: <dati veri, con fonte> — proposta: <cosa> — costo: <ore>`
> Diventa lavoro solo con una decisione nuova del proprietario. Se nessuno riapre nulla, scrivi "Nessuna decisione riaperta".
{PLACEHOLDER}
"""


def _t_sintesi(n: int, date: str, game: str, root: str | None = None, launch_dir: str | None = None) -> str:
    w = f"w{n:02d}"
    return f"""# Ondata {n} — Sintesi per il proprietario ({date})

> **SIMULATO.** Si compila **dopo** il panel, in italiano semplice. Ogni riga porta la **chiave** della criticità e, se c'è una proposta, l'ID `P-{w}-n`: è il pacchetto che legge game-developer (`references/dev-link.md` §5.1). Le decisioni del proprietario non contano come problemi.

## Il punteggio
{PLACEHOLDER}

## I problemi più pesanti adesso
| # | Chiave | Problema | Tester | Gravità | Proposta | Fix proposto | Ore [STIMA] |
|---|---|---|---|---|---|---|---|
{PLACEHOLDER}

## Nati da un gate di sviluppo o ricomparsi
> Problema nuovo nato da un gate: chiave nuova e `"from_gate_dev": NN` nel JSON → scrivi "nato col gate NN". Chiave `risolto` che torna: riapre come "ricomparso dopo il gate NN". Se non ce ne sono, scrivi "nessuno".
{PLACEHOLDER}

## Le proposte, in ordine di impatto per ora di lavoro
| ID | Chiave | Proposta | Ore [STIMA] | Rischio | Approvata? |
|---|---|---|---|---|---|
{PLACEHOLDER}

## Riapre la decisione (a parte)
> `Riapre la decisione: <D-NNN o testo> — prove: <dati veri, con fonte> — proposta: <cosa> — costo: <ore>`; oppure "Nessuna decisione riaperta".
{PLACEHOLDER}
"""


def _t_limite(n: int, date: str, game: str, root: str | None = None, launch_dir: str | None = None) -> str:
    return f"""# Ondata {n} — Il limite della demo/beta: proposta ({date})

> Solo se c'è una demo o beta gratuita. Preferenze del panel **SIMULATO**; dati di mercato **[FATTO]** con fonte; tempi del gioco **[STIMA]** da `w{n:02d}-runs.md`.

## 1. In breve: la proposta
> Dove finisce, quanti minuti, quanti contenuti (oggetti, livelli, modalità) su quelli del gioco completo.
{PLACEHOLDER}

## 2. Perché questi numeri (mercato vero)
{PLACEHOLDER}

## 3. Cosa c'è dentro e cosa resta da desiderare
{PLACEHOLDER}

## 4. La schermata finale
> Wishlist, cosa aggiunge il gioco completo, teaser.
{PLACEHOLDER}
"""


TEMPLATES = [
    ("brief", _t_brief), ("mappa-gioco", _t_mappa), ("schermate", _t_schermate), ("runs", _t_runs),
    ("mercato", _t_mercato), ("proposte-gameplay", _t_proposte), ("limite-beta", _t_limite),
]
OUTPUTS = [("sintesi", _t_sintesi)]   # written by init too (never overwritten), filled after the panel


def wave_dir(launch_dir: str) -> str:
    return os.path.join(launch_dir, "fg", "waves")


def fname(n: int, kind: str) -> str:
    return f"w{n:02d}-{kind}.md"


def init(launch_dir: str, n: int, date: str | None = None, game: str = "il gioco", project: str | None = None) -> dict:
    """Write the templates of wave n (never overwrite). With game-developer's docs/design-review/ in the project, the brief
    gets "Da ricontrollare" from changes-since and map / screens / runs start from the developer's files."""
    date = date or datetime.date.today().isoformat()
    root = project_root(launch_dir, project)
    d = wave_dir(launch_dir)
    os.makedirs(d, exist_ok=True)
    written, skipped = [], []
    for kind, fn in TEMPLATES + OUTPUTS:
        p = os.path.join(d, fname(n, kind))
        if os.path.exists(p):
            skipped.append(p)
            continue
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(fn(n, date, game, root, launch_dir))
        written.append(p)
    used = [_rel(root, review_file(root, v)) for v in REVIEW_SRC.values() if os.path.exists(review_file(root, v))]
    cs = find_changes_since(root, n, launch_dir)
    return {"written": written, "skipped": skipped, "from_dev": used, "changes_since": _rel(root, cs) if cs else None}


def fixes_from(root: str, n: int, launch_dir: str | None = None, src: str | None = None) -> tuple[str | None, list]:
    """(source file, fixes) from changes-since (.md: the `fixes` block as it is, gate_dev from the same file's table) or from
    `gate_link.py since --json` (.json: issue, what, gate_dev, status)."""
    if src is None:
        src = find_changes_since(root, n, launch_dir)
    if not src:
        return None, []
    with open(src, encoding="utf-8", errors="replace") as f:
        text = f.read()
    if src.lower().endswith(".json"):
        data = json.loads(text)
        rows = data.get("fixes", []) if isinstance(data, dict) else data
        keep = ("issue", "what", "gate_dev", "status")
        return src, [{k: f[k] for k in keep if k in f} for f in rows if isinstance(f, dict)]
    cs = parse_changes_since(text)
    if cs.get("fixes_error"):
        raise SystemExit(f"{src}: {cs['fixes_error']}")
    return src, cs["fixes"]


def merge_fixes(wave_json: str, fixes: list) -> list:
    """Append to the wave JSON the fixes it does not have yet (same issue and what). Never removes or edits a fix."""
    with open(wave_json, encoding="utf-8") as f:
        w = json.load(f)
    have = w.setdefault("fixes", [])
    seen = {(x.get("issue"), x.get("what")) for x in have if isinstance(x, dict)}
    added = [f for f in fixes if (f.get("issue"), f.get("what")) not in seen]
    have += added
    with open(wave_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(w, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return added


# ---------------------------------------------------------------------------------------------- check
def sections(text: str, level: int | None = None) -> list[tuple[str, str]]:
    """[(heading, body)] split at '#'-headings of the given level (None = level 2 and 3)."""
    pat = r"^(#{2})\s+(.*)$" if level == 2 else r"^(#{2,3})\s+(.*)$"
    out, cur, buf = [], None, []
    for line in text.splitlines():
        m = re.match(pat, line)
        if m:
            if cur is not None:
                out.append((cur, "\n".join(buf)))
            cur, buf = m.group(2).strip(), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        out.append((cur, "\n".join(buf)))
    return out


def body_until_next(text: str, heading_rx: str) -> str | None:
    """Body of the first heading (any level) matching heading_rx, up to the next heading of the same or higher level."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m and re.search(heading_rx, m.group(2), re.I):
            lvl, buf = len(m.group(1)), []
            for nxt in lines[i + 1:]:
                m2 = re.match(r"^(#{1,6})\s+", nxt)
                if m2 and len(m2.group(1)) <= lvl:
                    break
                buf.append(nxt)
            return "\n".join(buf)
    return None


def content_lines(body: str) -> list[str]:
    """Real content: not headings, guidance (blockquotes), placeholders, table header/separator rows or blank lines."""
    lines = body.splitlines()
    out = []
    for i, l in enumerate(lines):
        s = l.strip()
        if not s or s.startswith(">") or s.startswith("#") or PLACEHOLDER in s or s in ("---", "***"):
            continue
        if re.fullmatch(r"\|?[\s:|-]+\|?", s):          # table separator
            continue
        if s.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\|?[\s:|-]+\|?", lines[i + 1].strip()):
            continue                                       # table header row
        out.append(s)
    return out


def filled(body: str | None, min_lines: int = 1) -> bool:
    return body is not None and len(content_lines(body)) >= min_lines


class Report:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, file: str, label: str, status: str, detail: str = ""):
        self.items.append({"file": file, "label": label, "status": status, "detail": detail})

    def ok(self, file, label, cond, detail="", required=True, info=""):
        """detail is shown when the check fails (or warns), info when it passes."""
        self.add(file, label, "ok" if cond else ("fail" if required else "warn"), info if cond else detail)
        return cond


FILE_REF = re.compile(r"`[^`\n]*(?:/[^`\n]*|\.(?:cs|gd|gdscript|cpp|cc|c|h|hpp|py|js|ts|lua|rs|go|java|kt|swift|json|asset|uxml|uss|prefab|unity|tscn|tres|scn|uasset|umap|ini|cfg|yaml|yml|xml|csv|shader|hlsl|inputactions|md))(?::\d+)?[^`\n]*`", re.I)
TIMESTAMP = re.compile(r"(?<![\d:.,])\d{1,2}:\d{2}(?![\d:])")
GRADE = {"evidente": r"\b(evidente|ovvia|ovvio)\b", "trovabile": r"\btrovabile\b", "nascosta": r"\bnascost[ao]\b"}

# extra tester questions: patterns searched in the brief and in the tester keys of the wave JSON files
EXTRA_QUESTIONS = [
    ("pitch", "gioco spiegato in una frase (gancio)", r"una frase|one sentence|\bhook_lands\b|\bq_pitch"),
    ("runs", "dopo quante run/partite smetti", r"quante (run|partite)|\bq_stop_after"),
    ("price", "quanto pagheresti il gioco completo", r"quanto pagheresti|\bq_price"),
    ("moment", "momento che ricordi di più", r"momento[^\n]{0,40}ricord|ricordi di più|\bq_memorable|\bq_moment"),
    ("coop", "serve la co-op / il multiplayer", r"co-?op|multiplayer|multigiocatore|\bq_coop"),
    ("bored", "in quale minuto ti annoi", r"ti annoi|prima noia|\bq_bored"),
    ("after", "cosa fai finita la demo/beta", r"finita la (demo|beta)|dopo la (demo|beta)|\bq_after"),
    ("watch", "guardare un creator o giocare, clip", r"guarderesti|\bclip\b|\bq_watch"),
    ("lost", "dove non sapevi cosa fare / troppe cose a schermo", r"non sapevi cosa fare|troppe cose a schermo|troppe ui|\bq_lost"),
]

MAP_SECTIONS = [  # (label, heading regex, required)
    ("giro del gioco / loop", r"giro|loop|flusso|ciclo", True),
    ("economia / numeri", r"econom|mance|soldi|valut|monet|punteggi", True),
    ("progressione e sblocchi", r"sblocc|meta|progressione|salvadanaio", True),
    ("comandi", r"comandi|controlli|input", True),
    ("audio", r"audio|suon|musica", True),
    ("accessibilità", r"accessibilit", True),
    ("oggetti / perk / potenziamenti", r"oggett|perk|potenziam|carte|armi|abilit", False),
    ("ostacoli / disturbi / nemici", r"ostacol|disturb|nemic|pericol|hazard", False),
    ("eventi", r"eventi|evento", False),
    ("HUD e testi a schermo", r"hud|testi a schermo|interfaccia", False),
    ("cosa NON c'è", r"non c'è|non ce|rimandat|fuori", False),
]


def _read(p: str) -> str | None:
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_screens_block(text: str) -> dict | None:
    """The shared ```screens block (same grammar as game-developer's design_review.py): roots, places, edges, orphans.
    None if there is no block; {"error": ...} if a line is unreadable or there is no root."""
    m = re.search(r"```screens\s*\n(.*?)```", text, re.S)
    if not m:
        return None
    roots, nodes, edges = [], {}, []
    for raw in m.group(1).splitlines():
        line = re.sub(r"\s+#.*$", "", raw).strip()
        if not line or line.startswith("#"):
            continue
        r_ = re.match(r"^root\s*:\s*(.+)$", line, re.I)
        if r_:
            roots += [x.strip() for x in r_.group(1).split(",") if x.strip()]
            continue
        s_ = re.match(r"^(?:screen|place|feature)\s*:\s*(.+)$", line, re.I)
        if s_:
            parts = [x.strip() for x in s_.group(1).split("|")]
            nodes.setdefault(parts[0], "")
            for q in parts[1:]:
                h = re.match(r"hidden-ok\s*:?\s*(.*)$", q, re.I)
                if h:
                    nodes[parts[0]] = h.group(1) or "yes"
            continue
        e = re.match(r"^(.+?)\s*->\s*(.+?)(?:\s*:\s*(.*))?$", line)
        if e:
            a, b = e.group(1).strip(), e.group(2).strip()
            edges.append((a, b))
            nodes.setdefault(a, "")
            nodes.setdefault(b, "")
            continue
        return {"error": f"riga non leggibile: {raw.strip()}"}
    if not roots:
        return {"error": "manca la riga `root:`"}
    for x in roots:
        nodes.setdefault(x, "")
    seen, todo = set(roots), list(roots)
    while todo:
        a = todo.pop()
        for x, y in edges:
            if x == a and y not in seen:
                seen.add(y)
                todo.append(y)
    orphans = sorted(k for k in nodes if k not in seen and not nodes[k])
    return {"roots": roots, "places": len(nodes), "edges": len(edges), "orphans": orphans}


def run_rows(text: str) -> dict:
    """{run heading: [rows]} with the rows whose FIRST cell is a time (the format design_review.py reads)."""
    out, cur = {}, None
    for line in text.splitlines():
        h = re.match(r"^##\s+(.+)$", line)
        if h:
            cur = h.group(1).strip()
            continue
        if cur and line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if cells and RUN_TIME.match(cells[0].replace("*", "")):
                out.setdefault(cur, []).append(line)
    return out


def _wave_jsons(d: str, n: int) -> list:
    out = []
    for p in sorted(glob.glob(os.path.join(d, f"w{n:02d}-*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                out.append((p, json.load(f)))
        except (OSError, ValueError):
            continue
    return out


def check_link(r: "Report", launch_dir: str, n: int, root: str, texts: dict) -> None:
    """Contract items (references/dev-link.md): warnings only, so old waves and projects without game-developer still pass."""
    d = wave_dir(launch_dir)
    cs_path, cs = load_changes_since(root, n, launch_dir)
    brief = texts.get("brief") or ""
    if cs_path and texts.get("brief") is not None:
        rel = _rel(root, cs_path)
        rech = body_until_next(brief, r"da ricontrollare")
        cited = os.path.basename(cs_path) in brief and filled(rech)
        r.ok(fname(n, "brief"), "\"Da ricontrollare\" dai gate di sviluppo", cited,
             f"esiste `{rel}` ma il brief non lo cita o la sezione è vuota: copia i rischi (o rifai il brief con `wave_kit.py init`)", False,
             info=f"da `{rel}`: {len(cs['risks'])} rischi, {len(cs['gates'])} gate")
    if cs_path and cs["fixes"]:
        js = _wave_jsons(d, n)
        if js:
            have = {(f.get("issue"), f.get("what")) for _, w in js for f in (w.get("fixes") or []) if isinstance(f, dict)}
            miss = [f.get("issue") for f in cs["fixes"] if (f.get("issue"), f.get("what")) not in have]
            r.ok(os.path.basename(js[0][0]), "`fixes` dal file changes-since", not miss,
                 f"mancano {len(miss)} fix ({', '.join(sorted({str(x) for x in miss})[:6])}): `wave_kit.py fixes --wave {n} --write <json>`", False)
    if texts.get("schermate") is not None:
        b = parse_screens_block(texts["schermate"])
        fn = fname(n, "schermate")
        lab = "blocco ```screens (formato comune con game-developer)"
        if b is None:
            r.ok(fn, lab, False, "manca: aggiungilo per contare orfani e clic (`references/dev-link.md` §9)", False)
        elif "error" in b:
            r.ok(fn, lab, False, b["error"], False)
        else:
            r.ok(fn, lab, True, info=f"{b['places']} posti, {b['edges']} collegamenti")
            r.ok(fn, "nessun orfano nel blocco screens", not b["orphans"],
                 "irraggiungibili dalla radice e non segnati hidden-ok: " + ", ".join(b["orphans"][:8]), False)
    if texts.get("runs") is not None:
        rows = run_rows(texts["runs"])
        tags = sum(len(TAG_RX.findall(l)) for v in rows.values() for l in v)
        short = [h for h, v in rows.items() if len(v) < 5]
        r.ok(fname(n, "runs"), "righe che iniziano con il tempo della run e segni [MORTO] [TOP] [SPIRALE]…",
             len(rows) >= 3 and tags > 0 and not short,
             f"{len(rows)} run con righe a tempo, {tags} segni" + (f"; meno di 5 righe a tempo: {', '.join(short[:3])}" if short else "")
             + " (formato di `design_review.py runs`)", False, info=f"{len(rows)} run, {tags} segni")
    prop = texts.get("proposte-gameplay")
    if prop is not None:
        fn = fname(n, "proposte-gameplay")
        main = "\n".join(content_lines(re.split(r"riapre la decisione", prop, maxsplit=1, flags=re.I)[0]))
        if main.strip():
            ids = set(PID_RX.findall(main))
            r.ok(fn, f"proposte con ID P-w{n:02d}-n e chiave", bool(ids) and bool(re.search(r"\bchiav|`[a-z0-9]+(?:-[a-z0-9]+)+`|key:", main, re.I)),
                 "ogni proposta ha l'ID `P-wNN-n` e la chiave delle criticità che chiude (`references/dev-link.md` §5.1)", False, info=f"{len(ids)} ID")
        reo = body_until_next(prop, r"riapre la decisione") or ""
        lines = [l for l in content_lines(reo) if not re.search(r"nessun[ao]? .*riapert|nessuno riapre", l, re.I)]
        if lines:
            r.ok(fn, "riaperture nel formato del contratto (§4.3)", bool(REOPEN_RX.search(reo)),
                 "scrivi `Riapre la decisione: <D-NNN o testo> — prove: … — proposta: … — costo: <ore>`", False)
    sint = _read(os.path.join(d, fname(n, "sintesi")))
    if sint is not None and len(content_lines(sint)) >= 3:
        fn = fname(n, "sintesi")
        r.ok(fn, "righe con chiave e ID della proposta", bool(PID_RX.search(sint)) and bool(re.search(r"chiav|key", sint, re.I)),
             "la sintesi cita per ogni riga la chiave e `P-wNN-n` (`references/dev-link.md` §5.1)", False)
        status = {}
        sp = os.path.join(launch_dir, "issue_status.json")
        if os.path.exists(sp):
            try:
                with open(sp, encoding="utf-8") as f:
                    status = json.load(f)
            except (OSError, ValueError):
                status = {}
        born, back = [], []
        for _, w in _wave_jsons(d, n):
            for i in w.get("issues") or []:
                if not isinstance(i, dict):
                    continue
                if i.get("from_gate_dev") is not None:
                    born.append((i.get("key"), i["from_gate_dev"]))
                e = status.get(i.get("key"))
                if isinstance(e, dict) and e.get("status") == "risolto":
                    back.append(str(i.get("key")))
        miss_b = [str(k) for k, g in born if not re.search(rf"nat[oa] col gate {int(g)}\b", sint, re.I)]
        if born:
            r.ok(fn, "problemi nati da un gate: \"nato col gate NN\"", not miss_b, "manca per: " + ", ".join(sorted(set(miss_b))), False)
        if back:
            r.ok(fn, "chiavi risolte che tornano: \"ricomparso dopo il gate NN\"", bool(re.search(r"ricompars[oa] dopo il gate \d+", sint, re.I)),
                 "chiavi `risolto` in issue_status.json ma di nuovo nell'ondata: " + ", ".join(sorted(set(back))[:6])
                 + " → riaprile (`aperto`, nota \"ricomparso dopo il gate NN\") e scrivilo nella sintesi", False)


def check(launch_dir: str, n: int, project: str | None = None) -> dict:
    d = wave_dir(launch_dir)
    r = Report()
    texts = {kind: _read(os.path.join(d, fname(n, kind))) for kind, _ in TEMPLATES}

    def exists(kind, required=True):
        return r.ok(fname(n, kind), "file presente", texts[kind] is not None, "" if texts[kind] is not None else "manca: `wave_kit.py init` lo crea", required)

    # brief + extra questions
    if exists("brief"):
        t = texts["brief"]
        r.ok(fname(n, "brief"), "cosa si valuta", filled(body_until_next(t, r"cosa si valuta")), "sezione \"Cosa si valuta\" vuota")
    keys_text = ""
    for p in sorted(glob.glob(os.path.join(d, f"w{n:02d}-*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                w = json.load(f)
            keys_text += " " + " ".join(sorted({k for tt in w.get("testers", []) if isinstance(tt, dict) for k in tt}))
        except (OSError, ValueError):
            r.add(os.path.basename(p), "JSON leggibile", "warn", "non si legge")
    qsrc = (texts["brief"] or "").lower() + " " + keys_text
    missing = [lab for _, lab, rx in EXTRA_QUESTIONS if not re.search(rx, qsrc, re.I)]
    r.ok(fname(n, "brief"), f"domande extra ai tester ({len(EXTRA_QUESTIONS) - len(missing)}/{len(EXTRA_QUESTIONS)})", not missing,
         ("mancano: " + "; ".join(missing)) if missing else "")

    # game map
    if exists("mappa-gioco"):
        t, fn = texts["mappa-gioco"], fname(n, "mappa-gioco")
        refs = len(FILE_REF.findall(t))
        r.ok(fn, f"riferimenti ai file ({refs})", refs >= 5, "servono almeno 5 riferimenti `percorso` o `percorso:riga`" if refs < 5 else "")
        secs = sections(t)
        for label, rx, req in MAP_SECTIONS:
            hit = [b for h, b in secs if re.search(rx, h, re.I)]
            r.ok(fn, f"sezione: {label}", any(filled(b) for b in hit),
                 "manca o è vuota" if not hit else ("solo il modello, da compilare" if not any(filled(b) for b in hit) else ""), req)

    # screens
    if exists("schermate"):
        t, fn = texts["schermate"], fname(n, "schermate")
        rows = [l for l in t.splitlines() if l.strip().startswith("|") and not re.fullmatch(r"\|?[\s:|-]+\|?", l.strip())]
        graded = [l for l in rows if any(re.search(rx, l, re.I) for rx in GRADE.values())]
        r.ok(fn, f"schermate con voto di scoperta ({len(graded)})", len(graded) >= 3, "servono almeno 3 righe con evidente/trovabile/nascosta")
        used = [g for g, rx in GRADE.items() if any(re.search(rx, l, re.I) for l in graded)]
        r.ok(fn, "scala evidente (ovvia) / trovabile / nascosta spiegata", all(re.search(rx, t, re.I) for rx in GRADE.values()),
             "serve la legenda con i tre voti", info="usati: " + ", ".join(used) if used else "")
        r.ok(fn, "colonne come ci arrivi / il gioco te lo dice", bool(re.search(r"come ci arrivi|da dove", t, re.I)) and bool(re.search(r"te lo dice|lo scopr|scoperta", t, re.I)))
        r.ok(fn, "sezione: cosa resta nascosto o poco chiaro", filled(body_until_next(t, r"nascost|poco chiar|confus")), "", False)

    # runs
    if exists("runs"):
        t, fn = texts["runs"], fname(n, "runs")
        runs = {}
        for h, b in sections(t, 2):
            m = re.match(r"run\s*(\d+)", h, re.I)
            if m:
                runs.setdefault(int(m.group(1)), "")
                runs[int(m.group(1))] += "\n" + b
        good = {k: len(TIMESTAMP.findall("\n".join(content_lines(b)))) for k, b in runs.items()}
        ok_runs = [k for k, c in good.items() if c >= 5]
        per_run = ", ".join(f"run {k}: {c} tempi" for k, c in sorted(good.items()))
        r.ok(fn, f"almeno 3 run con i tempi mm:ss ({len(ok_runs)})", len(ok_runs) >= 3,
             (per_run + " (servono almeno 5 tempi per run)") if per_run else "nessuna sezione '## RUN N'", info=per_run)
        low = t.lower()
        marks = [("punti morti", r"punt[oi] mort|\[morto\]"), ("punti divertenti", r"divertent|\[top\]"), ("frustrazione", r"frustrazion|\[frustra\]"),
                 ("abbandono", r"abbandon")]   # the shared tags of dev-link.md §9 count as the marks
        miss = [lab for lab, rx in marks if not re.search(rx, low)]
        r.ok(fn, "segnati punti morti, divertenti, frustrazione, abbandono", not miss, ("mancano: " + ", ".join(miss)) if miss else "")
        extra = [("troppe UI", r"troppe ui|troppa roba|troppe cose|\[troppa-ui"), ("non si capisce cosa fare", r"non si capisce|cosa fare|perde il filo|\[confuso\]")]
        miss2 = [lab for lab, rx in extra if not re.search(rx, low)]
        r.ok(fn, "segnati troppe UI e momenti in cui non si capisce cosa fare", not miss2, ("mancano: " + ", ".join(miss2)) if miss2 else "", False)
        r.ok(fn, "numeri veri dal codice o dalla telemetria", bool(FILE_REF.search(t)) or bool(re.search(r"telemetri", low)), "", False)

    # market
    if exists("mercato"):
        t, fn = texts["mercato"], fname(n, "mercato")
        r.ok(fn, "recensioni vere (review_corpus.py / corpus)", bool(re.search(r"review_corpus|corpus|steam_reviews", t, re.I)) and filled(body_until_next(t, r"recension")),
             "serve una sezione sulle recensioni vere fatta con review_corpus.py")
        r.ok(fn, "dati sulla durata delle demo", filled(body_until_next(t, r"demo")) or bool(re.search(r"demo[^\n]{0,80}\d+\s*min", t, re.I)))
        r.ok(fn, "fonti con URL o file", bool(re.search(r"https?://", t)) or len(FILE_REF.findall(t)) >= 2)

    # proposals
    if exists("proposte-gameplay"):
        t, fn = texts["proposte-gameplay"], fname(n, "proposte-gameplay")
        reopen = body_until_next(t, r"riapre la decisione")
        r.ok(fn, "sezione \"Riapre la decisione\"", filled(reopen), "manca o è vuota (se nessuno riapre nulla, scrivilo)" if reopen is None or not filled(reopen) else "")
        main = "\n".join(content_lines(re.split(r"riapre la decisione", t, maxsplit=1, flags=re.I)[0]))   # real lines only, not the guidance
        r.ok(fn, "proposte con ore e rischio", bool(re.search(r"\bore\b", main, re.I)) and bool(re.search(r"rischi", main, re.I)),
             "ogni proposta dice ore [STIMA] e rischio")
        r.ok(fn, "prove di mercato", bool(re.search(r"prov[ae]|mercato|fonte|recension", main, re.I)), "ogni proposta porta una prova di mercato con fonte")

    check_link(r, launch_dir, n, project_root(launch_dir, project), texts)

    # demo / beta cap (optional)
    if exists("limite-beta", required=False):
        t = texts["limite-beta"]
        r.ok(fname(n, "limite-beta"), "proposta del limite compilata", len(content_lines(t)) >= 3, "solo il modello" if len(content_lines(t)) < 3 else "", False)

    fails = [i for i in r.items if i["status"] == "fail"]
    return {"wave": n, "dir": d, "ok": not fails, "fails": len(fails), "warns": sum(i["status"] == "warn" for i in r.items), "items": r.items}


def _n(k: int, one: str, many: str) -> str:
    return f"{k} {one if k == 1 else many}"


ICON = {"ok": "✅", "fail": "❌", "warn": "⚠️"}


def render(res: dict) -> str:
    out = [f"Ondata {res['wave']}: preparazione ({res['dir']})", ""]
    cur = None
    order = {}
    for i in res["items"]:
        order.setdefault(i["file"], len(order))
    for i in sorted(res["items"], key=lambda x: order[x["file"]]):   # stable: one block per file
        if i["file"] != cur:
            cur = i["file"]
            out.append(cur)
        out.append(f"  {ICON[i['status']]} {i['label']}" + (f" — {i['detail']}" if i["detail"] else ""))
    out.append("")
    if res["ok"]:
        out.append("Esito: preparazione completa" + (f" ({_n(res['warns'], 'avviso', 'avvisi')})" if res["warns"] else "") + ".")
    else:
        out.append(f"Esito: mancano {_n(res['fails'], 'cosa obbligatoria', 'cose obbligatorie')}" + (f" e {_n(res['warns'], 'avviso', 'avvisi')}" if res["warns"] else "")
                   + ". Completale prima del panel.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Prepare and check the mandatory material of a focus-group wave.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("init", help="write the template files of wave N (never overwrites)")
    pc = sub.add_parser("check", help="check that wave N has its preparation files, filled in")
    pf = sub.add_parser("fixes", help="the `fixes` array from game-developer's changes-since file (or gate_link.py since --json)")
    for p in (pi, pc, pf):
        p.add_argument("--launch-dir", default="launch")
        p.add_argument("--wave", type=int, required=True)
        p.add_argument("--project", help="game project root (default: the folder that contains launch/)")
    pi.add_argument("--date", help="YYYY-MM-DD (default today)")
    pi.add_argument("--game", default="il gioco", help="game name used in the headings")
    pc.add_argument("--json", action="store_true", help="machine-readable output")
    pf.add_argument("--from", dest="src", help="changes-since .md or the .json of `gate_link.py since --json` (default: found in docs/design-review/)")
    pf.add_argument("--write", help="wave JSON to complete: appends the missing fixes, never removes or edits one")
    a = ap.parse_args(argv)
    if a.wave < 1:
        ap.error("--wave must be >= 1")
    if a.cmd == "init":
        if a.date:
            try:
                datetime.date.fromisoformat(a.date)
            except ValueError:
                ap.error("--date must be YYYY-MM-DD")
        res = init(a.launch_dir, a.wave, a.date, a.game, a.project)
        for p in res["written"]:
            print(f"✅ creato   {p}")
        for p in res["skipped"]:
            print(f"⏭️ saltato  {p} (esiste già, non lo tocco)")
        if res["from_dev"]:
            print("ℹ️ partiti da game-developer: " + ", ".join(res["from_dev"]) + " (da verificare sul codice)")
        if res["changes_since"]:
            print(f"ℹ️ \"Da ricontrollare\" e fixes da {res['changes_since']}  →  wave_kit.py fixes --wave {a.wave} --write <json dell'ondata>")
        print(f"Poi: compila i file e controlla con  wave_kit.py check --launch-dir {a.launch_dir} --wave {a.wave}")
        return 0
    if a.cmd == "fixes":
        root = project_root(a.launch_dir, a.project)
        src, fx = fixes_from(root, a.wave, a.launch_dir, a.src)
        if not src:
            print("Nessun file changes-since in docs/design-review/: niente da copiare (chiedi `gate_link.py since` o scrivi i fixes a mano).")
            return 0
        if a.write:
            added = merge_fixes(a.write, fx)
            print(f"{len(added)} fix aggiunti a {a.write} da {_rel(root, src) if os.path.isabs(src) else src} ({len(fx) - len(added)} c'erano già)")
            for f in added:
                print(f"  + {f.get('issue')}: {f.get('what')}")
        else:
            print(json.dumps(fx, ensure_ascii=False, indent=1))
        return 0
    res = check(a.launch_dir, a.wave, a.project)
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else render(res))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
