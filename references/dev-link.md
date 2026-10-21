# Contratto game-developer ⇄ game-launch-strategist

contract: gdl-v3 · 2026-10-21

> **Documento condiviso.** Questo stesso testo, identico, sta in `game-developer/references/launch-link.md` e in `game-launch-strategist/references/dev-link.md`. Si cambia in tutte e due le copie insieme, alzando la versione (`gdl-v3`…). Se all'avvio le due righe `contract:` non coincidono, la skill lo dice al proprietario una volta e segue la regola più prudente delle due.
> I percorsi sono relativi alla radice del progetto del gioco; gli script si indicano con la cartella della skill (`<game-developer>/scripts/…`, `<launch>/scripts/research/…`).

Le due skill sono **complete da sole**. Insieme si passano il lavoro con file su disco, sempre gli stessi, in formati fissi. Nessuna delle due ha bisogno della chat dell'altra.

## 1. Chi c'è (rilevamento) e cosa succede se manca l'altra

| Segnale | Come si controlla |
|---|---|
| skill launch installata | `~/.claude/skills/game-launch-strategist/SKILL.md` o `~/.agents/skills/game-launch-strategist/SKILL.md` |
| skill dev installata | `~/.claude/skills/game-developer/SKILL.md` o `~/.agents/skills/game-developer/SKILL.md` |
| lavoro launch nel progetto | cartella `launch/` (`issue_status.json`, `TODO.md`, `fg/waves/`) |
| lavoro dev nel progetto | `docs/gates/`, `GAME_TASKS.md`, `DECISIONI.md` |

`python <game-developer>/scripts/gate_link.py --project . detect` stampa `linked` / `launch-only` / `solo`.

| Modo | Sviluppo (game-developer) | Lancio (game-launch-strategist) |
|---|---|---|
| **Insieme** (`linked`) | tutto questo contratto | tutto questo contratto |
| **Solo sviluppo** (niente `launch/`) | decisioni solo da `DECISIONI.md`; il lavoro arriva dal proprietario (note, giro di prova) invece che dalle ondate; i gate hanno lo stesso header con `closes: [nessuno: niente launch]`; design review fatta da sé (`references/design-review.md`) | — |
| **Launch senza skill dev** (`launch/` c'è, la skill dev no, o il gioco lo fa un'altra persona) | — | legge `docs/gates/*.md` com'è scritto (header se c'è, altrimenti il testo); costruisce mappa, schermate e run dal codice da sé (`wave_kit.py`); non scrive mai nel progetto del gioco |
| **Dev senza skill launch** (`launch/` c'è, la skill no) | legge i file di `launch/`; aggiorna `issue_status.json` con `gate_link.py apply-status`; spunta `TODO.md` a mano nello stesso formato (`[x]` + `· fatto il DATA (da 🤖, gate NN)`) | — |

Nessuna skill installa o lancia l'altra senza chiedere. Se manca, si dice in una riga cosa si perde ("senza la skill launch niente focus group né pagina di stato") e si va avanti.

## 2. Parole (per non confondersi)

| Parola | Vuol dire | Dove |
|---|---|---|
| **gate di sviluppo** | un blocco di lavoro chiuso sul gioco, numerato | `docs/gates/NN-slug.md` (dev) |
| **cancello** | Go/No-Go del lancio (0, A, B, C) | `launch/status.json`; nel JSON dell'ondata è il campo `gate` |
| `gate_dev` | il numero di un gate di sviluppo quando compare nei file del lancio | `fixes`, chiavi nuove nate da un gate |
| **chiave** | nome stabile di una criticità, uguale in tutte le ondate | `launch/issue_status.json`, JSON delle ondate |
| **ondata** `wNN` | un giro del focus group simulato | `launch/fg/waves/wNN-*` |
| **proposta** `P-wNN-n` | una modifica proposta dall'ondata, con ore e rischio | `wNN-proposte-gameplay.md`, sintesi |
| **approvata** | il proprietario ha detto sì, con una fonte (data) | §5.2 |
| **decisione** | scelta del proprietario che chiude un tema | §4 |

## 3. Chi possiede quali file

| File | Lo scrive | Lo legge | L'altra skill può |
|---|---|---|---|
| `launch/**` (ondate, sintesi, store, report, `STATUS.html`, `00-intenzioni.md`) | launch | dev | dev: niente |
| `launch/issue_status.json` | launch | dev | dev: **solo** con `gate_link.py apply-status` (§6) |
| `launch/TODO.md` | launch (`todo_track.py`) | dev | dev: **solo** `done` sulle righe 🤖 chiuse da un gate (§6) |
| `DECISIONI.md`, `GDD.md`, `GAME_TASKS.md`, `GAME_CONTEXT.md` | dev | launch | launch: niente |
| `docs/gates/**` (gate e `plan-wNN.md`) | dev | launch | launch: niente |
| `docs/design-review/**` (mappa, schermate, run, `changes-since-wNN.md`) | dev | launch | launch: niente (le copia e le verifica nei suoi `wNN-*`) |
| codice, scene, asset, build del gioco | dev | launch (sola lettura) | launch: mai |
| memoria del client (decisioni ricordate) | la chat principale | tutte e due | — |

Un file dell'altra skill cambiato mentre ci lavori = fermati e dillo, non unire a mano.

## 4. Decisioni del proprietario: una fonte sola, due registri

1. **Si leggono tutte, all'avvio di ogni skill e prima di ogni brief:** `DECISIONI.md`; "Decisioni prese" di `launch/TODO.md`; `launch/00-intenzioni.md` (registro e sezioni con data); in `launch/issue_status.json` le chiavi `accettato`, `non_problema`, `pianificato`, `sospeso`; la memoria del client se c'è.
2. **Ognuna scrive solo nel suo registro.** Il dev scrive `DECISIONI.md` (righe `D-NNN`), il launch "Decisioni prese" e `00-intenzioni.md`. All'avvio ognuna copia nel proprio registro le decisioni dell'altro che le mancano, con `fonte:` (es. `fonte: launch/00-intenzioni.md 2026-10-18`). Conflitto: vince la data più recente; senza data si chiede al proprietario una volta.
3. **Mai riaperte in silenzio.** Una decisione non è un problema, non abbassa un punteggio, non si "migliora" di nascosto. Si può solo proporre di cambiarla, in una sezione a parte con questa etichetta:
   `Riapre la decisione: <D-NNN o testo> — prove: <dati veri, con fonte> — proposta: <cosa> — costo: <ore>`
   (launch: in `wNN-proposte-gameplay.md` e nella sintesi; dev: nella sezione "Proposte" del gate o del report). Diventa lavoro solo con una decisione nuova del proprietario, scritta come riga nuova che "sostituisce D-NNN".
4. **Attribuzione.** "Il proprietario ha chiesto / deciso X" si scrive solo con la fonte (brief, chat con data, `D-NNN`, riga di `00-intenzioni.md`). Una scelta fatta da chi implementa si scrive come tale: `decided_by: implementer`.

## 5. Dal lancio allo sviluppo (dopo ogni ondata)

### 5.1 Il pacchetto che il launch lascia su disco
| File | Cosa serve al dev |
|---|---|
| `launch/fg/waves/wNN-sintesi.md` | i problemi più pesanti e le proposte in ordine, **ogni riga con la chiave** e l'ID `P-wNN-n` |
| `launch/fg/waves/wNN-proposte-gameplay.md` | per ogni proposta: `P-wNN-n`, chiavi, cosa cambia, perché, prova di mercato, ore [STIMA], rischio; a parte "Riapre la decisione" |
| `launch/issue_status.json` | lo stato di ogni chiave (§6.3) |
| `launch/TODO.md` | le righe 🤖 da fare, con `P-wNN-n` e `key:<chiave>` nel testo; nelle Dipendenze `ok del proprietario AAAA-MM-GG` quando è approvata |
| `launch/fg/waves/wNN-mappa-gioco.md`, `wNN-schermate.md`, `wNN-runs.md` | punto di partenza per la design review del dev (non si rifanno da zero) |
| decisioni (§4) | cosa non si tocca |

### 5.2 Quando una proposta è approvata
Una qualsiasi di queste, con data: la chiave è `in_lavorazione` in `issue_status.json`; la riga 🤖 della TODO ha `ok del proprietario AAAA-MM-GG`; `00-intenzioni.md` la registra come decisa; il proprietario l'ha detto nella chat del dev (→ riga in `DECISIONI.md`). Una proposta non approvata non diventa lavoro: si mostra al proprietario in una riga.

### 5.3 Cosa ne fa il dev
1. **Piano dei gate** `docs/gates/plan-wNN.md` (`templates/gate-plan.md`): **un gate = un blocco coerente** (stesse schermate o stesso sistema, provabile insieme in una sessione di gioco, di solito 3-15 h), **in ordine** (prima le regressioni nate da gate precedenti, poi impatto per ora, poi dipendenze), **con le ore**, le chiavi, la fonte dell'approvazione e i rischi da tenere d'occhio. Quello che aspetta va in "In attesa".
2. Task in `GAME_TASKS.md` con `Note: fg:wNN key:<chiave>[,<chiave>] gate:NN`.
3. **Design review "prima"** (mappa, schermate, run a tempi) se è più vecchia dell'ultimo gate; poi il gate; poi la review "dopo" (`references/design-review.md`).

## 6. Dallo sviluppo al lancio (dopo ogni gate)

### 6.1 I passi, sempre in quest'ordine
```bash
python <game-developer>/scripts/gate_link.py --project . check docs/gates/NN-slug.md          # header valido, foto su disco, chiavi vere
python <game-developer>/scripts/gate_link.py --project . apply-status docs/gates/NN-slug.md --write
python <game-developer>/scripts/gate_link.py --project . todo docs/gates/NN-slug.md --run      # todo_track.py done --by claude --note "gate NN"
python <game-developer>/scripts/design_review.py screens docs/design-review/screen-map.md      # se il gate ha toccato schermate/menu/negozio
```
Prima della prossima ondata (o quando il launch la prepara):
```bash
python <game-developer>/scripts/gate_link.py --project . since --out docs/design-review/changes-since-wNN.md
```
Il launch poi rigenera `STATUS.html` (è suo). Il dev non lancia mai gli script del launch tranne `todo_track.py done`.

### 6.2 Cosa legge il launch come "stato attuale"
- `docs/design-review/changes-since-wNN.md`: gate nuovi, chiavi toccate, **rischi da ricontrollare**, scelte di design cambiate, cosa provare; il blocco `fixes` va **così com'è** nel JSON dell'ondata.
- `docs/design-review/game-map.md`, `screen-map.md`, `runs.md` ("aggiornata al gate NN"): base per `wNN-mappa-gioco.md`, `wNN-schermate.md`, `wNN-runs.md` (si copiano e si verificano sul codice, si cita il gate).
- `owner_try` di ogni gate → righe 👤 "prova…" nella TODO (le aggiunge il launch).

### 6.3 Regole su `issue_status.json` (lato dev)
`apply-status` fa solo questo: chiavi in `closes` → `status: risolto`, `resolved: <data del gate>`; chiavi in `verify` → `status: da_verificare`; a tutte e due `gate: docs/gates/NN-slug.md` e in testa alla `note` "Gate NN (data): titolo. · " (la nota vecchia resta). Non tocca mai chiavi `accettato` / `non_problema` / `pianificato` / `sospeso`, non crea chiavi nuove (le crea il launch con l'ondata), non chiude niente da un gate che non è PASS. Fa una copia `.bak` prima di scrivere.

### 6.4 Dati di test reale e catture (qualsiasi motore)
- **Telemetria** (opt-in del giocatore, kit di playtest): `docs/playtest/telemetry.json` scritto da `<game-developer>/scripts/telemetry_report.py` (sessioni, tempo di gioco, dove si smette, morti per zona e causa, tempo al primo obiettivo, zone mai visitate). Per il launch è **test reale**: va con le critiche reali, **mai** mescolata con quelle del focus group simulato; cita la data e il numero di sessioni. Niente telemetria = si dice, non si stima.
- **Catture per store e trailer**: ogni cartella `captures/<nome>/` ha `manifest.json`; ogni file ha `produced: real-play | seed:<n> | debug-spawn:<regola> | staged:<cosa>`. Allo store vanno solo `real-play` / `seed`; una `staged` solo con ok del proprietario (riga in `DECISIONI.md`). Nucleon: `ncli.py capture plan.json` (in Play vero, regole non toccate); Unity: lo strumento di cattura del blocco E.
- **Prestazioni**: la riga `perf:` del gate (p95 contro `1000/targetFps`, sulla GPU vera) è il dato da usare per i requisiti della pagina store e per i rischi di recensione ("gira male"); `perf: skipped: software renderer` = dato mancante, non "va bene".
- Il launch legge questi file in sola lettura (§3) e non li rigenera.

## 7. Header dei gate di sviluppo (formato fisso, leggibile da macchina)

In testa a `docs/gates/NN-slug.md`, tra due righe `---` (modello: `game-developer/templates/gate.md`). Valori su una riga, liste `[a, b]` o righe `  - voce`. Dove non c'è niente: `nessuno: <motivo>` (mai vuoto).

| Chiave | Tipo | Regola |
|---|---|---|
| `gate` | numero | uguale al numero del nome file |
| `title` | testo | quello che il proprietario riconosce |
| `date` | AAAA-MM-GG | giorno di chiusura |
| `status` | `PASS` / `PARTIAL` / `FAIL` | solo PASS chiude chiavi |
| `source` | lista | da dove viene il lavoro (sintesi, piano, note del proprietario) |
| `wave` | `wNN` o `none` | ondata di origine |
| `closes` | lista di chiavi | → `risolto` |
| `verify` | lista di chiavi | → `da_verificare` (serve la prova con persone vere) |
| `todo` | lista di parole | ognuna trova **una** riga aperta di `launch/TODO.md` |
| `decisions` | lista `D-NNN` | decisioni applicate o rispettate |
| `files` | lista | file creati o cambiati (`(removed)` se tolti) |
| `screenshots` | lista | foto guardate, mai in `Temp/` o `Library/`; con PASS almeno una o `none: <perché non si vede>` |
| `risks` | lista, mai vuota | **rischi di gameplay introdotti**: cosa può peggiorare, per chi |
| `owner_try` | lista, mai vuota | azioni concrete da provare, una riga ciascuna |
| `design_changes` | lista | `cosa | perché | decided_by: implementer` o `decided_by: owner (<fonte>)` |
| `saves` | testo | `backup + restore identical` o `not touched` |
| `build` | testo | `none` salvo richiesta del proprietario |
| `tests` | testo | facoltativo: suite lanciate o `not run (<motivo / D-NNN>)` |

Il corpo resta libero (sezioni per punto, misure prima/dopo, file, dubbi) ma deve avere **`## Per il proprietario`** nella sua lingua, in parole semplici: cosa è cambiato e cosa provare. I gate vecchi senza header restano validi e non si riscrivono.

## 8. Il giro di regressione (un fix può creare un problema nuovo)

1. Ogni gate elenca in `risks` cosa può aver peggiorato (es. "l'abbraccio ora blocca 2 s: più difficile").
2. Il brief dell'ondata dopo ha una sezione **"Da ricontrollare"** con quei rischi (da `changes-since-wNN.md`); i tester li commentano apposta.
3. Un problema nuovo nato da un gate entra nel JSON dell'ondata con una **chiave nuova** e `"from_gate_dev": NN`; nella sintesi "nato col gate NN". Se invece torna un problema già `risolto`, la stessa chiave torna `aperto` con "ricomparso dopo il gate NN".
4. Nel piano dei gate successivo le regressioni vengono **prima** del resto.

## 9. Vocabolario comune per mappa, schermate e run

Le due skill scrivono questi file nello stesso formato, così `design_review.py` legge sia `docs/design-review/*` sia `launch/fg/waves/wNN-*`:
- **Schermate:** tabella (schermata e file · come ci arrivi · quando · il gioco te lo dice? · voto **evidente / trovabile / nascosta**) **più** un blocco ` ```screens ` con `root:`, `screen: Nome | file | hidden-ok: motivo` e righe `A -> B : come`.
- **Run a tempi:** un titolo `## ` per run, righe di tabella che iniziano con il tempo dall'inizio della run (`m:ss` o `m:ss-m:ss`), e i segni `[MORTO]` `[TOP]` `[FRUSTRA]` `[ABBANDONO]` `[CONFUSO]` `[TROPPA-UI:n]` `[SPIRALE]`.
- **Etichette:** **[FATTO]** letto nel codice o misurato · **[STIMA]** · **[OPINIONE]** · **[DA VERIFICARE]** · **SIMULATO** in testa a ogni file del panel.

## 10. Controllo di mercato precoce (offerto dal dev, non imposto)

Dopo il lock del GDD e prima del worker project (al più tardi prima della vertical slice), se la skill launch è installata il dev chiede una volta:
> "Vuoi un controllo rapido del concept contro giochi simili? `game-launch-strategist` in modalità **Mirata**: posizionamento + 5-10 comparabili reali + un panel simulato breve. ~30-60 min, scrive solo in `launch/`."
- Sì → si lancia la skill (Mirata: posizionamento, comparabili, focus group rapido) con `GDD.md`. Quello che cambierebbe il GDD si propone al proprietario; il GDD resta `locked` finché lui non accetta.
- No → `DECISIONI.md`: `controllo di mercato precoce: no`. Non si ripropone.

## 11. Liste di controllo

**Dev, a ogni gate:** header valido (`check` ✅) · meccanica vera provata nel gioco normale · foto guardate · salvataggi ripristinati identici · `risks` e `owner_try` pieni · scelte cambiate in `design_changes` con `decided_by` · `apply-status --write` · `todo --run` · mappa/schermate aggiornate se toccate, nessun orfano · niente build né suite di test non chieste.

**Launch, a ogni ondata:** legge `changes-since-wNN.md` (o lo chiede: `gate_link.py since`) · `fixes` dal file · "Da ricontrollare" nel brief · chiavi stabili, nuove con `from_gate_dev` se nate da un gate · `P-wNN-n` e chiavi in sintesi e proposte · righe 🤖 della TODO con `P-wNN-n`, `key:` e, quando c'è, `ok del proprietario AAAA-MM-GG` · decisioni mai contate come problemi, riaperture solo etichettate · `STATUS.html` rigenerato.
