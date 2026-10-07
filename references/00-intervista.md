# Fase 0A: intervista sulle intenzioni (più round)

L'analisi serve a ciò che il proprietario **vuole davvero**, non a un gioco in astratto. Prima di produrre numeri, calendario e consigli devi capire intenzioni, vincoli, tolleranza al rischio e cosa non è negoziabile. Più round vanno bene: il risultato finale deve essere di qualità massima, non veloce.

Si esegue **dopo** la lettura del progetto (Fase 0, `01-discovery.md`) e **prima** di tutto il resto. Output: `launch/00-intenzioni.md` (registro delle decisioni) e il riassunto in `status.json` → `intentions`.

## Principi

1. **Non chiedere ciò che puoi leggere.** Prima ispeziona repo, README, GDD, store page, build. Chiedi solo ciò che sa soltanto l'utente: intenzioni, preferenze, rischio, limiti personali.
2. **Ogni domanda dice perché la fai** (una riga) **e cosa cambierà nel piano.** Niente domande retoriche, nessuna ripetizione.
3. **Dopo ogni round dai consigli** (formato sotto), non solo raccogli. L'utente risponde "ok" per accettare un default.
4. **Segnala le tensioni** tra risposte ("vuoi vivere di questo ma hai 5 ore a settimana e 100 € di budget") con gentilezza e con numeri, senza giudicare.
5. **Formato.** Se hai lo strumento di domande strutturate (AskUserQuestion) usalo: 2-4 opzioni, la tua raccomandata per prima con "(Recommended)", massimo 4 domande per chiamata, più chiamate nello stesso round. Altrimenti un blocco numerato (massimo 6 domande) con il default tra parentesi. Le domande aperte vanno in testo libero.
6. **Aggiorna il registro a ogni round** (`00-intenzioni.md`) e non perdere nulla: le risposte decidono soglie, date, canali, contingenze.
7. **Tono rilassato.** Nessuna fretta; ma ogni round ha un obiettivo chiaro e si chiude.

### Formato del consiglio (dopo ogni round)

```text
Ho capito: [2-3 righe, con le parole dell'utente].
Consiglio: [raccomandazione in una riga] [OPINIONE]
Perché: [2-3 punti con dati o ragionamento]
Alternativa: [cosa faresti se pesasse di più X]
Cosa rischi: [conseguenza onesta]
Tensioni che vedo: [se ci sono]
Ti chiedo ancora: [1-3 domande di approfondimento, o "nulla, passiamo oltre"]
```

## Domanda zero: beta o gioco completo? (sempre, per prima, in ogni modalità)

**Chiedila sempre**, anche in Rapida, Mirata, Aggiornamento e Ondata, a meno che il progetto o l'utente l'abbiano già detto in modo esplicito; in Aggiornamento riconferma ("è ancora una beta?"). Cambia come si valuta quasi tutto (tabella in `01-discovery.md`, Fase 0, punto 4). Registrala come prima riga di `00-intenzioni.md` e in `status.json` → `product`.

Domande, una alla volta, con il default tra parentesi:
1. **Che cosa valuto: una beta / demo / vertical slice, oppure un gioco completo?** (e se è già uscito: post-lancio)
2. *Se beta:* **hai già le TODO o il design del gioco completo** (GDD, roadmap, Atti, elenco di ciò che manca)? Se sì, **dove li trovo?**
3. *Se beta:* che cosa contiene rispetto al gioco completo (es. Atto I di 3)? A che cosa serve la beta: feedback, demo per Next Fest, itch, vendita in accesso anticipato?
4. *Se completo:* la build è feature-complete? Cosa manca? C'è una data di uscita già fissata?

**Se è una beta e il piano del gioco completo esiste:** procedi in tre tempi.
- **Tempo 1, analisi completa come beta.** Tutto il percorso (fasi, ondate, calendario, contingenze) valuta la beta per quello che deve dimostrare: il loop, il feel, i primi 10 minuti, la chiarezza del pitch, la prontezza al test e alla demo. Il contenuto che manca perché è nel piano **non** si penalizza: si registra come distanza dal gioco completo.
- **Tempo 2, domande sul gioco completo** (Round R-D, sotto): contenuti totali, cosa si aggiunge, durata, data, prezzo, accesso anticipato, co-op, rischi di scope, ore ancora necessarie.
- **Tempo 3, analisi rapida del gioco completo** (Fase 10B in `06-synthesis-output.md`): pilastri sul piano, scope contro capacità, prezzo e durata, rischio di recensioni, e **che cosa migliorare adesso nella beta** per arrivarci. Il verdetto sulla beta resta distinto da quello (provvisorio, a confidenza bassa) sul gioco completo.

Se è una beta **senza** piano del gioco completo: valuta come beta e dì chiaramente che il giudizio sul prodotto finale non è possibile; proponi di scrivere il piano (una pagina basta) prima della Fase 10B.

## Percorso per modalità

- **Completa**: domanda zero, round 1-7 sotto, più i round di verifica dei dati (R-A, R-B, R-C) e, se è una beta con piano del gioco completo, R-D.
- **Rapida**: un solo blocco di massimo 8 domande che condensa i round 1-5 (con default); **la domanda zero (beta o gioco completo) è sempre la prima**.
- **Mirata**: la domanda zero più le sole domande dell'area richiesta (es. canali per "solo creator", budget e prezzo per "solo prezzo").
- **Aggiornamento / Ondata**: riassumi `00-intenzioni.md` in 5 righe e chiedi **solo cosa è cambiato**.

## I round

### Round 1: obiettivi e successo
- Cosa significa "successo" per te, in numeri o fatti (copie, euro, wishlist, community, portfolio, lavoro, soddisfazione)? Quale risultato ti farebbe dire "ne è valsa la pena" e quale "è andata molto bene"?
- Perché questo gioco e perché adesso? Ci sono scadenze personali (fine studi, contratto, Next Fest)?
- Quanto pesano guadagnare, imparare, costruire un portfolio, divertirsi? In ordine.
- Dopo il lancio: aggiornamenti, DLC, seguito, un nuovo gioco, o chiudere?
- Tra data e qualità: se dovessi scegliere, cosa sacrifichi?
**Cambia:** soglie del verdetto (obiettivo vendite o portfolio), break-even, ambizione degli scenari, calendario.

### Round 2: capacità, tempo e persone
- Ore **reali** a settimana per ciascuna persona (non quelle ideali) e periodi di stop prossimi.
- Chi fa arte, codice, marketing, amministrazione? Chi decide se non siete d'accordo?
- Esperienza di marketing e community che avete già (pubblico, account, newsletter).
- Comfort a esporsi: video con la faccia, streaming, scrivere post, rispondere in pubblico.
- Uso di AI nel gioco (codice, asset, testi) e posizione sulla dichiarazione pubblica.
- Lingue in cui potete comunicare con la community.
**Cambia:** verifica di capacità delle TODO, mix di canali, quali passi sono 👤 e quali 🤖, disclosure.

### Round 3: soldi, rischio e regole personali
- Budget in cassa, tetto massimo di perdita accettabile, cosa è già stato speso.
- Steam Direct: pagare presto per iniziare a raccogliere wishlist o solo dopo i gate?
- Pubblicità e creator a pagamento: mai, dopo i gate, subito? Chiavi gratuite ai creator?
- Prezzo: filosofia (accessibile, premium, early access), tolleranza agli sconti, prezzi regionali.
- Soci e ricavi: c'è un accordo scritto? Paese e inquadramento fiscale, commercialista già trovato?
- Rischio: lanciare presto e iterare, oppure aspettare un prodotto lucido? Early Access sì o no?
**Cambia:** ordine di pagamento nel calendario, uso del budget, prezzo, tripwire, contingenze economiche.

### Round 4: canali, community e stile
- Dove volete stare (TikTok, Shorts, YouTube, Reddit, Discord, itch.io, devlog) e dove non andrete mai.
- Frequenza di contenuti sostenibile per davvero; moderazione di un Discord.
- Voce e tono del gioco e delle comunicazioni; temi sensibili.
- Feedback: quanta critica volete ricevere, da chi (sconosciuti o amici), come reagirete.
- Piattaforme e formati: Steam-first o itch-first, demo, Next Fest, console in futuro.
**Cambia:** piano creator e community, kit del test reale, testi dello store, calendario dei contenuti.

### Round 5: prodotto, visione e non negoziabili
- Cosa del gioco non cambiereste mai (identità)? Cosa siete disposti a tagliare o cambiare (twist, scope, estetica, co-op)?
- Qual è secondo voi il punto di forza e cosa vi preoccupa di più?
- Scope: cosa è giocabile oggi, cosa è promesso; Atti o Early Access; co-op e rete.
- Comparabili amati, comparabili da cui distinguersi, giochi con cui **non** volete essere confrontati.
**Cambia:** posizionamento (differenziatori ammessi), audit, dealbreaker accettabili, tagli di scope.

### Round 6: scenari "e se…" (le intenzioni sotto stress)
Chiedi cosa farebbero davvero. Sono la base delle contingenze (`07-contingenze.md`): soglie e azioni devono essere **le loro**, non le tue.
- Dopo **una settimana su itch.io** i numeri sono molto sotto le attese: insisti per altri giorni, cambi cover e pagina, chiedi feedback, ti fermi?
- Un gate (A, B o C) fallisce: ritardi, riposizioni il gioco, pubblichi comunque?
- La pagina Steam viene rifiutata o la verifica fiscale ritarda.
- La demo va male al Next Fest (poche ore di gioco, nessuna wishlist).
- Un concorrente diretto esce nella vostra finestra.
- Un socio esce o il tempo si dimezza.
- Il gioco va **molto bene** all'improvviso: come reagite (hotfix, aggiornamenti, DLC, stampa)?
- Soglia di stop: a quali risultati misurabili ridimensionate, cambiate genere o spostate l'obiettivo?
**Cambia:** soglie, azioni e decisioni di `05d-contingenze.md`, criteri di stop e pivot.

### Round 7: riepilogo e conferma
Presenta il **profilo decisionale** in 10-15 righe (obiettivo, capacità, budget e rischio, canali, non negoziabili, regole di stop), le tensioni rimaste e le decisioni aperte. Chiedi conferma o correzioni. Solo dopo la conferma parte l'analisi.

## Round di verifica con i dati (reality check)

Quando i dati contraddicono o confermano un'intenzione, **riapri la domanda** con numeri reali e lascia decidere:

- **R-A, dopo Fase 2B e Ondata 1**: "il posizionamento è marginale e i 3 problemi sono questi: ne correggi quanti, entro quando?"
- **R-B, dopo Fase 5 (economia)**: "con i tuoi costi il break-even è N copie, cioè M wishlist al lancio: è realistico per te? Cambi prezzo, scope o obiettivo?"
- **R-C, prima di fissare calendario e contingenze**: conferma date, soglie e chi fa cosa.
- **R-D, dopo la Fase 10 (solo beta con piano del gioco completo)**: domande sul gioco completo prima dell'analisi rapida: quante ore di gioco e quali contenuti nel totale; cosa si aggiunge oltre la beta (Atti, modalità, co-op, contenuti); cosa è ancora solo un'idea; data di uscita e prezzo previsti; accesso anticipato sì o no; quante ore servono ancora e chi le fa; cosa tagliereste se il tempo non bastasse. Poi "ecco cosa vedo, ecco cosa migliorerei adesso".

Anche questi round hanno il formato del consiglio e finiscono nel registro.

## Registro `launch/00-intenzioni.md`

```markdown
# Intenzioni e decisioni
Aggiornato: AAAA-MM-GG · Round completati: 1-7, R-A, R-B

## Profilo decisionale
(10-15 righe: obiettivo, capacità, budget e rischio, canali, non negoziabili, regole di stop)

## Registro
| Round | Tema | Domanda | Risposta | Consiglio dato | Decisione | Impatto sul piano |
|---|---|---|---|---|---|---|

## Tensioni e rischi emersi
## Decisioni aperte
```
In `status.json`: `"product": {"kind": "beta|demo|vertical_slice|full|post_launch", "label": "Beta (Atto I)", "has_full_plan": true}` e `"intentions": {"summary": "...", "decisions": [{"topic": "Budget", "choice": "...", "why": "..."}]}` (3-8 decisioni chiave).

## Dove finiscono le risposte

| Risposta su… | Effetto |
|---|---|
| obiettivo e successo | criteri del semaforo, scenari, break-even |
| ore e persone | verifica di capacità, ripartizione 👤/🤖 dei passi |
| budget e rischio | ordine dei pagamenti, ads, prezzo, tripwire |
| canali e comfort | mix creator, hook, calendario dei contenuti |
| non negoziabili | differenziatori ammessi, tagli di scope |
| scenari "e se…" | contingenze, criteri di stop e pivot |
| paese e soci | sezione fiscale, accordo tra soci |
