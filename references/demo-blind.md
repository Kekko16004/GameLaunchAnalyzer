# Demo cieche: che cosa sa prevedere una prova di gioco?

**Domanda verificabile:** osservando solo i primi minuti di una demo appena pubblicata, la pagella di un'AI migliora il pronostico di un evento futuro rispetto a un tasso base? Non chiedere «quante copie venderà?». Servono due persone/sessioni **senza contesto o filesystem condiviso**: il **curatore** conosce identità, registro e orologio; il **valutatore** vede solo il dossier anonimo e le istruzioni qui sotto. Se non puoi separare i ruoli, fai una prova didattica (`rehearsal`), non un test empirico. Lo script non scarica né esegue giochi e non chiama un modello.

## 1. Prima delle uscite: scegliere un solo protocollo

I comandi sotto si lanciano da `scripts/research/` o usando il percorso assoluto degli script. Il registro privato è `$GLS_HOME/demo-blind.sqlite3` (default `~/.game-launch-strategist`). Per il **proprio progetto**, passare lo stesso `--launch-dir percorso/launch` a **ogni** comando: il registro separato finisce in `_raw/`. Mai distribuirlo ai valutatori. Date del protocollo in UTC, giorni del calendario, soglia inclusiva `>=`.

Esempio di `plan.json` (date illustrative: sostituirle con una finestra **futura**, lunga 1–3 giorni; per iniziare è meglio 1). `train_through` è l'ultima data per cui era disponibile qualsiasi risultato usato a monte; deve precedere anche la preregistrazione. Bloccare modello/versione, prompt, durata, azioni, impostazioni/seed quando supportati, regola di campionamento e fonti **prima** della prima uscita. Se il modello è opaco, non inventare una data di training: indicare in `model` il limite di conoscenza non verificabile, usare una versione già disponibile alla data del piano e demo uscite in seguito. `out_of_time` misura la separazione cronologica del protocollo, non certifica i pesi dell'AI.

```json
{
  "batch": "b01", "mode": "prospective", "start": "2027-01-08", "end": "2027-01-08",
  "train_through": "2027-01-05", "frame_kind": "steam_listed", "country": "US",
  "sampling": "Tutte le demo elencate nella regione US, ordine data poi AppID; nessuna sostituzione",
  "model": "Compilare: identificativo preciso della versione disponibile oggi",
  "setup": "Rubrica demo-blind-v1; prima prova 10 minuti + riavvio 3 minuti; prompt v1; contesto nuovo, rete off, una risposta",
  "targets": [
    {"metric": "demo_reviews_d14", "threshold": 10, "history": []},
    {"metric": "game_reviews_d30", "threshold": 50, "history": []}
  ]
}
```

```sh
python demo_blind.py plan --input plan.json
python demo_blind.py batches
```

**Target supportati** (sceglierli in anticipo, nessuna conversione recensioni→copie). D0 = data UTC di prima uscita pubblica pertinente; osservazione cumulativa alla chiusura del giorno Dn incluso, con snapshot salvato e filtro costante. Non usare il totale di oggi per una data passata.

| Metrica | Cosa conta / fonte esatta | Esclusioni |
|---|---|---|
| `demo_reviews_d14` | Numero di recensioni pubbliche **della demo** fino a D14, `demo_review_snapshot` | Non sono giocatori né vendite; se non c'è una pagina/review feed indipendente, `missing`. |
| `demo_players_d14` | Giocatori unici della demo fino a D14, export titolare `owner_unique_players` | Non download, play session o CCU. |
| `demo_returns_first20_d7` | Tra i primi **20** giocatori unici al loro primo avvio il giorno D0 (ordine cronologico), quanti lanciano volontariamente una seconda sessione fra D1 e D7 inclusi? `owner_d0_cohort_first20`, aggregato privato | Per i tuoi giochi è una misura del ritorno, non dell'esposizione. Stessa build e regola di reclutamento; non includere QA/team o sessioni obbligatorie. Se a D0 i giocatori eleggibili sono meno di 20, o non puoi distinguere le sessioni, `missing`, non 0. Non inviare identificativi. |
| `game_reviews_d30` | Numero di recensioni pubbliche **del gioco successivo** fino a D30 dalla sua prima uscita, `game_review_snapshot` | Non recensioni demo. Il proxy osservato non misura copie. |
| `game_units_d30` | Unità pagate nette del gioco successivo fino a D30, da report del titolare `owner_net_paid_units` | Non stime di proprietari, chiavi gratuite, wishlist, né recensioni moltiplicate. |

Preregistrare in `sampling` la definizione di prima uscita (es. prima disponibilità a pagamento, inclusa Early Access), regione/fonti, conteggio lingue/acquisti e ora del taglio. I target gioco sono **condizionali** all'uscita dopo la demo ed entro demo+D180; scandire anche chi non è uscito/senza dato. Un titolo già in vendita prima o il giorno della demo non è un «gioco successivo»: preferire solo target demo per quel bacino oppure segnare il target gioco mancante, mai spostarne l'origine. Le stime commerciali, se disponibili, restano un'analisi separata `[STIMA]`.

La baseline del singolo target è il tasso di superamento su una `history` privata di gruppi distinti **già osservati** allo stesso orizzonte, con stessa fonte, bacino e soglia (es. `{"group":"old-1","observed":"2026-12-01","value":9,"evidence":"snapshot-archivio-01"}`). Fornire la **serie consecutiva completa** della finestra storica dichiarata in `sampling`, non solo casi con esito positivo, e documentare i mancanti. Senza storico: `[]`, baseline ingenua 0,50, **non** una frequenza osservata. Non usare il tasso dei casi in test. Non cambiare più soglia, baseline né modello per il batch aperto.

## 2. Censire, poi preparare i dossier (solo curatore)

Al termine di una giornata UTC programmata raccogli il censimento corrispondente (questo primo comando usa Steam **solo lato curatore**, con autorizzazione dell'utente); controlla il percorso stampato:

```sh
python demo_intake.py --days 1 --end 2027-01-08 --cc US
python demo_intake.py --prepare-roster PERCORSO_SNAPSHOT.json --out roster.json
```

Lo snapshot privato in `$GLS_HOME/demo-intake` include le demo elencate dalla fonte, in ordine `(release_date, appid)`. Il radar giornaliero raccoglie un giorno quando è attivo; **non avvia un benchmark**. Riusa lo snapshot giornaliero esatto o usa `--days 1|2|3` e la fine/paese del piano. Un censimento generico di sette giorni non sostituisce la finestra preregistrata. Manifest incompleto: riprova senza sostituire la coorte. Se sei in ritardo, **non retrodatare**: registra la finestra mancata e preregistra un nuovo batch futuro. La completezza vale per la fonte/regione, non per tutte le demo del mondo.

Per **giochi propri, festival o fonte privata**: pianifica con `frame_kind:"private"`, `country:null`; usa alias privati stabili fra versioni/stesso gioco. Finita la finestra, **prima** di valutare la qualità/materiali, un custode congela la lista di tutti i casi in ordine di pubblicazione (ordine dei pari fissato nel piano):

```sh
python demo_blind.py frame --batch b01 --input frame.json --launch-dir ./launch
```

`frame.json`: `{"complete":true,"cases":[{"group":"g01","released":"2027-01-08"}]}`. Costruisci `roster.json` con lo `snapshot` SHA-256 restituito, `complete:true` e tutte le stesse righe nell'ordine originale. È `self_declared`, non un censimento verificato di mercato. Se la build non è ancora pubblicata, prepara un **test prospettico interno** con D0 deliberatamente fissato alla distribuzione della build ai tester, target proprietario pertinente e bacino descritto come interno: non chiamarlo esito Steam pubblico. Per un solo gioco non puoi stimare accuratezza generale; ripetizioni sulla stessa build/gioco non sono nuovi casi indipendenti. Se nel tuo contesto è solo il titolare a poter fornire dati, lascia i target non accessibili `missing`.

La bozza privata Steam contiene già le colonne; il curatore modifica **solo** `status`, `reason`, `trace`, `media`. Non rimuovere, non sostituire, non ordinare per popolarità. Gruppi duplicati, demo dello stesso gioco o gruppi già usati nella baseline/test → conservare riga, `contaminated`. L'alias Steam è stabile per AppID della demo, non identifica automaticamente port, cloni o più AppID per uno stesso gioco; il curatore deve collegarli nel suo indice privato.

* Per ogni demo acquisire **la stessa prova**: dalla prima azione controllabile, tentare obiettivo iniziale, ripetere il loop con una scelta diversa, raggiungere il limite di tempo e riavviare. Nessuna highlight reel scelta a posteriori. Registra tempi e input reali, cosa appare e cosa non si è potuto vedere. Mai inventare una run a partire da un titolo o un trailer.
* Togli titolo/crediti, nomi studio, AppID, link, nomi di file, voce nominativa, titoli finestra, overlay, notifiche, achievement globali, classifiche e metadati (anche sottotitoli, tracce audio, EXIF). Verifica manualmente la copia e l'audio; se riconoscibile non basta rinominare il file. Usa solo contenuti disponibili legittimamente, con permesso per fornirli al valutatore. Non distribuire eseguibili sconosciuti: il pack accetta solo `png`, `jpg`, `mp4`, `wav` o testo anonimizzato.
* Proibiti nel dossier o nel contesto AI: pagina Steam, news, recensioni, corpus precedente, andamento vendite, classifiche, risultati studio, modelli del radar, lookup, reverse image search, nomi e titoli. Le schede owner, chiave privata dei gruppi e snapshot non lasciano il curatore. La blacklist della CLI è una cintura di sicurezza, non anonimizzazione automatica.
* `ready`: materiale sufficiente per tutte e cinque le dimensioni; `insufficient`: nessun materiale/solo pitch o trailer senza loop; `unplayable`: tentativo riproducibile fallito/crash/blocco; `contaminated`: titolo riconosciuto, risultato noto, cross-over di gruppi. Sui tre stati esclusi motivo obbligatorio e liste vuote; **mai** voto zero o sostituzione con una demo popolare. Esempio riga pronta: `{"group":"g01","released":"2027-01-08","status":"ready","reason":"","trace":["00:45 ...","04:10 ...","10:20 ..."],"media":["redacted/opening.mp4"]}` (inserire osservazioni reali).

```sh
python demo_blind.py intake --batch b01 --manifest PERCORSO_SNAPSHOT.json --input roster.json
python demo_blind.py pack --batch b01 --case D0001 --out handoff/D0001
```

Per coorte privata ometti `--manifest` e aggiungi sempre `--launch-dir ./launch`. L'intake rifiuta righe perse/aggiunte, ordine o hash diversi. L'export controlla l'hash dei media, elimina percorsi e metadati **del roster**, non trasforma i byte del media. Copia **solo** la nuova cartella del singolo dossier in una sessione senza accesso alla cartella superiore, web, indici, storico chat o strumenti di ricerca. Il valutatore non invoca il registro. Una sessione vergine per dossier, niente confronto con gli altri candidati.

## 3. Prompt del valutatore (nessuna identità, nessun esito)

> Hai solo `dossier.json` e i media associati. Simula la scelta di una persona a cui il genere interessa, non un critico incaricato di trovare problemi. Non cercare il gioco né indovinarne l'identità. Se riconosci gioco o risultato, fermati (`contaminated`, senza nome). Se non vedi davvero una decisione, una ripetizione e una ragione per tornare/non tornare: `insufficient`; se l'avvio fallisce: `unplayable`. Distingui sempre ciò che **osservi** dal comportamento che **simuli**. Nessuna esperienza diretta dichiarata guardando una registrazione. Congela la prima risposta, senza repliche selezionate.

**Griglia invariabile**: 1 / 3 / 5 come sotto; 2 e 4 solo tra ancore adiacenti. Per ogni voto indicare un fatto localizzabile e una breve motivazione verificabile (non un ragionamento privato).

| Dimensione | 1 | 3 | 5 |
|---|---|---|---|
| `gameplay` | Azione senza risposta/nessuna scelta utile | Una scelta modifica un esito leggibile | Almeno due alternative praticabili, conseguenze diverse visibili |
| `hook` | La prima decisione non mostra la promessa | La promessa si capisce entro il primo loop | Prima decisione distintiva con payoff immediato osservabile |
| `variety` | Ripetizione identica, nessun adattamento | Una variazione richiede adattamento | Più situazioni cambiano decisioni, non solo scenografia |
| `readability` | Obiettivo o feedback incomprensibili dopo un tentativo | Obiettivo chiaro, un feedback richiede tentativo | Obiettivo, causa/effetto e recupero dall'errore si leggono in azione |
| `replay` | Nel limite osservato nessuna scelta da riprovare | Un'alternativa concreta inviterebbe al ritorno | Un'altra strategia è visibile e il riavvio ne mostra un esito diverso |

Schema della **risposta AI** (righe sintetiche illustrative, non dati sperimentali). `trace:N` parte da 1; se usi media, indica ad esempio `clip-01.mp4@00:45`. Per prove solo testuali `basis:"trace"`, per media `recording`. Nelle tre tappe: `observation` descrive il fatto, `response` la reazione **simulata**, inclusa la possibile uscita; esplicita nell'incertezza il limite più importante.

```json
{
  "id": "D0001", "status": "scored", "basis": "trace",
  "run": {
    "first_decision":{"evidence":"trace:1","observation":"Si aprono due corsie.","response":"Proverei quella illuminata."},
    "repeated_loop":{"evidence":"trace:2","observation":"Al secondo giro compare lo stesso ostacolo.","response":"Non cambierei strategia."},
    "return_choice":{"evidence":"trace:3","observation":"Il riavvio permette la seconda corsia.","response":"Tornerei per un solo tentativo."}
  },
  "scores": {
    "gameplay":{"value":3,"evidence":"trace:1","why":"La scelta cambia il percorso."},
    "hook":{"value":3,"evidence":"trace:1","why":"La biforcazione anticipa il primo loop."},
    "variety":{"value":2,"evidence":"trace:2","why":"Al secondo giro cambia il percorso ma non il problema."},
    "readability":{"value":4,"evidence":"trace:1","why":"La luce indica la corsia, non che cosa rischio."},
    "replay":{"value":3,"evidence":"trace:3","why":"Resta un percorso da provare."}
  },
  "uncertainty":"La traccia non mostra se al terzo giro cambia il problema."
}
```

Alternativa completa: `{"id":"D0001","status":"insufficient","reason":"La registrazione termina prima della seconda scelta."}`. Niente stima per dimensioni invisibili. Il curatore importa una risposta per caso entro demo+D3 e chiude **l'intero batch** prima di aprire qualunque esito:

```sh
python demo_blind.py judge --batch b01 --case D0001 --input risposta.json
python demo_blind.py seal --batch b01
```

Il motore restituisce subito le **probabilità congelate**: per ciascun target `p = clip(baseline + (media dei 5 voti - 3)/8, 0.01, 0.99)` arrotondata a sei decimali. È una regola esplicita e arbitraria messa **alla prova**, non una funzione stimata dalle vendite. Le dimensioni hanno uguale peso; a parità di voti e baseline il numero non cambia. Target diversi possono ricevere la stessa probabilità: non sono eventi equivalenti. Il modello può produrre voti diversi in un'altra esecuzione; archivia dossier, versione e prima risposta. Un'eventuale nuova formula è un **nuovo protocollo su finestre future**, non un ricalcolo del passato.

SQLite usa transazioni, inserimenti unici, trigger contro UPDATE/DELETE e data UTC reale; non esiste sovrascrittura dalla CLI. Esporta e conserva la ricevuta SHA-256 del `seal` in un luogo indipendente prima di aprire i risultati. Non è certificazione notarile: chi controlla file, orologio, o input può falsificarli. Se un giudizio manca oltre D3, chiudi comunque: `missed_deadline` resta nel denominatore. Per una contaminazione scoperta dopo: `python demo_blind.py quarantine --batch b01 --case D0001 --reason "Identità riconosciuta nel finale"`; non riscrive il pronostico. Riporta la sensibilità inclusi i quarantinati, soprattutto se la scoperta è post-reveal.

## 4. Solo dopo: osservare e confrontare

Il custode ricongiunge D0001 alla chiave privata. Salva snapshot datato, filtro o export originale, in area privata; niente credenziali o dati individuali nel registro. Registra il risultato **dal giorno UTC successivo** al termine della misura (es. D15 per un totale alla chiusura di D14). Valuta **tutti** gli ammessi quando possibile, anche gli esclusi dal giudizio: serve a capire la selezione. Un file per caso e metrica:

```json
{"id":"D0001","metric":"demo_reviews_d14","status":"observed","source":"demo_review_snapshot","as_of":"2027-01-22","value":6,"game_release":null,"evidence":"snapshot privato archivio-01 alla chiusura D14, lingua tutte"}
```

```sh
python demo_blind.py reveal --batch b01 --case D0001 --input outcome.json
python demo_blind.py report --batch b01
python demo_blind.py series
```

In caso di contatore inaccessibile o snapshot di D14 perso: `status:"missing"`, `value:null`, `evidence` spiega perché; mantenere `as_of` del giorno richiesto, non sostituire il totale odierno. Per il gioco, `game_release:"YYYY-MM-DD"` e `as_of` = uscita gioco+D30. Se nessuna uscita successiva verificata entro D180: `not_released` a demo+D180 (oppure `missing` se non verificabile), `game_release:null`. Non dichiarare stati finali prima della scadenza; fino ad allora `pending`. Un esito entra una sola volta, anche se mancante: registralo solo dopo la verifica.

Leggi per **ciascun target**: elenco e disponibilità di tutte le coorti (`batches`); censiti → classificazioni → giudicati → confrontabili; copertura sia su censiti sia sui giudicati; `missing`, `pending`, `not_released` distinti. Brier = media `(p-y)^2`, più basso è meglio. Confronta `baseline_brier_same_cases` sulle **stesse** coppie, non una popolazione diversa. `brier_gain > 0` = vantaggio descrittivo su quei casi. Nelle cinque fasce di calibrazione confronta media delle probabilità, frequenza osservata e N; vuoto è `null`, non 0. La serie mantiene i batch cronologici con cutoff precedente, include finestre non completate e non mischia target, soglie, simulazioni, varianti del metodo o bacini; riassunto ponderato per numero di casi. Se manca un censimento la copertura complessiva è ignota. `--as-of` è consentito solo in `mode:"rehearsal"` per imparare il flusso; nessun Brier di rehearsal è accuratezza empirica.

**Debrief**: riporta almeno i tre maggiori errori *se presenti*, p, esito, direzione, confronto con baseline, dimensione/prova e limite annotato **prima**. Distingui ipotesi («la leggibilità sembra sopravvalutata») da spiegazioni dimostrate; visibilità, prezzo e marketing non erano nel dossier. Controlla se esclusi/irreperibili alterano il risultato. Un solo caso, pochi eventi, molte astensioni o vantaggi instabili fra settimane → «non dimostrato», non «il metodo funziona». Non scegliere la settimana migliore. Per modificare rubrica, pesi o soglia usa solo batch già chiusi come sviluppo e riparti con un nuovo piano su gruppi **mai visti**. Sul proprio gioco usa il giudizio per decidere la prossima prova osservabile (per esempio testare con persone se la seconda corsia invita al riavvio), non come promessa di copie o prognosi certa.

## 5. Challenger v2 opzionale: imparare dai propri giochi senza riscrivere la pagella

**Cosa cambia:** la v1 continua a produrre e conservare lo stesso pronostico. Separatamente un piccolo modello impara quanto pesavano gameplay, hook, varietà, leggibilità e ritorno nei risultati passati **del bacino scelto**. L'obiettivo può essere, per esempio, «almeno 10 dei primi 20 giocatori D0 tornano entro D7»: nel piano v1 `demo_returns_first20_d7`, soglia `10`. Il numero è un esempio di soglia, non un risultato misurato. Assicurati che i progetti condividano popolazione, definizione, strumentazione e protocollo; una build dello stesso gioco provata 30 volte **non** equivale a 30 giochi indipendenti. Per un gioco solo è più utile raccogliere playtest umani. Non sostituire con recensioni o vendite gli esiti D7 mancanti.

**A. Fit, dopo la maturazione degli esiti.** Tutti i batch privati confrontabili devono appartenere allo **stesso registro** (un `--launch-dir` dedicato all'intero banco di prova, non una cartella per gioco; altrimenti l'archivio comune `GLS_HOME`). Non fondere DB a mano. Copia esattamente i campi dai piani v1 in `context.json`; `model` identifica il **valutatore** che ha dato i voti, non il challenger. Cambiare campionamento, metodo della baseline, regione, popolazione o modello AI → nuovo contesto, niente accorpamento per fare numero.

```json
{"version":"demo-blind-v1","frame_kind":"private","country":null,
 "sampling":"Tutte le demo distribuite al panel interno consecutivo",
 "model":"valutatore-A/versione-bloccata","setup":"prima run 10 min e riavvio 3 min, prompt v1",
 "baseline_method":"naive"}
```

```sh
python demo_challenger.py fit --artifact ritorno-v2a --context context.json --metric demo_returns_first20_d7 --threshold 10 --launch-dir banco/launch
python demo_challenger.py show --artifact ritorno-v2a --launch-dir banco/launch
```

Il fit considera **tutte** le finestre prospettiche dello stesso contesto/target/soglia terminate prima di oggi (UTC), mai rehearsal. Servono censimento e sigillo, un esito finale per **ogni** iscritto e timestamp reali precedenti al giorno di fit; `missing` e `not_released` sono finali, ma non esempi negativi. Le finestre incomplete/immature sono dichiarate e omesse in blocco. Quarantene e astensioni non insegnano al modello. Minimi fissati nel metodo: almeno 2 finestre non sovrapposte con coppie, 30 gruppi valutabili distinti, 6 successi e 6 insuccessi, copertura almeno 80% sui censiti nelle finestre mature. Altrimenti **«non addestrabile»**, nessun artefatto: raccogli altri casi senza cambiare soglia a posteriori. Controlla le finestre omesse anche quando il fit riesce: «maturo» non significa «rappresentativo».

Il metodo `demo-challenger-ridge-v2.0` è una regressione logistica sulle cinque dimensioni in `[-1,+1]`, con pesi regolarizzati verso zero (L2 `0.15`) e intercetta regolarizzata (`0.10`) verso la frequenza storica smussata `(positivi+1)/(N+2)`. Nessuna ricerca degli iperparametri o accesso ai dati di performance nella pagella. `show` restituisce coefficienti, cutoff esclusivo, gruppi, finestre, sigilli e hash di giudizi/esiti: materiale del curatore, mai del valutatore. Le probabilità sono stime, non copie né causalità. Lo script apre `demo-blind.sqlite3` in sola lettura; scrive in `demo-challenger.sqlite3`, affiancato e append-only. Salva separatamente le ricevute per audit: non sono firme contro la manomissione del disco.

**B. Prenotare una volta, poi fare davvero i pronostici.** Prepara con `demo_blind.py plan` almeno **tre nuovi lotti futuri** prima delle uscite, con lo stesso contesto e target/soglia. In un'unica prenotazione blocca l'intera prova, senza conoscere i dossier e senza scegliere le settimane migliori dopo. L'esempio presuppone che i tre piani si chiamino `b21 b22 b23`:

```sh
python demo_challenger.py reserve --artifact ritorno-v2a --batches b21 b22 b23 --launch-dir banco/launch
```

Per ciascun lotto esegui il flusso v1 normale (`intake`, dossier, `judge`, `seal`). **Subito dopo il sigillo v1, entro D+3 dalla prima uscita del lotto, prima di aprire QUALSIASI esito**, congela v2:

```sh
python demo_challenger.py freeze --artifact ritorno-v2a --batch b21 --launch-dir banco/launch
```

Ripeti per `b22` e `b23` alle rispettive scadenze, archiviando gli hash. Nessuna opzione per retrodatare. Si conservano insieme, per gli stessi ID, **v2, v1 già registrata e baseline del piano**, oppure il motivo di esclusione. Nessuna ricerca di esiti in fase di freeze. I gruppi già visti nel fit o in un lotto della prova, e i gruppi usati dalla baseline del lotto, non sono nuovi casi. Se ti sei dimenticato un freeze, il lotto conta come tale; non si può ricostruire ex post dai cinque voti. Non cambiare chiave dei gruppi tra batch. Mantieni tu la corrispondenza fra giochi, demo e fork con più AppID.

**C. Misurare e decidere.** Alle scadenze normali, il custode registra i risultati con `demo_blind.py reveal`. Questo comando può essere ripetuto per vedere i progressi senza rifare alcuna previsione:

```sh
python demo_challenger.py evaluate --artifact ritorno-v2a --launch-dir banco/launch
```

Leggi Brier v2/v1/baseline **sulle stesse coppie**, copertura su tutti gli iscritti, stati e risultati per singola finestra; assente non vale zero. **Non promuovere** finché non sono mature tutte le finestre prenotate (minimo tre), ciascuna con copertura ≥80% e vantaggio v2 su entrambi i confronti, almeno 30 coppie e 6 esiti per classe complessivi, e riduzione del Brier aggregato ≥0,01 contro **entrambi**. Quarantena postuma di una previsione del test o di un esempio usato nel fit → niente promozione. Il gate è una cautela operativa preregistrata, non un test di significatività; superarlo rende il modello soltanto **candidato a revisione umana** per quel bacino. La CLI non cambia la v1. Se correggi il metodo sulla base di questi errori, assegna un nuovo artefatto e **nuove finestre**; il lotto appena visto non torna vergine.
