# Fasi 7 e 7B: focus group, critiche (simulate e reali), pre-mortem

La Fase 7 produce due insiemi di critiche **tenuti separati e poi incrociati**:

- **Sezione A: critiche simulate**, di alta qualità, dal panel di tester.
- **Sezione B: critiche reali del genere**, estratte da recensioni e discussioni vere dei comparabili.

File: `launch/05-focusgroup.md` (sintesi, convergenza, giurati), `05a-critiche-simulate.md`, `05b-critiche-reali.md`, `fg/roster.md`, `fg/group_a.md`, `fg/group_b.md`, `fg/runs/`.

**Dichiarazione metodologica obbligatoria** (in testa a `05-focusgroup.md`): i tester della Sezione A non hanno materialmente giocato; hanno giudicato da documenti, codice, capsule, screenshot, video e dall'audit della build. Sono opinioni simulate con rigore euristico, non dati di mercato. La Sezione B è fatta di fonti reali.

---

## 7.0 Roster, composizione e calibrazione

### Composizione
- **Default 54 tester** = 2 gruppi indipendenti (A e B) da 27, ciascuno con 3 coorti da 9. **Rapida: 24** (2×12). Se l'utente chiede un altro numero (es. 100) scala mantenendo le coorti e dichiara che oltre una certa soglia si guadagna diversità di opinioni, non precisione statistica.
- **Le coorti vengono dal playbook** (3 per gruppo). Regola generale: **Gruppo A = pubblico core ed esperti**; **Gruppo B = scoperta, casual e attrito di mercato**.

### ID stabili e schede (usa `roster.py`)
Ogni tester ha un ID fisso (`A-01`…`A-27`, `B-01`…`B-27`) e una scheda. Genera lo scheletro deterministico, poi arricchiscilo a mano:

```bash
python3 <skill>/scripts/research/roster.py \
  --cohorts-a "veterani con centinaia di ore;min-maxer di sinergie;critici di bilanciamento" \
  --cohorts-b "casual del 'ancora una run';scroller di clip;cacciatori di valore" \
  --seed <slug-del-gioco> -o launch/fg/roster.json --md launch/fg/roster.md
# più campione in Aggiornamento: aggiunge ID in coda, gli esistenti restano IDENTICI
python3 <skill>/scripts/research/roster.py ... --per-group 36 --seed <slug-del-gioco> -o launch/fg/roster.json --md launch/fg/roster.md
```

Lo script fissa per ogni ID: coorte, fascia di età, ore nel genere, dispositivo, sensibilità al prezzo, pazienza, canale di scoperta, lingua, pregiudizio di partenza e se è un **bastian contrario** (dissenso obbligatorio). Tu aggiungi a mano la scheda narrativa (gusti, giochi di riferimento, cosa lo fa uscire dal gioco). **ID e schede non cambiano mai tra una versione e l'altra**: servono per l'Aggiornamento (7.5). Mai rinumerare.

### Regole di qualità
- **Evidenza obbligatoria**: ogni giudizio cita almeno un elemento concreto del progetto. Vietati commenti generici ("sembra carino").
- **Dissenso obbligatorio**: almeno il 15% dei tester di ogni coorte contraddice, con motivazione, la maggioranza della propria coorte (i bastian contrari del roster).
- **Indipendenza dei gruppi**: A e B non si vedono. Se hai a disposizione subagenti, valuta ogni gruppo in un contesto separato che riceve **solo** pacchetto di evidenze + schede del proprio gruppo (mai le risposte dell'altro, né un verdetto atteso). Senza subagenti: scrivi `group_a.md` e `group_b.md` in sequenza e non rileggere A mentre scrivi B. Dichiara quale metodo hai usato.
- **Un tester alla volta**: leggi la scheda, poi giudica. Se due tester producono la stessa frase, riscrivi il secondo con il suo angolo.
- **Pacchetto di evidenze**: prima di iniziare raccogli in un unico blocco ciò che i tester "vedono" (capsule/screenshot/clip, pitch, tag, descrizione, estratti di codice e GDD pertinenti). Nessun tester usa informazioni fuori da quel blocco.

### Calibrazione anti-gentilezza
1. Il panel vede il gioco come traffico **freddo** su Steam (capsule, titolo, tag, 2 secondi): il click al primo sguardo parte da una base bassa realistica. Se supera il 50% su 54, va giustificato.
2. **Controlli**: inserisci nel panel, alla cieca, la capsule del **comparabile di successo più vicino** e di un **comparabile debole**. Il loro punteggio è il righello: se il panel dà un punteggio simile al successo reale a un gioco che non lo merita, il panel è troppo gentile e riduci.
3. Confronta i numeri col comparabile reale più vicino; se il panel è più ottimista del mercato, riduci e spiega.
4. Presenta i risultati come intervalli (con N = 54 un singolo percento ha un'incertezza di circa ±13 punti **[STIMA]**, e il campione è simulato: l'intervallo misura la diversità del panel, non il mercato).
5. Scrivi sempre: "questi numeri ordinano i problemi, non prevedono le vendite".

---

## 7.1 SEZIONE A: critiche simulate (`05a-critiche-simulate.md`)

**Giro 1: ogni tester dice la sua.** Ogni tester dà verdetto, click sì/no, **una critica principale più un'eventuale secondaria**. Una critica è accettata se è:
1. **Specifica** a questo gioco (non applicabile a qualunque gioco).
2. **Ancorata** a un'evidenza (file, scena, screenshot, riga del GDD, elemento della capsule).
3. **Con conseguenza**: cosa farebbe il tester (esce al minuto X, chiede rimborso, non mette in wishlist, non consiglia).
4. **Con una correzione possibile**, anche abbozzata.
5. **Non duplicata** senza un angolo nuovo.

**Giro 2: voto e classifica.** Raggruppa le critiche simili, conta le occorrenze ("inizio troppo lento: 31 su 54"), produci:
- **Top 10 critiche simulate** ordinate per frequenza × severità, con i gruppi che le sollevano (A, B o entrambi).
- **Critiche di minoranza di qualità** (le 3 migliori espresse da pochi): possono essere giuste proprio perché controcorrente.

### Metriche quantitative (su N tester)

- **Click al primo sguardo**: quanti cliccano vedendo solo capsule, titolo e tag.
- **Verdetto di cassa** (percentuali e conteggi): `[WISHLIST SUBITO]`, `[ASPETTO SALDI / RECENSIONI]`, `[SCROLLO OLTRE / IGNORO]`, `[COMPRO E CHIEDO REFUND (<2 ORE)]`.
- **Punteggio wishlist pesato**:

  ```
  punteggio = ((Wishlist × 1,0) + (Saldi × 0,4) − (Ignoro × 0,2) − (Refund × 0,8)) / N × 100
  ```
  Mostra sempre il calcolo. Esempio con N = 54: 12 wishlist, 14 saldi, 24 ignoro, 4 refund → (12 + 5,6 − 4,8 − 3,2) / 54 × 100 = **17,8**. Il punteggio va da −80 a +100: **non è una percentuale**. Serve come confronto tra versioni e come filtro (Gate A), non come valore assoluto.
- **Soglia del Gate A**: default **35 [OPINIONE]**. Se hai i controlli (7.0), usa invece **80% del punteggio del comparabile di successo** (minimo 30). Motiva sempre la soglia che adotti.
- **Comprensione del pitch**: percentuale di tester che riformula correttamente il pitch (Fase 2B).
- **Convergenza A/B**: differenza tra i due gruppi sul punteggio wishlist. Se supera 15 punti spiegala: spesso il core ama ciò che il pubblico largo non capisce, o viceversa.
- **Problema N.1 di game feel**: la cosa più pesante per il divertimento, con evidenza (asimmetria del feedback, pacing dei primi minuti, tempo alla prima scelta significativa).
- **Leva strategica del genere**: la feature o il fattore che decide più wishlist (co-op, moddabilità, clippabilità, stile artistico, durata) e quante wishlist nascerebbero o morirebbero da lì.
- **Rischio rimborso**: percentuale e motivo principale.

### Heatmap delle criticità (top 5)

| Criticità | Gruppi | Frequenza (su N) | Severità | Impatto commerciale stimato | Costo fix (ore) |
|---|---|---|---|---|---|

---

## 7.2 SEZIONE B: critiche reali del genere (`05b-critiche-reali.md`)

Qui **non si inventa nulla**. Ogni voce ha una fonte.

### Metodo
1. Per ciascuno dei 5-8 comparabili più vicini (3 in Rapida) raccogli recensioni negative recenti con lo strumento:

   ```bash
   python3 <skill>/scripts/research/steam_reviews.py <appid...> --type negative --within-days 365 --limit 150 \
     --language english -o launch/_raw/reviews_negative.json
   # per un campione più ampio e per i "rimborsi": ordine per utilità o recenti, più lingue
   python3 <skill>/scripts/research/steam_reviews.py <appid> --type negative --sort recent --max-playtime-h 2 -o launch/_raw/reviews_refund_like.json
   ```
   Lo script restituisce per ogni recensione data, ore di gioco (totali e alla recensione), voti utili, URL e temi rilevati con una tassonomia di parole chiave, più un riepilogo delle frequenze. **Il riepilogo è un punto di partenza, non un'analisi**: leggi un campione delle recensioni e correggi i temi a mano.
2. Integra con recensioni di critica, post-mortem, thread Reddit e Discord e **motivi di rimborso** dichiarati (ricerca web).
3. Se Steam non è raggiungibile, usa fonti alternative, dichiara il limite del campione e scrivi in `ricerche-manuali.md` come completare a mano. **Mai riempire con critiche plausibili**: la sezione resta vuota con le istruzioni.
4. **Tassonomia dei temi**: raggruppa in temi (onboarding, ripetitività, bilanciamento, bug, prezzo/durata, UI, performance, netcode, contenuto, scrittura…) e stima per ognuno la **frequenza** nel campione (conteggio o fascia: raro, ricorrente, dominante) con **[FATTO]** e URL di esempio. Parafrasa: citazioni dirette sotto le 15 parole, una per fonte. Dichiara dimensione e bias del campione (le negative ordinate per utilità sovrarappresentano i problemi più discussi).
5. **Tabella del genere**:

   | Tema ricorrente | Frequenza nel campione | Fonti (URL) | Perché il pubblico lo punisce | Il nostro gioco ne soffre? |
   |---|---|---|---|---|

   L'ultima colonna vale **[SÌ]**, **[A RISCHIO]**, **[NO]** o **[NON VALUTABILE]**, sempre con evidenza dal progetto.
6. **Motivi di rimborso e abbandono**: i 5 più citati e come il gioco li affronta.
7. **Contro-lista**: i 5 temi che i recensori premiano di più (usa `--type positive` su un campione) e se il gioco li ha. Serve a non tagliare per sbaglio ciò che il pubblico ama.

**Privacy**: nei deliverable cita la recensione come "recensione Steam di <gioco>, <data>, <ore di gioco>" con l'URL; non riportare nomi o profili dei recensori.

---

## 7.3 Matrice di convergenza (in `05-focusgroup.md`)

Incrocia A e B. Una critica che compare in entrambe è la più affidabile.

| Tema | Simulata (freq. su N) | Reale (freq. nel campione) | Stato | Priorità |
|---|---|---|---|---|

Stato:
- **CONFERMATA**: in A e B → priorità massima.
- **PUNTO CIECO**: solo in B (il mercato si lamenta, il panel non l'ha vista) e il gioco ne soffre → priorità alta; aggiungi il tema al panel alla prossima esecuzione.
- **IPOTESI**: solo in A → da verificare con il test reale (Fase 9) prima di spendere ore.
- **FALSO ALLARME**: in A ma smentita dai dati reali (es. il genere premia proprio quella scelta) → declassa e spiega.

I **3 dealbreaker** nascono da questa matrice, non da una lista precostituita.

---

## 7.4 Tavolo dei 10 giurati

Dieci portavoce scelti dal playbook (es. per la strategia: min-maxer, scettico del tutorial, giocatore da divano; per l'horror: streamer da reaction, scettico dei jumpscare), con almeno un creator di short video, un cacciatore di rimborsi e un curatore indie. Confrontano i dati delle due sezioni e i risultati della Fase 2B:
- **Round 1, blind capsule**: reazione in una battuta.
- **Round 2, pilastri**: spiegano drop-off e punti morti con i dati della matrice.
- **Round 3, scontro diretto** (15-20 battute): dialogo acceso su ritmo, noia e differenziazione, senza sconti.
- **Round 4, i 3 problemi da risolvere entro [data a 14-20 giorni]**, scelti dalla matrice. Per ognuno: sintomo, causa probabile, intervento, ore, impatto atteso, rischio. Toccano il divertimento, quindi **richiedono l'ok del dev**.

---

## 7.5 Aggiornamento del panel con ID stabili

In modalità **Aggiornamento**:
1. Riusa `fg/roster.md` e `roster.json` senza modificare ID né schede. Se serve più campione rigenera con `--per-group` più alto: gli ID esistenti restano identici, i nuovi sono in coda (`A-28`…).
2. Salva ogni esecuzione in `fg/runs/vN-AAAA-MM-GG.md` con versione o commit della build e, per ogni ID, verdetto, critica principale, click.
3. Calcola il **delta per tester**:

   | ID | Verdetto prima | Verdetto dopo | Critica prima | Critica dopo | Causa attribuita |
   |---|---|---|---|---|---|
4. Calcola l'**effetto di ogni fix**: per ogni intervento della versione precedente, come è cambiata la frequenza della critica collegata (es. "apertura lenta: da 31/54 a 9/54"), quanti tester hanno cambiato verdetto e di quanto è variato il punteggio wishlist.
5. Segnala i **peggioramenti** (un fix che ha creato un problema nuovo) con la stessa evidenza dei miglioramenti.
6. Limite da dichiarare: i tester sono simulati con gli stessi bias, quindi il delta è **direzionale, non una prova**. Ogni miglioramento importante va confermato nel test reale.

---

## FASE 7B: pre-mortem

Output: **`launch/05c-premortem.md`**. Bilancia la gentilezza del panel simulato.

**Scenario**: sono passati 12 mesi dal lancio e il gioco è un flop. Definisci "flop" in modo misurabile (es. sotto il break-even, o sotto lo scenario pessimistico della Fase 5). Racconta in 5 righe come è andata, poi elenca le **5 cause più probabili** (3 in Rapida).

Per ogni causa:
1. **Causa e storia**: cosa è successo concretamente.
2. **Perché è probabile**: evidenza dal progetto, dai comparabili, dalla Sezione B o dal focus group.
3. **Probabilità** **[STIMA]** (intervallo) e **impatto** (basso, medio, alto, fatale).
4. **Segnale d'allarme misurabile** (tripwire): metrica, soglia, data di misura, strumento o fonte. Esempi: "wishlist sotto N a 8 settimane dalla pagina", "durata media demo sotto 12 minuti", "meno del 30% fa una seconda sessione", "click sulla capsule sotto X%", "sondaggio post-test sotto 7/10".
5. **Azione preventiva** adesso, con ore e responsabile.
6. **Azione di emergenza** se il segnale scatta (cosa si taglia, si cambia o si rimanda).

**Vincoli di qualità**:
- Almeno una causa di **prodotto**, una di **marketing/visibilità**, una di **mercato o tempismo**, una di **team** (scope, burnout, ore insufficienti) e una di **piattaforma/legale/tecnica**.
- Almeno una causa deve **contraddire il verdetto positivo** del panel o della Fase 2B, se ce n'è uno.
- Niente cause generiche ("marketing debole"): sempre con meccanismo e segnale.

Chiudi con la **tabella dei tripwire**:

| Causa | Segnale | Soglia | Data di misura | Azione di emergenza |
|---|---|---|---|---|

Le date vanno in `calendar.md` e le azioni preventive in `TODO.md`.
