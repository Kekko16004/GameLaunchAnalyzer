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

---

## FASE 4: Steam, itch.io, demo e calendario

Output: **`launch/02-platform.md`** e **`launch/calendar.md`**.

1. **Strategia demo e festival.** La demo è la valuta principale di Steam per molti generi, non per tutti (alcuni generi narrativi o a sorpresa la soffrono: vedi playbook). Decidi tra demo permanente, demo a tempo per Next Fest, playtest chiuso o niente demo, e motiva.
   - **Verifica le date del prossimo Steam Next Fest e le sue regole** (partecipazione ripetuta, scadenze di iscrizione e di review della build, requisiti della demo) su fonti ufficiali (Steamworks, annunci Valve) con ricerca web, non a memoria. Mesi e regole cambiano.
   - Calendario a ritroso con buffer: pagina Coming Soon attiva con anticipo sufficiente (intervallo da playbook e post-mortem), build demo inviata a Valve con margine, giorno di lancio che eviti uscite grandi del genere.
2. **itch.io vs Steam.** itch per test precoci con alpha/beta tester senza bruciare il primo impatto su Steam; il traffico caldo va convogliato verso la wishlist Steam. Se l'obiettivo è itch-first, adatta il piano (revenue share, bundle, jam, devlog).
3. **Cancelli Go / No-Go prima di pagare la fee di Steam Direct.**
   - **Gate 0, posizionamento**: la Fase 2B non è in FAIL.
   - **Gate A, qualità percepita**: punteggio wishlist del focus group (Fase 7) sopra la soglia. Default **35 [OPINIONE]** (il punteggio non è una percentuale, vedi formula in `04-focus-group.md`), oppure 80% del punteggio del comparabile di successo usato come controllo, minimo 30. Regolabile e motivato. È un filtro, non una garanzia.
   - **Gate B, test reale**: data fissata per un test con almeno **20 tester esterni** che non conoscono il team (kit in Fase 9). Soglie di default **[OPINIONE]**: sessione media sopra la durata minima del genere (tabella soglie, default 25 minuti) e almeno il 50% che inizia spontaneamente una seconda sessione.
   - **Gate C, capsule**: la capsule passa lo scroll test in almeno due round con persone esterne.
   - Se un gate fallisce: non pagare, scrivi quale azione lo sblocca e quando ripetere il test.
4. **Roadmap a ritroso con date assolute**: gate test, pagamento Steam Direct (solo se i gate passano), pubblicazione della pagina, date Next Fest con deadline di iscrizione e di invio build, data di lancio proposta, finestra di saldi successiva.
5. **Primi 14 giorni di lancio** (Steam premia la velocità iniziale): chi viene avvisato, quando, con quali asset, e piano B se la prima settimana va sotto le attese (aggiornamento di contenuto, DLC gratuito, evento a tema).
6. **Calendario dei tripwire**: inserisci in `calendar.md` le date in cui misurare i segnali d'allarme del pre-mortem (Fase 7B).

Formato di `calendar.md`:

| Data (AAAA-MM-GG) | Evento | Tipo (gate / scadenza / tripwire / lancio) | Dipendenze | Verificato il |
|---|---|---|---|---|

---

## FASE 5: prezzo, economia e proiezioni

Output: **`launch/03-pricing.md`**.

1. **Analisi prezzo**: distribuzione prezzi dei comparabili con oltre 100 recensioni (da `comps.csv`), rapporto prezzo/contenuto per il genere, tre proposte argomentate (**consigliato**, **penetrazione**, **premium**) con sconto di lancio conforme alle regole Steam **[DA VERIFICARE]**. Considera i prezzi regionali.
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

Ogni file termina con TODO nel formato di `references/06-synthesis-output.md`.
