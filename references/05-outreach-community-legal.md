# Fasi 8, 9, 10: creator, community, test reale, legale e fiscale

---

## FASE 8: outreach mirato

Output: **`launch/creators.csv`** e **`launch/06-creators.md`**. Non usare l'etichetta generica "influencer": TikTok, YouTube e Twitch/Kick hanno logiche diverse di scoperta e conversione.

### Pipeline con gli script

Esegui da qualsiasi cartella con il percorso assoluto della skill. Salva i grezzi in `launch/_raw/`.

```bash
S=<skill>/scripts/research ; RAW=launch/_raw
# 1. scrivi $RAW/topics.json: {"PlateUp!": ["PlateUp", "PlateUp gameplay ita"], ...}  (comparabili + query)
python3 $S/yt_research.py search --topics-json $RAW/topics.json --within month --within year --dedupe -o $RAW/yt_raw.json
python3 $S/yt_research.py channels $RAW/yt_raw.json --max-days 90 --exclude-title "trailer|soundtrack|ost" -o $RAW/yt_channels.json
python3 $S/yt_research.py subs $RAW/yt_channels.json --min-subs 1000 --max-subs 1000000 -o $RAW/yt_shortlist.json
# 2. URL TikTok / Shorts / Twitch / Instagram trovati con ricerca web, uno per riga in $RAW/social_urls.txt
python3 $S/social_verify.py --urls-file $RAW/social_urls.txt --since <OGGI-90-GIORNI> -o $RAW/social_verified.json
# 3. esclusioni, lingue e note vanno in $RAW/curation.json (mai nel codice)
python3 $S/build_creators.py --youtube $RAW/yt_shortlist.json --social $RAW/social_verified.json \
  --config $RAW/curation.json --priority-langs IT,EN -o launch/creators.csv
```

`<OGGI-90-GIORNI>` si calcola dalla data del sistema (es. `date -d '-90 days' +%F`), mai copiata da un esempio.

### Regole
1. **Mix di piattaforme dal playbook.** Non esiste un mix universale: cozy e roguelite visivi pesano su TikTok e Shorts, strategia e simulatori su YouTube long-form e streamer, horror su streamer e reaction. Parti dalle proporzioni del playbook e correggile con i comparabili. **Nessuna monocultura**: obiettivo nessuna piattaforma sotto il 10% del database, ma solo con voci verificate.
2. **Copertura linguistica** (obiettivi, adattali se il pubblico è regionale): creator nella lingua del team per feedback iniziale e passaparola (almeno 25%), internazionali in inglese per il mercato Steam (almeno 60%).
3. **Ricerca reale**: per ogni comparabile cerca chi ha pubblicato su quel gioco negli ultimi 60-90 giorni. Escludi profili inattivi da oltre 30 giorni, con feed interamente sponsorizzato o con pubblico non coerente col genere.
4. **Segmentazione per dimensione**: nano e micro (più reattivi), medi (da contattare con demo stabile, clip e trailer a Next Fest o al lancio), macro (da monitorare se l'hook innesca un trend). Le soglie numeriche per piattaforma vanno verificate; quelle di `build_creators.py` (nano < 10k, micro < 100k, medio < 1M) sono convenzioni modificabili.
5. **Database** (`creators.csv`, 80-120 voci verificate in Completa; **meno ma vere**, mai riempire con voci non verificate). Colonne prodotte da `build_creators.py`: `piattaforma, nome, url, lingua, iscritti_follower, segmento, priorita, gioco_coperto, titolo_video, url_video, data_pubblicazione_circa, views, perche, contatto, data_verifica`. L'**angolo di hook consigliato** va in `perche` (via `curation.json` → `notes`). Se non puoi verificare un contatto o un URL, lascia il campo vuoto e scrivi come trovarlo. Follower di TikTok/Instagram: **"da verificare a mano"**, non si leggono senza login.
6. **Modelli di pitch senza spam**:
   - **TikToker**: DM o email di 2-3 frasi, hook in una riga, clip verticale unlisted, link alla demo in un click.
   - **YouTuber e streamer**: email personalizzata di 3-4 frasi con riferimento a un loro video recente affine, sinossi in una riga, chiave o build privata con istruzioni, press kit breve.
   - Usa pitch e blurb di Fase 2B e 6B. Se c'è compenso o chiave, il creator deve poter dichiarare la collaborazione secondo le regole della piattaforma e le norme pubblicitarie del suo paese.
7. **Sequenza temporale**: chi contattare quando (settimane prima del festival, giorno del lancio, post-lancio), con un solo follow-up non insistente.
8. **Dati personali**: nel database solo contatti professionali **pubblici** (email di business, pagina contatti del canale). Niente dati privati; a campagna finita cancella o anonimizza ciò che non serve più (GDPR, se il creator è nello Spazio Economico Europeo).

---

## FASE 9: community, playtest e kit del test reale

Output: **`launch/07-community.md`**.

- **Community del genere**: subreddit, server Discord, forum e gruppi dove vive il pubblico del playbook, con le regole di autopromozione **verificate** di ciascuno:

  ```bash
  export REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=... REDDIT_USER_AGENT="launch-research/1.0 by u/<nome>"
  python3 <skill>/scripts/research/reddit_rules.py IndieDev indiegaming playmygame DestroyMyGame -o launch/_raw/reddit_rules.md
  ```
  Se risponde `403 Blocked` (senza OAuth succede quasi sempre), leggi la sidebar a mano e scrivilo in `ricerche-manuali.md`. Formati narrativi (problema risolto, clip curiosa, lezione appresa), non "comprate il mio gioco". Dichiara l'uso di AI generativa dove community o piattaforma lo richiedono.
- **Quando pubblicare.** Con GamesTracker: `gt_corpus.py marketing --db <percorso> --tag <tag> --md launch/_raw/gt_marketing.md` mostra, per i giochi migliori e per il resto, quanti post escono nelle finestre prima e dopo l'uscita (-90..-61, -60..-31, -30..-8, -7..-1, 0..+6, +7..+30), il mix di piattaforme e la mediana di views. È co-occorrenza, non causalità: usala per calibrare cadenza e piattaforme, non come regola.
- **Discord e newsletter**: se l'obiettivo è vendere, valuta se vale il costo di moderazione e proponi la soglia minima sensata.
- **Cadenza di devlog**: frequenza e formato realistici per il team (meglio poco e costante).
- **Kit del test reale (Gate B)**, pronto da usare:
  1. **Testo di reclutamento** (versioni per Reddit, Discord, social) senza hype e con chiarezza su cosa si chiede.
  2. **Criteri di selezione** di sconosciuti (non amici compiacenti), mix di esperienza nel genere.
  3. **Questionario di 5 domande**: cosa hai capito del gioco, dove ti sei annoiato o confuso, cosa ti è piaciuto di più, quanto pagheresti, lo consiglieresti (0-10 e perché).
  4. **Scheda di osservazione** per sessioni dal vivo (minuto del primo dubbio, minuto del primo sorriso, cosa non ha capito, se ha ricominciato).
  5. **Eventi di telemetria**: inizio e fine sessione, durata, morte o fallimento, punto di abbandono, seconda sessione.
  6. **Soglie di passaggio** del Gate B e **regole di scarto** dei dati (es. tester che non ha completato i primi 10 minuti).
  7. **Come confrontare** i risultati con le critiche simulate e reali (matrice di convergenza): le ipotesi della 7.3 diventano confermate o smentite.
  8. **Consenso e privacy**: dichiara cosa raccogli e perché, chiedi consenso per telemetria e registrazioni, conserva il minimo.

---

## FASE 10: branding, legale e fiscale

Output: **`launch/08-brand-legal.md`**. Non sei né avvocato né commercialista: segnala dove serve un professionista e non presentare mai cifre di imposte o contributi come fatti.

### Parte comune a tutti i paesi
- **Titolo e ricercabilità**: collisioni, caratteri speciali, memorabilità e pronuncia in inglese; marchi (EUIPO, TMview, USPTO, ufficio del paese del team).
- **Asset Steamworks**: dimensioni **attuali** di capsule e asset (verifica sulla documentazione Steamworks, cambiano), palette ad alto contrasto, localizzazione della capsule.
- **Questionari e classificazioni**: contenuti maturi, violenza, gambling o meccaniche assimilabili, rating (IARC/PEGI/ESRB) e dichiarazioni obbligatorie, incluso l'uso di AI. Verifica le policy di Valve.
- **Licenze**: asset, font, musica, plugin, middleware, modelli AI usati. Elenco con licenza e rischio (tabella `elemento | licenza | uso commerciale | attribuzione | rischio`). Per i giochi musicali la licenza della musica è un rischio primario.
- **Privacy**: policy e conformità (GDPR, CCPA) se ci sono telemetria, account o online.
- **Soci e proventi**: se ci sono più persone serve un accordo scritto sulla ripartizione prima di incassare (Steam paga un solo soggetto).

### Fiscale: parametrizzato per paese
Leggi il paese del team dal brief (Fase 0). Domande a cui rispondere per **qualunque** paese, con fonte ufficiale e data:
1. Steam richiede **interviste fiscali** (identità fiscale, modulo per i non residenti USA, ad es. W-8BEN/W-8BEN-E e trattati contro le doppie imposizioni): quali valgono per te?
2. Chi applica **IVA/sales tax** sulle vendite e chi la dichiara? (Di norma la piattaforma riscuote e versa; tu hai comunque obblighi di dichiarazione dei ricavi.)
3. Quale **forma giuridica o regime** (ditta individuale, società, regime agevolato) è sensato per la soglia di ricavi attesa?
4. Quali **contributi previdenziali** e **scadenze** si applicano?
5. Serve **partita IVA o equivalente** prima del primo pagamento?
6. Cosa va chiesto al **commercialista** prima di incassare?

Etichetta ogni cifra **[DA VERIFICARE]** con fonte dell'autorità fiscale del paese e rimando al professionista. Se il paese non è coperto, dichiara il limite invece di indovinare.

**Esempio: Italia** (se confermata nel brief): codice ATECO, regime forfettario o ordinario, contributi INPS (gestione separata o commercianti), partita IVA, scrittura privata tra soci, interviste fiscali Steam. Fonti: INPS, Agenzia delle Entrate. Intervalli, mai valori fissi.

Ogni file termina con TODO nel formato di `references/06-synthesis-output.md`.
