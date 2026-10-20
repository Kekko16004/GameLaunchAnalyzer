# Fasi 6 e 6B: hook visivi, clip e testi dello store

I giochi falliscono spesso perché nessuno clicca sulla capsule. Qui si valuta e poi si **scrive**.

---

## FASE 6: hook visivi e clip

Output: **`launch/04-clips.md`**.

### A. Scroll test dello store
1. **Micro-capsule** (la piccola, nei banner scuri di Steam): si distingue? Il titolo è leggibile? Il genere si capisce in 1,5 secondi? Confronta con le header scaricate dei comparabili (`steam_comps.py --headers-dir`).
2. **Coerenza artistica**: direzione intenzionale o kit di asset non amalgamati? Silhouette, palette, illuminazione. Segnali di asset flip o di contenuto generato senza cura.
3. **Primo screenshot e GIF**: il primo screenshot mostra l'azione migliore con feedback visivo, mai menu o loghi. Presenza di una GIF breve del core loop nella descrizione.
4. **Tag e titolo**: coerenti con il playbook e con i comparabili migliori.

Senza screenshot o capsule reali questa parte ha confidenza **bassa**: valuta solo ciò che esiste e scrivi cosa serve produrre.

### B. Hook e clip adattati al genere
1. Almeno **10 hook visivi**, usando i tipi di hook del playbook. Valuta ciascuno su: comprensione senza audio entro 2 secondi, sorpresa o soddisfazione, facilità di produrre la clip dalla build attuale.

   | # | Hook | Chiaro senza audio in 2 s | Sorpresa/soddisfazione | Producibile oggi | Voto |
   |---|---|---|---|---|---|
2. **3 storyboard** per video brevi (TikTok, Reels, Shorts): 0-2 s hook, 2-7 s sviluppo, 7-12 s payoff e CTA. Se il genere si presta meglio ad altro (devlog lungo, timelapse, screenshot per Pinterest), proponi quello.
3. **Cosa girare adesso**: lista di clip da registrare con la build attuale, ordinate per impatto, con durata e impostazioni di cattura.
4. **Kit pronto da postare (il risultato principale, pratico):** il proprietario non deve leggere teoria, deve postare.
   - `launch/clips.json`: una voce per clip con **storyboard completo** (inquadrature con tempi, cosa succede secondo per secondo, camera, testo d'apertura e quando compare, sottotitoli, musica ed effetti, ultimo fotogramma con la chiamata, durata, formato, piattaforme, **come registrarla nel gioco**: strumento, comando, scena, piano, evento, preparazione, prese) e stato `todo / recorded / posted`. Le clip vecchie o bocciate non si usano: si scrive lo storyboard nuovo. `social_kit.py clips --md launch/clips.md` controlla che ogni storyboard sia completo e scrive la pagina "Clip da fare" (anche in STATUS.html); `social_kit.py set C01 --status recorded --file <percorso>` quando la clip esiste.
   - `social_kit.py kit --clips launch/clips.json --start <oggi> --weeks 8 --calendar launch/calendar.md -o launch/_raw/social_kit.json`: un file per settimana in `launch/social-kit/` con 3-4 post: clip esatta (file o "da registrare entro"), 2-3 testi per i primi 1-2 s (quale usare questa volta), didascalia, hashtag, piattaforme con giorno e ora (stessa clip TikTok → Shorts → Reels in giorni consecutivi), chiamata giusta per la data (prima della pagina Steam: "segui", poi il link Steam **con UTM** per vedere in Steamworks le wishlist di ogni post), il post Reddit (titolo personale, subreddit a rotazione, regole da controllare), un "perché" di una riga con fonte e la **riga da 5 minuti** da incollare il giorno dopo (`social_content.py track add …` con visualizzazioni, like, commenti, visite al profilo, wishlist). Prima della pagina Steam la settimana serve a costruire il profilo e a provare i testi (stessa clip, due testi).
   - La domenica: `social_content.py learn` e di nuovo `social_kit.py kit --learn …`: la sezione "Cosa ha funzionato → cosa cambia" e la scelta di clip e testi si aggiornano da sole (clip e testi vincenti tornano, quelli deboli escono).
5. **Piano social con le prove** (visione lunga) (`social_content.py`, output `launch/social-plan.md` e passi settimanali in `calendar.md`):
   - `social_content.py evidence [--platform tiktok]`: le regole per TikTok, Reels, Shorts, X e Reddit con forza della prova (misurata / opinione esperta / aneddoto), fonte e data; i benchmark onesti per un account piccolo (di solito sotto 1.000 visualizzazioni a post; un post virale al mese è già un successo) e i rapporti visualizzazioni → wishlist trovati. Cita sempre la data delle prove: le piattaforme cambiano.
   - `moments --from-clips launch/04-clips.md [--runs launch/fg/waves]`: i momenti migliori del gioco (tabella degli hook con il voto, righe [TOP] delle run a tempi).
   - `plan --moments ... --start <data> --weeks 8 --per-week tiktok=4,youtube_shorts=3,instagram=3,reddit=1 --steam-live <data pagina> --itch-live <data beta> --game "<nome>" [--hooks launch/_raw/social_hooks.json] --calendar launch/calendar.md --md launch/social-plan.md -o launch/_raw/social_plan.json`: un calendario per piattaforma con due testi d'apertura (A/B) per post, didascalia, chiamata finale corretta per la data (prima della pagina Steam niente "wishlist"), il subreddit giusto con le sue regole e le pause tra un post e l'altro (es. r/IndieGaming ogni 2 settimane). La frequenza segue l'intervista (Round 4: frequenza sostenibile per davvero).
   - Dopo ogni post: `track add` (o `track import` dell'export di TikTok/YouTube) con visualizzazioni, like, condivisioni e **le wishlist del giorno dopo lette dall'utente in Steamworks** (regola 16: mai stimate). `learn` dice cosa rende **per questo gioco** (momento, gancio, formato contro la mediana della piattaforma e contro il tipico di un account piccolo; sotto 5 post lo dice); `plan --learn` rimette più spesso ciò che rende e `top_moves.py` propone "rifai il formato X" o "registra i numeri".
   - Reddit: `reddit_trends.py scan <sub…>` legge dal **feed RSS pubblico** i post migliori della settimana contro i nuovi (formato e titoli che rendono, "rende ×"); con le chiavi OAuth nel file privato usa l'API ufficiale con i punteggi veri. Se Reddit risponde 403/429 non si aggira: si riprova più tardi o si fanno i passi manuali scritti in `ricerche-manuali.md`. TikTok, Instagram e X non si leggono mai con script.

---

## FASE 6B: testi dello store (scritti davvero)

**Sorgente unica: `launch/store_kit.json`.** Scrivi prima di tutto questo file (formato nella testata di `scripts/research/store_kit.py`): da lì escono la scheda scritta del report, i file da incollare e i pulsanti "Copia" della pagina HTML. Contiene, **per Steam e per itch.io**:
- **campi** (nome, descrizione breve, tagline, sviluppatore, tipo di progetto, prezzo…) con il testo definitivo, il **limite di caratteri dichiarato con la data di verifica** (`limits`, **[DA VERIFICARE]**) e una nota;
- **descrizione lunga come blocchi**: testo (BBCode per Steam, Markdown per itch) e **posizioni dei media** (`type: media`) che dicono **cosa va in ogni punto** (quale GIF, quale screenshot, cosa mostra, file e alt), così l'utente sa dove mettere foto e GIF;
- **tag in ordine** con il perché (i primi 5 pesano di più) e **tag da evitare**;
- **screenshot in ordine** con cosa mostrano e didascalia (il primo è gameplay puro con feedback);
- **capsule e immagini** (nome, misura **[DA VERIFICARE]**, cosa devono comunicare in 1,5 secondi), **trailer** (durata, posizione, script);
- **impostazioni da compilare** (lingue, questionario dei contenuti, dichiarazione AI, categorie, prezzo, data, demo) e **checklist** prima di pubblicare.

```bash
python3 <skill>/scripts/research/store_kit.py check launch/store_kit.json            # limiti, tag, ordine screenshot, slot senza descrizione
python3 <skill>/scripts/research/store_kit.py render launch/store_kit.json --md launch/store_kit.md   # scheda scritta per il report
python3 <skill>/scripts/research/store_kit.py export launch/store_kit.json --dir launch/store_kit     # un file per campo, da incollare
```
**Pagine store vive.** Le pagine Steam e itch seguono il gioco: **dopo ogni decisione del proprietario, gate o ondata che cambia cosa il gioco è o promette** (Early Access, roadmap del multiplayer, accessibilità, lingue, prezzo, piattaforme, contenuto della beta) Claude aggiorna `store_kit.json` (campo `"updated": "AAAA-MM-GG"`), poi rilancia `check`, `render` ed `export`. `STATUS.html` (scheda Marketing e store, e un alert in Riepilogo) dice **"Pagine store aggiornate al <data>"** oppure **"da aggiornare"** quando il kit è più vecchio dell'ultima decisione in `00-intenzioni.md` (titolo `## AAAA-MM-GG`), dell'ultima ondata o dell'ultimo documento di gate; lo dice anche `store_kit.py check`.

**Early Access (solo se il gioco esce in EA).** Blocco `steam.early_access` con le sei domande che Steam mostra sulla pagina (lette su https://partner.steamgames.com/doc/store/earlyaccess il **2026-10-09**, da ricontrollare: scrivi la data in `verified_on`): *Why Early Access?* · *Approximately how long will this game be in Early Access?* · *How is the full version planned to differ from the Early Access version?* · *What is the current state of the Early Access version?* · *Will the game be priced differently during and after Early Access?* · *How are you planning on involving the Community in your development process?* (chiavi `why`, `duration`, `full_vs_ea`, `current_state`, `pricing`, `community`). Valve non dichiara limiti di caratteri: `check` avvisa oltre 1.200 caratteri (leggibilità, [OPINIONE]) o oltre un limite scritto in `limits`, segnala le risposte vuote e le frasi che suonano come promesse ("guaranteed", "will be released in 2027"…): Valve chiede di **non promettere** date o funzioni. In EA niente sconto permanente: il prezzo più basso è il prezzo base. La descrizione lunga deve dire "Early Access" e cosa c'è oggi; la roadmap è scritta come piano ("planned"), non come promessa.

**Accessibilità.** Blocco `accessibility` (`intro` + `features` [{label, value}]) per Steam e itch, preso dai documenti del gioco (gate, opzioni reali, non desideri): esce come lista da copiare (BBCode su Steam, Markdown su itch) e come sezione della pagina HTML. Dichiara solo ciò che è nella build pubblica.

Poi i punti 1-9 sotto sono il **contenuto** da mettere nel kit (non un documento a parte): `04b-store-copy.md` conserva trailer, capsule e piano di test, il kit conserva i testi copiabili.

**Benchmark veri, non di opinione.** Prima di scrivere usa `launch/_raw/store_bench.md` (Fase 2.9) e `launch/_raw/genre_bench.md` (2.0): mediane e quartili dei **migliori** per lunghezza della descrizione breve e lunga, GIF, screenshot, durata del trailer, tempo al primo taglio. Se una misura manca, dichiara che la soglia è di opinione. Cita sempre n e fonte (**[FATTO]**).

Output: **`launch/04b-store-copy.md`**. Non limitarti all'audit: **scrivi i testi pronti da incollare**, nella lingua del pubblico (di norma inglese, più l'italiano se il pubblico lo include), partendo dal pitch e dai differenziatori della Fase 2B.

1. **Descrizione breve di Steam**: 3 varianti con il numero di caratteri accanto a ciascuna (limite attuale **[DA VERIFICARE]**). La prima frase contiene genere + promessa + differenziatore nei primi 100 caratteri.
2. **Descrizione lunga**: struttura completa e pronta. Apertura con GIF segnaposto del core loop; titolo "About this game" con paragrafo di apertura; 4-6 blocchi (titolo breve + 2-3 righe + indicazione di GIF o screenshot); elenco "caratteristiche chiave" (5-7 voci); chiusura con call to action alla wishlist. Vietati muri di testo e superlativi non verificabili.
3. **Scelta dei tag**: elenco ordinato con motivazione per ciascuno, ricavata dai tag dei comparabili migliori (`steam_comps.py --steamspy`, colonna `steamspy_tags`) e dal playbook. Indica i primi 5 (pesano di più, **[DA VERIFICARE]**), i tag da evitare perché promettono ciò che il gioco non è, e il numero massimo consentito.
4. **Capsule: 3 varianti.** Le regole Valve sul testo nelle capsule sono restrittive **[DA VERIFICARE]**. Per ogni variante: composizione, logo/titolo, cosa comunica in 1,5 secondi, perché sceglierla. Proponi una **tagline** alternativa per dove il testo è consentito (descrizione breve, itch, social, trailer). Indica come testarle (due round con persone esterne, A/B se possibile).
5. **Script del trailer** (durata dalla mediana dei comparabili migliori in `store_bench.md`; senza dati, default 60-90 secondi **[OPINIONE]**): shot list con tempi (0-5 s hook senza bisogno di audio, poi sviluppo, momento più forte entro metà, ultimi 5 s con titolo, data o "wishlist now"), testi a schermo, indicazioni audio e musica, cosa tagliare. Versione corta da 15-20 secondi per i social.
6. **Pagina itch.io** (se prevista), **completa quanto quella Steam** e nel kit (`itch`): titolo, tagline, tipo di progetto (scaricabile, browser), stato di rilascio, prezzo e donazioni, genere, **tag** (massimo da verificare), descrizione in Markdown **con le posizioni dei media** (cover, GIF, screenshot, trailer incorporato), piattaforme e file, impostazioni di community e commenti, accessibilità, e il **link alla wishlist su Steam** appena esiste. Testo più breve e diretto; in bozza o con accesso limitato finché la build non è pronta.
7. **Blurb per press kit e creator**: una riga, un paragrafo, 5 fatti verificabili.
8. **Controllo veridicità**: per ogni affermazione dei testi indica l'evidenza nel gioco (file, scena, clip) in una tabella `affermazione | evidenza`. Mai promettere feature assenti, premi o citazioni inventati, paragoni con titoli famosi non giustificati. Dichiara l'uso di AI generativa dove la piattaforma lo richiede.
9. **Piano di test dei testi**: quale variante provare per prima e come misurare (click sulla capsule, tasso di wishlist per visita alla pagina).

**Dopo capsule, testi o trailer nuovi proponi all'utente una nuova ondata del focus group** (`04-focus-group.md`, 7.5): è il momento in cui il panel vede per la prima volta i materiali dello store e la timeline mostra se click e punteggio salgono. Parte solo con l'ok dell'utente.

Ogni file termina con TODO nel formato di `references/06-synthesis-output.md`.
