# Fase 11 e output finale: sintesi, report, TODO, stato, debriefing, controllo qualità

---

## FASE 11: sintesi "Success Maximizer"

Costruisci in `REPORT.md` la sezione che massimizza davvero le probabilità di successo:

1. **Le 5 leve a più alto impatto**, ordinate per punteggio **ICE** (Impatto, Confidenza, Facilità, da 1 a 10; ICE = media, mostra il calcolo), ciascuna con ore, scadenza e metrica. Alimentate da matrice di convergenza, posizionamento e pre-mortem.
2. **Le 3 cose da NON fare ora** (es. spendere in ads prima del gate, lanciare una pagina Steam acerba, aggiungere contenuto prima di sistemare l'apertura).
3. **Criteri di stop e di pivot**: a quali risultati misurabili (gate falliti due volte, tripwire scattati, wishlist sotto soglia a data X) conviene ridimensionare, cambiare genere o spostare l'obiettivo (da vendite a portfolio). Senza drammi: è gestione del rischio.
4. **Scenario migliore realistico**: cosa deve accadere, in ordine, perché il gioco superi le attese, e quali di quegli eventi dipendono dal team.
5. **Verifica di capacità**: confronta le ore totali delle TODO con le ore settimanali del team nel periodo fino al lancio. Se il piano supera la capacità, taglia e dillo.

---

## File prodotti (modalità Completa)

In `launch/`:

- `00-brief.md`, `01-dev.md`, `01b-positioning.md`, `02-platform.md`, `03-pricing.md`, `04-clips.md`, `04b-store-copy.md`
- `05-focusgroup.md`, `05a-critiche-simulate.md`, `05b-critiche-reali.md`, `05c-premortem.md`
- `06-creators.md`, `07-community.md`, `08-brand-legal.md`
- `fg/roster.md`, `fg/roster.json` (tester con ID stabili e giuria), `fg/waves/` (una serie di file per ondata: evidenze, gruppi A e B, dati JSON, dibattito, report, delta), `fg/timeline.md`, `fg/timeline.csv`
- `comps.csv`, `sources.md`, `creators.csv`, `calendar.md`, `03-pricing-calc.md`, `wishlists.csv`, `wishlist-status.md`, `status.json`, `STATUS.html`
- `_raw/`: dati grezzi degli script (`comps.json`, `corpus.json`/`corpus.md`, `store_pages.json`/`store_bench.md`, `hooks/`, `gt_*.json`/`gt_*.md`, `econ.json`, `wl_plan.json`, `my_features.json`, `reviews_*.json`, `yt_*.json`, `social_verified.json`, `reddit_rules.md`, `curation.json`, `topics.json`)
- `playbook-usato.md` (solo se ad hoc), `ricerche-manuali.md` (solo se serve), `history/` (in Aggiornamento)
- `REPORT.md`, `TODO.md`, `STATUS.md`

Le modalità Rapida e Mirata producono solo i file delle fasi eseguite, più `REPORT.md`, `TODO.md`, `STATUS.md`.

---

## `STATUS.md` (aggiornalo dopo ogni fase)

```markdown
# STATUS
Aggiornato: AAAA-MM-GG HH:MM | Modalità: Completa | Build/commit analizzato: <id>

| Fase | Stato (fatta / parziale / da fare) | File | Confidenza (bassa/media/alta) | Note |
|---|---|---|---|---|

## Ondate del focus group
| Ondata | Data | Build | Punteggio | Stato (fatta / proposta, in attesa di ok) |
|---|---|---|---|---|

## Ipotesi aperte
- <ipotesi usata al posto di un dato mancante>

## Dati non raggiunti / ricerche manuali
- <cosa, perché, dove è scritto come completarlo>

## Prossimo passo
<la prima cosa da fare alla ripresa>
```

Alla ripresa ("continua") leggi `STATUS.md` e riparti dalla prima fase non completata, senza riscrivere i file già fatti.

## `status.json` e pagina di stato (`STATUS.html`)

`status.json` è il riepilogo strutturato che alimenta la pagina per soci o publisher. Scrivilo (o aggiornalo) a fine Fase 11 e dopo ogni ondata; il resto della pagina arriva dai file già prodotti (timeline, wishlist, piano economico, calendario, TODO, documenti).

```json
{
  "game": "Nome del gioco", "updated": "AAAA-MM-GG", "mode": "Completa",
  "verdict": {"color": "verde|giallo|rosso", "provisional": false,
              "summary": "2-3 frasi, le stesse del verdetto esecutivo", "probability": "intervallo",
              "risks": ["rischio 1", "rischio 2", "rischio 3"]},
  "gates": {"0": {"state": "pass|fail|pending", "note": "..."}, "A": {}, "B": {}, "C": {}},
  "key_numbers": [{"label": "Comparabili analizzati", "value": "18", "note": "con dati verificati"}]
}
```
Genera la pagina:

```bash
python3 <skill>/scripts/research/status_page.py --launch-dir launch --audience partner     # private | partner | publisher
```
È un unico file HTML autonomo (nessuna richiesta di rete, tema chiaro e scuro, utilizzabile da telefono, grafici con vista tabella). **Non pubblicarla né inviarla**: dì all'utente dov'è il file e offri la pubblicazione in una riga (es. come artifact privato, se l'ambiente lo permette), e chiedi per chi è: `publisher` esclude economia interna, TODO e pre-mortem, `partner` li include, `private` aggiunge creator, community e fiscale. Controlla che nessun dato personale o riservato finisca nei documenti inclusi.

## Routine settimanale (dopo l'apertura della pagina Steam)

1. L'utente fornisce il totale wishlist da Steamworks: `wl_track.py add ...`.
2. `wl_track.py status`: se esce con codice 2 riporta subito l'ALLARME e l'azione di emergenza; altrimenti riassumi velocità, posizione rispetto agli scenari e alert.
3. Se è cambiato qualcosa di rilevante rigenera `status_page.py`. Se un'ondata del focus group è in attesa dell'ok, ricordalo.

## `ricerche-manuali.md`

Per ogni ricerca che non hai potuto fare: obiettivo, query o URL suggeriti, a cosa serve il dato, in quale file va a finire e quale cifra resta **[DA VERIFICARE]** finché manca.

---

## `REPORT.md` (struttura rigida)

1. **Verdetto esecutivo (max 15 righe)**: semaforo verde/giallo/rosso secondo i criteri in `SKILL.md`, probabilità stimata di recuperare i costi (intervallo), 3 rischi killer. Se il posizionamento non è PASS il verdetto non può essere verde.
2. **Genere, playbook, fase e confidenza per sezione.**
3. **Posizionamento e differenziazione**: pitch, 3 differenziatori, esito del test contro i comparabili.
4. **Audit dev e pilastri di genere.**
5. **Critiche e ondate**: top critiche simulate (A) dell'ultima ondata, temi reali del genere (B), matrice di convergenza, 3 dealbreaker, metriche del panel con calibrazione dichiarata e **timeline delle ondate** (`fg/timeline.md`) se ce n'è più d'una.
6. **Pre-mortem**: le 5 cause e la tabella dei tripwire.
7. **Mercato, comparabili e prezzo**: scenari con "cosa deve essere vero".
8. **Capsule, hook, testi dello store e trailer.**
9. **Piano piattaforme, Next Fest e gate** con date.
10. **Creator e community**, kit del test reale.
11. **Success Maximizer**: 5 leve, 3 "non fare", criteri di stop e pivot, verifica di capacità.
12. **Legale e fiscale**: cose da fare prima di incassare.
13. **Fonti verificate** con data di consultazione.

## `TODO.md`

Formato di ogni voce:

```
[ ] Azione concreta | Scadenza (AAAA-MM-GG) | Ore stimate | Dipendenze | Metrica di successo
```

Raggruppate per area: **Dev e pilastri**, **Posizionamento e store**, **Marketing e hook**, **Creator e community**, **Burocrazia e release**, **Tripwire e misure**. In testa: **"I 3 dealbreaker da risolvere in 14-20 giorni"**. Le scadenze sono date assolute calcolate dalla data odierna. In fondo: totale ore per area e confronto con la capacità del team (Fase 11.5).

## Delta in modalità Aggiornamento (`history/AAAA-MM-GG-delta.md`)

Cosa è migliorato, cosa è peggiorato, quali TODO sono chiuse, quali verdetti cambiano, quali tripwire del pre-mortem sono scattati. Per il focus group rimanda a `fg/waves/wNN-delta.md` e `fg/timeline.md` (prodotti da `fg_waves.py`, vedi `04-focus-group.md` 7.5); non ricalcolare i numeri a mano.

---

## Debriefing esecutivo in chat (formato obbligatorio)

Una volta scritti i file, rispondi in chat con un debriefing diretto, numerico e calibrato, da lead producer. Niente saluti o convenevoli. Riempi con i dati reali, senza segnaposto vuoti. Se un dato non è verificabile scrivilo nella riga stessa con **[DA VERIFICARE]**.

```text
[N] persone simulate in due gruppi indipendenti, critiche reali dei comparabili e strategia di lancio completa. Parti da launch/REPORT.md e launch/TODO.md; il resto è nei file 00-08 e in fg/. Nessuna delle persone simulate ha giocato: hanno giudicato da documenti, codice, screenshot e capsule. Sono opinioni simulate, non dati di mercato. Le critiche reali vengono da fonti online verificate.

Genere e fase: [genere primario/secondario, confidenza, fase, playbook usato].

Posizionamento: [pitch in una frase]. Differenziatori: [3]. Test contro [comparabile più vicino]: [PASS / MARGINAL / FAIL, perché]. [Se non PASS: le proiezioni sotto sono condizionate].

Verdetto onesto: [semaforo; oggi il gioco è / non è pronto per essere venduto, perché; gancio contro divertimento reale nei primi minuti].

- Persone simulate: [X]% wishlist subito, [Y]% aspetterebbe saldi/recensioni, [Z]% scorrerebbe oltre, [W]% comprerebbe e chiederebbe rimborso. Click al primo sguardo [A] su [N]. Pitch compreso da [B]%. Convergenza tra i due gruppi: [differenza in punti, cosa significa].
- Punteggio wishlist: [X] (soglia [S], motivata). Filtro, non previsione.
- Critiche più votate (simulate): [top 3 con frequenza].
- Critiche reali del genere che colpiscono il gioco: [top 3, fonte e frequenza]. Confermate da entrambe: [temi]. Punti ciechi del panel: [temi].
- Problema N.1: [descrizione concreta con evidenza].
- Leva strategica del genere: [feature o fattore, impatto stimato].

Pre-mortem, se tra un anno è un flop, le cause più probabili sono: [1-2-3 con segnale d'allarme e data di misura].

I 3 problemi da risolvere entro [data]. Toccano il divertimento, quindi aspettano il tuo ok:
1. [problema: intervento, ore, impatto atteso]
2. [...]
3. [...]

Steam: [pagare o non pagare adesso, motivo]. Date e cancelli:
- [Data gate test]: [soglie specifiche del genere]
- [Data pagamento]: solo se i gate passano
- [Mese pagina pubblica]
- [Date Next Fest, deadline iscrizione e invio build, verificate il (data)]

Testi dello store: pronti in launch/04b-store-copy.md (descrizioni, tag, 3 varianti di capsule, script del trailer).

Prezzo e vendite: prezzo consigliato [X], sconto di lancio [Y]%. Scenario base con [Z] wishlist: [A-B] copie nell'anno 1; pessimistico [C-D]; ottimistico [E-F]. Probabilità di recuperare i costi: [intervallo].

Canali: [piattaforma principale per questo genere e perché]. [2 hook più forti]. In lista [X] creator verificati ([Y] su [piattaforma], [Z] nella lingua del team, oppure istruzioni per cercarli a mano). Community: [dove e con quali regole].

Le 5 leve in ordine: [una riga ciascuna].
Da non fare ora: [3 punti].
Criteri di stop o pivot: [soglie misurabili e date].

Prima di incassare: [accordo tra soci se serve], [commercialista e inquadramento], [verifiche fiscali Steam]. Rimasto da verificare: [elenco breve o "nulla"].
```

Se esiste più di un'ondata aggiungi dopo il verdetto una riga di delta (dal tool): punteggio wishlist prima → dopo sugli stessi tester, problemi risolti e peggiorati, fix più efficace, tripwire scattati. Se un'ondata è **in attesa dell'ok dell'utente**, dillo qui con la data proposta.

La **segnalazione problemi** a fine di ogni ondata ha un suo formato breve (`04-focus-group.md`, 7.4) e viene mandata subito, non aspetta il debriefing finale.

In **Rapida** e **Mirata** il debriefing si accorcia alle sole righe delle fasi eseguite.

---

## Controllo di qualità prima di consegnare

- [ ] Genere riconosciuto con confidenza dichiarata; pilastri, coorti, hook, creator e prezzo derivano dal playbook.
- [ ] La fase del progetto ha determinato la profondità dell'audit.
- [ ] Il posizionamento è stato valutato contro i comparabili, e un eventuale FAIL/MARGINAL ha cambiato verdetto, scenari e TODO n. 1.
- [ ] Critiche **simulate** e **reali** in due file separati; le reali hanno fonte e sono parafrasate; nessuna critica "reale" è inventata.
- [ ] Matrice di convergenza presente e i 3 dealbreaker ne derivano.
- [ ] Pre-mortem con 5 cause, segnale misurabile, soglia e data; almeno una contraddice il verdetto positivo.
- [ ] Testi dello store scritti (descrizioni, tag, 3 capsule, trailer) e ogni affermazione ha un'evidenza nel gioco.
- [ ] Roster con ID stabili e giuria fissa; ogni ondata ha il suo file JSON validato da `fg_waves.py`; punteggi, delta e timeline vengono dal tool; metodo di indipendenza dei gruppi dichiarato.
- [ ] Ondata 1 eseguita prima delle fasi di piattaforma, prezzo e store e seguita dalla segnalazione problemi; nessuna ondata successiva lanciata senza l'ok dell'utente; evidenze delle ondate successive senza critiche né fix precedenti.
- [ ] Focus group calibrato (controlli o confronto col comparabile) e dichiarato non-dato-di-mercato; soglia del Gate A motivata.
- [ ] I benchmark di pagina store, trailer e genere vengono da `store_bench.py`, `review_corpus.py` o dal corpus GamesTracker, con n, filtri e data (altrimenti dichiarati di opinione); le cifre economiche vengono da `calc_econ.py` con aliquote dichiarate.
- [ ] Se esiste la pagina Steam: `wishlists.csv` e `wl_plan.json` esistono e `wl_track.py status` è stato eseguito; un ALLARME è stato riportato all'utente.
- [ ] `STATUS.html` generata per il pubblico scelto dall'utente e **non pubblicata** senza il suo ok.
- [ ] Ogni numero ha **[FATTO]**, **[STIMA]**, **[OPINIONE]** o **[DA VERIFICARE]**; nessun URL, email o creator inventato; ogni dato "da verificare sempre" ha data di consultazione.
- [ ] Cancelli con date assolute e soglie adattate al genere; TODO con azione, scadenza, ore, dipendenze, metrica; ore totali entro la capacità del team.
- [ ] Il semaforo applica i criteri di `SKILL.md`; il verdetto è marcato **provvisorio** se il materiale era insufficiente.
- [ ] `STATUS.md` aggiornato; nulla modificato nel progetto fuori da `launch/`.
- [ ] Il debriefing in chat segue il formato.
