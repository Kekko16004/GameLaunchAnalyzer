# Dopo il lancio: misurare prima di spendere ancora

Serve quando il gioco è già fuori o la demo/beta ha utenti reali. Identifica build e data di uscita senza ripetere domande già risolte. Parti da ciò che è successo: proponi tu il passaggio da verificare, la finestra e la metrica. Non chiedere quale risultato commerciale si vuole raggiungere. Per una demo gratuita osserva uso e ritorno, non copie vendute. Per una diagnosi quantitativa il proprietario può fornire **conteggi aggregati**; senza, dichiara cosa non si può concludere. Ore/euro residui sono facoltativi per la diagnosi; nessun esperimento a pagamento senza limite e autorizzazione. Mai chiedere accesso all'account né export nominativi.

## 1. Preparare il CSV locale

Il proprietario seleziona nel pannello due **periodi chiusi** di uguale durata; trascrive o rinomina le colonne in un CSV UTF-8 con virgole (BOM facoltativo). Questo è un **formato di scambio**, non un lettore universale di export Steamworks/itch. Non copiare token, ordini, email, ID dei giocatori, link traccianti o dati fiscali. Una riga per conteggio; niente stime da recensioni, follower o picchi pubblici. Tieni l'originale fuori dal repository e da cartelle condivise.

Esempio interamente fittizio, non un benchmark:

```csv
start,end,source,segment,metric,value
2026-10-01,2026-10-07,steamworks,store-all,impressions,1000
2026-10-01,2026-10-07,steamworks,store-all,store_visits,160
2026-10-08,2026-10-14,steamworks,store-all,impressions,1200
2026-10-08,2026-10-14,steamworks,store-all,store_visits,120
```

- `start,end`: date inclusive `AAAA-MM-GG` nel fuso del pannello, **non la data di esportazione**. Per una coorte usa l'intervallo di ingresso (acquisto/primo avvio); esporta solo una volta maturata la stessa durata di osservazione per tutti. Annota fuso e maturazione nel tuo registro. Un totale dalla pubblicazione non è un conteggio settimanale; non sommare letture cumulative. Se il pannello non offre un dato con questa definizione, ometti la riga.
- `source`: `steamworks`, `itch`, `telemetry` (telemetria del proprio gioco), `playtest` (test reale). `segment`: nome stabile del pubblico/perimetro, es. `store-all`, `demo-it`, `paid-refund-30d`. Solo lettere minuscole ASCII, cifre, `_` e `-`, massimo 48 caratteri; inizia con lettera o cifra. Non inserire identificativi di persone. Una coppia numeratore/denominatore deve riferirsi allo **stesso** perimetro, periodo e fonte.
- `value`: intero non negativo senza separatori delle migliaia, percentuali o valuta. Zero solo se osservato. Non espandere una percentuale stimando il conteggio.

| Passaggio | `metric` da esportare (numeratore / denominatore) | Che cosa conta |
|---|---|---|
| Esposizione Steam | `store_visits` / `impressions` | Visite ed esposizioni sulle stesse superfici. Se non puoi isolare le visite da quelle superfici, non interpretarlo come tasso di clic. |
| Interesse per la pagina Steam | `wishlist_adds` / `store_visits` | **Nuove aggiunte** del periodo, non saldo/stock wishlist. |
| Acquisti Steam | `units_sold` / `store_visits` | Copie a pagamento lorde, senza chiavi gratuite. Indice di volumi per 100 visite, **non** probabilità di acquisto di un visitatore. |
| Acquisto dalla wishlist Steam | `wishlist_buyers` / `wishlist_eligible` | Acquirenti unici provenienti dal gruppo in wishlist all'inizio / persone di quel gruppo. Se disponi solo delle vendite totali, lascia vuoto. |
| Pagina itch | `itch_downloads` / `itch_views` | Download e visite del periodo. Un nuovo download non garantisce un nuovo giocatore. |
| Demo (Steam, telemetria o test) | `demo_completions` / `demo_players` | Giocatori unici della stessa coorte che raggiungono il punto finale / giocatori osservati abbastanza a lungo. |
| Rimborsi Steam | `refunds` / `refund_eligible` | Copie di quella coorte rimborsate entro un orizzonte fissato / copie pagate della coorte già osservate per tutto l'orizzonte. Non usare rimborsi emessi oggi su acquisti passati divisi per vendite di oggi. |
| Ritorno al giorno 7 (Steam, telemetria o test) | `returned_d7` / `eligible_d7` | Nuovi giocatori tornati nel giorno 7 / nuovi giocatori osservabili fino al termine del giorno 7; usa la stessa definizione del giorno nel confronto. |
| Recensioni Steam | `positive_reviews` / `reviews` | Positive tra le nuove recensioni dello stesso insieme. Non rappresentano tutti gli acquirenti. |

## 2. Importare e fare la diagnosi

Esegui da qualsiasi cartella, sostituendo i percorsi con quelli reali. Su Windows va bene `py -3` al posto di `python`. Opzioni globali **prima** del sottocomando.

```text
python "<skill>/scripts/research/post_launch.py" --launch-dir "<gioco>/launch" import "<privato>/periodi.csv"
python "<skill>/scripts/research/post_launch.py" --launch-dir "<gioco>/launch" diagnose --end 2026-10-14 --compare-end 2026-10-07
```

`import` convalida tutto prima di aggiornare `launch/metrics.csv`; ripetere lo stesso import non cambia il file. `date,metric,value,note` resta leggibile da `metrics_track.py`: i conteggi di periodo si chiamano `post_` + nome della metrica, senza contaminare le serie manuali/cumulative; la nota registra inizio, fonte e segmento. Un solo valore e contesto per **(data di fine, metrica)** come nel tracker: scegli un segmento per analisi, non mescolare segmenti dello stesso giorno. Conflitto, input vuoto o riga errata → codice diverso da zero e nessun aggiornamento delle metriche. Per rettificare una riga controlla il grezzo e fai una copia privata del registro prima di correggerla. Non eseguire in contemporanea altri comandi che riscrivono il registro. Un `.post-launch-import.lock` può rimanere dopo un arresto anomalo: rimuovilo solo dopo aver verificato che non vi sia un import attivo.

`diagnose` rigenera **solo** `launch/post-launch.md` (non salvarci annotazioni manuali). Senza `--compare-end` dà una fotografia, non un andamento. Senza misure scrive cosa manca, non un fallimento commerciale. Con l'esempio: da **160/1000 = 16** a **120/1200 = 10** visite per 100 impression. Sono 6 visite in meno per 100 esposizioni, **non la prova che la capsula abbia peggiorato i clic**. Nessun invio in rete; sia `metrics.csv` sia il report sono privati. Non pubblicare `launch/` né includere questa sezione in materiali condivisi senza scelta esplicita e revisione dei contenuti.

## 3. Dalla diagnosi a una decisione

1. **Individua il primo passaggio con dati sufficienti**, non semplicemente la percentuale minore. Meno visite ma rapporto stabile? Controlla esposizione e fonte di traffico. Visite stabili e meno acquisti? Confronta prezzo effettivo, sconti, lingue, canali e descrizione. Più rimborsi o meno ritorni? Prima di comprare traffico, verifica problemi concreti nelle prime sessioni. Periodi con festival, aggiornamenti o pubblico diverso non sono controlli equivalenti anche se le date combaciano.
2. **Scrivi una prova prima di avviarla.** Esempio: «Sostituisco solo la prima immagine; proprietario: responsabile store. Stessa pagina, prezzo e fonte. Misuro acquisti lordi e visite, verifico anche rimborsi maturi. Leggo alla data ___, con almeno ___ visite e perdita massima ___ euro/ore». Il proprietario compila i limiti rispetto al piano, non usando un tasso generico del settore. Se possibile assegna in parallelo le due versioni a pubblici equivalenti; prima/dopo è solo un indizio. Non fermare una prova al primo giorno favorevole.
3. **Decidi al controllo programmato** e scrivi scelta, numeratore/denominatore, date, limiti e responsabile nel `TODO.md` o nel debriefing. **Continua** entro il tetto se supera il risultato concordato senza peggiorare i segnali di danno; replica prima di aumentare la spesa. **Cambia** una sola leva quando il problema ricorre, c'è una prova praticabile e resta budget. **Stop** alla prova/spesa se si raggiunge il limite di perdita o, dopo la replica concordata, non resta una strada sostenibile. Se mancano osservazioni, segna **inconcludente**: decidi se misurare ancora entro il tetto, non dichiarare il gioco irrecuperabile. Il proprietario, non lo script, approva investimenti e stop.
