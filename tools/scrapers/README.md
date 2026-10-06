# research-scrapers

Strumenti riutilizzabili per la ricerca di mercato di un lancio indie (comparabili Steam, creator YouTube/TikTok, regole subreddit). Versioni generiche e ripulite degli script scritti a mano in `BuffetPanic/launch/_raw/` (che restano invariati). Niente è legato a un gioco specifico: tutto passa da argomenti CLI.

- **Requisiti:** Python >= 3.9, solo libreria standard (`requirements.txt` è vuoto di proposito).
- **Rete:** ogni tool rispetta un intervallo minimo tra le richieste (`--rate`, in secondi), riprova con backoff esponenziale sugli errori 429/5xx e rispetta `Retry-After`.
- **Output:** JSON (default su stdout, oppure `-o file.json`) o CSV (`-o file.csv`, UTF-8 con BOM, si apre bene in Excel). I log vanno su stderr.
- **Credenziali:** nessuna nei file. Le chiavi opzionali si passano **solo** tramite variabili d'ambiente.

| Tool | Da quale script originale | Cosa fa |
|---|---|---|
| `steam_comps.py` | `fetch.py`, `comps.py`, `comps2.py` | Dati store + recensioni + stime Boxleiter (+ SteamSpy / Gamalytic) per i comparabili |
| `yt_research.py` | `yt.py`, `yt_batch.py`, `subs.py` (+ il raggruppamento per canale fatto a mano) | Cerca video recenti, li raggruppa per canale, aggiunge gli iscritti, verifica gli URL |
| `social_verify.py` | `tt.py` | Verifica gli URL di TikTok / YouTube (anche Shorts) / Instagram / Twitch con endpoint ufficiali |
| `reddit_rules.py` | (da `reddit_rules.txt`, fallito con 403) | Regole del subreddit + iscritti + segnalazione delle regole sulla promozione |
| `build_creators.py` | `build_creators.py` | Unisce tutto in un CSV di creator ordinato per priorità |
| `common.py` | — | HTTP con throttle e retry, scrittura JSON/CSV (lo usano tutti) |

---

## 1. `steam_comps.py`: comparabili Steam

Endpoint: `store.steampowered.com/api/appdetails`, `store.steampowered.com/appreviews` (pubblici); opzionali `steamspy.com/api.php` (`--steamspy`) e `gamalytic.com/api/game-details` (`--gamalytic`, stime di terze parti).

```bash
python steam_comps.py 1599600 728880 -o comps.json
python steam_comps.py --ids-file ids.txt --steamspy --gamalytic --boxleiter 30,60 -o comps.csv --headers-dir hdr
python steam_comps.py 1599600 --cc it --lang italian -o plateup_it.json
```

Ogni gioco produce una riga con: `name, release_date, coming_soon, price_base_cents, price_now_cents, discount_pct, developers, publishers, genres, categories, demos, movies, screenshots, reviews_total, reviews_positive, pct_positive, review_score_desc, boxleiter_x30, boxleiter_x60`. Con `--steamspy` si aggiungono `steamspy_owners` e `steamspy_tags`. Con `--gamalytic` si aggiungono `gamalytic_copies`, `revenue`, `accuracy`, `avg_playtime_h`, `followers`, `tags`, `first_release`, `audience_overlap` e `copies_per_review`. `--headers-dir` salva anche `<appid>.jpg`, cioè le capsule header usate per i confronti visivi.

**Limiti:** Boxleiter è solo una regola empirica (copie ≈ recensioni × 30–60). Gamalytic e SteamSpy sono stime di terze parti con accuratezza variabile, e Gamalytic può cambiare l'API senza preavviso. `appdetails` ha un rate limit di circa 200 richieste ogni 5 minuti: non scendere sotto `--rate 1`.

## 2. `yt_research.py`: creator YouTube

Ci sono due backend:
- **`api`**: YouTube Data API v3 ufficiale. Serve `YOUTUBE_API_KEY` (gratis da Google Cloud Console). Una ricerca costa 100 unità e la quota giornaliera è di 10.000, cioè circa 90 query al giorno. Dà date esatte (`publishedAt`) e iscritti esatti. **È il backend consigliato.**
- **`html`**: legge `ytInitialData` dalla pagina pubblica dei risultati, senza chiave e senza login. È quello che faceva `yt.py`. È fragile (si rompe se cambia il layout), le date sono relative ("2w ago") e i ToS di YouTube non incoraggiano l'accesso automatico: usalo con volumi bassi e `--rate` alto.
- `auto` (default): usa `api` se la chiave è impostata, altrimenti `html`.

```bash
# 1) ricerca: query singole, oppure un file topics.json {"PlateUp!": ["PlateUp", "PlateUp ita"], ...}
python yt_research.py search -q "PlateUp" -q "PlateUp ita" --within month --dedupe -o yt_raw.json
python yt_research.py search --topics-json topics.json --within month --within year --dedupe -o yt_raw.json
python yt_research.py search -q "cooking roguelite" --backend api --region IT --lang it -o yt_it.json

# 2) raggruppa per canale, tenendo solo i video degli ultimi 90 giorni
python yt_research.py channels yt_raw.json --max-days 90 --exclude-title "trailer|soundtrack|ost" -o yt_channels.json

# 3) iscritti, paese e descrizione, filtrati per fascia
python yt_research.py subs yt_channels.json --min-subs 1000 --max-subs 1000000 -o yt_shortlist.json

# 4) verifica che esistano video o Shorts specifici (oEmbed ufficiale, senza chiave)
python yt_research.py verify https://www.youtube.com/shorts/XXXXXXXXXXX --urls-file urls.txt -o yt_verified.json
```

Valori di `--within`: `hour, today, week, month, year, any` (ripetibile). Campi dei video: `vid, title, ch, url, when, days, views, topic, query, window`.

**Limiti:** con `html` l'età dei video è approssimata ("1mo" diventa 30 giorni). Alcuni canali nascondono gli iscritti (`subs = null`; tienili con `--keep-unknown`). `subs --backend api` funziona solo per i canali trovati via API, cioè quelli che hanno un `channel_id`.

## 3. `social_verify.py`: verifica URL social (solo endpoint ufficiali)

```bash
python social_verify.py https://www.tiktok.com/@utente/video/7677411131643809031 -o tt_verified.json
python social_verify.py --urls-file urls.txt --since 2026-07-01 -o verified.csv
```

La piattaforma viene riconosciuta dall'URL. Campi: `url, platform, ok, date, author, author_url, title, recent` (`recent` compare solo con `--since`).

| Piattaforma | Endpoint | Chiave | Cosa restituisce |
|---|---|---|---|
| TikTok | `tiktok.com/oembed` | nessuna | autore, handle, didascalia; **data ricavata dall'ID** (`id >> 32`) |
| YouTube e Shorts | `youtube.com/oembed` | nessuna | autore, canale, titolo (niente data: per quella usa `yt_research.py --backend api`) |
| Instagram | Graph API `instagram_oembed` | `IG_OEMBED_TOKEN` = `APP_ID\|CLIENT_TOKEN` di un'app Meta con "oEmbed Read" | autore, didascalia |
| Twitch | Helix (`clips`, `videos`, `users`) | `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` (app token client-credentials) | clip/VOD: data, visualizzazioni; canale: ultimi 5 VOD con data |

Senza chiave, Instagram e Twitch vengono **saltati** (`skipped`) invece di essere letti dalle pagine.

**Limiti (lavoro manuale):**
- **Follower TikTok:** non sono disponibili senza login. La pagina profilo e le pagine `/discover` rimandano al login (vedi `_raw/tt1.html`). Vanno letti a mano dall'app o dal browser.
- **Follower Instagram e Twitch:** servono token utente o permessi di business, quindi vanno letti a mano.
- **Ricerca su TikTok e Instagram:** non esiste un endpoint pubblico e legittimo senza login. Gli URL vanno trovati a mano (o tramite ricerca web) e poi verificati qui.
- **X/Twitter:** escluso. L'API richiede un piano a pagamento e l'oEmbed non dà dati utili per verificare la copertura.

## 4. `reddit_rules.py`: regole dei subreddit

```bash
export REDDIT_CLIENT_ID=...  REDDIT_CLIENT_SECRET=...   # app "script" su reddit.com/prefs/apps
export REDDIT_USER_AGENT="launch-research/1.0 by u/tuonome"
python reddit_rules.py IndieDev indiegaming playmygame DestroyMyGame -o reddit_rules.md
python reddit_rules.py --subs-file subs.txt -o reddit_rules.json
```

Restituisce le regole (titolo e testo), `subscribers`, `submission_type` e `promo_related_rules`, cioè i numeri delle regole che parlano di autopromozione, rapporto 10%, flair, Screenshot Saturday e simili. In `.md` queste regole sono marcate **[promo]**.

**Limiti:** senza OAuth Reddit risponde quasi sempre `403 Blocked` (verificato oggi). Lo script non prova ad aggirare il blocco: lo segnala e rimanda alla sidebar. Con OAuth app-only (gratis) funziona.

## 5. `build_creators.py`: CSV dei creator

```bash
python build_creators.py --youtube yt_shortlist.json --social tt_verified.json \
  --config curation.json --priority-langs IT,EN --tier-a-max 200000 --tier-b-max 1000000 \
  --ref-date 2026-10-06 -o creators.csv
```

`curation.json` (opzionale) contiene le scelte manuali, che prima erano scritte nel codice:

```json
{
  "exclude":   ["Canale da escludere"],
  "lang":      {"NomeCanale": "IT", "Furo": "EN"},
  "topic_fit": {"PlateUp!": "cucina + roguelite (il comp più vicino)"},
  "notes":     {"https://www.tiktok.com/@x/video/123": "Curatore co-op indie, chiude con 'wishlist it'"},
  "topics":    {"https://www.tiktok.com/@x/video/123": "Big Walk"}
}
```

Colonne (le stesse di `launch/creators.csv`): `piattaforma, nome, url, lingua, iscritti_follower, segmento, priorita, gioco_coperto, titolo_video, url_video, data_pubblicazione_circa, views, perche, contatto, data_verifica`.

Regole:
- **Lingua:** `config.lang`, poi il paese del canale, poi `--default-lang`.
- **Segmento:** nano < 10k, micro < 100k, medio < 1M, grande ≥ 1M.
- **Priorità:**
  - A = iscritti < `tier-a-max` e lingua prioritaria
  - B = (iscritti < `tier-b-max` e lingua prioritaria) oppure iscritti < `tier-a-max`
  - C = il resto
- **Righe social senza follower:** A se la lingua è prioritaria, altrimenti B.
- **`--ref-date`:** la data in cui hai fatto la ricerca. Serve a convertire "2w ago" in una data.

---

## Pipeline tipica (circa 15 minuti)

```bash
python steam_comps.py --ids-file comps_ids.txt --gamalytic -o out/comps.csv
python yt_research.py search --topics-json topics.json --within month --within year --dedupe -o out/yt_raw.json
python yt_research.py channels out/yt_raw.json --max-days 120 -o out/yt_channels.json
python yt_research.py subs out/yt_channels.json --max-subs 2000000 -o out/yt_shortlist.json
python social_verify.py --urls-file tiktok_urls.txt --since 2026-06-01 -o out/social.json
python reddit_rules.py --subs-file subs.txt -o out/reddit_rules.md
python build_creators.py --youtube out/yt_shortlist.json --social out/social.json --config curation.json --priority-langs IT,EN -o out/creators.csv
```

## Smoke test (2026-10-06, rete reale)

| Comando | Esito |
|---|---|
| `steam_comps.py 1599600 --steamspy --gamalytic --headers-dir` | OK: PlateUp! 27.376 recensioni (94,7%), demo trovata, SteamSpy 1–2M, Gamalytic 2,39M copie (87 copie per recensione), header scaricato |
| `yt_research.py search/channels/subs` (backend html) | OK: 20 video, 14 canali, iscritti letti 3 su 3 |
| `yt_research.py verify` | OK |
| `social_verify.py` | OK: 2 TikTok verificati (autore e data dall'ID) e 1 YouTube Short; Twitch e Instagram saltati come previsto (senza chiavi) |
| `reddit_rules.py` (anonimo) | **403 Blocked** (atteso): serve OAuth |
| `build_creators.py` | OK. Rigenerato da `_raw/yt_shortlist.json`: 230 righe YouTube |
| `yt_research.py --backend api` | **non testato** (nessuna `YOUTUBE_API_KEY`) |

---

## Come integrarli nella skill `game-launch-strategist`

1. Copia la cartella nella skill: `~/.claude/skills/game-launch-strategist/scripts/research/`, con tutti i `.py` (`common.py` compreso) più `requirements.txt` e questo `README.md`.
2. Nel `SKILL.md` aggiungi una sezione come questa:

```markdown
## Strumenti di ricerca (non riscriverli: usa scripts/research/)
Esegui sempre da `scripts/research/` e scrivi gli output in `<progetto>/launch/_raw/`.
- Comparabili Steam: `python scripts/research/steam_comps.py <appid...> --gamalytic -o <raw>/comps.json`
  -> usa reviews_total, pct_positive, boxleiter_x30/x60, gamalytic_copies per la tabella comps.
- Creator YouTube: `yt_research.py search --topics-json <raw>/topics.json --within month --dedupe`
  -> `channels --max-days 90` -> `subs --max-subs 1000000`. Prima scrivi topics.json
  ({"Comparabile": ["query", "query ita"]}). Se manca YOUTUBE_API_KEY usa il backend html con --rate 2.
- Video TikTok/Shorts/Twitch trovati via web search: verificali SEMPRE con `social_verify.py`
  prima di citarli. I follower TikTok/IG vanno segnati "da verificare a mano".
- Regole subreddit: `reddit_rules.py ... -o <raw>/reddit_rules.md`. Se esce 403, leggi la sidebar a mano.
- CSV finale: `build_creators.py --youtube ... --social ... --config <raw>/curation.json --priority-langs IT,EN`.
  Le scelte manuali (esclusioni, lingue, note) vanno in curation.json, non nel codice.
Non aggirare login, CAPTCHA o paywall. Le chiavi si passano solo da variabili d'ambiente.
```

3. Variabili d'ambiente opzionali: `YOUTUBE_API_KEY`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `IG_OEMBED_TOKEN`. Impostale nel profilo della shell o in `settings.json` (`env`), mai nei file della skill.
