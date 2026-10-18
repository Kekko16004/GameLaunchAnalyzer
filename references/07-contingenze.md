# Fase 7C: piani di contingenza ("se… allora") e metriche

Decidere **prima** cosa guardare, quando diventa un problema, cosa controllare per primo e cosa fare. Il pre-mortem (7B) dice cosa può andare storto; qui diventa un sistema misurabile. Si esegue dopo la Fase 7B e dopo il Round 6 dell'intervista (`00-intervista.md`): soglie e azioni sono quelle **del proprietario**, tu le rendi misurabili e le correggi con i dati.

Output: `launch/_raw/contingencies.json` (sorgente), `launch/05d-contingenze.md` (testo del report), `launch/metrics.csv` (le metriche che l'utente registra) e, nella pagina HTML, la sezione "Se… allora" aggiornata dallo strumento.

## Strumento

```bash
python3 <skill>/scripts/research/metrics_track.py catalog                                  # nomi usuali delle metriche e dove si leggono
python3 <skill>/scripts/research/metrics_track.py add --metric itch_views --value 412 --note "dopo il post su Reddit"
python3 <skill>/scripts/research/metrics_track.py check                                    # valida contingencies.json
python3 <skill>/scripts/research/metrics_track.py status --md launch/metrics-status.md --json launch/_raw/metrics_status.json
```
Esce con codice 2 se uno scenario con gravità `ALARM` è scattato. Le wishlist si leggono da sole da `launch/wishlists.csv`. Formato completo di `contingencies.json` nella testata dello script.

## Come si costruisce

1. **Elenca le variabili** per fase (matrice sotto), tenendo solo quelle che toccano le decisioni del proprietario.
2. **Per ogni scenario scrivi:** segnali misurabili (metrica, tipo `level` / `gain` / `avg` / `drop` / `ratio`, finestra, soglia), data di inizio della valutazione, gravità, **diagnosi in ordine** (cosa controllare prima, dalle spiegazioni più economiche da verificare), **azioni dalla più economica** (con chi le fa e il costo), **decisione** (continuare, cambiare, fermarsi) e **origine della soglia**.
3. **Soglie:** parti dai benchmark reali (`genre_bench.py`, `store_bench.py`, `review_corpus.py`, comparabili) e dalle risposte del Round 6. Se non c'è un dato, la soglia è **[OPINIONE]** e lo scrivi in `evidence` con il perché. Mai soglie senza origine.
4. **Una azione alla volta:** nelle azioni metti prima le prove economiche (cambiare cover, riscrivere le prime righe, chiedere ai tester di condividere) e solo dopo le costose (cambiare il gioco).
5. **Collega** gli scenari alle metriche da registrare e al calendario: ogni controllo ha una data (riga di tipo `tripwire` nel calendario e passo 👤 "registra le metriche").
6. **Controlla** con `metrics_track.py check`.

## Matrice delle variabili (punto di partenza, adatta al gioco e alle risposte)

| Fase | Variabile | Segnali tipici | Prima diagnosi | Prime azioni economiche |
|---|---|---|---|---|
| Beta su itch.io, prima settimana | pochi arrivi | visite in 7 giorni, provenienza | traffico o pagina? | cover e prime righe, clip su TikTok con link, condivisione dei tester |
| | arrivano ma non scaricano | scarichi / visite | la pagina promette ciò che il gioco è? | screenshot e GIF migliori, tagline, prezzo |
| | scaricano ma non tornano | seconda sessione, durata media | dove escono (minuto, schermata) | primi 10 minuti, tutorial, difficoltà |
| | molti bug | crash, segnalazioni per sessione | un bug o molti diversi? | hotfix mirato, telemetria |
| | nessun feedback | commenti, moduli compilati | il modulo è visibile? | pulsante in gioco, domanda mirata |
| Test reale (Gate B) | sessione corta o niente seconda sessione | tester, minuti, % seconda sessione | punto di abbandono | fix e secondo test |
| Pagina Steam online | wishlist sotto il percorso | wishlist a settimana contro lo scenario | capsule, tag, trailer, traffico | capsule A/B, primi 5 tag, trailer, creator |
| | visite senza wishlist | wishlist per visita | pagina debole | descrizione, GIF, prezzo annunciato |
| | poche impression | impression, click sulla capsule | tag e capsule | rifare capsule, tag |
| Demo | giocata troppo poco | durata mediana, % che finisce | dove si ferma | patch demo, tutorial |
| | gioca ma non mette in wishlist | wishlist da demo | call to action, fine demo | schermata finale con wishlist |
| Next Fest | sotto le mediane | wishlist nel fest, giocatori demo | visibilità o qualità? | livestream, risposte, creator, hotfix |
| Pagina o verifiche | pagina rifiutata, verifica fiscale in ritardo | stato Steamworks | motivo del rifiuto | correggere e reinviare, spostare le date |
| Lancio, prima settimana | poche recensioni, % positive bassa | recensioni, % positive, rimborsi | temi nelle negative (`steam_reviews.py`) | hotfix dei temi dominanti, risposta ai recensori |
| | rimborsi alti | refund rate, ore alla recensione | prime ore | primi 30 minuti, prezzo |
| Esterni | concorrente nella finestra | `watchlist.py` (ALLARME collisione) | quanto è simile | spostare la data, differenziare il messaggio |
| Persone | tempo dimezzato, socio che esce | ore reali a settimana | cosa taglia | tagliare scope, spostare il lancio |
| Successo improvviso | picco di giocatori o wishlist | giocatori, recensioni, wishlist | server, bug, aspettative | hotfix, comunicazione, piano di aggiornamenti |

## Come si presenta

- In `05d-contingenze.md`: una sezione per scenario, con tabella dei segnali, diagnosi, azioni, decisione e origine della soglia, e in testa la matrice riassuntiva.
- Nel report e nell'HTML: la sezione "Se… allora" mostra lo stato di ogni scenario (Scattato / Ok / Senza dati / Non ancora attivo) con icona **e** etichetta, e apre da sola quelli scattati.
- Alla routine settimanale (`06-synthesis-output.md`) si eseguono `wl_track.py status`, `metrics_track.py status` e `watchlist.py snap` + `report`; un ALLARME va riportato subito con l'azione di emergenza.

## Limiti da dichiarare

Le soglie sono ipotesi calibrabili: dopo le prime settimane di dati reali vanno riviste (annota la revisione). Poche osservazioni danno rumore: non reagire a una sola rilevazione, a meno di un ALLARME definito per quel caso.

---

## Soglie dal mercato reale

Le soglie dei tripwire di vendita ("sotto N copie a 30 / 90 giorni") si ancorano al base rate della fascia del gioco in `calibration.json`: p25 della fascia B al suo prezzo = allarme, mediana = in linea, p75 = sopra le attese. Durante il lancio, `market_tracker.py snapshot` (a +24h, 48h, 1 settimana, 1 mese, 3 mesi) e `--players-only` più volte al giorno misurano lo stesso percorso sul gioco e sui concorrenti; `timeline` mette accanto eventi e picchi (un evento prima di un picco non prova che lo abbia causato). L'ordine dei passi dei B vincenti (demo, Next Fest, trailer, creator) è in `calibration.json` → `marketing`.
