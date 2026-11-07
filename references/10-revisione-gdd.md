# Modalità Revisione GDD: valutare l'idea e renderla molto migliore

Si usa quando c'è un GDD (o un'idea scritta) e ancora poco o niente gioco: tipicamente subito dopo il lock del GDD di `game-developer` (contratto `dev-link.md` §10), oppure quando l'utente chiede "valuta la mia idea", "migliora il GDD", "il concept regge?". Non è un controllo di mercato veloce né una lista di ritocchi: è il momento in cui cambiare costa meno, quindi si dice la verità sull'idea e si propone **la versione più forte che il proprietario è disposto a fare**.

Output: `launch/_raw/gdd_review.json` (fonte, controllata da `gdd_review.py check`) e `launch/gdd-review.md` (da leggere, `gdd_review.py render`). Si scrive solo in `launch/`: il GDD lo cambia il dev (o il proprietario) con le proposte accettate.

## 1. Avvio (breve)

1. Fase B ridotta (`00a-bootstrap.md`): `project_scan.py`, poi leggi **tutto** `GDD.md`, `DECISIONI.md`, `GAME_CONTEXT.md` se c'è. Non richiedere all'utente ciò che il GDD dice già.
2. `python3 <skill>/scripts/research/gdd_review.py init --launch-dir launch --gdd GDD.md` (scheletro con le sezioni del GDD; non sovrascrive mai).
3. Data di sistema; se manca `launch/00-intenzioni.md` crealo con le risposte del punto 2.

## 2. Le domande (un solo turno, `AskUserQuestion`)

Chiedile insieme, con la raccomandata per prima. Sono la regola 17 (beta o completo) adattata al GDD, più il quadrante del cambiamento:

1. **Quanto sei disposto a cambiare il GDD?**
   - **2 · Struttura (consigliata dopo un lock)**: l'idea e il tema restano; possono cambiare loop, progressione, modalità, durata, scope e pitch.
   - **1 · Ritocchi**: il concept non si tocca; si rinforzano gancio, chiarezza, prima ora, scope.
   - **3 · Tutto in discussione**: anche genere, verbo centrale, ambientazione o pubblico, con versioni alternative del concept a confronto.
2. **Cosa non si tocca?** (scelta multipla): genere · tema e ambientazione · stile grafico · verbo centrale · piattaforma · scope e tempi · multiplayer. Il motore è sempre intoccabile (Q0 del dev).
3. **Il GDD descrive** la vertical slice / beta, o il gioco completo? (cambia il metro, come nella regola 17)
4. **Obiettivo** (se non è già in `00-intenzioni.md`): vendere / portfolio o lavoro / hobby / jam. Per hobby e portfolio i criteri economici pesano poco: dillo nella pagella.

Se l'utente risponde "decidi tu": livello 2, intoccabili = quelli che il GDD dichiara non negoziabili. Registra in `gdd_review.json` → `dial` (`level`, `untouchable` con le chiavi `genere`, `tema`, `stile`, `verbo`, `piattaforma`, `scope`, `multiplayer`; `owner_words` con le sue parole; `asked` = data) e una riga in `00-intenzioni.md`.

Se mancano capacità e tempi (squadra, ore a settimana, data desiderata) e il GDD non li dice, chiedili in una seconda domanda breve: lo scope si giudica solo contro la capacità.

## 3. I dati (in parallelo con subagenti dove puoi)

Tutto con gli script, mai a memoria (regole 2-3). Grezzi in `launch/_raw/`, ogni numero con data.

| Serve a | Come | Alimenta |
|---|---|---|
| Comparabili veri (8-15): 3-5 più vicini, 3 successi del genere, 2 flop | `steam_discover.py search/tag`, `steam_comps.py --steamspy --boxleiter` (`01-discovery.md` 2.1-2.3) | `comps`, aree `differenza`, `mercato`, `prezzo` |
| Domanda e affollamento del genere, coda alta vs mediano | `genre_bench.py --tag ...` (2.0) | `mercato` |
| Base rate reale e fascia del gioco | `~/.game-launch-strategist/calibration.json` (regola 23; se vecchio > 30 giorni proponi `cohort_bench.py update` + `calibrate`) | `mercato`, `rischio_flop` |
| Cosa il pubblico del genere premia e punisce | `review_corpus.py --comps ... --genre-tag ... --my-features launch/_raw/my_features.json` (2.8): le feature del GDD contro le recensioni vere | `loop`, `progressione`, `prima_ora`, le prove delle proposte |
| Perché giochi così floppano | `references/09-reddit-casi.md` §3-4 e la checklist "perché floppa" (`social_content.py flopcheck`, risposte dal GDD) | `rischio_flop`, `gancio` |
| Come si mostrano i migliori (gancio nei primi secondi, capsule) | `store_bench.py run` sui comparabili (2.9) | `gancio`, `clip` |
| Soglie del genere | `references/playbooks.md` (famiglia di genere) | tutte, come metro di partenza [OPINIONE] |
| Casi di giochi simili (wishlist, Next Fest) | `case_studies.py query/bench` | `mercato`, `scope` |
| Posizionamento | i test della Fase 2B (`01-discovery.md`): pitch in 25 parole, 3 differenziatori, "perché dovrei giocarlo invece di X?", test del twist, ancore di familiarità | `gancio`, `differenza` |

Con un GDD i differenziatori non sono "veri oggi" nella build: valutali come **promessi dal GDD** e scrivilo. Senza rete: completa ciò che dipende solo dal GDD, il resto **[DA VERIFICARE]** con le ricerche in `ricerche-manuali.md` (regola 3).

## 4. La pagella dell'idea (10 aree fisse)

`gancio` · `differenza` · `mercato` · `loop` · `progressione` · `prima_ora` · `clip` · `scope` · `prezzo` · `rischio_flop`. Per ognuna: voto 1-5, etichetta, perché in una o due frasi, fonte se [FATTO]. Severo e calibrato: **3 = come un gioco medio del genere che esce e passa inosservato**; 4 solo con una prova che regge il confronto con i comparabili che vendono; 5 quasi mai su un'idea scritta. Il gioco è "fascia B" finché i dati non dicono altro (regola 23).

Poi il **verdetto sull'idea**: `forte` / `promettente` / `fragile` / `da ripensare`, una riga che dice perché, i punti forti, i punti deboli e **la mossa che conta di più**. Il verdetto è sempre provvisorio (si valuta un'idea, non un prodotto) e non è il semaforo del lancio.

## 5. Le proposte: tanta ambizione quanta ne concede il proprietario

Ogni proposta è un `P-GDD-n` nel JSON con: `level` (1-3, mai sopra quello scelto), `touches` (cosa del gioco cambia: `pitch`, `loop`, `progressione`, `modalita`, `contenuti`, `onboarding`, `scope`, `prezzo`, `pubblico`, `ui`, `genere`, `tema`, `stile`, `verbo`, `piattaforma`, `multiplayer`; mai un intoccabile), `title`, `gdd_section` (una sezione vera del GDD o "nuova sezione: …"), `now` (testo attuale o "assente"), `proposed` (**il testo nuovo, pronto da incollare**, nello stile del GDD, con i numeri che servono a chi implementa), `why`, `evidence` (prove etichettate; [FATTO] con fonte), `impact`, `cost_hours` [STIMA], `risk`, `loses` (cosa si perde: c'è sempre qualcosa), `reopens` se cambia una riga di `DECISIONI.md`.

- **Livello 1, ritocchi** (sempre, almeno 3 tra tutte): gancio leggibile in 5 secondi, il primo minuto, un numero sbagliato, uno scope tagliato dove le recensioni non premiano, un pitch riscritto.
- **Livello 2, struttura** (almeno 2 se il quadrante lo permette): il loop rifatto attorno a ciò che le recensioni premiano, una progressione che dà un motivo per tornare, una durata giusta per il prezzo, una modalità che rende il gioco mostrabile, uno scope rimisurato sulla capacità reale. Ogni proposta di struttura deve poggiare su dati (recensioni, comparabili, casi), non solo su opinioni.
- **Livello 3, concept** (almeno 2 versioni alternative se il quadrante è 3): la stessa passione del proprietario in una forma con più mercato. Ogni alternativa: pitch in 25 parole, cosa resta dell'idea originale, cosa cambia, i comparabili che la sostengono, costo e rischio. Una deve essere **la più vicina all'originale che risolve il punto più debole**; l'altra può essere più audace.
- **Non trattenerti.** Se l'idea è fragile e il quadrante lo permette, dillo e proponi la versione forte: è il motivo per cui il proprietario ha scelto quel livello. Se invece l'idea è forte, non inventare cambi: meno proposte e più precise (con `no_structural_reason` / `no_concept_reason` per dire perché).
- **Mai sopra il quadrante.** Se il punto più debole si risolve solo con un cambio sopra il livello scelto, non diventa una proposta: scrivilo in `verdict.weak_spots` con una riga "si risolverebbe solo con un cambio di livello N" e lascia decidere al proprietario se alzare il livello.

## 6. Panel rapido SIMULATO (facoltativo, consigliato con il livello 2-3)

Stesso metodo calibrato del focus group (`04-focus-group.md` 7.0b-7.0e) in piccolo: 12 tester del genere dal roster (`roster.py`, gli ID restano) ricevono **solo il pitch e il loop** di ciascuna versione (originale e 1-2 proposte forti), alla cieca e in ordine diverso. Per ognuna: lo riformulano correttamente? (test di comprensione del pitch, 2B.8) lo metterebbero in wishlist? cosa li confonde? Risultati in `panel` (`size`, `method`, `results` con `version`, `pitch_ok_pct`, `wishlist_pct`, `notes`). Etichetta sempre **SIMULATO**: ordina le versioni, non prevede vendite (regola 7).

## 7. Controllo, pagina, scelte del proprietario

```bash
python3 <skill>/scripts/research/gdd_review.py check  --launch-dir launch          # ❌ = da sistemare prima di mostrarla
python3 <skill>/scripts/research/gdd_review.py render --launch-dir launch          # -> launch/gdd-review.md
```

In chat, corto: verdetto in tre righe, la pagella (aree e voti), poi le proposte in ordine di impatto per ora, una riga ciascuna, con il link a `launch/gdd-review.md` per il testo completo. Poi le scelte con `AskUserQuestion` a scelta multipla (al massimo 4 opzioni per domanda: raggruppa per livello, una domanda per gruppo; le alternative di concept si scelgono una sola). Registra:

```bash
python3 <skill>/scripts/research/gdd_review.py decide --launch-dir launch P-GDD-1 P-GDD-4 accettata
python3 <skill>/scripts/research/gdd_review.py decide --launch-dir launch P-GDD-2 rifiutata --note "la co-op resta fuori"
python3 <skill>/scripts/research/gdd_review.py render --launch-dir launch
```

e una riga datata in `00-intenzioni.md` per ogni scelta. Una proposta rifiutata non si ripropone; si può riaprire solo con dati nuovi e l'etichetta "Riapre la decisione".

## 8. Passaggio al GDD

- **Con `game-developer`** (contratto `dev-link.md` §10): il dev esegue `gdd_review.py pending --launch-dir launch --decisions DECISIONI.md` e applica a `GDD.md` le accettate non ancora applicate (bozza → recap delle sole modifiche → ok del proprietario → di nuovo locked), una riga in `DECISIONI.md` per proposta con `fonte: launch/gdd-review.md P-GDD-n`. Quando la revisione viene dalla stessa chat del dev, dillo in una riga e restituisci il passo al dev.
- **Senza la skill dev**: il proprietario incolla il testo "Proposto" nelle sezioni indicate; tu non scrivi mai `GDD.md` (regola 8).
- **Dopo**: le proposte accettate diventano righe 🤖/👤 della TODO solo se c'è un lavoro di lancio da fare (es. "riscrivere il pitch nella pagina Steam"); il resto è lavoro del dev. Se esiste `STATUS.html`, rigeneralo.

## 9. Controllo di qualità prima di mostrarla

- `check` senza errori; ogni [FATTO] con fonte e data; numero di comparabili e di recensioni dichiarato.
- La pagella non è gonfiata: almeno un'area sotto il 3 o una prova che dica perché no.
- Ogni proposta ha il testo pronto da incollare, non "migliorare il loop".
- Le proposte rispettano il quadrante e gli intoccabili; le decisioni di `DECISIONI.md` sono riaperte solo con l'etichetta.
- In chat c'è il link a `launch/gdd-review.md` e la domanda sulle scelte; niente viene applicato al GDD senza ok.
