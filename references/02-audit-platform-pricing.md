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
Le aliquote (quota Steam, IVA/sales tax, rimborsi, sconto medio, imposte locali) sono **input dichiarati [DA VERIFICARE]** con fonte nel report, non fatti dello script. I prezzi e le fasce di successo del genere vengono da `genre_bench.py` (fasce di prezzo).

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

Ogni file termina con TODO nel formato di `references/06-synthesis-output.md`.
