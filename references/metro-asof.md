# Metro e pronostici: che cosa è stato davvero verificato

`asof-v1` indica il protocollo di prova, **non** un bollino di accuratezza. L’esito è una fascia di **copie stimate dalle recensioni**, non il venduto Steamworks. Il modello riguarda uscite nuove, classificate a pagamento nel campione; non si applica a giochi gratuiti, né misura l’effetto causale di fare una demo o un trailer.

Da una shell nella radice della skill, su un archivio locale già raccolto:

```powershell
python scripts/research/cohort_bench.py calibrate --dataset dati/cohorts --market-dir dati/market -o dati/calibration.json
python scripts/research/cohort_bench.py metro --dataset dati/cohorts --calibration dati/calibration.json
python scripts/research/cohort_bench.py score --features launch/prelaunch.json --calibration dati/calibration.json -o launch/_raw/metro.json
python scripts/research/predictions.py --launch-dir launch sync
python scripts/research/predictions.py --launch-dir launch eval
```

Per un replay offline aggiungere `--today YYYY-MM-DD` **prima** del sottocomando. Non retrodatare uno score live o una pagina osservata oggi.

* **Completezza:** `quality` conta settimane utilizzabili, incomplete e non certificate. `legacy_descriptive` conserva separatamente i riepiloghi storici dove possibile. Un `grade=B` storico non è una fascia globale: servono `global_tier`, `grade_scope=global_verified`, pacchetto di ancore e batch di revisione. Prezzo e genere nelle tabelle descrittive si riferiscono alla pagina rilevata, non necessariamente alla pagina pre-lancio.
* **Segnali:** una demo menzionata in una notizia datata prima dell'uscita è documentata; il flag demo nella pagina di oggi non documenta il passato. Analogamente per video, screenshot, lingue e prezzo: entra la pagina solo se `store_observed_on < release_date`. Mancanza di menzioni ≠ certezza che l'evento non sia avvenuto. Il conteggio delle notizie si limita al feed recuperato. Un voto visivo senza osservazione datata prima dell'uscita non è una caratteristica pre-lancio. L'affollamento *effettivo* del giorno d'uscita non è un predittore.
* **Prova:** ogni settimana di test usa solo esiti D30/D90 già maturi **e già rilevati prima del lunedì** di quella settimana. Il modello e le baseline si ricalcolano per ciascun fold, senza usare le etichette di test. `backtest.folds` espone cutoff, ultimo controllo, numerosità, caratteristiche e Brier. Confrontare il Brier (più basso è meglio) con la frequenza storica e con quella delle ultime quattro settimane di training disponibili. Intervalli di Wilson: in percentuale; descrivono il campione, non le probabilità di successo del proprio gioco.
* **Decisione:** sotto 60 giochi con esito osservato non c’è un metro; sotto due settimane di test, 30 osservazioni di test o con vantaggio non stabile non viene emessa una previsione personalizzata. Servono almeno cinque esempi di entrambi gli esiti della soglia 1.000 copie. `score.mode=base_rate` mostra solo le frequenze del campione; `not_applicable` non ha probabilità; solo `model` può fornire leve. I campi progetto mancanti non diventano automaticamente zero/B. Anche una leva valida è una variazione del modello, non il ritorno garantito dell'investimento.

Per preregistrare e valutare due revisioni della stessa ipotesi usare lo stesso `--series`; usare serie diverse per scenari distinti:

```powershell
python scripts/research/predictions.py --launch-dir launch add --metric real_wishlist_pct --value 35 --unit "%" --series demo-en --until 2027-01-31
```

Una misura chiude una previsione solo dopo la sua data e la registrazione (a risoluzione giornaliera), entro `--today` e l’eventuale `--until`, non prima di `--due`, e prima della revisione successiva. Si prende la prima misura ammissibile. La mediana D30 si confronta con `copies_30d`, non con D90. Le vecchie stime automatiche di cui non si può verificare il protocollo restano nel registro ma non contano nel tasso di successo.
