# Fasi 0, 1, 2, 2B: scoperta, genere, mercato, posizionamento

Percorsi: `launch/` è nella radice del progetto del gioco. Date, etichette e regole generali sono in `SKILL.md`.

---

## FASE 0: scoperta, fase del progetto e obiettivo

Leggi README, GDD, note, TODO, file di configurazione dell'engine, cartelle di asset, plugin, build script, file Steam, screenshot e trailer presenti. Segnali utili per riconoscere l'engine:

| Engine | Segnali |
|---|---|
| Unity | `ProjectSettings/ProjectVersion.txt`, `Packages/manifest.json`, `Assets/` |
| Unreal | `*.uproject`, `Content/`, `Config/DefaultEngine.ini` |
| Godot | `project.godot`, `*.tscn`, `*.gd` |
| GameMaker | `*.yyp` |
| Custom / altri | `Cargo.toml` (Bevy), `CMakeLists.txt`, `package.json` (web), `love` / `main.lua` |
| Steamworks | `steam_appid.txt`, Steamworks.NET, Facepunch.Steamworks, GodotSteam, `*.vdf` di SteamPipe |

Costruisci **`launch/00-brief.md`**:

1. **Scheda tecnica**: engine e versione, render pipeline, piattaforme, Steam Deck, Steamworks, SteamPipe, Steam Input, localizzazione, cloud save, telemetria.
2. **Genere e confidenza**: genere primario, sottogenere, eventuale secondario, confidenza in percentuale (Fase 1).
3. **Pubblico e mood**: a chi parla, quando si gioca, cosa promette.
4. **Fase del progetto** (determina la profondità di tutto il resto): *Idea/Concept* (si valuta il concept, non il game feel), *Prototipo*, *Vertical slice*, *Demo/Alpha*, *Pre-release/Beta*, *Post-lancio* (ci sono dati reali: recupero o rilancio).
5. **Obiettivo dichiarato**: vendite, community, portfolio, hobby con possibile ritorno. Cambia le soglie: un portfolio non ha bisogno di break-even.
6. **Team e vincoli**: persone, ore a settimana, budget, **paese e inquadramento fiscale**, soci.
7. **Stato dei contenuti**: cosa è giocabile, cosa manca, durata di run o sessione, volumi, bug noti.
8. **Materiale disponibile e confidenza**: elenca cosa hai (build giocabile, screenshot, clip, GDD, pagina store, dati wishlist). Ogni sezione del report riceve una confidenza **bassa / media / alta** in base al materiale: senza screenshot la capsule non si valuta, senza build il game feel non si valuta, e lo dici.

### Poi l'intervista sulle intenzioni

Dopo aver letto il progetto **non andare avanti da solo**: esegui l'intervista a più round di `references/00-intervista.md` (obiettivi, capacità, soldi e rischio, canali, non negoziabili, scenari "e se…", conferma) e scrivi `launch/00-intenzioni.md`. Le ipotesi che non vengono confermate restano segnate nel brief. In Rapida basta un blocco di massimo 8 domande.

---

## FASE 1: Genre Router e playbook

Rende la skill adattiva: pilastri, coorti, hook, creator, demo, prezzo e rischi dipendono dal playbook. Il genere decide *quale tipo di successo è realistico*; trattare uguali un cozy sim, un horror e uno strategico è l'errore più comune di un'analisi generica.

1. **Rileva il genere** da più segnali, mai da uno solo: tag che il gioco userebbe su Steam, meccaniche nel codice (carte, ondate, griglie di costruzione, dialoghi ramificati, netcode), struttura di cartelle e asset, GDD, screenshot, input richiesti.
2. **Scegli il playbook** in `references/playbooks.md`. Se ibrido: primario (70%) + secondario (30%), massimo 8 pilastri, priorità al primario.
3. **Se il genere non è nei playbook o la confidenza è < 70%**, costruisci un playbook ad hoc in `launch/playbook-usato.md`:
   a. Trova 5 comparabili di successo recente e 3 flop istruttivi (`steam_discover.py`).
   b. Dalle loro recensioni (`steam_reviews.py`) estrai le 5 cose che il pubblico premia e le 5 che punisce: sono i **pilastri**.
   c. Cerca dove quel pubblico scopre i giochi (subreddit, Discord, creator, festival) e quale hook visivo funziona.
   d. Cerca durata tipica, fascia di prezzo e struttura della demo dei successi.
   e. Definisci 3 coorti del Gruppo A (esperti) e 3 del Gruppo B (scoperta e attrito).
   f. Elenca i rischi specifici.
4. **Documenta** nel brief: playbook scelto, motivo, adattamenti, dubbi.

---

## FASE 2: ricerca di mercato e comparabili

Output: `launch/sources.md`, `launch/comps.csv`, dati grezzi in `launch/_raw/`. In Rapida bastano 8-10 comparabili; in Completa 15-25 (minimo 8).

### 2.0 Benchmark di genere (dati pubblici, a ogni esecuzione)

I giochi più recensiti del tag, con anno di uscita, prezzo e demo, dicono cosa serve per essere visibili e come vanno le uscite recenti. Si costruiscono a runtime, ogni volta che servono, da fonti pubbliche:

```bash
python3 <skill>/scripts/research/genre_bench.py --tag Roguelike --tag Cooking --enrich 80 \
  --mine price=<prezzo> --mine reviews_per_year=<obiettivo> --md launch/_raw/genre_bench.md -o launch/_raw/genre_bench.json
```
Distribuzioni (p25 / mediana / p75 / p90), coorti per anno di uscita, fasce di prezzo, demo contro senza demo, soglia di visibilità e la posizione dei tuoi numeri. **Limite da ripetere sempre:** la lista contiene i giochi *più recensiti* del tag, cioè la coda alta di successo, non il gioco mediano: le cifre dicono cosa serve per emergere, non cosa aspettarsi. Cita tag, n e data di lettura.

Poi metti sotto osservazione i comparabili più vicini e i possibili concorrenti della tua finestra: `watchlist.py add <appid...> --role comp|competitor`; ogni controllo successivo con `watchlist.py snap` e `report --launch <data>` (segnala impennate, saldi, uscite, cali di % positive e collisioni con la tua data).

### 2.1 Trova i comparabili

```bash
# da una parola chiave o dal nome di un gioco noto -> appid
python3 <skill>/scripts/research/steam_discover.py search "cooking roguelite" "overcooked" -o launch/_raw/discover_search.json
# i giochi più recensiti per tag (SteamSpy), con data di uscita e prezzo
python3 <skill>/scripts/research/steam_discover.py tag Roguelike Cooking --enrich 40 -o launch/_raw/discover_tags.json
```

Integra con ricerca web (post-mortem, classifiche, "giochi simili a X", sezione "Più giochi come questo" di Steam). Scegli un **mix**: successi recenti (ultimi 2-3 anni), successi medi, flop istruttivi, team di dimensione simile, fascia di prezzo simile. Mai solo i mega-hit.

### 2.2 Estrai i dati

```bash
python3 <skill>/scripts/research/steam_comps.py <appid...> --steamspy --gamalytic --boxleiter 30,60 --headers-dir launch/_raw/hdr -o launch/_raw/comps.json
python3 <skill>/scripts/research/steam_comps.py --ids-file launch/_raw/ids.txt --steamspy --gamalytic -o launch/comps.csv
```

Per ciascun comparabile completa a mano le colonne che gli script non danno: `vicinanza` (1-3 per i più vicini), `durata_h`, `demo_o_nextfest`, `stile_capsule_trailer`, **`cosa_ha_funzionato_nel_marketing`**, `momento_virale_e_perche`. Nessuna di queste si inventa: fonte nella riga o `[DA VERIFICARE]`.

### 2.3 Stima delle vendite

- **Boxleiter** (copie ≈ recensioni × moltiplicatore): usa sempre un **intervallo** (default 30-60) e dichiara che varia per genere, prezzo, anno e piattaforma.
- Incrocia con Gamalytic e, se disponibili, SteamDB o VG Insights. Se `copies_per_review` di Gamalytic cade fuori da 30-60 (in un test su un titolo cooperativo molto venduto era 87), allarga l'intervallo e spiegalo.
- Ogni stima porta il suo margine di errore e l'etichetta **[STIMA]**.

### 2.4 Dati di mercato del genere

Post-mortem recenti; conversione wishlist→vendita (default prudente **[DA VERIFICARE]** 0,10-0,30× nel primo anno per un indie piccolo); ritmo di accumulo delle wishlist organiche; tasso di completamento della demo; quanti giochi simili escono al mese e che soglia di qualità serve per emergere. Le distribuzioni per anno, prezzo e demo vengono da `genre_bench.py` (2.0), con il limite della coda alta.

### 2.5 Regole attuali delle piattaforme

Requisiti della pagina Steam, tag, demo e playtest, finestre di visibilità al lancio, dichiarazione dell'uso di AI, criteri Steam Deck, fee Steam Direct, revenue share di Steam e itch. Tutto con data di consultazione (vedi "Da verificare sempre" in `SKILL.md`).

### 2.6 Finestra di mercato

Uscite grandi nello stesso genere nei prossimi 12 mesi (da evitare), saldi stagionali e festival tematici utili. Per i concorrenti già noti usa `watchlist.py` (ruolo `competitor`) con la tua data di lancio: segnala la collisione di finestra.

### 2.7 Collisioni di titolo e marchio

Ricerca su Steam, Google, itch.io, TikTok, YouTube; controllo base su EUIPO e TMview (e sull'ufficio marchi del paese del team). Non è consulenza legale: segnala dove serve un professionista.

### 2.8 Recensioni reali: dei comparabili e del genere (per la Sezione B)

Raccoglile **ora**: servono già all'Ondata 1 del focus group, che arriva subito dopo l'audit. Servono due letture, non una: cosa dicono sui **tuoi comparabili** e cosa dicono sui **giochi dello stesso tipo**, perché le critiche del genere valgono spesso anche per te. Prima scrivi `launch/_raw/my_features.json` con le caratteristiche del tuo gioco (dal brief e dal GDD): `{"cucina": "cook|recipe|kitchen", "co-op": "co-?op|with friends"}`. Poi:

```bash
python3 <skill>/scripts/research/review_corpus.py --comps <appid_comparabili...> --genre-tag <Tag> [<Tag>...] \
  --max-genre-games 20 --my-features launch/_raw/my_features.json \
  -o launch/_raw/corpus.json --md launch/_raw/corpus.md --csv launch/_raw/corpus_features.csv
```
Produce, da migliaia di recensioni reali con data, ore di gioco e URL: temi **puniti** e **premiati** per comparabili e per genere (percentuale media e in quanti giochi compaiono) e, per ogni caratteristica del tuo gioco, quanto è citata nelle negative contro le positive (premiata, punita, divisiva, poco discussa) con le recensioni più utili da leggere e parafrasare. Riporta sempre quante recensioni e quanti giochi, e i limiti (campione non casuale, parole chiave in inglese). I dettagli per singolo gioco (rimborsi, poche ore) si ottengono con `steam_reviews.py` (`04-focus-group.md`, 7.2).

### 2.9 Pagina store e trailer dei comparabili (benchmark veri)

```bash
python3 <skill>/scripts/research/store_bench.py run --ids-file launch/_raw/ids.txt --frames-dir launch/_raw/hooks \
  -o launch/_raw/store_pages.json --md launch/_raw/store_bench.md
```
Misura in automatico, per ciascun comparabile: lunghezza della descrizione breve e lunga, GIF, immagini, screenshot, numero e **durata dei trailer**, lingue, achievement, demo; con `ffmpeg` anche tempo al primo taglio, tagli nei primi 5 secondi e lunghezza media dell'inquadratura, più fotogrammi a 0/2/5/10/20/30 s. Poi quartili, confronto tra i migliori (per recensioni all'anno) e il resto, e correlazioni di rango. Guarda tu i fotogrammi per giudicare l'hook: lo strumento misura il ritmo, non capisce cosa è un buon inizio. Alimenta le Fasi 6 e 6B al posto delle soglie di opinione. Con pochi comparabili le correlazioni sono indizi, non prove.

`sources.md`: una riga per fonte, con URL, data di consultazione e a quale numero o regola serve.

---

## FASE 2B: posizionamento e differenziazione

Output: **`launch/01b-positioning.md`**. È il filtro più importante: se il gioco non si distingue, il resto dell'analisi pesa meno.

1. **Pitch in una frase** (max 25 parole, anche in inglese): "[Gioco] è un [genere] in cui [azione centrale] per [emozione o promessa], a differenza di [alternativa]". Deve essere compreso da uno sconosciuto in 5 secondi.
2. **Giocatore bersaglio in una riga** e dove si trova (community, creator, festival).
3. **Tre differenziatori reali.** Ognuno deve superare 4 prove, con evidenza dal progetto o dai comparabili:
   - **Vero oggi**: esiste nella build, non è una promessa del GDD.
   - **Visibile**: si capisce da uno screenshot o da una clip di 5 secondi.
   - **Rilevante**: compare nelle recensioni positive o nelle richieste dei giocatori dei comparabili.
   - **Non scontato**: i comparabili non lo hanno, o lo fanno peggio, e non è copiabile in un mese.

   Distingui un **differenziatore** da una *feature* (ce l'hanno tutti) e dal *polish* (qualità, non identità). Se ne trovi meno di tre, scrivilo.
4. **Test "perché dovrei giocarlo invece di [comparabile]?"**: per ognuno dei 3 comparabili più vicini scrivi, dal punto di vista di un giocatore scettico, la risposta in due frasi. Voto: **[PASS]** (ragione vera, chiara, visibile), **[MARGINAL]**, **[FAIL]**.
5. **Test del twist**: se il gioco si descrive come "X incontra Y", verifica che Y cambi davvero il modo di giocare e non sia solo estetica.
6. **Mappa di posizionamento** testuale su due assi rilevanti per il genere (complessità/accessibilità, tono, ritmo): comparabili contro il gioco, lo spazio libero e se qualcuno lo vuole.
7. **Esito e conseguenze**:
   - **PASS**: procedi.
   - **MARGINAL**: il primo intervento dei 14-20 giorni è rafforzare un differenziatore e rifare il test. Il verdetto non può essere verde.
   - **FAIL**: il verdetto non può essere verde. Le proiezioni delle Fasi 5 e 7 sono marcate **"condizionate alla differenziazione"** e lo scenario pessimistico diventa il caso base. La TODO n. 1 è "rifare il posizionamento": opzioni (cambiare o restringere il twist, nicchia più stretta, genere adiacente, scope ridotto e uscita piccola a prezzo basso), con ore e test per verificarle. Niente outreach né ads finché il test non è ripetuto.
8. **Test di comprensione del pitch** (usato in Fase 7): ai tester si dà solo il pitch e si chiede di riformularlo; la percentuale che lo riformula correttamente misura la chiarezza.

### TODO di fine fase
Ogni file termina con TODO nel formato di `references/06-synthesis-output.md`.
