# Modalità Trailer: dal colloquio al prompt del trailer, alle riprese, al controllo

Output: **`launch/trailer/<versione>/`** (`trailer.json` = fonte unica; `PROMPT.md`, `storyboard.md` + `storyboard.json`, `assets-plan.md`, `credits-ledger.csv`, `recording-brief.md` + `.json`, `qa-checklist.md`, `kit.json`) e la scheda **Trailer** di `STATUS.html`.

Strumento: `scripts/research/trailer_kit.py` · conoscenza: `scripts/research/data/trailer_craft.json` (regole con fonte e data, specifiche delle piattaforme, prompt negativo di base, fonti di asset con licenza). Si usa anche `store_bench.py` (pagine e trailer dei concorrenti).

Un trailer è il materiale di marketing che rende di più per un indie (Steam lo mette prima degli screenshot e ne ricava il mini-trailer di 6 s): qui non si improvvisa. Il lavoro è in due tempi: **prima il piano** (questo file, sempre), **poi riprese e montaggio** (solo quando il proprietario lo chiede).

---

## A. Intervista sul trailer (più domande, con consigli)

Prima leggi quello che c'è già: `launch/00-intenzioni.md`, "Decisioni prese" di `TODO.md`, note del proprietario sui trailer precedenti (es. `tools/release/trailer/NOTE-*.md`: **obbligatorie**), le sintesi delle ultime ondate (momenti che i tester ricordano, clip più condivise), i gate recenti (che aspetto ha il gioco oggi). Non chiedere quello che sai già: scrivi la risposta dedotta con la fonte e chiedi conferma solo dove manca.

Domande (con la tua raccomandata per prima e il compromesso in una riga):

| # | Tema | Domanda | Consiglio tipico |
|---|---|---|---|
| 1 | Scopo | Annuncio, pagina Coming Soon, Next Fest, lancio, aggiornamento? | Coming Soon = genere + verbo unico in 5 s; Next Fest = "gioca la demo adesso"; lancio = prezzo e contenuto. Meglio due trailer giusti che uno buono a tutto |
| 2 | Durata | Principale e tagli corti? | Principale 45-60 s per un indie (mediana dei concorrenti vincenti ~60-70 s, Balatro 39 s); sempre 30 s verticale, 15 s verticale, GIF della pagina |
| 3 | Piattaforme | Steam, itch, YouTube, TikTok/Shorts/Reels, X, Reddit, stampa? | Il canale principale decide quale taglio curare di più |
| 4 | Momenti | Quali momenti non devono mancare? | Partire da quelli che i tester (veri o simulati) ricordano; massimo 1 grande disastro prima del titolo |
| 5 | Tono | Comico, epico, accogliente, teso? | Quello che il gioco mantiene davvero nei primi 10 minuti |
| 6 | Da evitare | Cosa non vuoi vedere? | Va tutto nel prompt negativo e nei controlli |
| 7 | Note | Note obbligatorie su trailer precedenti? | Diventano una sezione non negoziabile del prompt |
| 8 | Materiale | Che riprese esistono e sono ancora valide (gioco cambiato, look nuovo)? | Riprese di un gioco vecchio = rifarle; aspettare il look definitivo |
| 9 | Scadenza | Entro quando? | Trailer prima della pagina Coming Soon; Next Fest: il video ufficiale ha una scadenza propria [DA VERIFICARE] |
| 10 | Audio e asset | Musica e suoni: del gioco, fatti con il codice, trovati online? Voce? Budget? | Prima la colonna del gioco; poi asset creati col codice; poi CC0/CC-BY; mai NC; niente voce se il proprietario non la vuole |
| 11 | Credito e dichiarazioni | Che credito pubblico? AI da dichiarare? | Un solo credito; la dichiarazione AI di Steam la decide il proprietario dopo aver letto la pagina ufficiale [DA VERIFICARE] |

Registra domande, risposte, consigli e fonti in `trailer.json` → `interview`. Le domande ancora senza risposta vanno in `open_questions` **con il default che userai**: finiscono in cima a `PROMPT.md` ("Domande aperte"). La decisione presa va anche in `00-intenzioni.md` con la data.

## B. Controllo degli strumenti

```bash
python3 <skill>/scripts/research/trailer_kit.py tools --spec launch/trailer/<v>/trailer.json
```
Scrive in `trailer.json` → `tools`: versione di **brag** e **hyperframes** (dal file `~/.agents/.skill-lock.json`: sorgente, hash, data), la CLI di HyperFrames (`npx hyperframes --version`), ffmpeg/ffprobe. Aggiornare:
- brag e le skill di HyperFrames sono skill installate con `npx skills`: `npx skills update brag -g -y`, `npx skills update hyperframes -g -y` (se brag è installato come plugin di Claude Code: `claude plugin update brag`);
- la CLI: `npx --yes hyperframes@latest --version`.

Regole fisse: **brag sempre con `--full`** (su Opus 5.5 brag passa da solo a brag-slim, che per un trailer non basta), **mai `--voice`** se il proprietario non vuole la voce. Musica di brag (ende.app) e SFX Kenney inclusi: Kenney è CC0; la licenza della musica di brag è **[DA VERIFICARE]** (lo dice il suo README): non usarla finché non è confermata per iscritto.

## C. Concorrenti e genere: i trailer veri, misurati

1. **Comparabili:** i diretti (stessa meccanica o stesso ciclo), i vincenti del genere e 1-2 deboli istruttivi, da `launch/comps.csv`.
2. **Misure automatiche:**
```bash
python3 <skill>/scripts/research/store_bench.py run <appid…> --frames-dir launch/_raw/trailer_<v>/frames -o launch/_raw/trailer_<v>/store_pages_trailer.json --md launch/_raw/trailer_<v>/store_bench_trailer.md
python3 <skill>/scripts/research/trailer_kit.py measure "<trailer_url HLS dal JSON>" --name "<gioco>" --appid <id> -o launch/_raw/trailer_<v>/measured.json
python3 <skill>/scripts/research/trailer_kit.py measure <il nostro trailer attuale.mp4> --name "<noi vN>" --appid noi-vN -o launch/_raw/trailer_<v>/measured.json
python3 <skill>/scripts/research/trailer_kit.py bench launch/_raw/trailer_<v>/store_pages_trailer.json --measured launch/_raw/trailer_<v>/measured.json --spec launch/trailer/<v>/trailer.json --md launch/_raw/trailer_<v>/trailer_bench.md -o launch/_raw/trailer_<v>/trailer_bench.json
```
`measure` dà durata, **tutti** i tagli, inquadratura media (anche per terzo del trailer), primo taglio, tagli nei primi 5 s, volume (LUFS integrati, picco vero), tratti fermi e neri, tempo musicale stimato (±3 BPM, possibili errori di doppio/metà). Limite: un taglio tra due inquadrature quasi uguali può non essere visto (e spesso nemmeno lo spettatore lo vede).
3. **Giudizio a occhio** (fotogrammi a 0/2/5/10/20/30 s in un foglio unico con ffmpeg `hstack`/`vstack`): per ogni gioco scrivi in `trailer.json` → `competitors` i primi 3 secondi, le scritte, la musica, la struttura, il finale e **la lezione per noi**. Etichetta **[OPINIONE]**.
4. **Il nostro aggancio oggi, onesto** (`hook_current`): misure del nostro trailer attuale contro la mediana dei vincenti, cosa funziona, cosa manca, cosa cambia nella versione nuova. Se c'è un render vecchio, lancia anche `trailer_kit.py qa` su di esso: è il modo più rapido per vedere i difetti con i numeri.

## D. Conoscenza del mestiere (`data/trailer_craft.json`)

Regole parafrasate da fonti vere, ognuna con URL, data di lettura, forza della prova (documentazione della piattaforma, misurata, esperto, guida di terzi) e a quali formati si applica: Derek Lieu (primo piano, ritmo, trailer come tutorial, ottimizzazione social), How To Market A Game (gioco nei primi 5 s, niente CG finto), GameDiscoverCo (l'errore del trailer lento), documentazione Steam (primo trailer di gioco con HUD, visione senza audio, mini-trailer 6×1 s, specifiche, coda di scoperta < 10 s, niente contenuti futuri), zone sicure e formati verticali, volume (-14 LUFS / -1 dBTP, riferimento non ufficiale), licenze, dichiarazione AI di Steam.

```bash
python3 <skill>/scripts/research/trailer_kit.py craft [--topic hook|structure|pacing|steam|social|audio|text|legal|gif] [--applies main|vertical|gif]
```
Prima di ogni trailer: rileggi le regole `platform_doc` e `third_party` sulle pagine originali se sono più vecchie di 3 mesi, aggiorna `date` e, se cambiano, la regola. Le misure nostre (`store_bench`, `measure`) aggiornano le regole `measured` con n e data.

## E. Il prompt e lo storyboard (`trailer_kit.py build`)

Scrivi `launch/trailer/<v>/trailer.json` (struttura: vedi la testata di `trailer_kit.py` e l'esempio di Buffet Panic! `launch/trailer/v3/trailer.json`):
- `brand` (credito unico, parole e nomi vietati nei testi pubblici, palette, font, loghi);
- `concept` (logline + **5 righe**);
- `formats`: `main` (45-60 s), `short30` (16:9, derivato), `vertical30`, `vertical15`, `gif` (loop della pagina);
- `shots`: **una voce per inquadratura** con `id, format, t0, t1, section, source (gameplay|rig|ui|card), screen, camera, text, audio` + `record` (scena, preparazione, camera, HUD, eventi da marcare, durata, prese, note) + facoltativi `action` (obbligatorio per le schermate UI), `oner_beats` (i colpi di un piano unico), `similar_group` (per la regola del tre), `text_box` e `text_cap_px` (zona sicura e leggibilità), `xfade`, `why`;
- `music` (`voice: false`, regole, **punti di sincronia** con i tempi), `recording` (regole e cattura), `panel` (ancore vere con la fascia), `assets` (ogni file con licenza), `qa_extra`;
- `prompt`: i paragrafi del prompt maestro (intro, missione, strumenti, storia atto per atto, regole di montaggio, camera, look, tipografia, formati, regole applicate per ID, note del proprietario, asset, "fatto vuol dire") + `negative_extra`.

```bash
python3 <skill>/scripts/research/trailer_kit.py check launch/trailer/<v>/trailer.json
python3 <skill>/scripts/research/trailer_kit.py build launch/trailer/<v>/trailer.json --bench launch/_raw/trailer_<v>/trailer_bench.json [--strict]
```
`check` blocca (ERRORE): primo taglio oltre 3 s (verticale 2 s) senza `oner_beats`, gioco dopo i 5 s, cartello o logo prima del gioco, buchi o sovrapposizioni tra inquadrature, lunghezza fuori dal ±10 %, scritte con meno di 0,3 s per parola, testo verticale fuori dalla zona sicura o troppo piccolo per un telefono, UI ferma oltre 1 s o senza azione, finale senza cartello o senza il credito, parole vietate nei testi pubblici (AI, nomi), voce accesa contro la decisione, licenze NC; avvisa (WARN) su più di tre inquadrature simili di fila, cartello finale fuori da 3-4 s, troppe parole, licenze non nell'elenco pulito.

`build` scrive: **`PROMPT.md`** (Domande aperte con default · concetto in 5 righe · aggancio onesto · intervista · strumenti · tabella dei concorrenti misurati · **MASTER PROMPT** in inglese, lungo e dettagliato: missione, consegne, invocazione degli strumenti, storia, shot list per ogni formato, regole di montaggio e camera, look, tipografia e brand, musica e sincronie, formati, regole del mestiere con fonte, note del proprietario, asset, definizione di "fatto" · **NEGATIVE PROMPT** = base + aggiunte del gioco · fonti), `storyboard.md/.json`, `assets-plan.md`, `credits-ledger.csv` (unisce, non cancella le righe esistenti), `recording-brief.md/.json`, `qa-checklist.md`, `kit.json` (lo legge `status_page.py`).

**Scheda Trailer in `STATUS.html`** (rigenera con `status_page.py`): pulsante **Copia** con prompt positivo + negativo (un clic), il prompt leggibile, le domande aperte, lo storyboard **a schede** (una per inquadratura: tempo, cosa si vede, camera, testo, audio, come girarla), la tabella dei trailer dei concorrenti, i controlli di qualità e gli avvisi del controllo. Nascosta nella versione per publisher (`--hide trailer` per toglierla altrove).

Regole di scrittura del prompt: inglese, concreto (tempi, inquadrature, suoni legati a eventi visibili), una sola idea per inquadratura, ogni regola con il suo perché, niente aggettivi vuoti ("epic", "amazing"). Il prompt deve poter essere eseguito da qualcuno che non ha mai visto il gioco.

## F. Asset: trovare o creare, sempre nel registro

Ordine: **1) asset del gioco** (già nel suo registro di licenze: copia la riga) → **2) creati con il codice** → **3) trovati online con licenza pulita**. Fonti con licenza, note e data in `trailer_craft.json` → `asset_sources` (Kenney CC0, OpenGameArt filtrato CC0, Freesound solo CC0/BY, Pixabay con la sua licenza e il rischio Content ID per brano, Poly Haven CC0, incompetech CC-BY: in conflitto con "un solo credito", meglio CC0). Da non usare: generatori AI di musica/voce/immagini, brani commerciali, licenze NC o "uso personale" (`avoid_sources`).

Creare con il codice ("come farebbe una persona": sintesi deterministica, niente modelli):
```bash
python3 <skill>/scripts/research/trailer_kit.py synth whoosh launch/trailer/<v>/audio/whoosh_01.wav --seed 1 --ledger launch/trailer/<v>/credits-ledger.csv --credit "<studio>" --used-in <v>
# tipi: whoosh, pop, tick, hit, riser, stinger (accordo su --bpm), music (bozza swing di --bars battute: solo segnaposto)
```
Immagini e cartelli: HTML/CSS/SVG dentro HyperFrames con i token del brand, o fotogrammi del gioco. Ogni file entra in `credits-ledger.csv` (id, file, tipo, autore, URL, licenza, credito, chi l'ha fatto e come, data, stato) **prima** di entrare nel montaggio. I crediti CC-BY vanno nella descrizione del video, non a schermo.

**Dichiarazione AI di Steam [DA VERIFICARE]:** dal 2024 il questionario dei contenuti chiede di dichiarare i contenuti generati con l'AI presenti nel gioco **o nel marketing e nella pagina** (aggiornamento riportato il 2026-01-16: esenti gli strumenti di efficienza come gli assistenti al codice). Non è scritto se suoni o immagini scritti con codice da un assistente contino. Scrivilo onestamente al proprietario, digli di rileggere la pagina Steamworks il giorno del caricamento e lascia a lui la decisione; nel frattempo preferisci asset del gioco e CC0. Mai menzionare l'AI nei materiali pubblici se il proprietario non vuole, ma **mai** consigliare di non dichiarare ciò che va dichiarato.

## G. Controllo di qualità (solo quando esiste un render)

Automatico:
```bash
python3 <skill>/scripts/research/trailer_kit.py qa <render.mp4> --spec launch/trailer/<v>/trailer.json --format main --md launch/trailer/<v>/qa-main.md -o launch/trailer/<v>/qa-main.json
```
Controlla: primo taglio ≤ 3 s (verticale ≤ 2 s), durata ±10 %, inquadratura media per terzo (da confrontare con i concorrenti), **-14 LUFS ± 1** integrati e **picco vero ≤ -1 dBTP**, nessuna immagine ferma oltre 1 s prima del cartello finale, niente nero nei primi 10 s, risoluzione/fps/codec (Steam 1920x1080 30/60 fps H.264/AAC; verticale 1080x1920). Leggibilità a misura di telefono, zone sicure TikTok e contenuti vietati dal prompt negativo si controllano già sullo storyboard (`check`) e poi **a mano**, fotogramma per fotogramma, su un foglio a 0,5 s (compenetrazioni, teste tagliate, testi di debug).

**Criterio dai flop: trailer con azione entro 3 s.** Il gioco che gira (non logo, non intro, non sviluppatore davanti allo schermo) deve comparire entro i primi 3 secondi (verticale 2 s) e il gancio deve capirsi senza audio. Da guardare a mano sul foglio dei fotogrammi 0/2/5 s: se a 3 s non si vede ancora cosa fa il giocatore, il trailer non passa, anche se il primo taglio è nei tempi. Fonte: `references/09-reddit-casi.md`, 19 thread di flop su 57 accusano il trailer, 15 su 57 il gancio poco chiaro (2026-11-03); è la voce FC01 di `social_content.py flopcheck`. Nella rubrica del focus group non è una settima dimensione: pesa dentro "chiarezza" (peso alzato il 2026-11-03, `scripts/research/data/rubric_weights.json`).

**Panel di spettatori alla cieca** (simulato, stesso metodo calibrato del focus group, `04-focus-group.md` 7.0b-7.0e):
```bash
python3 <skill>/scripts/research/trailer_kit.py panel init --spec launch/trailer/<v>/trailer.json --render <render.mp4> --out-dir launch/trailer/<v>/panel
# i tester del roster guardano i trailer con un codice (il nostro mescolato con 3+ trailer veri: 2+ forti del genere e 1 debole, con la fascia attesa)
python3 <skill>/scripts/research/trailer_kit.py panel score launch/trailer/<v>/panel/panel-results.json --key launch/trailer/<v>/panel/panel-key.json --md launch/trailer/<v>/panel/panel.md
```
Primi 10 s a volume zero, poi con l'audio: "che gioco è e cosa fai?", aggancio, chiarezza, divertimento visto, ritmo, wishlist sì/forse/no, il momento che ricordi, cosa confonde. Punteggio grezzo e normalizzato sulle ancore; se un'ancora deriva oltre 8 punti dalla sua fascia **si ricalibra prima di leggere il nostro voto**. Senza render il panel si rifiuta di partire: non si giudica uno storyboard come se fosse un video. Etichetta sempre **SIMULATO**: ordina i problemi, non prevede le wishlist.

## H. Passaggio al lato sviluppo (`game-developer`)

`build` scrive `launch/trailer/<v>/recording-brief.md` e `.json`: **una riga per ripresa** (nome `v<N>_<scena>`), con scena, preparazione, camera, HUD, eventi da marcare nel file `.events.json`, durata + margini, numero di prese, inquadrature che la usano e note (compenetrazioni, teste). È il brief di registrazione per chi gira nel gioco.

Come si passa (contratto `references/dev-link.md`, gdl-v3): il launch possiede `launch/**`, il dev lo legge; quindi il dev **legge** `recording-brief.*` e registra con i suoi strumenti (registratore del gioco, cattura a 60 fps fissi, niente spawn o eventi forzati), scrivendo il suo gate in `docs/gates/` come sempre; il launch non tocca mai il gioco. Il brief non è ancora una voce della tabella del contratto: alla prossima versione (gdl-v3) va aggiunto in **tutte e due** le copie (`dev-link.md` e `launch-link.md` del dev), non in una sola. Senza la skill dev: il brief resta valido per una persona che gira a mano.

Le riprese partono solo con la richiesta del proprietario e, se il gioco sta cambiando aspetto, dopo il gate che lo chiude.

## I. Dopo

- `todo_track.py`: spunta il piano, aggiungi "rispondere alle domande aperte" (👤), "riprese e montaggio" (🤖, quando lo chiede il proprietario), "dichiarazione AI da rileggere" (👤).
- `status_page.py` per la scheda Trailer; `store_kit.json` → `trailer` quando il video esiste.
- Dopo un trailer nuovo proponi una nuova ondata del focus group (`04-focus-group.md` 7.5): il panel vede i materiali nuovi. Solo con l'ok.

Ogni file termina con TODO nel formato di `references/06-synthesis-output.md`.
