# Replay luglio 2026: interesse pubblico, non fatturato

Protocollo fissato prima della lettura delle etichette individuali del test.
Campione: unica coorte Steam locale 15–21 luglio 2026; giochi con data di
uscita nel periodo, pagina `type=game`, a pagamento nel rilevamento, senza
richiedere un certo esito, tier o conta di recensioni. Lo storico di luglio
era già comparso in un precedente benchmark aggregato: non è un nuovo holdout
prospettico. Nessun addestramento sulle sue etichette.

1. Segnale datato: su tutti i candidati con feed news disponibile e non
   troncato, prevedere positivo se almeno due giorni distinti con news
   ufficiali prima dell'uscita e almeno una menzione pre-uscita di demo o
   Next Fest. Confronto: regola più semplice «qualunque menzione pre-uscita
   di demo/Next Fest». Misure: tabella di confusione, richiamo e precisione
   alle soglie fissate. Le date sono quelle di pubblicazione; archivio
   recuperato successivamente. Non è il vecchio metro commerciale.
2. Giudizio del pitch: fra candidati con menzione ufficiale pre-uscita
   di demo, descrizione breve utilizzabile, prendere i primi 48 nell'ordine
   SHA256(`gls-july-pitch-20261126:` + appid), senza consultare gli esiti.
   Copiare solo il testo, togliendo identità note, link e frasi con indicatori
   di successo. Due valutazioni AI indipendenti e senza tool sullo stesso
   identico testo. A: impressione complessiva 1–5 (mezzi punti ammessi).
   B: chiarezza del loop, gancio distintivo, scelte/varietà promesse,
   pubblico riconoscibile, ciascuno 1–5, media semplice.
   Entrambi: `p = 0.5 + (voto-3)/8`; positivo se `voto >= 3.5`.
   Se riconosciuto, non interpretabile o contaminato: astensione, conservare
   il caso, confronto sulle stesse coppie. Non chiedere sensazioni ai comandi
   né inventare gameplay: il pitch è la **pagina archiviata dopo l'uscita**,
   non una copia dimostrabilmente uguale alla pagina di lancio.
3. Prima della rivelazione: salvare i punteggi per alias, sigillo SHA-256,
   identificazione del metodo, data UTC. Rivelare soltanto `reviews_d30`
   con data di verifica fra uscita+D30 e data dell'audit inclusa. È una
   ricostruzione da istogramma: 30 recensioni **non sono** 30 acquirenti.
   Tabella di confusione, accuratezza, Brier, AUC e differenza appaiata
   (bootstrap per gioco, 10.000 ricampionamenti, seme 1126). Confronto
   banale «nessuno supera la soglia»; per il Brier la baseline ingenua
   preregistrata è p=0,5. Non adattare regole o soglie dopo la verifica.

Non è la misura della precisione di `demo_blind.py` o di `demo_challenger.py`.
Quel confronto richiede gameplay anonimo, previsioni storiche congelate e
risultati indipendenti sugli stessi giochi. Gli esempi simulati non contano.
