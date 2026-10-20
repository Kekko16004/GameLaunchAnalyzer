# Fasi 3, 4, 5: audit dev, piattaforme e calendario, prezzo

---

## FASE 3: audit dev e pilastri di genere

Output: **`launch/01-dev.md`**. La profondità dipende dalla fase: per *Idea/Concept* valuta coerenza, rischio di scope e differenziazione e salta il game feel; da *Prototipo* in su valuta anche l'esperienza di gioco. Senza build giocabile dichiara che il game feel non è valutabile.

### A. Primi 10 minuti (prima impressione)
- Un giocatore senza istruzioni capisce cosa fare entro 30 secondi?
- Tempo alla prima scelta significativa (obiettivo dalla tabella soglie in `playbooks.md`).
- Dove nascono attrito, frustrazione inspiegata, disorientamento?
- Leggibilità (contrasto, outline, UI), camera, comandi, tutorial, **game feel** (screenshake, audio feedback, hitstop, animazioni di conferma).
- **Asimmetria del feedback**: cosa succede quando il giocatore fa bene rispetto a quando sbaglia? Se l'errore è spettacolare e il successo è muto, il gioco non gratifica.

### B. Matrice dei pilastri del genere (obbligatoria)
**La domanda zero decide come si vota** (beta o gioco completo, vedi `00-intervista.md`; è scritta in `00-brief.md` e in `status.json` come `product`):
- **Beta / demo / vertical slice**: un pilastro è **PASS** se la build lo dimostra già, anche con poco contenuto; è **MARGINAL** se lo si intravede ma regge solo con il contenuto previsto; è **FAIL** solo se manca o funziona male nella parte che c'è. Il contenuto che nel piano del gioco completo esiste ma nella beta no **non è un FAIL: è un gap** da elencare nella Fase 10B, con le ore per colmarlo.
- **Gioco completo / post-lancio**: si vota quello che il giocatore compra. Contenuto mancante, bug e rifinitura contano per intero.
- **Beta gratuita = assaggio che deve vendere il gioco finale.** Aggiungi alla matrice un pilastro trasversale **"Spinta all'acquisto"**: la beta lascia con la voglia di avere il resto? Controlla: (a) il gancio e il loop reggono oltre la prima sessione e danno un motivo per tornare; (b) c'è un finale di beta o un punto di arrivo che chiude senza saziare (cliffhanger, promessa di ciò che manca); (c) la beta mostra almeno un momento "voglio di più" (la meccanica più forte, un boss, una scelta) e non regala l'intero valore del gioco finale; (d) c'è un invito concreto alla wishlist o alla mailing list nel punto di massimo entusiasmo (non all'avvio); (e) niente che faccia sembrare il prodotto finale già finito o già visto. PASS solo con almeno (a), (b) e (d).
- Scrivi sempre nella tabella a quale dei due metri è stato applicato.

Prendi i pilastri dal playbook. Per ognuno: **[PASS]**, **[MARGINAL]** o **[FAIL]**, motivazione concreta, **evidenza** (file, scena, screenshot, riga di codice) e costo in ore per portarlo a PASS.

| Pilastro | Voto | Evidenza | Ore per PASS |
|---|---|---|---|

Chiudi con il punteggio pilastri (n PASS / totale) e i **3 pilastri più deboli per impatto commerciale**.

### C. Scope, qualità tecnica e Steam readiness
- Framerate con scena carica, caricamenti, memoria, crash, hardware minimo.
- Controller e Steam Deck senza mouse obbligatorio.
- Steamworks: cloud save, achievement, overlay.
- Telemetria essenziale per i playtest (retention, punti di abbandono, durata sessione), nel rispetto del GDPR se si raccolgono dati.
- **Feature a rischio da tagliare** contro il feature creep: per ogni taglio, ore risparmiate e impatto atteso sul divertimento.
- Accessibilità di base (sottotitoli, rimappatura tasti, opzioni per daltonici): pesa spesso sulle recensioni.

**Subito dopo la Fase 3 parte l'Ondata 1 del focus group** (`04-focus-group.md`), con segnalazione dei problemi all'utente. Le fasi seguenti (4, 5, 6, 6B) si eseguono dopo; quelle che dipendono dal prodotto si rivedono se i fix cambiano qualcosa.

---

## FASE 4: Steam, itch.io, demo e calendario

Output: **`launch/02-platform.md`** e **`launch/calendar.md`**.

1. **Strategia demo e festival.** La demo è la valuta principale di Steam per molti generi, non per tutti (alcuni generi narrativi o a sorpresa la soffrono: vedi playbook). Decidi tra demo permanente, demo a tempo per Next Fest, playtest chiuso o niente demo, e motiva.
   - **Verifica le date del prossimo Steam Next Fest e le sue regole** (partecipazione ripetuta, scadenze di iscrizione e di review della build, requisiti della demo) su fonti ufficiali (Steamworks, annunci Valve) con ricerca web, non a memoria. Mesi e regole cambiano.
   - Calendario a ritroso con buffer: pagina Coming Soon attiva con anticipo sufficiente (intervallo da playbook e post-mortem), build demo inviata a Valve con margine, giorno di lancio che eviti uscite grandi del genere.
2. **itch.io vs Steam.** itch per test precoci con alpha/beta tester senza bruciare il primo impatto su Steam; il traffico caldo va convogliato verso la wishlist Steam. Se l'obiettivo è itch-first, adatta il piano (revenue share, bundle, jam, devlog).
3. **Cancelli Go / No-Go prima di pagare la fee di Steam Direct.**
   - **Gate 0, posizionamento**: la Fase 2B non è in FAIL.
   - **Gate A, qualità percepita**: punteggio wishlist del focus group (Fase 7) sopra la soglia. Default **35 [OPINIONE]** (il punteggio non è una percentuale, vedi formula in `04-focus-group.md`), oppure 80% del punteggio del comparabile di successo usato come controllo, minimo 30. Conta l'**ultima ondata**; la timeline mostra se il punteggio sale dopo i fix. Regolabile e motivato. È un filtro, non una garanzia.
   - **Gate B, test reale**: data fissata per un test con almeno **20 tester esterni** che non conoscono il team (kit in Fase 9). Soglie di default **[OPINIONE]**: sessione media sopra la durata minima del genere (tabella soglie, default 25 minuti) e almeno il 50% che inizia spontaneamente una seconda sessione.
   - **Gate C, capsule**: la capsule passa lo scroll test in almeno due round con persone esterne. Un'ondata del focus group con le capsule nuove è un pre-test utile, non sostituisce le persone vere.
   - Se un gate fallisce: non pagare, scrivi quale azione lo sblocca e quando ripetere il test.
3b. **Finestra di lancio e concorrenti** (`launch_window.py`): la data non si sceglie nel vuoto. Metti in `launch/window.csv` ciò che pesa attorno alla data (`launch_window.py add --date … --name … --kind competitor|big_release|festival|sale|holiday --weight 1-5 --source …`): i rivali già seguiti con `watchlist.py` entrano da soli; grandi uscite, festival e saldi li aggiungi tu con la fonte e la data di lettura (per le uscite in arrivo vedi `steamdb_assist.py links`; date dei saldi e dei festival **[DA VERIFICARE]** su fonti ufficiali). Poi `launch_window.py plan --launch <data> --md launch/window.md -o launch/_raw/window.json`: dà il punteggio di affollamento per settimana, le 5 settimane più tranquille e dove cade la data scelta. Se la settimana è affollata, riapri la scelta della data con l'utente (non cambiarla in silenzio) e scrivi nel calendario il piano B. Il punteggio è un'euristica [OPINIONE] e vale solo per ciò che è in lista.
3c. **Calendario ufficiale degli eventi Steam** (`steam_events.py`). Saldi stagionali, Next Fest e fest a tema pesano sulla data più di quasi tutto il resto: non si scrivono a memoria.
   - `steam_events.py fetch` legge la pagina pubblica di Valve (https://partner.steamgames.com/doc/marketing/upcoming_events) e le pagine delle edizioni del Next Fest; se la pagina non si legge usa il file curato `scripts/research/data/steam_events_fallback.json` e lo dice. Date non pubblicate = **[DA VERIFICARE]** con lo schema abituale ("Summer Sale di solito fine giugno - inizio luglio"), mai un giorno inventato. `list` per vederle, `export-window --csv launch/window.csv` per metterle nella finestra di lancio (`launch_window.py plan` le conta comunque da solo).
   - `steam_events.py deadlines --launch-dir launch --launch <data EA o 1.0>` scrive in `calendar.md` e `TODO.md` i passi 👤 datati: iscrizione al Next Fest scelto (di default l'ultimo prima dell'uscita) con le scadenze Valve (trailer, revisione della demo, press preview), i fest a tema compatibili con i tag della pagina (`store_kit.json`) e gli avvisi sui saldi. `top_moves.py` propone "iscriviti al fest X entro Y" quando mancano meno di 45 giorni.
   - **Regole** [FATTO Valve, lette il 2026-10-17; OPINIONE dove scritto]: (1) **mai uscire dentro un saldo stagionale o un Next Fest** (il negozio è occupato dall'evento; va bene la settimana prima o dopo [OPINIONE, Zukowski 2023]); (2) per scontare il gioco in un saldo stagionale bisogna essere usciti da **almeno 30 giorni** (vale anche per l'uscita in EA): conta la data rispetto al saldo successivo; (3) un gioco entra in **un solo Next Fest**, serve pagina pubblica e demo, si esce dopo la fine del fest; demo in revisione 5 settimane prima per la press preview, 3 settimane prima per il fest; (4) i **fest a tema** sono visibilità gratis anche per Coming Soon e demo: l'invito arriva per email se tag e pagina corrispondono al tema (controlla i tag ~6 settimane prima, la scadenza tipica); mai aggiungere tag non veri per entrare.
3d. **Coming Soon lungo o Next Fest? La regola pratica dalle prove** (letto il 2026-10-17; dettaglio e fonti nel `launch/wishlist-strategia-*.md` del progetto che l'ha prodotta).
   - **Non è una scelta: servono entrambi, in quest'ordine.** Nel nostro dataset (950 nuove uscite giugno-luglio 2026, 237 di fascia B, recensioni a 30 giorni) i B con **Next Fest + almeno 180 giorni pubblici prima dell'uscita** arrivano a ≥ 50 recensioni (~1.750 copie) nell'84 % dei casi (n = 31), contro il 45 % con Next Fest e meno di 180 giorni (n = 22) e il 24 % senza Next Fest (n = 178). Correlazione, non causa: chi fa il Next Fest e tiene la pagina a lungo di solito ha anche più cura, soldi o publisher. [FATTO sul campione]
   - **Il Next Fest moltiplica quello che porti**: il guadagno del fest cresce con le wishlist che hai all'ingresso (Spearman 0,825, Zukowski su 182 giochi, feb 2026; mediana 322 sotto le 1.000, 1.006 tra 1.000 e 9.999). Quindi pagina presto, demo **prima** del fest (circa 2,5× wishlist), e **l'ultimo Next Fest prima dell'uscita**. [OPINIONE con dati auto-dichiarati]
   - **Lunghezza della pagina**: almeno ~6 mesi (Valve via Zukowski 2023: +300 % di vendite contro 30 giorni; Valve: "nessun grosso svantaggio" a tenerla a lungo, salvo se il gioco cambia molto). Oltre l'anno non aiuta di per sé: GameDiscoverCo (ott 2025) trova che i giochi che convertono peggio stavano su Steam in media 411 giorni contro 214 dei migliori (crescita organica lenta = poco interesse).
   - **Dopo il fest**: la data di uscita esatta va fissata in Steamworks **circa 2 mesi prima** (il calendario personale di Steam, sulla home da giugno 2026, porta wishlist nelle settimane prima dell'uscita, per Zukowski 300-3.000 al giorno ai giochi che ci entrano; "Popolari in arrivo" ora chiede ~100.000 wishlist). Non serve uscire 2 settimane dopo il fest per tenere "fresche" le wishlist: l'età non le svaluta in modo misurabile (A Song of Iron via Zukowski); contano il totale, i saldi da evitare e la regola dei 30 giorni.
   - **Soglie** [OPINIONE, Zukowski]: prime 2 settimane di pagina, Bronze 23-68 / Silver 79-441 / Gold 134-1.575 (benchmark 2026); ≥ 2.000 all'ingresso del Next Fest; ≥ 7.000 prima di uscire (anche in EA). Le wishlist valgono circa la metà di qualche anno fa (Zukowski, 13/10/2026: vendite del primo mese per wishlist dimezzate tra 2020-22 e 2023-25) e la prima settimana vende in mediana 0,10-0,15× le wishlist (GameDiscoverCo, ott 2025): ricalcola gli scenari con questi numeri.
   - **Il fattore fortuna esiste ma è raro e quasi mai cieco**: nel dataset, dei B/C con ≥ 500 recensioni a 30 giorni (29) solo 4 erano "piatti" (niente demo, Next Fest, playtest, pagina sotto i 90 giorni) e tutti avevano un publisher o erano gratuiti; dietro le "esplosioni" ci sono quasi sempre un video grande di un creator, Shorts virali dello sviluppatore o un franchise. Non si pianifica sulla fortuna: si prepara il terreno (pagina, link, mailing list) perché, se arriva, non vada sprecata.
3e. **Checklist dagli errori di Zukowski** ("60 Game Marketing Mistakes", Chris Zukowski, 2023, howtomarketagame.com) [OPINIONE]. Quelli già coperti altrove (trailer, capsule, genere chiaro, demo, Next Fest, lingue, follow-up dei creator, sconti) restano dove sono; questi mancavano:
   - prevedi **3 settimane** per far approvare la pagina Coming Soon (e i trailer montati da altri richiedono mesi);
   - **prima di qualsiasi post** esistono mailing list o Discord e il link alla pagina Steam: un post virale senza destinazione è perso;
   - fai dell'apertura della pagina un **annuncio** ("announcement trailer", post "annunciamo"), non una pubblicazione silenziosa;
   - **un evento/notizia Steam almeno ogni 3 settimane**, che parla del gioco (come si gioca, nemici, livelli), con titoli che incuriosiscono, mai "Update #11";
   - **conto alla rovescia** per ogni momento grosso (pagina, demo, fest, uscita, saldi): una settimana prima, 3 giorni, 1 giorno, il giorno, 3 giorni dopo, l'ultimo giorno e 8 ore prima della fine;
   - **Tag Wizard una volta al mese** (i giocatori aggiungono tag sbagliati);
   - non preoccuparti delle **wishlist cancellate** (10-12 % è normale, salgono durante i saldi) né del **tasso di clic** (scende quando Steam ti mostra di più): guarda le wishlist;
   - **segna la causa di ogni picco** di wishlist (chi, quale video) nel tracker, per ricontattarli al lancio (`wl_track.py add --note`);
   - **candidati a tutti i festival** di terzi in tema (decidono gli organizzatori), e una settimana prima scrivi all'organizzatore per verificare di esserci;
   - nel Next Fest **usa le dirette in evidenza** (gli slot di streaming in cima alla pagina);
   - **ignora le richieste di chiavi** non sollecitate (rivenditori); ai creator scelti manda la chiave subito, senza "rispondi e te la mando";
   - **un solo account social e Discord per lo studio**, non uno per gioco; il canale tuo vero è la mailing list;
   - inviti all'azione **diretti e brevi** ("Wishlist now") in ogni post, email e video;
   - obiettivo esplicito delle **prime 10 recensioni** (il badge compare a 10; le chiavi gratis non contano);
   - dopo l'uscita sconti **a gradini** (mai sotto il 20 % nei primi 6 mesi, poi 30-40-50 %), ≥ 20 % per far partire le email ai wishlister;
   - per la ricerca di genere guarda **tutte** le uscite dell'anno, non solo i campioni (lo fa già `cohort_bench.py`).
4. **Roadmap a ritroso con date assolute**: gate test, pagamento Steam Direct (solo se i gate passano), pubblicazione della pagina, date Next Fest con deadline di iscrizione e di invio build, data di lancio proposta, finestra di saldi successiva.
5. **Primi 14 giorni di lancio** (Steam premia la velocità iniziale): chi viene avvisato, quando, con quali asset, e piano B se la prima settimana va sotto le attese (aggiornamento di contenuto, DLC gratuito, evento a tema).
6. **Calendario dei tripwire e delle ondate**: inserisci in `calendar.md` le date in cui misurare i segnali d'allarme del pre-mortem (Fase 7B) e le **ondate del focus group proposte** (dopo i fix, dopo le capsule, prima di Next Fest, prima di pagare Steam Direct, pre-lancio): ognuna parte solo con l'ok dell'utente.

7. **Tracker delle wishlist** (appena la pagina Coming Soon è online): Steam non pubblica le wishlist, quindi si registrano a mano da Steamworks una volta a settimana. Crea il piano con scenari, data di lancio e tripwire del pre-mortem, poi aggiorna e controlla:

   ```bash
   python3 <skill>/scripts/research/wl_track.py plan --launch <AAAA-MM-GG> --start <data pagina> --econ launch/_raw/econ.json \
     --tripwire "<data>:<soglia>:<segnale>:<azione di emergenza>" --event "<data>:Next Fest" -o launch/_raw/wl_plan.json
   python3 <skill>/scripts/research/wl_track.py add --wishlists <totale> --followers <n> --note "<cosa è successo>" --csv launch/wishlists.csv
   python3 <skill>/scripts/research/wl_track.py status --md launch/wishlist-status.md --json launch/_raw/wl_status.json
   ```
   `status` confronta con i percorsi degli scenari e con i tripwire, segnala rallentamenti, cali, dati vecchi e picchi non annotati, e **esce con codice 2 se un tripwire è scattato**. Quando succede, riporta all'utente l'ALLARME con l'azione di emergenza del pre-mortem, senza minimizzare. I percorsi sono lineari: una semplificazione **[OPINIONE]**.

### Early Access o lancio 1.0 (beta gratuita → Early Access a pagamento → 1.0)

Da decidere **prima** di fissare calendario, prezzo e Next Fest, quando il proprietario pensa a un percorso "beta gratis, poi accesso anticipato a pagamento, poi 1.0". Le domande vengono dal Round R-D (`00-intervista.md`); qui ci sono i criteri, le regole e i numeri.

**Criteri per scegliere** [OPINIONE, da pesare con il proprietario]:
| Criterio | Va bene per l'EA se… | Meglio aspettare la 1.0 se… |
|---|---|---|
| Capacità contro lavoro che resta | il team ha ore a settimana stabili per 12-24 mesi di aggiornamenti | le ore bastano solo per finire, non per aggiornare in pubblico |
| Contenuto all'uscita in EA | c'è già un gioco che vale il prezzo **oggi**: varie ore di contenuto, un ciclo completo, pochi bug | c'è una fetta (un atto, una mappa) che si "finisce" in meno di 2 ore |
| Il motivo principale per comprare | è già dentro all'uscita in EA (es. la co-op, se il pubblico compra per giocare con gli amici) | arriva solo più avanti: chi compra per quello lo cerca subito e rimborsa |
| Roadmap onesta | si può promettere poco e mantenere; le date sono larghe | il gioco "vero" esiste solo nella roadmap |
| Community | qualcuno può rispondere ogni settimana a recensioni, Discord e segnalazioni | nessuno ha tempo per la community durante lo sviluppo |

**Regole di Valve** (leggi le pagine ufficiali e scrivi la data di lettura; ultima verifica di questa skill: **[FATTO] letto 2026-10-09**; rileggile a ogni uso):
- L'Early Access si vende **per quello che il gioco è adesso**: niente promesse di funzioni future come motivo d'acquisto. Fonte: https://partner.steamgames.com/doc/store/earlyaccess
- Il **Next Fest** è per giochi **non ancora usciti**: un gioco uscito in Early Access non può più partecipare. Quindi il Next Fest va fatto **prima** dell'uscita in EA. Fonte: https://partner.steamgames.com/doc/marketing/upcoming_events/nextfest
- Un gioco in EA **non ha di nuovo la visibilità del lancio** fino alla 1.0, e anche alla 1.0 la spinta è più piccola di quella dell'uscita in EA. Fonte: pagina Early Access sopra.

**Numeri** (GameDiscoverCo, dicembre 2025, https://newsletter.gamediscover.co/p/the-state-of-steam-early-access-graduates, **[FATTO] letto 2026-10-09**; i rimborsi da GameDiscoverCo 2025-02-04):
- dei 225 giochi usciti dall'EA che avevano venduto più di 5.000 copie in EA, **solo il 20 %** ha incassato di più nel mese della 1.0 che nel primo mese di EA;
- **mediana: il mese della 1.0 incassa il 40 %** del primo mese di EA (è il default di `calc_econ.py --full-vs-ea`);
- **durata mediana dell'EA: 437 giorni**;
- **rimborsi**: circa 12 % in EA contro circa 8 % alla 1.0.

**Conseguenza: l'uscita in EA è IL lancio.** Va preparata come una 1.0: pagina Coming Soon presto, wishlist, Next Fest prima, creator, trailer, prezzo. La 1.0 è una seconda spinta più piccola, non un secondo lancio.

**Prezzo tipico**: più basso in EA, alzato alla 1.0, e **detto chiaramente sulla pagina** fin dall'inizio ("il prezzo salirà alla 1.0"); chi compra presto si sente premiato. Calcolalo con `calc_econ.py --ea-price <prezzo EA> --full-price <prezzo 1.0>` (sezione "Accesso anticipato" del piano economico).

**Beta o demo gratuita + EA**: la beta gratuita (itch) o la demo Steam servono a raccogliere wishlist e a far provare il gioco; l'EA è il prodotto che si paga. Le due cose stanno insieme se la demo/beta è **una parte chiara** (es. il primo atto) e l'EA aggiunge abbastanza da valere il prezzo dal primo giorno. Ordine consigliato: beta/demo → Next Fest (con la demo) → uscita in EA → aggiornamenti → 1.0.

**Calendario**: se si sceglie l'EA, in `calendar.md` compaiono questi passi (formato sotto): pagina Steam con la sezione "Early Access" compilata (perché EA, quanto dura, cosa c'è adesso, cosa arriverà, prezzo), **Next Fest prima dell'EA**, uscita in EA, roadmap pubblica, aggiornamenti periodici, annuncio del prezzo che sale, **1.0**.

### Il calendario: `launch/calendar.md` (dettagliato, a passi, con chi fa cosa)

Non basta una tabella di date. Il calendario è il documento che l'utente segue giorno per giorno, quindi ha **quattro parti**:

1. **Decisioni e ipotesi** in testa (citazione): obiettivo scelto dal proprietario (intervista), ipotesi usate, fonte e data di verifica delle date Steam.
2. **Date fisse** (tabella `Data | Evento | Tipo | Fonte e data di verifica`): ancore non spostabili (iscrizioni, scadenze di revisione, inizio del festival, saldi da evitare). Tipo: `gate`, `scadenza`, `tripwire`, `ondata`, `lancio`.
3. **Piano a ritroso** (tabella `Quando | Cosa | Note`): lavoro tra un'ancora e l'altra, con margini di sicurezza e il **perché** di ogni vincolo.
4. **Passi in ordine** (sotto), il cuore: numerati, per fasi, ciascuno con il proprietario del passo.
5. **Piano B**: cosa cambia se un gate fallisce o una scadenza salta.

#### Passi in ordine (formato letto da `plan_steps.py` e dalla pagina HTML)

```markdown
## ✅ Passi in ordine
🤖 le faccio io (Claude). Quelle segnate 👤 le fai tu
### FASE 1 — Adesso (ottobre)
1. [ ] 👤 **Crea il modulo di feedback**: apri `tools/release/community/feedback-form-EN.md` e segui le istruzioni in cima (~20 min). · 📅 2026-10-20
2. [ ] 👤 **Mandami il link del modulo** (e quello d'invito del Discord). · 📅 2026-10-22
3. [ ] 🤖 Lo collego al pulsante Feedback della beta, alla pagina itch e al Discord.
### FASE 2 — Inizio novembre: test con persone vere
4. [ ] 👤+🤖 **Pagina itch** in bozza. · 📅 2026-11-10
   nota opzionale su una riga indentata
```

Regole:
- **Ogni passo ha un proprietario:** 👤 lo fa l'utente, 🤖 lo fa Claude, 👤+🤖 insieme. I passi 🤖 che toccano il prodotto o pubblicano qualcosa riportano "(solo con il tuo ok)" (regola 8 e 14 di `SKILL.md`).
- **I passi 👤 spiegano come:** quale file aprire, cosa produrre, quanto tempo richiede (~20 min), perché conta. Niente "gestire la community": un'azione che si può spuntare.
- **Scadenza `· 📅 AAAA-MM-GG`** su ogni passo 👤 e sui passi con data fissa; derivata dalle ancore e dalla capacità del team (ore a settimana dall'intervista).
- **Fasi con titolo e periodo** ("FASE 3 — Metà-fine novembre: Steam"), ordinate nel tempo; l'ultima può essere "Dopo (marzo 2027 →)".
- **Copri l'intero percorso:** ricerca e decisioni (gate, soldi, accordo tra soci, commercialista), prodotto (🤖 con ok), materiali (capsule, trailer, pagine: vedi `store_kit.json`), community e creator, pagine itch e Steam, demo e Next Fest, metriche da registrare (`wl_track.py`, `metrics_track.py`), ondate del focus group (con ok), lancio e dopo.
- **Se c'è l'Early Access**, i passi chiave hanno nomi chiari e una data: `**Pagina Steam con la sezione Early Access**`, `**Next Fest con la demo (prima dell'EA)**`, `**Uscita in Early Access**`, `**Roadmap pubblica**`, `**Annuncio: il prezzo sale alla 1.0**`, `**Uscita 1.0**`; i tripwire di wishlist si misurano prima dell'uscita in EA, non della 1.0.
- **Controlla** con `plan_steps.py check`; durante il lavoro usa `plan_steps.py next --owner me` (cosa tocca all'utente), `done N` (spunta) e `summary`.

```bash
python3 <skill>/scripts/research/plan_steps.py check
python3 <skill>/scripts/research/plan_steps.py next --owner me --limit 5
python3 <skill>/scripts/research/plan_steps.py done 2 3
```

---

## FASE 5: prezzo, economia e proiezioni

Output: **`launch/03-pricing.md`**.

1. **Analisi prezzo**: distribuzione prezzi dei comparabili con oltre 100 recensioni (da `comps.csv`), rapporto prezzo/contenuto per il genere, tre proposte argomentate (**consigliato**, **penetrazione**, **premium**) con sconto di lancio conforme alle regole Steam **[DA VERIFICARE]**. Considera i prezzi regionali.
Esegui il calcolo con lo strumento, così le cifre si riproducono e si rifanno in un secondo quando cambia un prezzo o un'aliquota (il calcolo resta leggero: un comando, una tabella):

```bash
python3 <skill>/scripts/research/calc_econ.py --price <prezzo> --costs <costi_cassa> --hours <ore> --hourly <tariffa> --partners <n> \
  --wishlists <pess,base,ott> --conv 0.10,0.20,0.30 --md launch/03-pricing-calc.md -o launch/_raw/econ.json
```
Le aliquote (quota Steam, IVA/sales tax, rimborsi, sconto medio, imposte locali) sono **input dichiarati [DA VERIFICARE]** con fonte nel report, non fatti dello script. I prezzi e le fasce di successo del genere vengono da `genre_bench.py` (fasce di prezzo). Lo scenario prudente parte dal base rate di `cohort_bench.py` (FASE 2.0b): cosa vende un gioco di fascia B a quel prezzo dopo ~3 mesi, non cosa vendono i comparabili famosi. Con la calibrazione presente, `calc_econ.py ... --calibration --tier B` aggiunge accanto ai tre scenari da wishlist quattro scenari dal mercato reale (p25, mediana, p75, p90 delle copie della fascia, al prezzo se il gruppo ha almeno 30 giochi), con la data dei dati; gli scenari da wishlist restano.

**Metro oggettivo e mosse.** Le leve di `cohort_bench.py score` (quanto cambia la probabilità di superare 1.000 copie aggiungendo trailer, demo, Next Fest, lingue, mesi di Coming Soon…) entrano in `top_moves.py`, che le scrive in `TODO.md` e `calendar.md` come passi datati. Gli scenari di vendita restano tre (da wishlist) più quattro dal mercato reale; il metro dà la fascia più probabile, mai una cifra sola.

**Cosa hanno fatto i B che vendono, e in che ordine.** Se `calibration.json` ha la sezione `marketing` (da `market_tracker.py social` sui giochi B del dataset), riporta nel piano la tabella vincenti / perdenti: notizie Steam prima dell'uscita, demo e Next Fest, giorni tra il primo trailer e l'uscita, video di creator e visualizzazioni, post Reddit, aggiornamenti nei primi 90 giorni. Usala per ordinare i passi del calendario (FASE 4), sempre come correlazione, mai come garanzia.

2. **Dal lordo al netto**, per copia, sempre con intervalli e fonte:

   ```
   netto_per_copia = prezzo_lordo
                     × (1 − quota_IVA_o_sales_tax)      # intervallo, varia per paese
                     × (1 − quota_rimborsi)             # [DA VERIFICARE] per il genere
                     × (1 − revenue_share_piattaforma)  # verifica la quota attuale
                     − imposte_e_contributi_locali      # dipende dal paese (Fase 10)
   ```
3. **Break-even**: `copie_necessarie = costi_totali / netto_per_copia`, dove i costi comprendono fee di Steam Direct, strumenti, licenze, marketing e **costo del tempo di sviluppo** (ore × tariffa, anche figurativa se l'obiettivo è viverne). Se l'obiettivo è portfolio o hobby, mostra comunque il numero ma non usarlo come criterio del verdetto.
4. **Tre scenari** (pessimistico, base, ottimistico):

   | | Pessimistico | Base | Ottimistico |
   |---|---|---|---|
   | Wishlist al lancio | | | |
   | Conversione anno 1 | | | |
   | Copie anno 1 | | | |
   | Ricavo lordo | | | |
   | Incasso netto | | | |
   | **Cosa deve essere vero** | | | |

   "Cosa deve essere vero" è concreto: es. "servono 8.000 wishlist al lancio, cioè circa N visualizzazioni di trailer e M visite alla pagina a un tasso di wishlist del X%" **[STIMA]**.
5. **Probabilità onesta** di superare il break-even, con intervallo e ragioni. Se è bassa, dillo e proponi come alzarla (scope ridotto, prezzo, genere adiacente, partner, funding).
6. Se la Fase 2B è in FAIL o MARGINAL, marca tutte le proiezioni **"condizionate alla differenziazione"** e usa lo scenario pessimistico come caso base.
7. **Collega gli scenari al tracker**: gli scenari di `econ.json` diventano gli obiettivi di wishlist al lancio del tracker (vedi Fase 4, punto 7).
8. **Con o senza publisher** (sempre se nell'intervista la risposta è "sì" o "non so"): `publisher_scout.py rank --game launch/_raw/publisher_game.json --live --econ launch/_raw/econ.json -o launch/_raw/publisher_scout.json --md launch/publisher-scout.md`. Il file dice, scenario per scenario, quanto resta da soli e con i due accordi tipici (solo marketing 30 %, accordo completo 50 % con anticipo e recupero delle spese) e **quante volte più copie deve vendere il publisher** perché convenga; poi la lista per fasce con la probabilità per invio **[STIMA]** e il prossimo passo. Il database (`data/publishers.json`) ha fonti e data per ogni publisher: `publisher_scout.py check` segnala le voci più vecchie di 180 giorni da riverificare. Niente "nessuno vi prende": se nessuno è realistico adesso, il file dice cosa sblocca i successivi (es. "demo pubblica + 2.000 wishlist").
9. **Casi reali alla nostra fase** (`case_studies.py`): prima di fissare i tripwire del Next Fest esegui `case_studies.py tripwires --entering <le soglie del calendario> --calendar launch/calendar.md -o launch/_raw/nextfest_expect.json`: scrive nella sezione Tripwire "entri con N → atteso +X … +Y" dal sondaggio (n alto) con accanto i casi auto-dichiarati simili, e `md -o launch/case-studies.md` per la tabella "cosa hanno fatto giochi come il nostro". I casi sono ottimisti per costruzione (chi va bene lo racconta): vale il sondaggio. I casi nuovi letti in post e post-mortem si aggiungono con `case_studies.py add` (sempre con URL e data).

Ogni file termina con TODO nel formato di `references/06-synthesis-output.md`.
