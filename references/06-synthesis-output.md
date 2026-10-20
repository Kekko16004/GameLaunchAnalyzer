# Fasi 10B e 11 e output finale: gioco completo, sintesi, report, TODO, stato, debriefing, controllo qualità

---

## FASE 10B: gioco completo (solo se il prodotto analizzato è una beta, demo o vertical slice)

Si esegue **dopo** l'analisi completa fatta con il metro "beta" (Fasi 3-10) e dopo le domande sul gioco completo (Round R-D in `00-intervista.md`). Non sostituisce nulla: il verdetto sulla beta resta com'è.

**Ingressi**: TODO, GDD, roadmap o elenco di contenuti del gioco completo (se l'utente non li ha, chiedi una pagina di piano: contenuti, durata, feature, data di uscita sperata), più le risposte del Round R-D. Se non esiste alcun piano, la Fase 10B si riduce a "cosa serve scrivere" e lo dici.

**Analisi rapida** (una pagina, niente nuove ondate del focus group):
1. **Tabella dei gap**: `Pilastro | Beta oggi | Gioco completo pianificato | Gap | Azione (ore)`. I pilastri sono quelli della Fase 3; il gap è ciò che manca per portare ogni pilastro a PASS *nel prodotto che si venderà*.
2. **Scope contro capacità**: ore del piano completo (dalle TODO) contro ore settimanali del team fino alla data di uscita. Se non ci stanno, proponi i tagli e il rinvio.
3. **Durata e prezzo**: la durata prevista regge il prezzo che emerge da `calc_econ.py` e dai comparabili? (Il prezzo della beta, se c'è, non è quello del gioco completo.)
4. **Rischio recensioni**: i temi negativi ricorrenti del genere (`review_corpus.py`, `genre_bench.py`) applicati al piano: quali il piano previene, quali no, quali la beta nasconde (ripetitività, fine contenuti, bilanciamento a lungo termine).
5. **Spinta all'acquisto** (se la beta è gratuita, e lo è spesso): la beta invoglia a spendere all'uscita? Metti la percentuale `would_buy` dell'ultima ondata, il pilastro "Spinta all'acquisto" (Fase 3), il punto di conversione (fine beta, invito alla wishlist) e due o tre leve concrete per aumentarla: un finale che lascia voglia di continuare, il momento migliore mostrato per ultimo, una promessa chiara di ciò che arriva, wishlist al picco di entusiasmo, un vantaggio per chi ha giocato la beta. Dichiara cosa **non** regalare.
6. **Cosa migliorare adesso**: da 3 a 5 azioni ordinate per impatto, divise tra "migliora la beta (serve ai test e alla wishlist)" e "prepara il gioco completo (serve all'uscita)".
7. **Verdetto sul gioco completo**: sempre **provvisorio** (si basa su un piano, non su una build). Una riga, con ciò che lo renderebbe definitivo.

Output: **`launch/01c-full-game.md`**, e in `status.json` il campo `full_game` (vedi sotto). Se l'utente ha già il gioco completo, la Fase 10B si salta.

---

## FASE 11: sintesi "Success Maximizer"

Costruisci in `REPORT.md` la sezione che massimizza davvero le probabilità di successo:

1. **Le 5 leve a più alto impatto**, ordinate per punteggio **ICE** (Impatto, Confidenza, Facilità, da 1 a 10; ICE = media, mostra il calcolo), ciascuna con ore, scadenza e metrica. Alimentate da matrice di convergenza, posizionamento e pre-mortem.
2. **Le 3 cose da NON fare ora** (es. spendere in ads prima del gate, lanciare una pagina Steam acerba, aggiungere contenuto prima di sistemare l'apertura).
3. **Criteri di stop e di pivot**: a quali risultati misurabili (gate falliti due volte, tripwire scattati, wishlist sotto soglia a data X) conviene ridimensionare, cambiare genere o spostare l'obiettivo (da vendite a portfolio). Senza drammi: è gestione del rischio.
4. **Scenario migliore realistico**: cosa deve accadere, in ordine, perché il gioco superi le attese, e quali di quegli eventi dipendono dal team.
5. **Verifica di capacità**: confronta le ore totali delle TODO con le ore settimanali del team nel periodo fino al lancio. Se il piano supera la capacità, taglia e dillo.

---

## File prodotti (modalità Completa)

In `launch/`:

- `00-contesto.md` (Context Pack della Fase B), `00-brief.md`, `01-dev.md`, `01b-positioning.md`, `01c-full-game.md` (solo se beta con piano del gioco completo), `02-platform.md`, `03-pricing.md`, `04-clips.md`, `04b-store-copy.md`
- `05-focusgroup.md`, `05a-critiche-simulate.md`, `05b-critiche-reali.md`, `05c-premortem.md`
- `06-creators.md`, `07-community.md`, `08-brand-legal.md`
- `fg/roster.md`, `fg/roster.json` (tester con ID stabili e giuria), `fg/waves/` (una serie di file per ondata: **preparazione** `wNN-brief.md`, `wNN-mappa-gioco.md`, `wNN-schermate.md`, `wNN-runs.md`, `wNN-mercato.md`, `wNN-proposte-gameplay.md`, `wNN-limite-beta.md` se c'è una demo o beta gratuita, controllati con `wave_kit.py check`; poi evidenze, gruppi A e B, dati JSON, dibattito, metriche, report, delta, `wNN-sintesi.md` per il proprietario; dettagli in `04-focus-group.md` 7.1, Passo 0), `fg/timeline.md`, `fg/timeline.csv`
- **`fg/waves/wNN-sintesi.md`** (per il proprietario e per game-developer, `dev-link.md` §5.1): ogni riga di problemi e proposte ha la colonna **Chiave** (la chiave stabile di `issue_status.json`) e, se c'è una proposta, l'ID **`P-wNN-n`** (lo stesso di `wNN-proposte-gameplay.md`, numerato da 1, non cambia più); una sezione "Nati da un gate di sviluppo o ricomparsi" ("nato col gate NN" / "ricomparso dopo il gate NN"); le riaperture a parte, una riga ciascuna: `Riapre la decisione: <D-NNN o testo> — prove: <dati veri, con fonte> — proposta: <cosa> — costo: <ore>`. Il modello lo scrive `wave_kit.py init`.
- **Il punteggio nella sintesi** (`04-focus-group.md` 7.0b-7.0e): sempre **grezzo e normalizzato sulle ancore** accanto all'ondata prima, la tabella delle ancore (giochi veri, fascia dal mercato, scarto) e, se le ancore derivano, l'avviso in grande con cosa si è fatto (rigiudicata o no); il **voto della rubrica pesata per genere** con i pesi e la loro fonte; se l'ondata ha un **tema**, scritto in testa e ricordato nel confronto con le ondate generali. La sintesi copre **tutto il gioco** (cosa è cambiato dall'ultima ondata, tutte le aree della rubrica), poi il tema.
- `comps.csv`, `sources.md`, `creators.csv`, `window.csv`, `window.md`, `calendar.md` (con i passi 👤/🤖), `03-pricing-calc.md`, `00-intenzioni.md`, `05d-contingenze.md`, `store_kit.json`, `store_kit.md`, `store_kit/`, `wishlists.csv`, `wishlist-status.md`, `metrics.csv`, `metrics-status.md`, `watchlist.csv`, `watchlist-report.md`, `status.json`, `STATUS.html`, `REPORT.html`, `charts/` (grafici `.svg`)
- `_raw/`: dati grezzi degli script (`comps.json`, `corpus.json`/`corpus.md`, `store_pages.json`/`store_bench.md`, `hooks/`, `econ.json`, `wl_plan.json`, `window.json`, `project_scan.json`, `contingencies.json`, `genre_bench.json`, `my_features.json`, `reviews_*.json`, `yt_*.json`, `social_verified.json`, `reddit_rules.md`, `curation.json`, `topics.json`)
- `playbook-usato.md` (solo se ad hoc), `ricerche-manuali.md` (solo se serve), `history/` (in Aggiornamento)
- `REPORT.md`, `TODO.md`, `STATUS.md`

Le modalità Rapida e Mirata producono solo i file delle fasi eseguite, più `REPORT.md`, `TODO.md`, `STATUS.md`.

---

## `STATUS.md` (aggiornalo dopo ogni fase)

```markdown
# STATUS
Aggiornato: AAAA-MM-GG HH:MM | Modalità: Completa | Build/commit analizzato: <id>

| Fase | Stato (fatta / parziale / da fare) | File | Confidenza (bassa/media/alta) | Note |
|---|---|---|---|---|

## Ondate del focus group
| Ondata | Data | Build | Punteggio | Stato (fatta / proposta, in attesa di ok) |
|---|---|---|---|---|

## Ipotesi aperte
- <ipotesi usata al posto di un dato mancante>

## Dati non raggiunti / ricerche manuali
- <cosa, perché, dove è scritto come completarlo>

## Prossimo passo
<la prima cosa da fare alla ripresa>
```

Alla ripresa ("continua") leggi `STATUS.md` e riparti dalla prima fase non completata, senza riscrivere i file già fatti.

## `status.json` e pagina di stato (`STATUS.html`)

`status.json` è il riepilogo strutturato che alimenta la pagina per soci o publisher. Scrivilo (o aggiornalo) a fine Fase 11 e dopo ogni ondata; il resto della pagina arriva dai file già prodotti (timeline, wishlist, piano economico, calendario, TODO, documenti).

```json
{
  "game": "Nome del gioco", "updated": "AAAA-MM-GG", "mode": "Completa",
  "verdict": {"color": "verde|giallo|rosso", "provisional": false,
              "summary": "2-3 frasi, le stesse del verdetto esecutivo", "probability": "intervallo",
              "risks": ["rischio 1", {"text": "rischio 2", "issues": ["chiave-criticità"]}, "rischio 3"]},
  "gates": {"0": {"state": "pass|fail|pending", "note": "..."}, "A": {}, "B": {}, "C": {}},
  "key_numbers": [{"label": "Comparabili analizzati", "value": "18", "note": "con dati verificati"}],
  "intentions": {"summary": "obiettivo, capacità, budget, canali, regole di stop in 2-3 frasi",
                 "decisions": [{"topic": "Budget", "choice": "solo Steam Direct", "why": "nessuna ads prima dei gate"}]},
  "product": {"kind": "beta|demo|vertical_slice|full|post_launch", "label": "Beta (Atto I)", "has_full_plan": true},
  "full_game": {"summary": "verdetto provvisorio sul gioco completo in 1-2 frasi",
                "gaps": [{"area": "Contenuto", "today": "1 biome", "target": "4 biomi", "action": "3 biomi nuovi", "hours": 120}]},
  "issue_aliases": {"run-variety": ["run ripetitive", "poca variet"], "tray-feel": ["vassoio"]},
  "roadmap": {"note": "una riga sul piano (es. beta gratuita = demo di 30-60 min)",
              "milestones": [{"date": "AAAA-MM-GG", "end": "AAAA-MM-GG", "title": "Pagina Coming Soon su Steam", "phase": "Pagina",
                              "what": "cosa succede, una riga", "needs": "cosa serve, una riga", "state": "done|next|later",
                              "step": 23, "approx": true}]}
}
```
`issue_aliases` (facoltativo, espressioni regolari senza distinzione di maiuscole) collega a una chiave di criticità i testi che la nominano con altre parole: i rischi del verdetto e le righe delle tabelle nei documenti (per esempio la matrice di convergenza di `05-focusgroup.md`). Così accanto a quel testo compare la decisione del proprietario. Un rischio può anche dire le sue chiavi direttamente (`{"text": …, "issues": [...]}`).
`product` va scritto sempre (la pagina lo mostra in testa: "valutato come: Beta"); `full_game` solo se la Fase 10B è stata eseguita.
`roadmap` è un'uscita **standard**: solo le tappe chiave vere (di solito test con amici o chiuso, Steam Direct pagato, pagina Coming Soon, beta gratuita su itch, demo pubblica su Steam, Steam Next Fest, Early Access, 1.0), prese da `calendar.md`, `00-intenzioni.md` e dalle decisioni del proprietario. Campi facoltativi: `end` (tappa che dura più giorni), `phase`, `state` (altrimenti si calcola da data e passi), `step` (numero del passo in `calendar.md`, per il link ai dettagli), `approx` (data stimata). **Claude la aggiorna dopo ogni decisione.** Se manca, `status_page.py` ricava le tappe da `calendar.md` per parole chiave (al meglio).

**Com'è fatta la pagina.** Larga fino a 1400 px (e leggibile a 390 px), divisa in **schede** fisse in alto; la pagina ricorda l'ultima scheda aperta. In cima a Riepilogo e Calendario c'è la **roadmap** (tappe chiave su una linea del tempo); il riquadro in testa dice anche **cosa manca per passare al livello successivo**:
| Scheda | Contenuto |
|---|---|
| **Riepilogo** | roadmap, verdetto con i rischi (ognuno con la decisione del proprietario) e i cancelli, riquadro "Adesso" (tocca a te / tocca a Claude), numeri chiave (punteggio beta e gioco completo separati, tetto e margine), alert, andamento di wishlist e ondate, profilo decisionale, **probabilità oneste decisione per decisione** (`honest_odds.py`: copie, publisher, Next Fest, social, simulato contro reale, ognuna con base, etichetta, cosa la sposta e il **controllo incrociato** quando due fonti non concordano) |
| **Gioco e test** | pilastri per nome (esito, perché in una riga, cosa fare, ore solo se l'audit le stima in modo credibile), criticità ondata per ondata, grafici del focus group, ondate (beta e gioco completo ben distinte, con tetto e margine), recensioni reali con "il tuo gioco ne soffre? / ce l'hai?", beta contro gioco completo, documenti di questa parte (audit, focus group, critiche) |
| **Marketing e store** | pagine Steam e itch da copiare, **social** (prossimi post con i ganci A/B, cosa rende per noi, tendenze di Reddit), creator, documenti (posizionamento, clip, testi dello store, creator, community) |
| **Piano e soldi** | passi in ordine, **TODO viva**, cancelli, date fisse, economia, piani se… allora, finestra di lancio, concorrenti, **publisher** (risposta sì / no / non so, lista per fasce, con o senza publisher), SteamDB, mercato e comparabili, documenti (piattaforme, prezzo, pre-mortem, contingenze) |
| **Calendario** | roadmap e griglie dei mesi da oggi all'uscita con ogni cosa datata (passi e tabelle di `calendar.md`, scadenze di `TODO.md`, eventi Steam, showcase online, ondate, gate, tripwire), colorata per chi la fa (👤 / 🤖 / insieme), ritardi in evidenza, clic sul giorno per i dettagli, agenda dei prossimi 14 giorni |
| **Mercato reale** | tutto il mercato vero: base rate, metro oggettivo, comparabili, mosse |
| **Documenti** | report completo, intenzioni, brief, legale e fiscale, domande e risposte, glossario |
Genera la pagina:

```bash
python3 <skill>/scripts/research/status_page.py --launch-dir launch --audience private     # predefinito: private | partner | publisher
```
È un unico file HTML autonomo (nessuna richiesta di rete, tema chiaro e scuro, utilizzabile da telefono, grafici con vista tabella messi nella scheda a cui appartengono, filtrati per pubblico). **Non pubblicarla né inviarla**: dì all'utente dov'è il file e offri la pubblicazione in una riga (es. come artifact privato, se l'ambiente lo permette), e **genera `private`, senza chiedere il pubblico** (è il default: tutto, per il proprietario). Chiedi per chi è solo se l'utente dice che la pagina andrà ad altri: `publisher` esclude economia interna, TODO e pre-mortem, `partner` li include, `private` aggiunge creator, community e fiscale. Controlla che nessun dato personale o riservato finisca nei documenti inclusi.

## Grafici nel report (`REPORT.html` e `charts/`)

Il report si guarda, non solo si legge. Dopo aver scritto `REPORT.md` e aggiornato `status.json`:

```bash
python3 <skill>/scripts/research/report_html.py --launch-dir launch            # launch/REPORT.html: testo + grafici accanto a ogni sezione
python3 <skill>/scripts/research/charts_export.py --launch-dir launch          # launch/charts/*.svg + index.md, per incorporarli nei Markdown
```
I grafici nascono dai file già prodotti (`01-dev.md`, `fg/timeline.csv`, `_raw/genre_bench.json`, `corpus.json`, `econ.json`, `window.json`, `calendar.md`, `creators.csv`, `comps.csv`, `store_pages.json`, `status.json`); quello che manca non viene disegnato. Per avere più grafici, produci quei file con gli script. Nel `REPORT.md` incorpora gli `.svg` più utili dove servono (`![Pilastri](charts/product-1.svg)`) e scrivi sotto una riga di lettura. Regole: una sola scala per grafico, legenda sempre con due o più serie, il numero resta in tabella, nessun grafico con due punti dati. Dì all'utente dove sono `REPORT.html` e `charts/`; sono file locali.

## Criticità ordinate e domande e risposte (STATUS.html)

**Criticità, ondata per ondata.** La sezione si ricostruisce da sola dai file delle ondate (`fg/waves/wNN-*.json`) a ogni rigenerazione: **dopo ogni ondata rilancia `status_page.py`** (e `report_html.py`). Un'ondata beta si confronta solo con la beta precedente, una "gioco completo" solo con la "gioco completo" precedente (il tipo viene da `"stage"`, o dal nome del file `-beta` / `-full`, o dall'etichetta). Si apre sull'ultima ondata beta. Ha un bottone per ogni ondata, uno **Per cancello** (a quale Gate 0/A/B/C appartiene ogni criticità, in quale ondata è nata e se è aperta o risolta) e uno **Evoluzione** (tabella criticità × ondata con andamento e grafico: già presenti, nuove, risolte). Ogni riga ha gravità, quota di tester, variazione rispetto all'ondata prima, stato, cancello e cosa fare; sotto, le criticità **risolte in quell'ondata** con la correzione. Per questo ogni problema nel file dell'ondata porta `gate` e `area`.
- **Altre fonti** (test reale del Gate B, recensioni reali, pre-mortem, consigli): `criticita.py add --key … --label … --severity alta --source playtest --gate B --opened AAAA-MM-GG` (e `criticita.py close <chiave>` quando è risolta); finiscono nell'ondata del loro periodo e nella vista per cancello.
- Il formato a mano in `status.json` → `critiques_by_wave` (`wave`, `score`, `note`, `items` con `issue`, `severity`, `seen_by`, `status`, `action`, `gate`) resta valido per le ondate che non hanno un file.

### Pagine store vive (`store_kit.json`)

Dopo ogni decisione del proprietario, gate o ondata che cambia cosa il gioco è o promette (Early Access, roadmap, accessibilità, lingue, prezzo), Claude aggiorna `store_kit.json` (`"updated"`), rilancia `store_kit.py check / render / export` e rigenera `STATUS.html`, che mostra "Pagine store aggiornate al <data>" o "da aggiornare" (dettagli in `03-store-clips.md`).

### Stato vivo: `launch/issue_status.json` (le decisioni del proprietario)

I problemi segnalati all'inizio non restano fermi: cambiano a ogni ondata **e a ogni decisione del proprietario**. Le decisioni stanno in `launch/issue_status.json`, una voce per chiave di criticità (le stesse chiavi dei file delle ondate):
```json
{
 "_note": "Decisioni del proprietario sulle criticità (aggiornato AAAA-MM-GG)",
 "run-variety": {"status": "pianificato", "note": "Beta = 1 mappa; 3-4 mappe nel gioco completo.", "aliases": ["run ripetitive"]},
 "tray-feel":   {"status": "da_verificare", "note": "Si giudica solo giocando: test con persone vere."},
 "perf-unknown": {"status": "risolto", "note": "Misurate: ~220 FPS su GTX 1660 Super."}
}
```
| `status` | Vuol dire | Dove finisce |
|---|---|---|
| `aperto` | da affrontare, nessuna decisione | **Da fare adesso** |
| `in_lavorazione` | ci si sta lavorando (dire in quale gate) | **Da fare adesso** |
| `da_verificare` | deciso a parole, va confermato (test reale, misura) | **Da fare adesso** |
| `risolto` | sistemato (dire come o in quale gate) | Già deciso |
| `pianificato` | si farà più avanti (dire quando: beta finita, gioco completo…) | Già deciso |
| `accettato` | si tiene così, per scelta | Già deciso |
| `non_problema` | il proprietario non lo considera un problema | Già deciso |
**Campi del gate di sviluppo (con `game-developer`, `dev-link.md` §6.3).** Dopo un gate il dev lancia `gate_link.py apply-status --write`, che è l'unico modo in cui scrive in questo file: chiavi chiuse → `"status": "risolto"`, chiavi da confermare → `"da_verificare"`, e a tutte e due aggiunge
```json
 "ui-chaos": {"status": "risolto", "note": "Gate 57 (2026-10-19): Scheda Stasera. · nota di prima", "gate": "docs/gates/57-stasera.md", "resolved": "2026-10-19"}
```
- `gate`: percorso del gate di sviluppo che ha toccato la chiave (è un gate di **sviluppo**, non il cancello 0/A/B/C, che sta nel JSON dell'ondata come `issues[].gate`);
- `resolved`: data del gate che l'ha chiusa (solo con `risolto`).
**Il launch non sovrascrive e non cancella mai `gate` e `resolved`**: quando aggiorna una chiave cambia solo `status`, `note`, `aliases`, e i campi del dev restano anche se la chiave torna `aperto` (sono la storia). Non tocca le chiavi nuove create dal dev (non ne crea: le chiavi le crea il launch con l'ondata) né le decisioni del proprietario.
- **Approvata** (`dev-link.md` §5.2): la chiave passa a `in_lavorazione` con `todo_track.py approve` (sotto, `TODO.md`), nota "Approvata dal proprietario il DATA (P-wNN-n)."
- **Ricomparsa** (`dev-link.md` §8): una chiave `risolto` che i tester citano di nuovo torna `aperto`, nota in testa "Ricomparso dopo il gate NN (ondata wNN)." (NN = il gate scritto in `gate`); `gate` e `resolved` restano. Nella sintesi: "ricomparso dopo il gate NN".
- **Nata da un gate**: un problema nuovo causato da un gate entra come chiave **nuova** (`aperto`), con `"from_gate_dev": NN` nel JSON dell'ondata; nota "Nato col gate NN."; nella sintesi "nato col gate NN" (anche `STATUS.html` lo mostra).
- **`fixes` del JSON dell'ondata**: si riempiono dal blocco `fixes` di `docs/design-review/changes-since-wNN.md` **così com'è** (`issue`, `what`), con `gate_dev` (numero del gate di sviluppo, preso dalla tabella dello stesso file) o, da `gate_link.py since --json`, anche `status` (`risolto` / `da_verificare`): `wave_kit.py fixes --launch-dir launch --wave N --write <json>` aggiunge quelli che mancano e non toglie né cambia quelli scritti a mano. `fg_waves.py` li valida e `STATUS.html` mostra "gate di sviluppo NN" accanto alla correzione.

Una criticità che i tester segnalano e che **non è nel file** compare come **"Da decidere"** e resta tra le cose da fare adesso. Ovunque compaiano criticità (ondata per ondata, per cancello, evoluzione, grafico "Critiche da affrontare adesso", ondate del focus group, rischi del verdetto, righe della matrice di convergenza e delle altre tabelle dei documenti, temi delle recensioni reali) la pagina mostra la decisione come etichetta con icona e nota, e separa **Da fare adesso** da **Già deciso** (chiuso, si apre con un clic). Le domande e risposte ("criticità aperte più gravi") seguono le stesse decisioni.

**Regola: Claude aggiorna `issue_status.json` subito dopo ogni decisione del proprietario** (anche detta in chat: "questo va bene così", "lo facciamo nel completo", "fatto nel gate 48") **e dopo ogni ondata** (le chiavi nuove entrano come `aperto` o con la decisione proposta e confermata; quelle sparite e sistemate passano a `risolto` con il gate). Poi rigenera `STATUS.html`. Non cambiare mai una decisione del proprietario senza dirglielo: se i dati la contraddicono (per esempio un `non_problema` che sale nell'ondata), riapri la domanda.

**Le recensioni reali** ("Di cosa si lamentano i giocatori", "Cosa piace ai giocatori") dicono per ogni tema se il TUO gioco ne soffre o ce l'ha: il giudizio viene dalla tabella di `05b-critiche-reali.md` (etichette **[SÌ]**, **[A RISCHIO]** con livello, **[NO]**, **[NON VALUTABILE]**, **[IN PARTE]** / **[PARZIALE]**, anche più d'una per riga: "[NO] per la beta… [A RISCHIO] per il gioco a pagamento"), e dalla quota di tester dell'ultima ondata beta e dell'ultima "gioco completo" che hanno sollevato le criticità collegate (mappa tema → chiavi in `theme_labels.py`, `THEME_ISSUES`; per un progetto si aggiunge `launch/_raw/theme_issues.json`). **Dopo un fix importante ricontrolla quella tabella di `05b`**: è un giudizio con data, non si aggiorna da solo.

**Domande e risposte.** Tre gruppi con ricerca e filtro per argomento: **le tue domande** (con ondata e cancello a cui si riferiscono), **domande frequenti con le risposte di oggi** (si ricalcolano dai dati: perché il verdetto, cosa fare adesso, cosa è cambiato, criticità più gravi, posso pagare Steam, quando uscire, quante copie servono, a che punto sono le wishlist, cosa succede se va male…) e **domande che conviene farti adesso** (dedotte dallo stato del progetto). **Regola: ogni domanda sostanziale che l'utente ti fa mentre lavorate la salvi** con `qa.py add --q "…" --a "…" --topic Cancelli [--wave 2] [--gate B]` (la stessa domanda si aggiorna, non si duplica); lo stesso vale per `status.json` → `qa` (`custom: true` per le sue). Campo facoltativo `breakeven_basis: "cash"` in `status.json` per mostrare il break-even sui soli soldi spesi.
Per il pubblico `publisher` le due sezioni non compaiono (`--hide critiques,qa` per toglierle agli altri).

## Spiegazioni semplici e collegamenti (Markdown e HTML)

Chi legge i report può non conoscere i termini (wishlist, gate, ICE, tripwire, break-even, percentile, hook, capsule…) né sapere dove sta ogni cosa. Dopo aver scritto i file:

```bash
python3 <skill>/scripts/research/md_enrich.py --launch-dir launch     # link tra i .md + glossario in fondo a REPORT.md (si può rilanciare)
```
- **Nei Markdown**: la prima menzione di creator, community, calendario, pagine Steam e itch, prezzo e piano economico, focus group, critiche, pre-mortem, contingenze, posizionamento, audit, gioco completo, finestra di lancio, legale, testi dello store, hook e clip, TODO diventa un link al file giusto; un nome di file tra apici (`calendar.md`) diventa un link; `REPORT.md` chiude con un glossario dei soli termini usati.
- **Nelle pagine HTML** (`STATUS.html`, `REPORT.html`) lo fa già `glossary.py`: ogni termine tecnico ha una spiegazione che compare al passaggio del mouse, al tocco o con la tastiera; la menzione di una cosa che ha una sua sezione porta a quella sezione (mai alla sezione in cui sei già); in fondo c'è il glossario con le sole parole usate.
- **Scrivendo**: la prima volta che un termine tecnico compare nel testo, spiegalo in mezza riga con parole semplici. Niente gergo senza spiegazione, niente sigle senza dire cosa sono.

## Routine settimanale (dopo l'apertura della pagina Steam, e durante la beta su itch.io)

L'utente porta i numeri, tu fai il resto. Una volta a settimana:

1. **Numeri dell'utente**: totale wishlist da Steamworks (`wl_track.py add`) e le altre metriche (`metrics_track.py add --metric itch_views --value N`: visite e scarichi itch, iscritti Discord, giocatori e durata della demo, ecc.; `metrics_track.py catalog` elenca i nomi).
2. **Controlli**: `wl_track.py status`, `metrics_track.py status`, `watchlist.py snap` seguito da `watchlist.py report --launch <data>`. Un codice di uscita 2 è un ALLARME: riportalo subito con l'azione di emergenza prevista, senza minimizzare; gli altri alert in una riga ciascuno.
3. **Passi**: `plan_steps.py next --owner me` per dire cosa tocca all'utente adesso (e quali sono in ritardo), `plan_steps.py done N` per spuntare ciò che è fatto.
4. Se è cambiato qualcosa di rilevante, rigenera `status_page.py` e ricorda se un'ondata del focus group è in attesa dell'ok.

## `ricerche-manuali.md`

Per ogni ricerca che non hai potuto fare: obiettivo, query o URL suggeriti, a cosa serve il dato, in quale file va a finire e quale cifra resta **[DA VERIFICARE]** finché manca.

---

## `REPORT.md` (struttura rigida)

1. **Verdetto esecutivo (max 15 righe)**: semaforo verde/giallo/rosso secondo i criteri in `SKILL.md`, probabilità stimata di recuperare i costi (intervallo), 3 rischi killer. Se il posizionamento non è PASS il verdetto non può essere verde.
2. **Genere, playbook, fase e confidenza per sezione.** Dichiara qui il **tipo di prodotto valutato** (beta, demo, completo…) e il metro usato. In testa al report: il **profilo decisionale** (da `00-intenzioni.md`): cosa vuole il proprietario e quali decisioni guidano il piano.
3. **Posizionamento e differenziazione**: pitch, 3 differenziatori, esito del test contro i comparabili.
4. **Audit dev e pilastri di genere.**
5. **Critiche e ondate**: top critiche simulate (A) dell'ultima ondata, temi reali del genere (B), matrice di convergenza, 3 dealbreaker, metriche del panel con calibrazione dichiarata e **timeline delle ondate** (`fg/timeline.md`) se ce n'è più d'una.
6. **Pre-mortem**: le 5 cause e la tabella dei tripwire.
7. **Mercato, comparabili e prezzo**: scenari con "cosa deve essere vero".
8. **Capsule, hook, testi dello store e trailer**, con la **scheda copiabile delle pagine Steam e itch.io** (`store_kit.md`): ogni campo, la descrizione lunga con le posizioni di foto e GIF, tag in ordine, screenshot, capsule, impostazioni e checklist.
9. **Piano piattaforme, Next Fest e gate** con date, e il **calendario a passi** (`calendar.md`): fasi, chi fa cosa (👤/🤖), scadenze, prossimi 5 passi per l'utente.
10. **Creator e community**, kit del test reale. Includi un riepilogo di `creators.csv` (numero totale, tabella dei creator di priorità A con piattaforma, lingua e perché, e il rimando al file completo; la tabella intera è collassabile in `STATUS.html`).
11. **Beta oggi e gioco completo** (solo se il prodotto è una beta con un piano del gioco completo): sintesi della Fase 10B, tabella dei gap, scope contro capacità, "cosa migliorare adesso" e verdetto provvisorio sul gioco completo.
12. **Success Maximizer**: 5 leve, 3 "non fare", criteri di stop e pivot, verifica di capacità. Seguito da **"Se… allora"**: la matrice dei piani di contingenza (`05d-contingenze.md`) con segnali, soglie, diagnosi, azioni e decisioni per ogni scenario (itch, Steam, demo, Next Fest, lancio, esterni, persone).
13. **Legale e fiscale**: cose da fare prima di incassare.
14. **Fonti verificate** con data di consultazione.

## `TODO.md` (viva: si aggiorna dopo ogni cancello, ondata e decisione)

Formato di ogni voce (separatore ` — ` oppure ` | `):

```
- [ ] 👤 **Azione concreta** — Scadenza (AAAA-MM-GG) — Ore stimate — Dipendenze — Metrica di successo
```
In testa una riga `Aggiornato: AAAA-MM-GG`. 👤 = la fa il proprietario, 🤖 = Claude, 👤+🤖 = insieme.

**Regola: la TODO non deve mai restare indietro.** Dopo ogni gate chiuso, ogni ondata e ogni decisione del proprietario, Claude spunta ciò che è fatto e aggiunge ciò che è nuovo **con lo script**, non a mano:
```bash
python3 <skill>/scripts/research/todo_track.py --file launch/TODO.md stats                      # aperte / fatte per sezione, in ritardo
python3 <skill>/scripts/research/todo_track.py --file launch/TODO.md done "perk iniziale" --by claude --note "gate 39"
python3 <skill>/scripts/research/todo_track.py --file launch/TODO.md done "#12"                  # per numero, come in `list`
python3 <skill>/scripts/research/todo_track.py --file launch/TODO.md add --section "Dev e pilastri" --text "🤖 **Fix X** — 2026-10-20 — 2 h — nessuna — 0 errori"
python3 <skill>/scripts/research/todo_track.py --file launch/TODO.md reopen "perk iniziale"
python3 <skill>/scripts/research/todo_track.py --file launch/TODO.md drop "clip settimanali" --why "decisione: clip a beta finita"   # superata da una decisione: [-], resta scritta ma non si conta
```
`done` cambia `[ ]` in `[x]`, aggiunge "· fatto il DATA (da 🤖, nota)" e aggiorna `Aggiornato:`; se le parole trovano più righe non tocca nulla e mostra i candidati. `STATUS.html` (scheda Piano e soldi) mostra la TODO viva: avanzamento, aperte e fatte per sezione (le fatte chiuse), in ritardo, e un avviso **"Da aggiornare"** quando `TODO.md` è più vecchio dell'ultima ondata, di `issue_status.json` o del calendario.

**Righe di lavoro sul gioco (con `game-developer`, `dev-link.md` §5.1).** Ogni riga 🤖 che chiede una modifica al gioco porta nel testo l'ID della proposta e le chiavi, e le Dipendenze dicono se il proprietario l'ha approvata:
```
- [ ] 🤖 **Scheda Stasera unica** (P-w10-1, key:new-too-much-ui,new-hidden-rules) — 2026-10-25 — 3-5 h — ok del proprietario 2026-10-19 — 0 avvisi nei primi 10 s
```
- `P-wNN-n` = l'ID della proposta in `wNN-proposte-gameplay.md` e nella sintesi; `key:<chiave>[,<chiave>]` = le chiavi di `issue_status.json`. Il gate del dev le cita (`todo: ["P-w10-1"]`) e alla chiusura spunta la riga con `todo_track.py done "P-w10-1" --by claude --note "gate 58"`: l'ID deve trovare **una sola** riga aperta, quindi nelle Dipendenze delle altre righe non scrivere l'ID esatto di un'altra proposta ("dopo la scheda Stasera", non "dopo P-w10-1").
- Quando il proprietario dice sì (in chat, con la data): `todo_track.py approve "P-w10-1" --date AAAA-MM-GG --status-file launch/issue_status.json` scrive `ok del proprietario AAAA-MM-GG` nelle Dipendenze (al posto di "nessuna", o dopo un ";") e porta le chiavi della riga a `in_lavorazione` (mai le decisioni del proprietario, mai le chiavi già `risolto`, mai i campi `gate` / `resolved`). Una proposta non approvata resta senza `ok del proprietario`: il dev non la trasforma in lavoro.
```bash
python3 <skill>/scripts/research/todo_track.py --file launch/TODO.md approve "P-w10-1" --date 2026-10-19 --status-file launch/issue_status.json
```

**Decisioni del dev (`DECISIONI.md`) nei registri del launch (`dev-link.md` §4.2).** All'avvio e prima di ogni brief: `todo_track.py sync-decisions --decisions DECISIONI.md --intents launch/00-intenzioni.md` mostra le righe `D-NNN` che mancano sia in "Decisioni prese" sia in `00-intenzioni.md`; con `--write` le aggiunge in fondo a "Decisioni prese" così: `- **Area:** decisione (fonte: DECISIONI.md D-NNN, AAAA-MM-GG)`. Non riporta indietro le righe che il dev aveva copiato dal launch (fonte `launch/…`). **`DECISIONI.md` non si scrive mai**: è del dev. Se una decisione del dev contraddice una del launch, vince la data più recente; senza data si chiede al proprietario una volta.

Raggruppate per area: **Dev e pilastri**, **Posizionamento e store**, **Marketing e hook**, **Creator e community**, **Burocrazia e release**, **Tripwire e misure**. In testa: **"I 3 dealbreaker da risolvere in 14-20 giorni"**. Le scadenze sono date assolute calcolate dalla data odierna. In fondo: totale ore per area e confronto con la capacità del team (Fase 11.5).

## Delta in modalità Aggiornamento (`history/AAAA-MM-GG-delta.md`)

Cosa è migliorato, cosa è peggiorato, quali TODO sono chiuse, quali verdetti cambiano, quali tripwire del pre-mortem sono scattati. Per il focus group rimanda a `fg/waves/wNN-delta.md` e `fg/timeline.md` (prodotti da `fg_waves.py`, vedi `04-focus-group.md` 7.5); non ricalcolare i numeri a mano.

---

## Debriefing esecutivo in chat (formato obbligatorio)

Una volta scritti i file, rispondi in chat con un debriefing diretto, numerico e calibrato, da lead producer. Niente saluti o convenevoli. Riempi con i dati reali, senza segnaposto vuoti. Se un dato non è verificabile scrivilo nella riga stessa con **[DA VERIFICARE]**.

```text
[N] persone simulate in due gruppi indipendenti, critiche reali dei comparabili e strategia di lancio completa. Parti da launch/REPORT.md e launch/TODO.md; il resto è nei file 00-08 e in fg/. Nessuna delle persone simulate ha giocato: hanno giudicato da documenti, codice, screenshot e capsule. Sono opinioni simulate, non dati di mercato. Le critiche reali vengono da fonti online verificate.

Intenzioni confermate: [obiettivo, capacità, budget e rischio, canali, regola di stop, in 3 righe]. Decisioni ancora aperte: [elenco o "nessuna"].

Genere e fase: [genere primario/secondario, confidenza, fase, playbook usato]. Prodotto valutato come: [beta / demo / completo, e con quale metro].

Posizionamento: [pitch in una frase]. Differenziatori: [3]. Test contro [comparabile più vicino]: [PASS / MARGINAL / FAIL, perché]. [Se non PASS: le proiezioni sotto sono condizionate].

[Solo per una beta con piano del gioco completo] Gioco completo (analisi rapida, verdetto provvisorio): [gap principali, ore contro capacità, 2-3 cose da migliorare adesso].

Verdetto onesto: [semaforo; oggi il gioco è / non è pronto per essere venduto, perché; gancio contro divertimento reale nei primi minuti].

- Persone simulate: [X]% wishlist subito, [Y]% aspetterebbe saldi/recensioni, [Z]% scorrerebbe oltre, [W]% comprerebbe e chiederebbe rimborso. Click al primo sguardo [A] su [N]. Pitch compreso da [B]%. Convergenza tra i due gruppi: [differenza in punti, cosa significa].
- Punteggio wishlist: [X] (soglia [S], motivata). Filtro, non previsione.
- Tetto e margine: tetto di questa versione [T] (solo correzioni possibili adesso) e margine [T-X] punti; tetto del gioco completo [F] (con i contenuti pianificati, non è margine di oggi); [stop alle idee nuove e test reali / problemi risolvibili da chiudere: ...].
- Critiche più votate (simulate): [top 3 con frequenza].
- Critiche reali del genere che colpiscono il gioco: [top 3, fonte e frequenza]. Confermate da entrambe: [temi]. Punti ciechi del panel: [temi].
- Problema N.1: [descrizione concreta con evidenza].
- Leva strategica del genere: [feature o fattore, impatto stimato].

Pre-mortem, se tra un anno è un flop, le cause più probabili sono: [1-2-3 con segnale d'allarme e data di misura].

I 3 problemi da risolvere entro [data]. Toccano il divertimento, quindi aspettano il tuo ok:
1. [problema: intervento, ore, impatto atteso]
2. [...]
3. [...]

Steam: [pagare o non pagare adesso, motivo]. Date e cancelli:
- [Data gate test]: [soglie specifiche del genere]
- [Data pagamento]: solo se i gate passano
- [Mese pagina pubblica]
- [Date Next Fest, deadline iscrizione e invio build, verificate il (data)]

Testi dello store: pronti in launch/04b-store-copy.md (descrizioni, tag, 3 varianti di capsule, script del trailer).

Prezzo e vendite: prezzo consigliato [X], sconto di lancio [Y]%. Scenario base con [Z] wishlist: [A-B] copie nell'anno 1; pessimistico [C-D]; ottimistico [E-F]. Probabilità di recuperare i costi: [intervallo].

Canali: [piattaforma principale per questo genere e perché]. [2 hook più forti]. In lista [X] creator verificati ([Y] su [piattaforma], [Z] nella lingua del team, oppure istruzioni per cercarli a mano). Community: [dove e con quali regole].

I tuoi prossimi 3 passi (👤, con data): [..]. I miei, con il tuo ok (🤖): [..]. Calendario completo in launch/calendar.md, pagine Steam e itch pronte da copiare in launch/store_kit.md.
Se va male: [i 3 scenari più probabili, ciascuno con segnale, soglia e prima azione]. Metriche da registrare ogni settimana: [elenco].

Le 5 leve in ordine: [una riga ciascuna].
Da non fare ora: [3 punti].
Criteri di stop o pivot: [soglie misurabili e date].

Prima di incassare: [accordo tra soci se serve], [commercialista e inquadramento], [verifiche fiscali Steam]. Rimasto da verificare: [elenco breve o "nulla"].
```

Se esiste più di un'ondata aggiungi dopo il verdetto una riga di delta (dal tool): punteggio wishlist prima → dopo sugli stessi tester, problemi risolti e peggiorati, fix più efficace, tripwire scattati. Se un'ondata è **in attesa dell'ok dell'utente**, dillo qui con la data proposta.

La **segnalazione problemi** a fine di ogni ondata ha un suo formato breve (`04-focus-group.md`, 7.4) e viene mandata subito, non aspetta il debriefing finale.

In **Rapida** e **Mirata** il debriefing si accorcia alle sole righe delle fasi eseguite.

---

## Controllo di qualità prima di consegnare

- [ ] Genere riconosciuto con confidenza dichiarata; pilastri, coorti, hook, creator e prezzo derivano dal playbook.
- [ ] **Fase B eseguita**: `00-contesto.md` con motore e versione, documenti letti con il loro nome come fonte, tabella degli strumenti (disponibile, usato per, se manca come collegarlo); niente "non posso vedere il gioco" senza aver controllato strumenti e disco; se un MCP del motore era collegato, le evidenze (schermate, log) vengono dalla build vera.
- [ ] La domanda "beta o gioco completo?" è stata fatta per prima e la risposta è in `00-brief.md`, `status.json` (`product`) e nel report; pilastri, focus group e verdetto usano il metro giusto.
- [ ] Se la beta è gratuita: pilastro "Spinta all'acquisto" votato, `would_buy` chiesto ai tester e riportato, punto di conversione e leve indicati.
- [ ] Se è una beta con piano del gioco completo: analisi completa come beta, poi domande sul gioco completo, poi `01c-full-game.md` (gap, capacità, durata/prezzo, rischio recensioni, cosa migliorare); il verdetto sulla beta non è mescolato con quello, provvisorio, sul gioco completo.
- [ ] La fase del progetto ha determinato la profondità dell'audit.
- [ ] Il posizionamento è stato valutato contro i comparabili, e un eventuale FAIL/MARGINAL ha cambiato verdetto, scenari e TODO n. 1.
- [ ] Critiche **simulate** e **reali** in due file separati; le reali hanno fonte e sono parafrasate; nessuna critica "reale" è inventata.
- [ ] Matrice di convergenza presente e i 3 dealbreaker ne derivano.
- [ ] Pre-mortem con 5 cause, segnale misurabile, soglia e data; almeno una contraddice il verdetto positivo.
- [ ] Testi dello store scritti (descrizioni, tag, 3 capsule, trailer) e ogni affermazione ha un'evidenza nel gioco.
- [ ] Roster con ID stabili e giuria fissa; ogni ondata ha la preparazione completa (`wave_kit.py check` tutto ✅: mappa del gioco, schermate, 3+ run a tempi, mercato, proposte con "Riapre la decisione", domande extra) e il suo file JSON validato da `fg_waves.py`; punteggi, delta e timeline vengono dal tool; metodo di indipendenza dei gruppi dichiarato.
- [ ] Ondata 1 eseguita prima delle fasi di piattaforma, prezzo e store e seguita dalla segnalazione problemi; nessuna ondata successiva lanciata senza l'ok dell'utente; evidenze delle ondate successive senza critiche né fix precedenti.
- [ ] Focus group calibrato (controlli o confronto col comparabile) e dichiarato non-dato-di-mercato; soglia del Gate A motivata.
- [ ] I benchmark di pagina store, trailer e genere vengono da `store_bench.py`, `review_corpus.py` o `genre_bench.py`, con n, tag e data, e il limite della coda alta dichiarato (altrimenti dichiarati di opinione); le cifre economiche vengono da `calc_econ.py` con aliquote dichiarate.
- [ ] Se esiste la pagina Steam: `wishlists.csv` e `wl_plan.json` esistono e `wl_track.py status` è stato eseguito; un ALLARME è stato riportato all'utente.
- [ ] L'intervista è stata fatta (round completati e registro in `00-intenzioni.md`), le decisioni guidano soglie, calendario e contingenze, e i round di verifica con i dati sono stati proposti.
- [ ] `calendar.md` ha ancore, piano a ritroso, **passi in ordine con proprietario 👤/🤖 e scadenze** (`plan_steps.py check` senza errori) e piano B.
- [ ] `store_kit.json` passa `store_kit.py check` per Steam e itch.io; ogni slot media dice cosa mostra; i limiti hanno la data di verifica.
- [ ] Pagine store aggiornate dopo l'ultima decisione, gate o ondata (`store_kit.py check` dice "aggiornate al…"); se c'è l'Early Access, le sei risposte del questionario sono compilate senza promesse; l'accessibilità elenca solo opzioni reali.
- [ ] `contingencies.json` passa `metrics_track.py check`; ogni soglia ha un'origine; le soglie rispecchiano le risposte del Round 6.
- [ ] `creators.csv` riepilogato nel report e incluso (collassabile) in `STATUS.html`.
- [ ] Termini tecnici spiegati la prima volta; `md_enrich.py` eseguito (link tra i documenti, glossario in `REPORT.md`) prima di generare `REPORT.html` e `STATUS.html`.
- [ ] Le criticità di ogni ondata portano `gate` e `area`; le altre fonti sono in `criticita.csv`; `STATUS.html` rigenerato dopo l'ultima ondata mostra ondata per ondata, per cancello ed evoluzione; le domande dell'utente sono salvate con `qa.py`.
- [ ] `REPORT.html` e `charts/` generati; ogni sezione con numeri ha il suo grafico; i grafici si leggono (una riga che dice cosa guardare) e la vista tabella c'è.
- [ ] Finestra di lancio valutata con `launch_window.py` (`window.csv` con fonte e data di lettura); se la settimana è affollata la scelta della data è stata riaperta con l'utente.
- [ ] `STATUS.html` generata per il pubblico scelto dall'utente e **non pubblicata** senza il suo ok.
- [ ] Ogni numero ha **[FATTO]**, **[STIMA]**, **[OPINIONE]** o **[DA VERIFICARE]**; nessun URL, email o creator inventato; ogni dato "da verificare sempre" ha data di consultazione.
- [ ] Cancelli con date assolute e soglie adattate al genere; TODO con azione, scadenza, ore, dipendenze, metrica; ore totali entro la capacità del team.
- [ ] Il semaforo applica i criteri di `SKILL.md`; il verdetto è marcato **provvisorio** se il materiale era insufficiente.
- [ ] `STATUS.md` aggiornato; nulla modificato nel progetto fuori da `launch/`.
- [ ] `status.json` → `roadmap` con le tappe chiave aggiornate all'ultima decisione.
- [ ] Con `game-developer`: brief con "Da ricontrollare" dal `changes-since-wNN.md` (`wave_kit.py check` senza avvisi del contratto), `fixes` copiati così come sono (`wave_kit.py fixes --write`), sintesi e proposte con chiave e `P-wNN-n` su ogni riga, riaperture nel formato `Riapre la decisione: … — prove: … — proposta: … — costo: …`, problemi nati da un gate con chiave nuova e `from_gate_dev`, chiavi risolte che tornano riaperte "ricomparso dopo il gate NN", righe 🤖 con `P-wNN-n`, `key:` e `ok del proprietario` quando approvate, decisioni di `DECISIONI.md` importate con `fonte:`; `gate` e `resolved` di `issue_status.json` intatti.
- [ ] `issue_status.json` riflette tutte le decisioni del proprietario e l'ultima ondata; `TODO.md` spuntata e aggiornata con `todo_track.py` (nessun avviso "Da aggiornare" in `STATUS.html`).
- [ ] Il debriefing in chat segue il formato.

---

## STATUS.html: riassunto dai dati e scheda Mercato reale

Prima di rigenerare la pagina: `predictions.py sync`, `top_moves.py apply` (le 3 mosse in `TODO.md` e `calendar.md`, senza duplicati) e, se la calibrazione ha più di 30 giorni, la proposta di aggiornarla. In cima alla pagina il riassunto si scrive da solo dai dati (freschezza dei dati per prima se sono vecchi, ondata con la sua tendenza SIMULATO, base rate [STIMA], metro, problemi gravi, mosse, scadenza, accuratezza delle previsioni); il semaforo resta come piccolo badge. La scheda **Mercato reale** raccoglie tutto il mercato vero; le altre schede hanno una scheda che la collega. Mai più ottimisti dei dati.
