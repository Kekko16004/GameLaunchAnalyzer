# research scripts

Reusable tools for launch market research: Steam comparables and reviews, creators on YouTube/TikTok/Twitch, subreddit rules, and the simulated-tester roster. Nothing is tied to a specific game: everything goes through CLI arguments.

- **Requirements:** Python ≥ 3.9, standard library only (`requirements.txt` is empty on purpose).
- **Network:** every tool keeps a minimum interval between requests (`--rate`, seconds), retries 429/5xx with exponential backoff and honours `Retry-After`.
- **Output:** JSON (stdout by default, or `-o file.json`) or CSV (`-o file.csv`, UTF-8 with BOM, opens cleanly in Excel). Logs go to stderr.
- **Credentials:** never in files. Optional keys are passed **only** through environment variables.
- **Failure mode:** a blocked or failing endpoint is logged and skipped; the tools never invent data and never try to bypass logins, CAPTCHAs or blocks.

| Tool | What it does | Skill phase |
|---|---|---|
| `steam_discover.py` | Find comparables: store search by keyword/name, most-reviewed games per tag (SteamSpy) | 2 |
| `steam_comps.py` | Store data + review summary + Boxleiter estimates (+ SteamSpy / Gamalytic) for given app ids | 2, 6, 6B |
| `steam_reviews.py` | Real negative/positive Steam reviews with date, playtime, votes, URL, keyword themes | 7 (real critiques) |
| `roster.py` | Deterministic roster of simulated testers with stable IDs | 7 |
| `yt_research.py` | Search recent videos, group by channel, add subscribers, verify URLs | 8 |
| `social_verify.py` | Verify TikTok / YouTube (Shorts) / Instagram / Twitch URLs with official endpoints | 8 |
| `reddit_rules.py` | Subreddit rules, subscribers, self-promotion flags | 9 |
| `build_creators.py` | Merge everything into a prioritised creators CSV | 8 |
| `common.py` | Throttled HTTP with retries, JSON/CSV writers (used by all) | – |

---

## 1. `steam_discover.py`: find comparables

```bash
python steam_discover.py search "cooking roguelite" "overcooked" --limit 8 -o search.json
python steam_discover.py tag Roguelike Cooking --enrich 40 --released-after 2021 --max-reviews 20000 -o tags.csv
```

- `search` uses the public store search endpoint and returns `appid, name, price, metascore, url` per hit (bundles are skipped).
- `tag` merges the SteamSpy top-100 lists of one or more tags. Games matching more tags rank first, then by review count. `--require-all` keeps only games present in every list; `--min-reviews` / `--max-reviews` cut mega-hits or unproven titles; `--enrich N` adds release date, price, genres and demo from the store for the top N rows (one request each); `--released-after YEAR` filters on the enriched date.

**Limits:** SteamSpy is third-party and lists only about 100 games per tag; owners are ranges; tag names are case-sensitive (`Roguelike`, `City Builder`). The output is a candidate list, not the final comparable set.

## 2. `steam_comps.py`: Steam comparables

Endpoints: `store.steampowered.com/api/appdetails`, `store.steampowered.com/appreviews` (public); optional `steamspy.com/api.php` (`--steamspy`) and `gamalytic.com/api/game-details` (`--gamalytic`, third-party estimates).

```bash
python steam_comps.py 1599600 728880 -o comps.json
python steam_comps.py --ids-file ids.txt --steamspy --gamalytic --boxleiter 30,60 -o comps.csv --headers-dir hdr
python steam_comps.py 1599600 --cc it --lang italian -o plateup_it.json
```

One row per game: `name, release_date, coming_soon, price_base_cents, price_now_cents, discount_pct, developers, publishers, genres, categories, demos, movies, screenshots, reviews_total, reviews_positive, pct_positive, review_score_desc, boxleiter_x30, boxleiter_x60`. `--steamspy` adds `steamspy_owners`, `steamspy_tags`. `--gamalytic` adds `gamalytic_copies`, `revenue`, `accuracy`, `avg_playtime_h`, `followers`, `tags`, `first_release`, `audience_overlap`, `copies_per_review`. `--headers-dir` also saves `<appid>.jpg` capsule headers for visual comparison.

**Limits:** Boxleiter is a rule of thumb (copies ≈ reviews × 30–60, varies by genre, price and year). Gamalytic and SteamSpy are estimates with varying accuracy, and Gamalytic may change its API without notice. `appdetails` allows roughly 200 requests per 5 minutes: do not go below `--rate 1`.

## 3. `steam_reviews.py`: real reviews for the "real critiques" section

```bash
python steam_reviews.py 1599600 728880 --type negative --within-days 365 --limit 150 -o reviews_neg.json
python steam_reviews.py 1599600 --type negative --sort recent --max-playtime-h 2 -o refund_like.json
python steam_reviews.py 1599600 --type positive --limit 100 -o praised.json
python steam_reviews.py --ids-file ids.txt --language all --themes-json my_themes.json -o reviews.csv
```

Uses the public `appreviews` endpoint with cursor pagination (100 per page). Per review: `date, language, playtime_at_review_h, playtime_forever_h, votes_up, votes_funny, helpful_score, steam_purchase, received_for_free, early_access, url, text (truncated), themes`. Per game: a summary with the theme tally (count and %), median playtime at review, share of reviews written under 2 hours (a refund-like signal), median helpful votes and the date range.

Filters: `--type negative|positive|all`, `--sort helpful|recent|updated`, `--language`, `--within-days`, `--min-votes-up`, `--min/--max-playtime-h`, `--purchase all|steam|other`, `--include-offtopic`, `--limit`, `--max-pages`. Reviewer names are not collected.

**Limits and honesty:**
- `--sort helpful` (Steam's order) over-represents the most discussed problems; `--sort recent` is closer to a random slice of current complaints. State which one you used.
- Themes come from an English keyword list (`THEMES` in the script; extend or override with `--themes-json {"theme": "regex"}`). They are a starting point: read a sample and correct by hand. Non-English reviews are not matched unless you add patterns.
- `day_range` is capped at 365 and honoured by Steam only with the helpful order. Steam hides flagged review-bomb periods by default (`--include-offtopic` to see them).
- In deliverables paraphrase reviews, quote under 15 words, one quote per source.

## 4. `roster.py`: simulated testers with stable IDs

```bash
python roster.py --cohorts-a "veterans;min-maxers;balance critics" \
                 --cohorts-b "casuals;clip scrollers;value hunters" --seed mygame \
                 -o launch/fg/roster.json --md launch/fg/roster.md
python roster.py ... --per-group 12      # quick mode (2 x 12)
python roster.py ... --per-group 36      # later: appends A-28.. / B-28.., existing IDs untouched
```

Two groups (A = core/experts, B = discovery/casual), exactly three cohorts each (taken from the genre playbook); tester *n* belongs to cohort `(n-1) % 3`. Every trait (name, age band, hours in genre, device, price sensitivity, patience, discovery channel, language, starting bias, contrarian flag) is derived from `sha256(seed:ID)`, so the same seed and cohorts always give the same roster and adding testers never changes the existing ones. At least 22% of every cohort are flagged contrarians (the skill requires mandatory dissent of at least 15%).

The Markdown file is append-only: rerunning only adds rows for new IDs, so hand-written cards are never overwritten. Rerunning with a different seed, cohorts or language weights is refused unless you pass `--force`.

Everything is fictional and simulated; the default language weights are **not market data** (`--langs "EN:55,IT:10,..."` to adjust).

## 5. `yt_research.py`: YouTube creators

Two backends:
- **`api`**: official YouTube Data API v3. Needs `YOUTUBE_API_KEY` (free from Google Cloud Console). A search costs 100 units against a 10,000 daily quota (about 90 queries/day). Exact dates and subscriber counts. **Recommended.**
- **`html`**: reads `ytInitialData` from the public results page, no key, no login. Fragile (breaks on layout changes), dates are relative ("2w ago"), and YouTube's ToS discourage automated access: use low volume and a high `--rate`.
- `auto` (default): `api` if the key is set, otherwise `html`.

```bash
python yt_research.py search -q "PlateUp" -q "PlateUp ita" --within month --dedupe -o yt_raw.json
python yt_research.py search --topics-json topics.json --within month --within year --dedupe -o yt_raw.json
python yt_research.py search -q "cooking roguelite" --backend api --region IT --lang it -o yt_it.json
python yt_research.py channels yt_raw.json --max-days 90 --exclude-title "trailer|soundtrack|ost" -o yt_channels.json
python yt_research.py subs yt_channels.json --min-subs 1000 --max-subs 1000000 -o yt_shortlist.json
python yt_research.py verify https://www.youtube.com/shorts/XXXXXXXXXXX --urls-file urls.txt -o yt_verified.json
```

`topics.json` is `{"Comparable": ["query", "query ita"], ...}`. `--within` values: `hour, today, week, month, year, any` (repeatable).

**Limits:** with `html`, video age is approximate ("1mo" becomes 30 days). Some channels hide subscribers (`subs = null`; keep them with `--keep-unknown`). `subs --backend api` only works for channels found through the API (those with a `channel_id`).

## 6. `social_verify.py`: social URL verification (official endpoints only)

```bash
python social_verify.py https://www.tiktok.com/@user/video/7677411131643809031 -o tt_verified.json
python social_verify.py --urls-file urls.txt --since 2026-07-01 -o verified.csv
```

The platform is detected from the URL. Output fields: `url, platform, ok, date, author, author_url, title, recent` (`recent` only with `--since`).

| Platform | Endpoint | Key | Returns |
|---|---|---|---|
| TikTok | `tiktok.com/oembed` | none | author, handle, caption; **date decoded from the video id** (`id >> 32`) |
| YouTube / Shorts | `youtube.com/oembed` | none | author, channel, title (no date: use `yt_research.py --backend api`) |
| Instagram | Graph API `instagram_oembed` | `IG_OEMBED_TOKEN` = `APP_ID\|CLIENT_TOKEN` of a Meta app with "oEmbed Read" | author, caption |
| Twitch | Helix (`clips`, `videos`, `users`) | `TWITCH_CLIENT_ID` + `TWITCH_CLIENT_SECRET` | clip/VOD: date, views; channel: last 5 VODs |

Without keys Instagram and Twitch are **skipped**, never scraped.

**Manual work:** TikTok followers need a login (profile and `/discover` pages redirect to it); Instagram and Twitch follower counts need user tokens or business permissions; there is no public, legitimate search endpoint for TikTok or Instagram (find URLs by hand or web search, then verify them here); X/Twitter is excluded (paid API, oEmbed gives nothing useful).

## 7. `reddit_rules.py`: subreddit rules

```bash
export REDDIT_CLIENT_ID=...  REDDIT_CLIENT_SECRET=...   # "script" app at reddit.com/prefs/apps
export REDDIT_USER_AGENT="launch-research/1.0 by u/yourname"
python reddit_rules.py IndieDev indiegaming playmygame DestroyMyGame -o reddit_rules.md
python reddit_rules.py --subs-file subs.txt -o reddit_rules.json
```

Returns rules (title and text), `subscribers`, `submission_type` and `promo_related_rules`: the numbers of rules mentioning self-promotion, 10% ratio, flair, Screenshot Saturday and similar (flagged **[promo]** in `.md`). The flagging is a regex heuristic: read the rules.

**Limits:** anonymous requests usually get `403 Blocked`. The script does not try to bypass it: it reports the error and points to the sidebar. App-only OAuth (free) works.

## 8. `build_creators.py`: creators CSV

```bash
python build_creators.py --youtube yt_shortlist.json --social tt_verified.json \
  --config curation.json --priority-langs IT,EN --tier-a-max 200000 --tier-b-max 1000000 \
  --ref-date 2026-10-06 -o creators.csv
```

`curation.json` (optional) holds the manual choices that would otherwise live in code:

```json
{
  "exclude":   ["Channel to exclude"],
  "lang":      {"ChannelName": "IT", "Other": "EN"},
  "topic_fit": {"PlateUp!": "cooking + roguelite (closest comp)"},
  "notes":     {"https://www.tiktok.com/@x/video/123": "Co-op indie curator, ends with 'wishlist it'"},
  "topics":    {"https://www.tiktok.com/@x/video/123": "Big Walk"}
}
```

Columns: `piattaforma, nome, url, lingua, iscritti_follower, segmento, priorita, gioco_coperto, titolo_video, url_video, data_pubblicazione_circa, views, perche, contatto, data_verifica`.

- **Language:** `config.lang`, then the channel country, then `--default-lang`.
- **Segment:** nano < 10k, micro < 100k, medio < 1M, grande ≥ 1M.
- **Priority:** A = subscribers < `tier-a-max` and priority language; B = (subscribers < `tier-b-max` and priority language) or subscribers < `tier-a-max`; C = the rest. Social rows without follower counts: A if the language is a priority, otherwise B.
- **`--ref-date`:** the day the search ran; converts "2w ago" into a date.
- YouTube channels with unknown subscriber counts are skipped with a warning (the count is logged).

---

## Typical pipeline

```bash
python steam_discover.py tag Roguelike Cooking --enrich 40 -o out/discover.json
python steam_comps.py --ids-file comps_ids.txt --steamspy --gamalytic -o out/comps.csv
python steam_reviews.py --ids-file comps_ids.txt --type negative --limit 150 -o out/reviews_neg.json
python roster.py --cohorts-a "..;..;.." --cohorts-b "..;..;.." --seed mygame -o out/roster.json --md out/roster.md
python yt_research.py search --topics-json topics.json --within month --within year --dedupe -o out/yt_raw.json
python yt_research.py channels out/yt_raw.json --max-days 120 -o out/yt_channels.json
python yt_research.py subs out/yt_channels.json --max-subs 2000000 -o out/yt_shortlist.json
python social_verify.py --urls-file tiktok_urls.txt --since 2026-06-01 -o out/social.json
python reddit_rules.py --subs-file subs.txt -o out/reddit_rules.md
python build_creators.py --youtube out/yt_shortlist.json --social out/social.json --config curation.json --priority-langs IT,EN -o out/creators.csv
```

## Test status

| Tool | Status |
|---|---|
| `steam_comps.py`, `yt_research.py` (html backend: search, channels, subs, verify), `social_verify.py` (TikTok, YouTube), `build_creators.py` | Run against the live services on 2026-10-06 (PlateUp! 27,376 reviews at 94.7%, SteamSpy 1–2M owners, Gamalytic 2.39M copies = 87 copies/review; 20 videos, 14 channels, 3/3 subscriber counts; 2 TikToks and 1 Short verified). Re-checked offline after the date-handling changes. |
| `reddit_rules.py` anonymous | `403 Blocked` (expected: OAuth needed). |
| `yt_research.py --backend api` | Not tested (no `YOUTUBE_API_KEY`). |
| `steam_reviews.py`, `steam_discover.py`, `roster.py` | Tested **offline** against canned responses shaped like the documented APIs (paging, duplicate and cursor handling, filters, day-range cap, early stop on recent sort, theme tally, CSV output, tag ranking, roster determinism and append-only behaviour). **Not yet run against the live Steam endpoints**: do a first run with one app id and check the output before relying on it. |
