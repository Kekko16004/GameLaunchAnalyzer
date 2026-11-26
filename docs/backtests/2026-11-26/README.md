# Cosa predice il pitch a risultati nascosti?

**Risposta:** sulla coorte analizzata non è migliorato il giudizio sul pitch.
Due sessioni AI indipendenti hanno ricevuto solo lo stesso elenco di testi e
alias; il confronto è fra **impressione libera** e **rubrica testuale a quattro
voci**, non fra due versioni del modello sulle demo giocate. La rubrica ha
individuato più giochi sopra soglia, ma ha generato molti più falsi positivi.

**Esito osservabile:** almeno 30 recensioni nei primi 30 giorni, come
ricostruito nell'archivio locale Steam. Non sono copie, ricavi, redditività
né ritorni alla demo. Soglia e regole fissate nel [protocollo](protocol.md)
prima di aprire i risultati. Il punteggio non è una probabilità già calibrata.

## Stessi 47 giochi, zero esiti mostrati ai giudici

Tra i giochi a pagamento della settimana 15–21 luglio 2026, 173 avevano
una menzione ufficiale pre-uscita di demo e un pitch utilizzabile. Selezionati
48 per hash, nessuna astensione, 47 con esito D30 utilizzabile; 26 sopra
soglia, 21 sotto. La descrizione disponibile è quella archiviata dopo
il lancio, non una copia garantita di quella pubblicata prima. I titoli
noti al preparatore sono stati rimossi; eventuali alias rimasti nel testo
non garantiscono anonimato assoluto. Nessun valutatore ha segnalato di
riconoscere un gioco. Un giudice per metodo: non si separa l'effetto della
rubrica dalla variabilità tra esecuzioni.

| Metodo | Pronostici giusti | Giochi sopra soglia trovati | Falsi allarmi | Probabilità: errore Brier ↓ |
|---|---:|---:|---:|---:|
| Impressione commerciale | 31/47 (66,0%) | 16/26 | 6 | 0,212 |
| Chiarezza, gancio, varietà, pubblico | 25/47 (53,2%) | 21/26 | 17 | 0,262 |

La rubrica recupera cinque successi netti al costo di undici falsi allarmi
netti. Aggiunge valore come lista di cose da controllare, **non** come
previsione migliore. Delta accuratezza −12,8 punti percentuali (intervallo
bootstrap appaiato 95%: −29,8 … +6,4); peggioramento Brier +0,050
(+0,011 … +0,090). L'errore Brier di una probabilità fissa di 0,5 è 0,250.
Anche ignorando la soglia scelta, la capacità di ordinare sopra/sotto
(AUC) è 0,766 per l'impressione e 0,508 per la rubrica. L'incertezza
calcolata non copre altre settimane, revisioni della pagina o altri giudici.

Due esempi per interpretare l'errore: P47, un puzzle che descrive chiaramente
le proprie regole, riceve 4,75 dalla rubrica ma non arriva alla soglia; P19,
un racconto folk che comunica atmosfera più che meccaniche, riceve 2,75 e
la supera. Sono esempi, non dimostrazioni che la causa sia il genere o il
marketing. Identità aperte dopo il sigillo: [Prime Prism, P47](https://store.steampowered.com/app/4364970/)
ha **0** recensioni D30 nella ricostruzione in archivio;
[Scarlet Deer Inn, P19](https://store.steampowered.com/app/1553260/) ne ha **333**.
Fonte dei conteggi: `cohort_2026-07-15_2026-07-21.csv`, campi `reviews_d30`
e `checked_d30` (2026-10-13), non i totali correnti delle pagine linkate.
Nessuna soglia o peso è stato ritoccato dopo averli aperti.

## Segnali pubblicati prima del lancio: 538 giochi confrontabili

574 candidati in archivio, 571 con feed utilizzabile, **538** con segnale
e risultato abbinabili; 146 sopra soglia. Regole e verdetti calcolati prima
di aprire i conteggi D30.

| Chiamare positivo quando… | Corretti | Precisione dei sì | Giochi sopra soglia trovati |
|---|---:|---:|---:|
| Mai (riferimento banale) | 392/538 = 72,9% | — | 0/146 |
| C'è una notizia ufficiale di demo o Next Fest prima del lancio | 395/538 = 73,4% | 86/169 = 50,9% | 86/146 |
| Come sopra, più attività ufficiale in almeno due giorni distinti | 402/538 = 74,7% | 80/150 = 53,3% | 80/146 |

La regola più selettiva guadagna **7 classificazioni corrette (+1,3 punti)**
contro l'altra regola: 13 falsi allarmi in meno, ma 6 successi in più
mancati. Non è una prova di un miglioramento del modello di gameplay né
un guadagno da applicare ai giochi del proprietario.

## Riproducibilità e limiti

- [Voti A](a.json), [voti B](b.json), [pronostici congelati](frozen.json),
  [risultati per alias](results.json), [codice](replay.py).
- Sigillo prima della rivelazione: `d37336fac5b6e0e060038ec40bb19ae5fe882d835cf71498d43cbc7da2781208`.
  L'archivio di esecuzione privato è `~/.game-launch-strategist/backtests/pitch-20261126/`.
  Per riprodurre: nuova cartella, `replay.py prepare CARTELLA`, copiarvi
  `a.json` e `b.json`, `replay.py freeze CARTELLA`, quindi `replay.py reveal
  CARTELLA --seal HASH_STAMPATO`. Servono la coorte e le cache originali.
- I casi sono storici e l'esistenza della coorte e di un vecchio benchmark
  aggregato erano note. Gli esiti individuali non sono entrati nei due
  input di giudizio; il confronto non è un pronostico pubblicato a luglio.
- Nessun archivio di demo **giocate** con voti storici multi-gioco e vendite
  o ritorni reali abbinabili è stato trovato. Il delta tra `demo_blind` v1
  e `demo_challenger` v2 su esiti futuri rimane **non misurato**.
