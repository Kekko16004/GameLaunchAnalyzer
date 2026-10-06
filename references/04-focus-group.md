# Fasi 7 e 7B: focus group a ondate, critiche (simulate e reali), pre-mortem

Il focus group qui è un **processo ripetibile**, non un'analisi unica:

- **Ondata 1 si esegue presto**, subito dopo l'audit (Fase 3), prima di piattaforme, prezzo, store e creator: i problemi del prodotto vanno visti quando costa poco correggerli.
- A fine ondata c'è la **segnalazione problemi** all'utente (7.4).
- Un'**ondata successiva parte solo quando l'utente dà l'ok** (7.5), con gli stessi tester, per vedere come cambiano opinioni e problemi nel tempo (delta e timeline).

Due insiemi di critiche restano **separati e poi incrociati**: **Sezione A** (simulate, dal panel) e **Sezione B** (reali, da recensioni e discussioni vere dei comparabili).

**Dichiarazione metodologica obbligatoria** (in testa a `05-focusgroup.md` e a ogni report d'ondata): i tester della Sezione A non hanno giocato; hanno giudicato da documenti, codice, capsule, screenshot, video e dall'audit della build. Sono opinioni simulate con rigore euristico, non dati di mercato né statistica. La Sezione B è fatta di fonti reali.

## File

```
launch/05-focusgroup.md            sintesi viva: ultima ondata, convergenza, dealbreaker, link alla timeline
launch/05a-critiche-simulate.md    top critiche dell'ultima ondata (lo storico sta in fg/waves/)
launch/05b-critiche-reali.md       Sezione B
launch/fg/roster.json, roster.md   tester con ID stabili (mai modificati)
launch/fg/waves/wNN-evidence.md    cosa ha visto il panel in quell'ondata
launch/fg/waves/wNN-group-a.md, wNN-group-b.md   giudizi dei due gruppi
launch/fg/waves/wNN-AAAA-MM-GG.json   dati dell'ondata (input di fg_waves.py)
launch/fg/waves/wNN-debate.md      dibattito della giuria
launch/fg/waves/wNN-report.md      report strutturato dell'ondata
launch/fg/waves/wNN-delta.md       confronto con l'ondata precedente (da N = 2)
launch/fg/timeline.md, timeline.csv   andamento di tutte le ondate
```

---

## 7.0 Casting: roster, regole di diversità, osservabilità

### Composizione
- **Default 54 tester** = 2 gruppi indipendenti (A e B) da 27, ciascuno con 3 coorti da 9. **Rapida: 24** (2×12). Se l'utente chiede un altro numero scala mantenendo le coorti e dichiara che oltre una certa soglia si guadagna diversità di opinioni, non precisione statistica.
- **Le coorti vengono dal playbook** (3 per gruppo). Gruppo A = pubblico core ed esperti; Gruppo B = scoperta, casual e attrito di mercato.

### Genera il roster (`roster.py`)
```bash
python3 <skill>/scripts/research/roster.py \
  --cohorts-a "veterani con centinaia di ore;min-maxer di sinergie;critici di bilanciamento" \
  --cohorts-b "casual del 'ancora una run';scroller di clip;cacciatori di valore" \
  --seed <slug-del-gioco> -o launch/fg/roster.json --md launch/fg/roster.md
```
Per ogni ID lo script fissa: coorte, nome fittizio, età, ore nel genere, **livello** (principiante / intermedio / esperto), **personalità** (scettico, entusiasta, meticoloso, impaziente, schietto, analitico, pacato, ironico), **stile di parola** (concisa, prolissa, tecnica, colloquiale, diretta), dispositivo, **esigenza di accessibilità** (circa 1 su 9: daltonismo, bassa visione, schermo piccolo, una mano, vincolo motorio, luci/motion sickness, udito ridotto), sensibilità al prezzo, pazienza, canale di scoperta, lingua, pregiudizio di partenza, **bastian contrario**. In `roster.json` c'è anche la **giuria** di 10 (`jury`), scelta dagli stessi ID per coprire i ruoli obbligatori.

Tu aggiungi a mano nella colonna *Scheda* di `roster.md` gusti, giochi di riferimento e cosa fa uscire quel tester dal gioco. **ID e colonne tecniche non cambiano mai** tra ondate. Per più campione riesegui con `--per-group` più alto: gli ID esistenti restano identici, i nuovi sono in coda.

### Regole di diversità (obbligatorie)
- Almeno **un principiante assoluto**, **uno scettico** che cerca difetti, **un esperto/veterano**, **un impaziente** che esce al primo attrito, **un profilo di accessibilità**, **un bastian contrario**: la giuria li copre sempre; nei gruppi sono distribuiti dallo script.
- Mai un panel accomodante: i tester hanno punti di vista in conflitto. Se due tester condividono lo stesso giudizio con parole diverse, riscrivi il secondo con il suo angolo (stesso scopo della regola "rebalance the cast").
- **Dissenso**: almeno il 15% di ogni coorte contraddice, con motivazione, la maggioranza della propria coorte (i bastian contrari).

### Cosa possono osservare i tester
| Materiale | Cosa permette di giudicare |
|---|---|
| Screenshot, capsule, immagini | estetica, layout, leggibilità, gerarchia visiva |
| Codice, architettura, GDD | struttura e scelte tecniche, cablaggio UI; **non** il feel a runtime |
| Testo, pitch, concept | reazione concettuale, non esperienza vissuta |
| Video, clip, trailer | flusso visivo e ritmo, solo se davvero visibili |

**I tester non inventano mai feature o comportamenti non visti.** Se un dettaglio manca lo dicono ("non è chiaro cosa succede dopo questo bottone"): è un feedback valido. Il feel di gioco senza build giocabile non si valuta.

### Calibrazione anti-gentilezza
1. Il panel vede il gioco come traffico **freddo** su Steam (capsule, titolo, tag, 2 secondi): il click al primo sguardo parte da una base bassa realistica. Sopra il 50% su 54 va giustificato.
2. **Controlli**: inserisci alla cieca la capsule del **comparabile di successo più vicino** e di uno **debole**. Il loro punteggio è il righello: se il panel è generoso con ciò che non lo merita, riduci. Registra i punteggi in `controls` del file d'ondata.
3. Confronta con il comparabile reale più vicino; se il panel è più ottimista del mercato, riduci e spiega.
4. Risultati come intervalli (con N = 54 una percentuale ha circa ±13 punti di incertezza **[STIMA]**, e il campione è simulato: l'intervallo misura la diversità del panel, non il mercato).
5. Scrivi sempre: "questi numeri ordinano i problemi, non prevedono le vendite".

---

## 7.1 Una ondata, passo per passo

### Passo 1: pacchetto di evidenze (`wNN-evidence.md`)
Raccogli in un unico blocco **tutto e solo** ciò che i tester vedono nello **stato attuale** del gioco: capsule e screenshot esistenti (o concept se non c'è nulla), pitch, tag, descrizione, clip, estratti di codice e GDD pertinenti, versione/commit della build. Elenca anche ciò che **manca** ("nessuna build giocabile", "nessun trailer"). Nessun tester usa informazioni fuori da questo blocco.

**Anti-ancoraggio (ondate > 1)**: il pacchetto descrive solo lo stato attuale. Non contiene le critiche delle ondate precedenti né l'elenco dei fix fatti: i tester non devono sapere cosa "dovrebbe" essere migliorato.

### Passo 2: impressioni indipendenti (Giro 1)
Ogni tester giudica **da solo**, leggendo prima la sua scheda, senza vedere gli altri. Due formati:

- **Giuria (10 ID da `roster.json`)**: 3-5 righe nella propria voce (personalità e stile della scheda) su **estetica, punti forti, confusione, attrito e la singola modifica prioritaria**. Concrete e ancorate ("il bottone principale ha poco contrasto sullo sfondo"), mai vaghe ("sembra pulito").
- **Altri tester**: record compatto con verdetto, click al primo sguardo, pitch riformulato correttamente sì/no, una critica principale più una secondaria, ciascuna con evidenza, conseguenza ("esce al minuto X", "chiede rimborso", "non mette in wishlist") e correzione possibile.

Una critica è accettata se è: specifica a questo gioco; ancorata a un'evidenza; con conseguenza; con una correzione abbozzata; non duplicata senza un angolo nuovo. Niente adulazione: un difetto riceve critica diretta.

**Indipendenza dei gruppi**: A e B non si vedono. Con subagenti, valuta ogni gruppo in un contesto separato che riceve solo il pacchetto di evidenze e le schede del proprio gruppo (mai le risposte dell'altro). Senza subagenti: scrivi `group-a` e `group-b` in sequenza senza rileggere A mentre scrivi B. Dichiara il metodo.

Scrivi `wNN-group-a.md` e `wNN-group-b.md` (impressioni della giuria incluse nel gruppo di appartenenza).

### Passo 3: dati dell'ondata e metriche (`fg_waves.py`)
Trascrivi i giudizi nel file `fg/waves/wNN-AAAA-MM-GG.json` (schema in testa a `fg_waves.py`: per tester `verdict`, `click`, `pitch_ok`, `issues`; elenco `issues` con **chiavi stabili**, gravità e raccomandazione; `controls`; da N = 2 anche `fixes`). **Riusa le stesse chiavi dei problemi di ondata in ondata**, altrimenti il delta non li collega. Poi:

```bash
python3 <skill>/scripts/research/fg_waves.py metrics launch/fg/waves/wNN-AAAA-MM-GG.json --roster launch/fg/roster.json -o launch/fg/waves/wNN-metrics.md
```
Lo script valida (ID, verdetti, duplicati), calcola e **non si ricalcola a mano**:

- **Verdetto di cassa**: `WISHLIST`, `SALDI` (aspetto saldi/recensioni), `IGNORO`, `REFUND` (compro e rimborso < 2 ore).
- **Punteggio wishlist**: `((W × 1,0) + (S × 0,4) − (I × 0,2) − (R × 0,8)) / N × 100`. Va da −80 a +100, **non è una percentuale**. Esempio N = 54: 12 W, 14 S, 24 I, 4 R → (12 + 5,6 − 4,8 − 3,2) / 54 × 100 = **17,8**. Serve a confrontare ondate e come filtro (Gate A), non come valore assoluto.
- **Soglia Gate A**: `--gate N`; altrimenti 80% del punteggio del controllo di successo (minimo 30); altrimenti **35 [OPINIONE]**. Motiva sempre la soglia adottata.
- Click al primo sguardo, comprensione del pitch, punteggio di A e di B con **gap** (oltre 15 punti va spiegato: spesso il core ama ciò che il pubblico largo non capisce, o viceversa).
- **Matrice dei problemi** ordinata per frequenza × gravità, con quanti A e quanti B li sollevano.

Aggiungi nel report: **problema N.1 di game feel** (la cosa più pesante per il divertimento, con evidenza), **leva strategica del genere** (la feature o il fattore che decide più wishlist, con quante wishlist nascerebbero o morirebbero), **rischio rimborso** (percentuale e motivo).

### Passo 4: dibattito della giuria (`wNN-debate.md`)
I 10 della giuria (`jury` in `roster.json`, **gli stessi ID a ogni ondata**: ruoli principiante, esperto, scettico, impaziente, accessibilità, bastian contrario, cacciatore di valore/rimborsi, creator di clip/streamer, più voci di coorte; se nel roster manca un curatore indie o un creator di short video, aggiungi quel ruolo a un ID senza cambiarne le colonne tecniche) discutono con i dati dei Passi 2-3 e della Sezione B sul tavolo.

**Tono**: rilassato e vivace, come una sessione di playtest tra pari. Formato `**Nome (ID):** battuta`, una per riga, concisa e naturale.

- **Round 1, interrogatorio incrociato**: reagiscono alle impressioni altrui, confermano o contestano, chiedono chiarimenti ("come hai capito che era interattivo?"), citano riferimenti concorrenti.
- **Round 2, approfondimento**: 2-3 punti più controversi o critici; cercano un terreno comune o spiegano perché le prospettive divergono davvero.
- **Round 3, i 3 problemi da risolvere entro [data a 14-20 giorni]**, scelti dalla matrice di convergenza (7.3). Per ognuno: sintomo, causa probabile, intervento, ore, impatto atteso, rischio. Toccano il divertimento: **richiedono l'ok del dev**.

Regole: ognuno mantiene voce, competenza e pregiudizi; **nessuno cede per cortesia senza motivazione**; partecipazione dinamica (alcuni parlano più di altri, niente giro obbligato); **nessun narratore** né riassunti dentro la chat (la sintesi sta nel report). Lunghezza: Rapida 10-16 battute; Completa 25-35 su tre round.

### Passo 5: report d'ondata (`wNN-report.md`)
Senza dialoghi, per sviluppatori e designer:

1. **Verdetto esecutivo** (2-3 frasi): accoglienza generale e linee di frattura.
2. **Punti forti validati** con il consenso (es. "5/6 della giuria, critici compresi" o n su N).
3. **Problemi di usabilità e chiarezza**, ordinati per frequenza e gravità.
4. **Feedback visivo ed estetico**, con la divergenza di gusto.
5. **Matrice dei problemi**: `Problema | Individuato da | Gravità (alta/media/bassa) | Raccomandazione` (prodotta da `fg_waves.py`).
6. **Temi divisivi** e cosa li guida (esperienza, target, aspettative).
7. **Quick win** (3-5, alto impatto e poco sforzo).
8. **Domande aperte**: ipotesi che richiedono il test con persone vere.
9. *(opzionale)* **Voti individuali** 1-10 con una frase ciascuno.
10. Metriche (Passo 3), matrice di convergenza (7.3) e i **3 dealbreaker**.

Chiudi il report con la dichiarazione: valutazione **simulata** con persone fittizie, non ricerca empirica; accelera la scoperta euristica ma le decisioni critiche si validano con utenti reali.

### Passo 6: aggiornamenti
Aggiorna `05-focusgroup.md`, `05a-critiche-simulate.md`, la timeline (7.5) e `STATUS.md` (numero ondata, build, punteggio). Poi la segnalazione all'utente (7.4).

---

## 7.2 SEZIONE B: critiche reali del genere (`05b-critiche-reali.md`)

Qui **non si inventa nulla**. Ogni voce ha una fonte. Si raccoglie **una volta** in Fase 2 (comparabili) e si rifà solo se cambiano i comparabili.

### Metodo
1. Per ciascuno dei 5-8 comparabili più vicini (3 in Rapida):

   ```bash
   python3 <skill>/scripts/research/steam_reviews.py <appid...> --type negative --within-days 365 --limit 150 \
     --language english -o launch/_raw/reviews_negative.json
   python3 <skill>/scripts/research/steam_reviews.py <appid> --type negative --sort recent --max-playtime-h 2 -o launch/_raw/reviews_refund_like.json
   python3 <skill>/scripts/research/steam_reviews.py <appid...> --type positive --limit 100 -o launch/_raw/reviews_positive.json
   ```
   Lo script restituisce data, ore di gioco, voti utili, URL e temi per parola chiave, più il riepilogo delle frequenze. **Il riepilogo è un punto di partenza, non un'analisi**: leggi un campione e correggi i temi a mano.
2. Integra con critica professionale, post-mortem, thread Reddit e Discord e **motivi di rimborso** dichiarati (ricerca web).
3. Se Steam non è raggiungibile usa fonti alternative, dichiara il limite del campione e scrivi in `ricerche-manuali.md` come completare. **Mai riempire con critiche plausibili**: la sezione resta vuota con le istruzioni.
4. **Tassonomia dei temi** (onboarding, ripetitività, bilanciamento, bug, prezzo/durata, UI, performance, netcode, contenuto, scrittura…) con **frequenza** nel campione (conteggio o fascia: raro, ricorrente, dominante), **[FATTO]** e URL di esempio. Parafrasa; citazioni sotto le 15 parole, una per fonte. Dichiara dimensione e bias del campione (ordine per utilità vs recenti).
5. **Tabella del genere**:

   | Tema ricorrente | Frequenza nel campione | Fonti (URL) | Perché il pubblico lo punisce | Il nostro gioco ne soffre? |
   |---|---|---|---|---|

   Ultima colonna: **[SÌ]**, **[A RISCHIO]**, **[NO]**, **[NON VALUTABILE]**, con evidenza dal progetto.
6. **Motivi di rimborso e abbandono**: i 5 più citati e come il gioco li affronta.
7. **Contro-lista**: i 5 temi più premiati (campione `--type positive`) e se il gioco li ha, per non tagliare per sbaglio ciò che il pubblico ama.

**Privacy**: nei deliverable cita "recensione Steam di <gioco>, <data>, <ore di gioco>" con l'URL; non riportare nomi o profili dei recensori.

---

## 7.3 Matrice di convergenza (in `05-focusgroup.md`, rifatta a ogni ondata)

Incrocia A (ultima ondata) e B. Una critica in entrambe è la più affidabile.

| Tema | Simulata (freq. su N) | Reale (freq. nel campione) | Stato | Priorità |
|---|---|---|---|---|

- **CONFERMATA**: in A e B → priorità massima.
- **PUNTO CIECO**: solo in B (il mercato si lamenta, il panel non l'ha vista) e il gioco ne soffre → priorità alta; aggiungi il tema al panel nell'ondata successiva.
- **IPOTESI**: solo in A → da verificare con il test reale (Fase 9) prima di spendere ore.
- **FALSO ALLARME**: in A ma smentita dai dati reali (il genere premia proprio quella scelta) → declassa e spiega.

I **3 dealbreaker** nascono da questa matrice, non da una lista precostituita.

---

## 7.4 Segnalazione problemi (checkpoint dopo ogni ondata)

Appena l'ondata è scritta, **scrivi in chat** (anche nel mezzo di una Completa), breve e numerico:

```text
ONDATA [N] - segnalazione problemi (panel simulato, non dato di mercato)
Stato valutato: [build/commit, materiali visti]. Metodo gruppi: [subagenti separati / sequenziale].
Punteggio wishlist [X] (soglia [S], motivata) | A [..] vs B [..] | click [..]% | pitch capito [..]%
[Ondate > 1: punteggio [prima] -> [dopo] ([+/-]); risolti: [..]; peggiorati o nuovi: [..]]

Problemi, dal più pesante:
1. [problema] | visto da [n/N] ([gruppi]) | gravità [..] | fix proposto | ore
2. ...
3. ...
Divisivi: [temi]. Quick win: [3-5 voci]. Punto cieco rispetto alle critiche reali: [temi].

Serve il tuo ok sui 3 problemi che toccano il divertimento: [1], [2], [3].
Quando li hai sistemati (o decidi di non farlo) dimmelo e lancio l'Ondata [N+1] con gli stessi tester.
Nel frattempo continuo con le fasi che non dipendono dai fix: [elenco].
```

Regole:
- Non fermare tutto in attesa: prosegui con le fasi indipendenti dai fix (piattaforme, calendario, ricerca creator, legale) e rimanda a dopo l'ok ciò che dipende dal prodotto (testi dello store, capsule, trailer).
- Se l'utente non risponde subito, nel debriefing finale segnala che **l'Ondata N+1 è in attesa del suo ok**.
- Tu **non modifichi il progetto** (regola 8): proponi gli interventi, li fa l'utente.

---

## 7.5 Ondate successive: variazioni nel tempo

**Mai in automatico.** Una nuova ondata parte solo quando l'utente la chiede o dà l'ok dopo una segnalazione. Proponila a questi momenti e mettila in `calendar.md` come riga di tipo `ondata`:

1. **Dopo i 3 problemi risolti** (di norma 14-20 giorni dopo l'Ondata 1).
2. **Dopo capsule, testi dello store o trailer nuovi** (Fase 6/6B): è anche il test del Gate C.
3. **Dopo l'aggiornamento della demo o prima di Next Fest.**
4. **Prima di pagare Steam Direct** (rivalutazione dei Gate A e C).
5. **Pre-lancio** e dopo ogni grande aggiornamento di contenuto.

Procedura (modalità **Ondata**, o parte di **Aggiornamento**):
1. Chiedi all'utente cosa è cambiato, oppure rilevalo (diff del codice, nuova build, nuovi asset) e scrivilo in `fixes` collegandolo alle chiavi dei problemi.
2. **Stesso roster, stesse schede, stessa giuria.** Rigenera con `roster.py` solo se serve più campione: i nuovi ID (`A-28`…) restano segnati come "nuovi" e il delta li esclude dal confronto a parità di tester.
3. Pacchetto di evidenze **solo con lo stato attuale** (anti-ancoraggio: niente critiche vecchie, niente elenco di fix). Le ondate precedenti si leggono **dopo** aver scritto i giudizi, solo per il delta.
4. Esegui i Passi 2-6 (nel dibattito aggiungi un round sul cosa è cambiato, solo dopo i giudizi indipendenti).
5. Delta e timeline:

   ```bash
   python3 <skill>/scripts/research/fg_waves.py delta launch/fg/waves/w01-....json launch/fg/waves/w02-....json \
     --roster launch/fg/roster.json -o launch/fg/waves/w02-delta.md
   python3 <skill>/scripts/research/fg_waves.py timeline launch/fg/waves --roster launch/fg/roster.json \
     -o launch/fg/timeline.md --csv launch/fg/timeline.csv
   ```
   Il delta mostra punteggio a parità di tester, spostamenti di verdetto, effetto di ogni fix (RISOLTO, MIGLIORATO, PEGGIORATO, NUOVO, INVARIATO con banda di rumore di 10 punti) e per tester cosa è cambiato; compila tu la colonna *Causa attribuita*. La timeline mostra l'andamento di punteggio, verdetti, click, pitch, gap A/B e problemi gravi.
6. Segnala i **peggioramenti** (un fix che ha creato un problema nuovo) con la stessa evidenza dei miglioramenti.
7. **Occhi freschi** (opzionale, ogni 2-3 ondate): aggiungi un gruppo di ID nuovi solo per quell'ondata per verificare che il panel stabile non si sia "adattato" al gioco.
8. Aggiorna la matrice di convergenza, i dealbreaker, `STATUS.md` e la segnalazione problemi (7.4).

Limite da dichiarare sempre: i tester sono simulati con gli stessi bias, quindi il delta è **direzionale, non una prova**; differenze di pochi punti sono rumore. Ogni miglioramento importante va confermato nel test reale (Gate B).

---

## FASE 7B: pre-mortem

Si esegue **dopo** Fasi 4-5 (servono break-even, scenari e calendario). Output: **`launch/05c-premortem.md`**. Bilancia la gentilezza del panel simulato.

**Scenario**: sono passati 12 mesi dal lancio e il gioco è un flop. Definisci "flop" in modo misurabile (sotto il break-even, o sotto lo scenario pessimistico della Fase 5). Racconta in 5 righe come è andata, poi elenca le **5 cause più probabili** (3 in Rapida).

Per ogni causa:
1. **Causa e storia**: cosa è successo concretamente.
2. **Perché è probabile**: evidenza dal progetto, dai comparabili, dalla Sezione B o dal focus group.
3. **Probabilità** **[STIMA]** (intervallo) e **impatto** (basso, medio, alto, fatale).
4. **Segnale d'allarme misurabile** (tripwire): metrica, soglia, data di misura, strumento. Esempi: "wishlist sotto N a 8 settimane dalla pagina", "durata media demo sotto 12 minuti", "meno del 30% fa una seconda sessione", "click sulla capsule sotto X%", "sondaggio post-test sotto 7/10", "punteggio dell'ondata sotto soglia dopo i fix".
5. **Azione preventiva** adesso, con ore e responsabile.
6. **Azione di emergenza** se il segnale scatta.

**Vincoli di qualità**:
- Almeno una causa di **prodotto**, una di **marketing/visibilità**, una di **mercato o tempismo**, una di **team** (scope, burnout, ore insufficienti) e una di **piattaforma/legale/tecnica**.
- Almeno una causa deve **contraddire il verdetto positivo** del panel o della Fase 2B, se ce n'è uno.
- Niente cause generiche ("marketing debole"): sempre con meccanismo e segnale.

Chiudi con la **tabella dei tripwire**:

| Causa | Segnale | Soglia | Data di misura | Azione di emergenza |
|---|---|---|---|---|

Le date vanno in `calendar.md`, le azioni preventive in `TODO.md`.
