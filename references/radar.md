# Radar: misura il mercato anche fra due sessioni

Il radar conserva l'archivio comune in `GLS_HOME` (di norma `~/.game-launch-strategist`), separato dai file del gioco. **All'apertura della chat, esegui `check`, non `run`.** Il controllo è locale, non crea file, non consulta Windows e non scarica dati. Un giro manuale o un'attività pianificata richiede una scelta esplicita del proprietario.

Negli esempi `radar.py` indica il percorso completo della copia installata: `<skill>/scripts/research/radar.py`. La directory corrente non conta. Per un archivio diverso usare `GLS_HOME` oppure `python radar.py --home "D:/Archivio radar" …` (l'opzione globale precede il comando).

```text
python radar.py check
python radar.py check --launch-dir "D:/Giochi/Prova/launch"
python radar.py profile add prova --launch-dir "D:/Giochi/Prova/launch"
python radar.py profile list
python radar.py run
python radar.py profile remove prova
```

`profile add` collega una cartella del progetto **già esistente**: autorizza gli aggiornamenti di quel progetto nei giri futuri. Non indovinare il percorso, non registrare la cartella di lavoro della skill. Per spostare un profilo: rimuovi il nome e aggiungilo con il nuovo percorso. `remove` non tocca i file del gioco; lo storico delle fasi rimane nell'archivio privato. Senza profili, funziona la sola raccolta comune.

## Cosa esegue un giro

| Frequenza | Operazione | Dove verificare |
|---|---|---|
| Giornaliera | Giochi seguiti: giocatori contemporanei e snapshot dovuti. Non ricostruisce a posteriori un picco perso. | `market/players.csv`, `market/snapshots.csv` |
| Giornaliera, separata | Censimento demo con `demo_intake.py --days 1`; se manca o la risposta è parziale il radar lo segnala e continua le fasi indipendenti. | Archivio privato del censimento; **nessun trasferimento al giudice**. Non prepara dossier né avvia previsioni cieche. |
| Settimanale | `cohort_bench.py update`: nuove uscite, pagine mancanti e ricontrolli maturati. Il periodo scatta quando la domenica di fine coorte è passata da almeno due giorni (martedì). | `cohorts/cohort_*.csv` e relativi `*.quality.json` |
| Settimanale | Ricerca di più venduti, più giocati e nuovi giochi in crescita (`market_tracker.py discover`); per ogni settimana richiesta **verificata** legge le notizie Steam dei giochi a pagamento rimasti dopo il filtro. `metro` parte dopo notizie e calibrazione. | `market/tracked.json`, `cohorts/_work/<settimana>/apps/<appid>.json`, `calibration.json` |
| Settimanale, per profilo | Aggiornamento comparabili se esiste `comps.csv`; se esiste `prelaunch.json` ricalcola il punteggio prima del registro previsioni e delle 3 mosse. | `<launch>/_raw/comps_calibrated.json`, `_raw/metro.json`, `predictions.json`, `TODO.md`, `calendar.md` |
| Ogni giro, per profilo | Rigenera la pagina privata anche se una fase di mercato o di quel progetto è bloccata. Un avviso datato distingue ciò che manca; scompare dopo la ripresa riuscita. Un errore in un altro progetto non inquina la pagina. | `<launch>/STATUS.html`, `_raw/radar_status.json` |

`run` sceglie le fasi scadute delle due frequenze. `run --cadence daily` fa solo la parte giornaliera (se non esistono ancora giochi seguiti serve prima un giro settimanale); `run --cadence weekly` fa solo la parte settimanale. `run --new-weeks 4` copre le ultime quattro settimane ammissibili (valore predefinito); dopo un'interruzione lunga allarga la finestra, per esempio `run --new-weeks 12`, poi controlla con `check --new-weeks 12`. Si possono chiedere fino a 52 settimane; `0` non scopre nuove coorti. Più settimane possono richiedere ore. Non ricrea osservazioni giornaliere dei giorni in cui il computer era spento.

**Notizie e budget.** Al massimo 120 giochi interrogati per giro, ripartiti tra le settimane richieste: con quattro settimane, 30 per settimana; i giochi già letti non consumano il budget. Una lista vuota restituita dall'API è una lettura, una risposta assente non lo è. Dopo tre errori consecutivi la settimana si ferma. Budget esaurito o dati mancanti → codice `2`, ripresa dai file delle singole app. Le settimane sane avanzano anche se una vicina ha un buco; senza notizie complete il radar non aggiorna il modello individuale. Esempio di ripresa mirata, usando il **percorso vero indicato da `check`**: `python cohort_bench.py --dir "<GLS_HOME>/cohorts/_work/<settimana>" news --paid-only --max-requests 30`. Non retrodata una pagina store: contano solo i segnali ammessi dal protocollo del modello.

**Punteggio del progetto.** Il radar ricalcola anche se cambi `prelaunch.json` nella stessa settimana. Prima di riprovare sposta il vecchio risultato in `_raw/metro.previous.json` (storico, mai usato come valore attuale). Solo uno score individuale corrente viene pubblicato in `_raw/metro.json`; se il comando restituisce soltanto frequenze del campione o “non applicabile”, il risultato va in `_raw/metro.fallback.json` e la pagina lo segnala. Se il modello è bloccato, il comando fallisce o viene rimosso l'input di uno score già gestito dal radar, non viene riproposta la vecchia probabilità. I pronostici **già registrati** restano nel loro storico.

## Come leggere il risultato

- `queue`: fasi dovute o da recuperare. `last_phases`: periodo, inizio/fine locali, tentativi, comando effettivo ed eventuale motivo del problema; `running` rimasto dopo un'interruzione non è un successo. `check --launch-dir …` identifica il profilo locale senza nascondere i lavori condivisi.
- `cohorts`: per settimana mostra `complete`, `partial`, `unverified` (CSV storico senza manifest), `invalid` (manifest illeggibile/incoerente) o `missing`. Espone data del manifest, copertura della finestra e conteggi di giochi, letture delle recensioni e pagine store quando disponibili. Una settimana senza prova di completezza non vale come campione completo. Un buco **fuori** dalla finestra richiesta non viene riempito automaticamente.
- `cohort_backlog`: capsule dei giochi mantenuti ancora senza voto, e ricontrolli a 30/90/180 giorni già maturati ma non ancora misurati, sulle settimane verificate. Un valore mancante **non significa zero giocatori o zero vendite**. Il radar non assegna voti visivi. `calibration` indica data, numero di giochi votati, finestra dell'esito e disponibilità del modello, non una garanzia sull'accuratezza.
- Uscita `0` da `run` = completate le operazioni richieste o già eseguite, **non** “il modello è affidabile”, “la coda umana è vuota” o “il gioco venderà”. `2` = problema, dati parziali o fase bloccata; le fasi indipendenti continuano. `3` = altro giro attivo. `check` restituisce `0` anche quando ci sono lavori in coda: non è un gate commerciale.
- Per riprendere, rilancia lo **stesso** `run`: ritenta i pezzi incompleti e sblocca i dipendenti. Due giri sullo stesso archivio non scrivono insieme. Stato e profili hanno salvataggio atomico in `radar/state.json` e `radar/profiles.json`. Il lock è del sistema operativo, si libera alla chiusura: **non cancellare `radar/lock`**. I messaggi grezzi di rete non vengono copiati nei log del radar.

## Windows: programma solo se lo scegli

```text
python radar.py schedule status
python radar.py schedule install --at 09:00
python radar.py schedule install --at 09:00 --apply
python radar.py schedule uninstall
python radar.py schedule uninstall --apply
```

Senza `--apply`, installazione e rimozione sono **anteprime**. `schedule status` interroga solo l'Utilità di pianificazione locale e mostra nome, comando, ora desiderata/registrata, prossima/ultima esecuzione, ultimo codice e task precedenti rilevati. `schedule` non usa `run` per “provare” l'installazione.

L'attività `\GameLaunchStrategist-Radar` avvia una volta al giorno il Python, lo script e l'archivio specificati con percorsi assoluti. Il proprietario deve avere una sessione Windows aperta; niente password salvate, privilegi elevati o servizio nascosto. `StartWhenAvailable` consente di recuperare un'attivazione persa quando possibile; la frequenza settimanale la decide il radar. Cambiando ora, percorso Python o copia della skill: rimuovere prima il task Radar, poi reinstallarlo.

L'installazione si ferma se trova un nome occupato o attività `WeeklyMarket`/`DailyPlayers` (anche suffissi, trattini o cartelle diverse). Controlla anche le azioni riconoscibili di task rinominati che lanciano `market_tracker.py discover/snapshot`, `cohort_bench.py update`, `radar.py run` o wrapper con i nomi precedenti; non può ispezionare il contenuto di wrapper arbitrari. Ricontrolla prima e dopo la registrazione. Non disabilita, cancella o migra i task precedenti: controlla prima cosa lanciano, poi scegli se conservarli **invece** del radar. La rimozione verifica la ricevuta (`radar/task.json`), il marcatore e l'azione registrata; senza corrispondenza non tocca il task. Su altri sistemi `run` e `check` funzionano da terminale, `schedule` non registra nulla.
