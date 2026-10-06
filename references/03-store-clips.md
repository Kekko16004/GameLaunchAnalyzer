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
