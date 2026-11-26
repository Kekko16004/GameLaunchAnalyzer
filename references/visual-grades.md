# Voti delle capsule: due domande, due archivi

**Tier globale:** rispetto alle ancore fisse di *questo genere*, quanto bene la capsula comunica in piccolo? A/B/C descrive la presentazione, non la qualità del gioco, le vendite né la somiglianza al progetto. **Somiglianza:** quanto la direzione visiva è vicina a quella della *nostra* capsula? Una capsula A può essere `distant`. Uno storico `grade=B` significava «circa al livello del mio gioco»: non copiarlo in `global_tier`.

Lo strumento (`scripts/research/visual_grades.py`, Python standard, offline) **non vede le immagini**. Prepara pacchetti, convalida giudizi esterni e applica solo quelli che superano il protocollo. Nessuna immagine di mercato né alcun voto autentico sono forniti come dato iniziale.

## 1. Congela il metro prima di vedere gli esiti

Un curatore sceglie, con diritti d'uso locale, almeno tre **capsule vere e distinte** per un genere, con la stessa funzione e proporzioni delle capsule da giudicare. Meglio più di un esempio per fascia e stili diversi: un look minimalista non è automaticamente C. Non selezionare per recensioni, vendite o fama. Escludi dal lotto gli ancoraggi; immagini identiche a un'ancora sono escluse automaticamente. Scrivi una nota su un dettaglio *osservabile*, senza nome del titolo né segnali di successo. In `source` conserva privatamente provenienza e data di acquisizione, senza credenziali.

Rubrica `capsule-v1`: guarda alla stessa dimensione (circa 230 × 108 px), poi verifica a risoluzione originale. Valuta **gerarchia e leggibilità** di titolo/soggetto, **riconoscibilità della promessa di genere**, **coerenza e rifinitura** della composizione. Per A devi indicare perché raggiunge il riferimento alto; B è la fascia intermedia tra le ancore, non il default; C ha una debolezza visibile paragonabile al riferimento basso. Non dare punti per budget apparente, quantità di dettagli, genere di tua preferenza o coincidenza con il progetto.

Modello di `pack.json` (i nomi sono esempi di **file da fornire**, e le osservazioni vanno sostituite dopo lettura):

```json
{
  "genre": "puzzle", "version": "v1", "curator": "curatore-01",
  "anchors": [
    {"tier":"A","image":"capsule/alta.png","source":"provenienza e data","note":"Motivo visivo della fascia alta"},
    {"tier":"B","image":"capsule/media.jpg","source":"provenienza e data","note":"Motivo visivo della fascia intermedia"},
    {"tier":"C","image":"capsule/bassa.webp","source":"provenienza e data","note":"Motivo visivo della fascia bassa"}
  ]
}
```

Usa la via assoluta dello script se sei fuori dalla sua directory. Negli esempi PowerShell:

```powershell
$vg = (Resolve-Path scripts/research/visual_grades.py).Path
python $vg freeze --manifest D:/archivio/pack.json
```

Il pack viene copiato in `$GLS_HOME/visual/packs/puzzle/v1` (default `~/.game-launch-strategist/visual/`). La coppia genere/versione non si sovrascrive. Il manifest lega i byte delle immagini con SHA-256; anche note, rubrica e fonti entrano nell'identità del pack. Per cambiare ancora o criterio serve una **nuova versione**, non una modifica a mano. Ripeti per ogni genere; «global» vuol dire indipendente dal progetto, **non** che A di generi/versioni diversi abbia identica distribuzione. Documenta il genere scelto prima del voto nei casi ibridi; non provare più pack per tenere il tier migliore.

## 2. Dividi la settimana e assegna il lotto cieco

```powershell
$week = 'D:/archivio/cohorts/cohort_2026-09-07_2026-09-13.csv'
python $vg prepare --pack puzzle/v1 --week $week --size 30 --chunk 1
```

`prepare` segue il file `.source` affiancato al CSV oppure `--headers D:/archivio/work/headers` (file `<appid>.jpg|png|webp|jpeg`). Usa solo righe `keep` con genere/tag corrispondente al nome del pack: `Puzzle` → `puzzle`, `City Builder` → `city-builder`. Ordina per appid e suddivide *prima* di escludere le immagini assenti: usa i blocchi `1..chunks` sulla stessa settimana senza selezionare i titoli «belli». Conserva conteggi esclusi e motivi; un lotto totalmente senza immagini fallisce. Un'immagine entra solo se il suo hash coincide con `header_sha256` registrato dal collector per quella riga. Vecchia settimana senza hash? **Non riempire il campo a mano** né usare l'header odierno come prova pre-lancio. Una ricattura è una nuova osservazione. `store_observed_on` data i dettagli del negozio, non i byte della capsula.

L'output dà `batch`, `blind`, `n`, `skipped`, `chunk`, `chunks`. Consegna al valutatore **solo la cartella `blind`**, non il CSV, la directory di lavoro, `.source`, `key.json`, i vecchi fogli nominativi, le metriche o la capsula del progetto. Apri davvero tutte le immagini del `packet.json`, incluse le ancore; non inferire nulla dai nomi dei file. Il cieco nasconde le etichette e gli esiti, non può cancellare marchi già disegnati sulla capsula o i ricordi di chi la riconosce. Se riconosci il titolo e conosci i risultati, segnala `doubt=1`; se non puoi formulare un giudizio visivo, scrivi `?`.

Scheda da dare all'agente:

> Per ogni id del pacchetto confronta solo ciò che vedi con le ancore del genere. Restituisci CSV `id,tier,confidence,doubt,note`: A/B/C oppure `?`; confidenza soggettiva tra 0 e 1, **non** probabilità di vendita; `doubt` 0/1; una frase su un dettaglio visibile e la differenza rispetto all'ancora. Su immagine non apribile, `?,0,1` spiegando il limite. Non cercare il titolo online, non leggere dati adiacenti, non usare la mia capsula come B. Non inventare risposte mancanti.

```powershell
$batch = 'ID_ESATTO_STAMPATO_DA_PREPARE'
python $vg import --batch $batch --votes D:/lavoro/voti.csv --rater modello-revisione-pass1
```

Un file completo per lotto, id copiati dal pacchetto e non numeri di riga. Id assenti, ripetuti o estranei, confidenza invalida, digest cambiato o nota vuota bloccano l'intero import. Il primo giudizio non può essere rimpiazzato dopo aver visto la QA.

## 3. Seconda lettura e applicazione

Il **15% casuale arrotondato in alto (minimo uno)** è estratto prima del primo voto; aggiungi *tutti* i `?`, i `doubt=1` e i casi con confidenza < 0,70. Fornisci al secondo valutatore esclusivamente la **nuova** cartella cieca stampata da `import`. Id nuovi, nessun primo voto né motivo della selezione. Usa la stessa rubrica e lo stesso formato; meglio una persona o un modello indipendente in un contesto pulito. Cambiare lo pseudonimo dello stesso giudice non rende indipendenti due giudizi: la CLI non può autenticare il valutatore.

```powershell
python $vg qa --batch $batch --votes D:/lavoro/seconda-lettura.csv --rater revisore-02
```

Se nel campione preregistrato il revisore non conferma un tier o resta incerto, l'output `extended_qa` chiede la **restante parte del lotto**. Consegnala allo stesso revisore con le stesse precauzioni e ripeti `qa` col nuovo file. Senza QA richiesta completa, `apply` fallisce. Per i casi riletti prevale la seconda lettura indipendente; incertezza residua/`?` non dà alcun tier. Gli altri passano per QA **del lotto**, non come se fossero stati riletti individualmente.

```powershell
python $vg apply --batch $batch --week $week
```

L'output distingue `sample_exact / sample_size` (conferme nel campione casuale), `reread`, `global_verified` e `withheld`. Non interpretare l'accordo come accuratezza di previsione. Se due lettori discordano spesso, sospendi gli altri lotti e ricalibra un *nuovo* pack, non aggiustare quello usato dopo aver visto gli esiti.

La scrittura atomica sul CSV settimanale controlla di nuovo appid, `keep`, genere e `header_sha256`. Eseguila **tra** due aggiornamenti del collector, non durante una riscrittura della settimana. Non modifica il manifest qualità: una settimana parziale non diventa completa grazie alla QA visiva. Colonne nuove:

| Campo | Contratto per gli altri strumenti |
|---|---|
| `grade` | Originale lasciato intatto, sempre legacy: mai fallback globale. |
| `global_tier` | A/B/C solo da lotto approvato. Mancante = non osservato, non B. |
| `grade_scope` | `global_verified` per `global_tier`; `legacy` per la sola vecchia etichetta; altrimenti vuoto. |
| `anchor_pack` | `genere/versione@<sha256 del manifest>`: non rimescolare versioni senza dichiararlo. |
| `visual_batch` | Id audit in `$GLS_HOME/visual/batches/`; `key.json`, primo voto, secondo voto ed eventuale estensione consentono la verifica per singolo caso. |

Il modello usa solo tier con **tutti e quattro** i nuovi campi coerenti e continua ad applicare i suoi vincoli su completezza e tempi: «voto QA» non prova che l'immagine fosse osservabile prima dell'uscita. Il collector conserva i campi al refresh solo se descrivono ancora la stessa immagine. `apply` non sostituisce un tier già attribuito da un altro lotto.

## 4. Somiglianza al singolo progetto (facoltativa)

Solo dopo aver chiuso il globale, mostra al valutatore la capsula locale del progetto e le immagini con gli id del **primo** `packet.json`. Chiedi: «Soggetto, composizione e linguaggio grafico si rivolgono allo stesso immaginario?», non «è migliore del mio gioco?». Ignora le lettere delle ancore. Usa `id,similarity,confidence,doubt,note` con `close`, `partial`, `distant` oppure `?`.

```powershell
python $vg compare --batch $batch --reference D:/mio-gioco/capsula.png --votes D:/lavoro/simili.csv --rater revisore-progetto --launch-dir D:/mio-gioco/launch
```

Ottieni `launch/visual_comparisons/<batch>-<hash>/comparison.json`: riferimento per hash, appid, somiglianza, confidenza, dubbio e motivo. Usalo per scegliere comparabili o esplorare divergenze, **non** per addestrare un tier globale. Non viene inserito nel CSV né condiviso tra progetti.
