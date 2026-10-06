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

Output: **`launch/04b-store-copy.md`**. Non limitarti all'audit: **scrivi i testi pronti da incollare**, nella lingua del pubblico (di norma inglese, più l'italiano se il pubblico lo include), partendo dal pitch e dai differenziatori della Fase 2B.

1. **Descrizione breve di Steam**: 3 varianti con il numero di caratteri accanto a ciascuna (limite attuale **[DA VERIFICARE]**). La prima frase contiene genere + promessa + differenziatore nei primi 100 caratteri.
2. **Descrizione lunga**: struttura completa e pronta. Apertura con GIF segnaposto del core loop; titolo "About this game" con paragrafo di apertura; 4-6 blocchi (titolo breve + 2-3 righe + indicazione di GIF o screenshot); elenco "caratteristiche chiave" (5-7 voci); chiusura con call to action alla wishlist. Vietati muri di testo e superlativi non verificabili.
3. **Scelta dei tag**: elenco ordinato con motivazione per ciascuno, ricavata dai tag dei comparabili migliori (`steam_comps.py --steamspy`, colonna `steamspy_tags`) e dal playbook. Indica i primi 5 (pesano di più, **[DA VERIFICARE]**), i tag da evitare perché promettono ciò che il gioco non è, e il numero massimo consentito.
4. **Capsule: 3 varianti.** Le regole Valve sul testo nelle capsule sono restrittive **[DA VERIFICARE]**. Per ogni variante: composizione, logo/titolo, cosa comunica in 1,5 secondi, perché sceglierla. Proponi una **tagline** alternativa per dove il testo è consentito (descrizione breve, itch, social, trailer). Indica come testarle (due round con persone esterne, A/B se possibile).
5. **Script del trailer** (durata da playbook; default 60-90 secondi, guarda i comparabili): shot list con tempi (0-5 s hook senza bisogno di audio, poi sviluppo, momento più forte entro metà, ultimi 5 s con titolo, data o "wishlist now"), testi a schermo, indicazioni audio e musica, cosa tagliare. Versione corta da 15-20 secondi per i social.
6. **Pagina itch.io** (se prevista): testo più breve e diretto, con link alla wishlist su Steam.
7. **Blurb per press kit e creator**: una riga, un paragrafo, 5 fatti verificabili.
8. **Controllo veridicità**: per ogni affermazione dei testi indica l'evidenza nel gioco (file, scena, clip) in una tabella `affermazione | evidenza`. Mai promettere feature assenti, premi o citazioni inventati, paragoni con titoli famosi non giustificati. Dichiara l'uso di AI generativa dove la piattaforma lo richiede.
9. **Piano di test dei testi**: quale variante provare per prima e come misurare (click sulla capsule, tasso di wishlist per visita alla pagina).

Ogni file termina con TODO nel formato di `references/06-synthesis-output.md`.
