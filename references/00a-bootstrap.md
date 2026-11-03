# Fase B: avvio a freddo (capire gioco, motore e strumenti anche in una chat nuova)

Una chat nuova non ricorda nulla e non sa quali strumenti ha il progetto. **La skill non deve dipendere da ciò che è stato detto prima**: all'avvio ricostruisce il contesto da tre fonti, in quest'ordine: **gli strumenti della sessione**, **il disco** (progetto e documenti), **l'utente** (solo per ciò che resta). Vale in tutte le modalità (in Rapida e Mirata basta il passo 1, 2 e la conferma).

**Regola contro l'autolimitazione.** Prima di scrivere "non posso vedere il gioco", "non posso eseguirlo" o "non ho accesso a X": hai fatto l'inventario del passo 1 (compresa la ricerca degli strumenti differiti) e letto il disco? Se un progetto Unreal ha un MCP dell'editor collegato, lo usi per guardare la build; se c'è un terminale, lo usi per eseguire e misurare. Un limite si dichiara solo dopo aver controllato, dicendo cosa manca e come collegarlo.

## 1. Inventario degli strumenti DI QUESTA SESSIONE (non del disco)

1. Leggi l'elenco degli strumenti che hai ora (nomi `mcp__…`, shell, lettura file, ricerca web, subagenti, skill disponibili). Se la sessione ha strumenti differiti (si caricano con `ToolSearch`), **cercali per parola chiave prima di dichiarare che mancano**: `unreal`, `unity`, `godot`, `blender`, `terminal`, `browser`, `playwright`, `screenshot`, `steam`, `ffmpeg`.
2. Compila la tabella (finirà in `00-contesto.md`):

| Capacità | Cosa cercare | Uso in questa skill |
|---|---|---|
| Editor del motore | MCP Unreal (editor), Unity CLI / CoplayDev MCP, MCP Godot | guardare la build vera: schermate, livello, log, test, avvio e stop del Play (sola lettura) |
| Terminale / OS | shell, TerminalMCP (`shell_exec`, `screen`, `input`, `watch`) | eseguire gli script, `ffmpeg`, build e test già presenti, screenshot di finestra, QA con input reale |
| Browser | Playwright / browser MCP / fetch web | pagine Steam e itch, comparabili, regole, SteamDB a mano (nel rispetto dei termini) |
| Immagini | lettura di PNG/JPG | guardare capsule, screenshot, fotogrammi: l'hook si giudica guardando |
| Altre skill | `game-developer`, `real-world-design`, `dataviz`… | riusare ciò che hanno prodotto (vedi passo 4) |
| Subagenti | `Agent`/`Task` | ricerca parallela, gruppi del focus group in contesti separati |
| Social (Agent Reach, interno alla skill) | `reach.py doctor` (copia privata in `~/.game-launch-strategist/reach`, mai un `agent-reach` globale) | leggere X, TikTok, Instagram, Facebook, Reddit, YouTube con sottotitoli, Bilibili, XiaoHongShu, GitHub, V2EX, LinkedIn, web e RSS; sola lettura |
| Reddit | `reddit_backends.py doctor` | quale backend Reddit risponde da questa macchina (Agent Reach con login, OAuth, JSON, archivio Arctic Shift, RSS, ThreadSnoop) |

3. Per ogni capacità: **disponibile / collegata ma non risponde / assente**. Se il progetto la prevede (passo 2) ma non è collegata, vedi il passo 6.
4. **Social: inventario con Agent Reach.** Lancia
   ```bash
   python3 <skill>/scripts/research/reach.py doctor --md launch/_raw/reach-doctor.md
   python3 <skill>/scripts/research/reddit_backends.py doctor -o launch/_raw/reddit-doctor.json
   ```
   La tabella dice canale per canale **pronto / non pronto** e il comando che sblocca il canale. Nel Context Pack scrivi solo i canali pronti come "posso leggere"; per gli altri dai al proprietario i comandi di `reach.py setup` (con il percorso vero della skill, tipo `! python <skill>/scripts/research/reach.py login twitter`: apre la finestra del browser dedicato nella sua lingua e controlla il canale; si lanciano con `!` davanti, il login lo fa lui nella finestra del browser dedicato, account secondario consigliato) e prosegui senza aspettare. `--live` rifà il controllo dal vivo (qualche minuto, rete). Se Agent Reach interno manca (la tabella dice "non installato"): il proprietario lancia `! python <skill>/scripts/research/reach.py install` (lo fa anche l'aggiornamento della skill). Se X (o un altro sito) blocca il login del browser dedicato, alternativa: il login si copia dal Chrome/Edge normale del proprietario, da UN profilo che sceglie lui: `! python <skill>/scripts/research/reach.py collega-browser` stampa i passi (estensione OpenCLI solo in quel profilo, `browser profiles`, `browser use ID` obbligatorio, `login <canale|tutti> --dal-mio-browser`). Tu non scegli il profilo e non lanci la copia al suo posto. Mai login, cookie o password in chat.

## 2. Scansione del disco: `project_scan.py`

```bash
python3 <skill>/scripts/research/project_scan.py --root . -o launch/_raw/project_scan.json --md launch/_raw/project_scan.md
```
Parte dalla cartella corrente e cerca anche nelle cartelle sopra. Riconosce **Unreal** (`.uproject`: versione, plugin attivi, MCP, Steam, mappe), **Unity** (`ProjectVersion.txt`: versione, render pipeline, pacchetti, MCP, scene, file di GameDeveloperSkill), **Godot**, **Nucleon** (`project.ncproject`: grafica, livelli, landscape, script, test dei verbi, documenti UI, telemetria della skill dev), GameMaker, Defold, Ren'Py, RPG Maker, Construct e framework web o nativi. Elenca **i documenti che spiegano il gioco, in ordine di importanza**, ciò che hanno lasciato altre skill, Steam e itch, screenshot e video, git (credenziali rimosse), eseguibili sul PC, **server MCP configurati nel progetto** (mai le chiavi) e se la porta dell'MCP Unreal risponde. Dà anche indizi di genere: sono ipotesi da confermare.
Nessun motore riconosciuto → una sola domanda (percorso del progetto, oppure "è un progetto personalizzato") e si va avanti con i documenti.

### Come si decide il motore (strumenti collegati + file)

Il motore si deduce **incrociando due cose**, e quasi sempre basta:
- **Strumenti collegati** a questa chat: un MCP o un tool con `unreal` nel nome → Unreal; `unity` o Unity CLI → Unity; `godot` → Godot; `nucleon` o `ncli` → Nucleon; solo browser e terminale → probabile gioco web o personalizzato.
- **File del progetto** (lo scan): `.uproject` → Unreal; `ProjectSettings/ProjectVersion.txt` → Unity; `project.godot` → Godot; `project.ncproject` → Nucleon; altri marcatori per GameMaker, Defold, Ren'Py, RPG Maker, Construct; `package.json`, `Cargo.toml`, `CMakeLists.txt` per framework web e nativi; `index.html` con `<canvas>` o WebGL → gioco HTML5; `index.html` senza canvas → è un sito (la pagina del gioco, non il gioco).
Se i due concordano, non chiedere nulla. Se uno solo dà un indizio (strumento collegato ma cartella sbagliata, o file senza strumento) usa quello e dì cosa manca. Se discordano (per esempio MCP Unreal ma progetto Unity) o ci sono più progetti, elencali e chiedi **una** domanda: quale è il gioco da lanciare.

## 3. Leggi i documenti giusti (non tutti)

Nell'ordine che dà lo scan, fino a circa 15 file e le prime 200 righe di ciascuno: `CLAUDE.md`, `AGENTS.md`, `GDD`, `GAME_CONTEXT.md`, `GAME_TASKS.md`, `README`, pitch/visione, roadmap, TODO, note di design, `launch/STATUS.md` se esiste. Ogni fatto che ne ricavi porta il **nome del file** ("dal GDD: …"). Ciò che è scritto lì **non si richiede all'utente**: lo si propone come risposta e si chiede solo conferma.

## 4. Riusa ciò che hanno già prodotto altre skill (progetti di `game-developer`)

| File | Dove entra qui |
|---|---|
| `GDD.md` (se `locked`) | Fasi 0, 1, 0A: genere, stile, pilastri, pubblico, piattaforme, stack; le domande già risposte si saltano (si cita il GDD) |
| `GAME_TASKS.md` | TODO del **gioco completo** (Fase 10B) e stato reale del lavoro (fatti / aperti / bloccati) → beta o completo? |
| `GAME_CONTEXT.md` | loop dei 30 secondi e dei 3 minuti, vittoria e sconfitta, controlli: base di audit e di evidenze |
| `docs/gates/*.md`, `docs/lint/scene-lint.json`, `docs/playtest.md` | cosa è stato **dimostrato** (test, lint, playtest): qualità tecnica della Fase 3. I gate nuovi hanno un'intestazione leggibile da macchina (gate, data, PASS/PARTIAL/FAIL, chiavi chiuse, rischi, cosa provare): `project_scan.py` dà l'ultimo (`dev_link.gates_with_header`) |
| `DECISIONI.md` | decisioni del proprietario prese nella chat del dev (`D-NNN`): valgono come le tue, non si contano come problemi; quelle che mancano in "Decisioni prese" e `00-intenzioni.md` si importano con `todo_track.py sync-decisions` (`fonte: DECISIONI.md D-NNN`). Non si scrive mai |
| `docs/design-review/` (`game-map.md`, `screen-map.md`, `runs.md`, `changes-since-wNN.md`), `docs/gates/plan-wNN.md` | stato attuale del gioco dopo i gate e piano dei gate: base della prossima ondata (`references/dev-link.md` §6.2, `04-focus-group.md` Passo 0) |
| `ASSET-LEDGER.md` | licenze degli asset, dichiarazione AI di Steam, crediti: Fasi 4 e 10 |
| `screenshots/000-index.md`, `art/reference/BOARD.md`, `docs/scene-map.md` | evidenze reali, riferimenti visivi, contenuto della scena |
Il GDD non contiene prezzo, budget, date e capacità del team: quelli restano all'intervista.
Con `game-developer` vale il contratto `references/dev-link.md` (leggilo se lo scan dà `dev_work` o `docs/design-review/`): chi scrive quali file, decisioni in due registri, cosa lasciare su disco dopo ogni ondata, cosa leggere dopo ogni gate. Si scrive solo in `launch/`.

## 5. Guarda la build con gli strumenti del motore (sola lettura)

Se l'editor è collegato, **la build vera batte qualsiasi descrizione**. Ammesso: schermate, elenco di livelli/attori/asset, log, test automatici già presenti, avvio e stop del Play (PIE) per vedere i primi minuti. **Vietato** salvare, creare o modificare oggetti, importare, cancellare, fare build di rilascio (regola 8: si scrive solo in `launch/`).

| Motore | Come |
|---|---|
| **Unreal 5.8+** | MCP ufficiale dell'editor (plugin *ModelContextProtocol* attivo): `list_toolsets` → `describe_toolset <nome>` → `call_tool`. Usa i toolset di schermate, elenco attori (sola lettura), controllo PIE, log, test di automazione. Se il progetto ha `Content/Python/gds_ue.py` (GameDeveloperSkill): `gds_ue.shot(...)`, `gds_ue.lint(autofix=False)`. Avvio: **prima l'Editor, poi l'agente**, lanciato dalla cartella del `.uproject`; configurazione client con `ModelContextProtocol.GenerateClientConfig ClaudeCode`; endpoint predefinito `http://127.0.0.1:8000/mcp` solo locale **[DA VERIFICARE]** |
| **Unity** | Unity CLI (`unity command …`, `eval`, `run_tests`, `screenshot`) o MCP CoplayDev (console, stato editor, screenshot). Se esiste `Assets/_Game/Editor/GDS`: `gds_scene_map`, `gds_lint`, `gds_sheet` (sola lettura). Un solo Editor aperto: non lanciarne un secondo |
| **Nucleon** | MCP integrato nell'editor (Editor Preferences > AI > Enable Server, o `--mcp-stdio`). Se c'è la skill `game-developer`: `python <game-developer>/scripts/ncli.py --project . ping` (stato), `shot <png> --pos x,y,z --target x,y,z` (vista di gioco), `capture plan.json` (catture in Play vero con manifest), `lint` (sola lettura), `log`; mai `build`/`save` (sono del dev). Senza la skill: tool MCP `editor_state`, `scene_list`, `capture_viewport`, `read_log`, `play_control` (sola lettura). Coordinate Z up, metri |
| **Godot** | MCP Godot se c'è; altrimenti `godot --headless --path . --quit` per errori di caricamento e lettura di `.tscn`/`.gd`; per le immagini chiedi uno screenshot o una clip |
| **Altro / personalizzato** | esegui il comando di avvio documentato (README), cattura con TerminalMCP `screen` o chiedi un video; leggi il codice dei sistemi principali |
| **Qualsiasi** | `ffmpeg`/`ffprobe` sui video trovati (durata, tagli, fotogrammi), `project_scan.py` per i media, TerminalMCP `input` per giocare i primi minuti solo se l'utente lo consente |

## 6. Se lo strumento previsto non è collegato

Non fermarti e non fingere. Dì in **una riga** cosa manca e **come collegarlo** (per Unreal: plugin attivo, Editor acceso, agente avviato dalla cartella del progetto, config generata), poi prosegui con documenti e codice e scrivi in `00-contesto.md` cosa si perde ("nessuna build verificata: audit su codice e documenti, confidenza bassa"). Quando l'utente collega lo strumento, rifai solo i passi che ne beneficiano.

## 7. Dove gli strumenti entrano nelle fasi

| Fase | Uso |
|---|---|
| 0 Scoperta | versione, plugin, Steamworks, scene e mappe, stato (beta o completo) dai file |
| 3 Audit | avvia il Play, schermate dei primi 10 minuti, log di errori e avvisi, test esistenti, frame rate se lo strumento lo dà |
| 4 Piattaforme | Steamworks presente (`steam_appid`, plugin o pacchetto), controller, Steam Deck |
| 5 Prezzo | durata e contenuti reali (scene, mappe, `GAME_TASKS.md`), non solo dichiarati |
| 6 Hook / 7 Focus group | **schermate reali** nel pacchetto di evidenze (con data e versione), fotogrammi da video veri con `ffmpeg` |
| 10 Legale | `ASSET-LEDGER.md`, licenze, dichiarazione AI |

## 8. Output: `launch/00-contesto.md` (Context Pack)

Struttura fissa, breve (una pagina):
1. **Progetto**: nome, motore e versione, percorso, versione del gioco, repository.
2. **Cosa so e da dove**: elenco di fatti, ognuno con il file di origine.
3. **Stato**: beta, demo o completo? (indizi: versione, `GAME_TASKS.md`, slice del GDD, nomi dei file) → proposta per la domanda zero.
4. **Genere**: ipotesi con confidenza e indizi (non verdetto).
5. **Strumenti**: la tabella del passo 1, con "usato per" e "se manca, cosa perdo / come collegarlo".
6. **Documenti letti** e documenti trovati ma non letti.
7. **Lacune**: solo ciò che nessuna fonte dice. Diventano le domande dell'intervista.
Salva anche `_raw/project_scan.json`.

**Conferma all'utente** (5-8 righe, poi prosegui senza aspettare se non c'è nulla di ambiguo): *Ho capito che è [gioco] in [motore e versione], genere probabile [x], stato probabile [beta/completo]. Posso usare [strumenti]. Non posso [strumenti] ([come collegarli]). Dai documenti ho già [cosa]. Mi manca [cosa]: parto dalla domanda zero (beta o completo?), con la mia risposta dedotta da confermare.*

## 9. Chat già calda e riprese

- Se la conversazione contiene già il contesto (altra skill usata, lavoro svolto), il bootstrap si riduce a verificare gli strumenti e a leggere `launch/STATUS.md`: non rifare domande già risposte.
- Se `00-contesto.md` esiste, rilancia la scansione e dì in 3 righe cosa è cambiato (versione, task, documenti nuovi, strumenti ora collegati) prima di riprendere da `STATUS.md`.
