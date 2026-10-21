# research scripts

Reusable tools for launch market research: Steam comparables and reviews, creators on YouTube/TikTok/Twitch, subreddit rules, and the simulated-tester roster. Nothing is tied to a specific game: everything goes through CLI arguments.

- **Requirements:** Python ≥ 3.9, standard library only (`requirements.txt` is empty on purpose).
- **Network:** every tool keeps a minimum interval between requests (`--rate`, seconds), retries 429/5xx with exponential backoff and honours `Retry-After`.
- **Output:** JSON (stdout by default, or `-o file.json`) or CSV (`-o file.csv`, UTF-8 with BOM, opens cleanly in Excel). Logs go to stderr.
- **Credentials:** never in files. Optional keys are passed **only** through environment variables.
- **Windows:** `common.py` switches stdout/stderr to UTF-8 on import, so emoji and arrows in `plan_steps.py`, `store_kit.py` and the others no longer crash a cp1252 console.
- **Failure mode:** a blocked or failing endpoint is logged and skipped; the tools never invent data and never try to bypass logins, CAPTCHAs or blocks.

| Tool | What it does | Skill phase |
|---|---|---|
| `steam_tags.py` | Resolve tag spellings (Roguelite → Rogue-lite, typos, aliases) and verify each SteamSpy list | 2 |
| `steam_discover.py` | Find comparables: store search by keyword/name, most-reviewed games per tag (SteamSpy) | 2 |
| `steam_comps.py` | Store data + review summary + Boxleiter estimates (+ SteamSpy / Gamalytic) for given app ids | 2, 6, 6B |
| `steam_reviews.py` | Real negative/positive Steam reviews with date, playtime, votes, URL, keyword themes | 7 (real critiques) |
| `roster.py` | Deterministic roster of simulated testers with stable IDs, casting traits and a 10-person jury | 7 |
| `fg_waves.py` | Validate a focus-group wave, compute score and metrics, delta between waves, timeline | 7 |
| `wave_kit.py` | Mandatory preparation of every wave: templates (`init`) and checklist (`check`) for the game map, screen map, timed runs, market, gameplay proposals, demo cap | 7 |
| `yt_research.py` | Search recent videos, group by channel, add subscribers, verify URLs | 8 |
| `social_verify.py` | Verify TikTok / YouTube (Shorts) / Instagram / Twitch URLs with official endpoints | 8 |
| `reddit_rules.py` | Subreddit rules, subscribers, self-promotion flags | 9 |
| `build_creators.py` | Merge everything into a prioritised creators CSV | 8 |
| `review_corpus.py` | Many real reviews of the comparables AND of the genre: punished/rewarded themes, what they say about your game's features | 2, 7 |
| `store_bench.py` | Store page and trailer analysis of the comparables (description, GIFs, trailer length, cuts, frames) vs how they performed | 2, 6, 6B |
| `trailer_kit.py` | Trailer system: tool versions (brag, HyperFrames, ffmpeg), full measurement of any trailer (file or Steam HLS URL: all cuts, shot length per third, LUFS/true peak, frozen and black stretches, tempo), competitor table, storyboard checks, LONG master prompt + negative prompt + storyboard + asset plan + credits ledger + recording brief + QA list (+ Trailer tab of STATUS.html), automatic QA of a render, blind viewer panel with real anchors, code-made SFX/music sketches | Trailer, 6 |
| `genre_bench.py` | Genre benchmarks at runtime from public data: distributions, cohorts by year, price bands, demo, visibility bar, your numbers | 2, 5 |
| `market_tracker.py` | The whole market over time: head (top sellers, most played, tag tops), breakouts, snapshots at +24h/48h/1w/1m/3m, multi-method copy estimates, marketing per game (Steam news, YouTube, Reddit, Twitch) with timelines, manual-check file for SteamDB / TikTok / IG / X | 2, 5, 7C, routine |
| `top_moves.py` | The 3 moves with most impact now (open issues, real winners' recipe, metro levers, deadlines), written into TODO.md and calendar.md without duplicates | 4, 7, 11, every run |
| `predictions.py` | Predictions log: every wave and estimate vs what really happened, accuracy over time | 7, 7C, 11 |
| `market_page.py` | The real-market parts of STATUS.html: header summary, Mercato reale tab, cards in the other tabs | 11 |
| `entity_match.py` | Does this video / post really talk about this game? Scored entity matching with measured precision | 2, 8 |
| `cohort_bench.py` | Base rate of the real competition: games released per day, automatic junk filter, contact sheets for strict A/B/C visual grading, outcomes per tier (Boxleiter range, ≥100 / 1,000 / 10,000 copies, "became popular"), what separates winners from losers | 2, 5 |
| `project_scan.py` | Cold start: reads the project from disk (engine and version, ranked context documents, what other skills left, Steam, media, git, tools, configured MCP servers) | B |
| `steamdb_assist.py` | SteamDB as a manual lookup: links to open and an append-only record of followers, wishlist rank, player peaks, lowest price (no scraping) | 2, 7C |
| `watchlist.py` | Comparables and competitors over time: snapshots, growth, discounts, releases, collision with your window | 2, 7C |
| `plan_steps.py` | Step-by-step calendar: who does what (👤 / 🤖), due dates, ticking, summary, format check | 4 |
| `store_kit.py` | Copy-ready Steam and itch.io pages from `store_kit.json`: check, written sheet, files to paste | 6B |
| `metrics_track.py` | Metrics you record and "if... then" contingency scenarios with thresholds, diagnosis and actions | 7C |
| `calc_econ.py` | Light economic plan: gross to net, break-even, three scenarios, sensitivity | 5 |
| `wl_track.py` | Weekly wishlist records vs scenarios and pre-mortem tripwires, with alarms | 4, 7B |
| `steam_events.py` | Steam's official event calendar (seasonal sales, Next Fest, themed fests) from Valve's page with a curated fallback; feeds the launch window, writes dated registration steps and sale warnings into calendar.md / TODO.md | 4, 7C, routine |
| `promo_events.py` | Non-Steam promotion calendar, mostly online (digital showcases, third-party Steam fests, itch.io, Reddit threads, streams, newsletters, the Italian scene; physical events in a separate optional list): submission windows, cost, requirements, reach and acceptance odds for a small team; matches tags and stage, writes 8-12 dated applications a year into calendar.md / TODO.md, feeds top_moves and window.csv | 4, 8, routine |
| `launch_window.py` | Competitor calendar for your launch window: weekly crowding score, quietest weeks, where your date stands | 4, 7C |
| `charts.py`, `report_charts.py` | Inline SVG charts (bars, columns, stacked, bullets) and the chart groups built from the files in `launch/` | 11 |
| `criticita.py` | Criticalities wave by wave, per gate and as an evolution matrix (status new / persistent / rising / falling / resolved / back), plus a register for other sources (`add`, `close`, `list`) | 7, 11 |
| `qa.py` | Questions and answers section: the owner's saved questions, answers computed from today's data, suggested questions; log CLI (`add`, `list`, `rm`) | 11 |
| `glossary.py` | Plain-Italian tooltips, links to the section that deals with the thing mentioned, and a glossary, for the HTML pages | 11 |
| `md_enrich.py` | Links between the Markdown documents of `launch/` and a plain-Italian glossary at the end of `REPORT.md` | 11 |
| `report_html.py` | `REPORT.md` as one illustrated HTML page: charts next to each section | 11 |
| `charts_export.py` | Every report chart as a standalone `.svg` (for Markdown reports) | 11 |
| `status_page.py` | One self-contained HTML status page (seven tabs incl. Calendario, roadmap, live issue decisions, live TODO, every URL clickable) | 11 |
| `calendar_view.py` | The Calendario tab (month grids to the launch, day panel, hover preview, 14-day agenda) and the Roadmap of key milestones, used by `status_page.py` | 11 |
| `weblinks.py` | Bare URLs in the generated pages become short, safe links (new tab, `rel=noopener`), used by `status_page.py` and `report_html.py` | 11 |
| `todo_track.py` | Keep `TODO.md` alive: list, stats, mark done / reopen, add | 4, 11, routine |
| `publisher_scout.py` | Publisher shortlist for a game from the curated `data/publishers.json` (sources and date per entry): fit (declared genres + real Steam catalog via store search and SteamSpy tags, stage, wishlists, team, price, platform, region), tiers realistic now / after X / stretch / dream with per-pitch odds and next step, never "nobody"; with/without publisher on calc_econ numbers (break-even copies multiplier); `check` for stale entries | 0A, 5, 8 |
| `case_studies.py` | Real launch / Next Fest records from dev posts and post-mortems (source URL + date) plus survey benchmarks; `bench` (Next Fest gain entering with N), `tripwires` into calendar.md, `query`, `add` / `import` into the private file | 2, 4, 7C |
| `reddit_trends.py` | What performs on a subreddit now: formats and title hooks of top vs new posts (lift), from public RSS (OAuth API when keys exist); no bypass of 403/429 | 6, 9 |
| `social_content.py` | Evidence-based social module: patterns per platform with strength and sources, small-account benchmarks, post planner (moments → calendar per platform with A/B hooks, CTA by date, subreddit rules and cooldowns, weekly steps in calendar.md), post tracker (manual or CSV export) and `learn` (what works for THIS game, fed back into the plan and top_moves) | 6, 8, 9 |
| `social_kit.py` | Weekly ready-to-post kit (3 cross-posted clips + 1 Reddit post: exact clip or storyboard, A/B hook texts, caption, hashtags, day/time, CTA by date, Steam link with UTM, one-line why with source, 5-minute logging line) and the clip registry with full storyboards and status (todo / recorded / posted); next week's kit is rebuilt from what worked | 6, 8 |
| `honest_odds.py` | One honest-odds card per decision (copies, publisher, Next Fest, social, simulated vs real) with basis, label, what moves it and a cross-check when two sources disagree; shown in STATUS.html | 11 |
| `common.py` | Throttled HTTP with retries, JSON/CSV writers (used by all) | – |

---

## 1. `steam_discover.py`: find comparables

```bash
python steam_discover.py search "cooking roguelite" "overcooked" --limit 8 -o search.json
python steam_discover.py tag Roguelike Cooking --enrich 40 --released-after 2021 --max-reviews 20000 -o tags.csv
```

- `search` uses the public store search endpoint and returns `appid, name, price, metascore, url` per hit (bundles are skipped).
- `tag` merges the SteamSpy top-100 lists of one or more tags. Games matching more tags rank first, then by review count. `--require-all` keeps only games present in every list; `--min-reviews` / `--max-reviews` cut mega-hits or unproven titles; `--enrich N` adds release date, price, genres and demo from the store for the top N rows (one request each); `--released-after YEAR` filters on the enriched date.

- **Tag spelling is resolved for you** (`steam_tags.py`): SteamSpy is case- and hyphen-sensitive and a wrong spelling silently returns another tag's list (`Roguelite` vs `Rogue-lite`). Every tag is matched against the official Steam tag list (live, with a built-in fallback), aliases, hyphen variants and, for typos, the closest names (`rogueliek` → Roguelike); each returned list is **verified** by checking that its most reviewed games really carry the tag, and wrong lists are discarded with a warning. `--exact-tags` queries only the spelling you typed; `--no-validate-tags` skips the verification. `python steam_tags.py Roguelite rogueliek` shows how a name resolves.

**Limits:** SteamSpy is third-party and lists only about 100 games per tag; owners are ranges. The output is a candidate list, not the final comparable set.

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

Two groups (A = core/experts, B = discovery/casual), exactly three cohorts each (taken from the genre playbook); tester *n* belongs to cohort `(n-1) % 3`. Every trait (name, age band, hours in genre, device, price sensitivity, patience, discovery channel, language, starting bias, contrarian flag) is derived from `sha256(seed:ID)`, so the same seed and cohorts always give the same roster and adding testers never changes the existing ones. At least 20% of every cohort (of 2 or more testers) are flagged contrarians (the skill requires mandatory dissent of at least 15%).

The Markdown file is append-only: rerunning only adds rows for new IDs, so hand-written cards are never overwritten. Rerunning with a different seed, cohorts or language weights is refused unless you pass `--force`.

Casting traits (same idea as a persona panel): skill level (derived from hours in genre), personality, speaking style, and an accessibility need for about 1 tester in 9 (colour-blindness, low vision, small screen, one hand, motor constraint, flashing lights/motion sickness, reduced hearing). `roster.json` also holds a **jury** of 10 IDs covering the mandatory roles (novice, expert, skeptic, impatient, accessibility, contrarian, value hunter, clip/stream creator): the same people debate in every wave, and the jury does not change when testers are appended.

Everything is fictional and simulated; the default language weights are **not market data** (`--langs "EN:55,IT:10,..."` to adjust).

## 4b. `fg_waves.py`: focus-group waves, deltas, timeline

The simulated panel judges the game; this tool does the arithmetic, so scores and trends are reproducible. A *wave* is one run of the same roster on one state of the game, stored as `launch/fg/waves/wNN-YYYY-MM-DD.json` (schema in the script's header: per tester `verdict` WISHLIST/SALDI/IGNORO/REFUND, `click`, `pitch_ok`, `issues`; a list of issues with stable keys, severity and recommendation; optional `controls` and, from wave 2, `fixes`). Link with game-developer (`references/dev-link.md`): a fix may carry `gate_dev` (development gate number) and `status` (`risolto` / `da_verificare`), an issue created by a gate carries `from_gate_dev`; both are validated (numbers only) and shown ("nato col gate NN" next to the issue in `metrics`, `delta` and STATUS.html).

```bash
python fg_waves.py metrics launch/fg/waves/w01-2026-10-06.json --roster launch/fg/roster.json -o launch/fg/waves/w01-metrics.md
python fg_waves.py delta launch/fg/waves/w01-2026-10-06.json launch/fg/waves/w02-2026-10-27.json --roster launch/fg/roster.json -o launch/fg/waves/w02-delta.md
python fg_waves.py timeline launch/fg/waves --roster launch/fg/roster.json -o launch/fg/timeline.md --csv launch/fg/timeline.csv
```

- `metrics`: validates (tester IDs against the roster, verdict values, duplicates, issue keys), then computes verdict counts, the wishlist score `((W*1.0)+(S*0.4)-(I*0.2)-(R*0.8))/N*100` (range -80..100, not a percentage), A vs B score and gap (flagged above 15), first-glance click, pitch comprehension, and the issue matrix ranked by frequency x severity. Gate A threshold: `--gate N`, else 80% of the success control (min 30), else 35.
- `delta`: score on the **same testers only** (new IDs are listed but excluded from the like-for-like score), verdict movements, effect of each issue (RESOLVED / IMPROVED / WORSE / NEW / UNCHANGED, noise band `--noise`, default 10 points), fixes applied, per-tester changes with an empty "attributed cause" column.
- `timeline`: all waves in a folder (`wNN-*.json`) with score trend and sparkline, verdict shares, click, pitch, A/B scores, number of high-severity issues, top issue and Gate A status.

**Limits:** the panel is simulated with the same biases every time, so deltas are directional, not proof; differences of a few points are noise (with N = 54 a percentage carries roughly +-13 points of uncertainty). Confirm important changes with real testers.

## 4b1. `wave_kit.py`: mandatory preparation of every wave

Before the panel judges, every wave gets six files built from the real game (any engine), in `launch/fg/waves/`: `wNN-brief.md` (what is judged, standard + extra tester questions, outputs), `wNN-mappa-gioco.md` (total game map with file references), `wNN-schermate.md` (every screen: how you reach it, when, whether the game tells you, grade *evidente / trovabile / nascosta*), `wNN-runs.md` (3+ simulated runs with mm:ss timestamps and dead spots, fun peaks, frustration, quit points, too much UI, unclear moments), `wNN-mercato.md` (real reviews via `review_corpus.py`, demo-length data, sources), `wNN-proposte-gameplay.md` (proposals with evidence, hours, risk, plus a separate "Riapre la decisione" section) and, optionally, `wNN-limite-beta.md` (what to cut in a free demo/beta).

```bash
python wave_kit.py init  --launch-dir launch --wave 10 [--date 2026-11-02] [--game "My Game"]   # Italian templates; existing files are never overwritten (reported as skipped)
python wave_kit.py check --launch-dir launch --wave 10 [--json]                                 # Italian ✅/❌ checklist; exit 1 if something required is missing
```
`check` verifies: every file present (limite-beta only warns); the brief's "Cosa si valuta" filled and the nine extra questions present (in the brief or as tester keys in the wave JSON: `hook_lands`, `q_stop_after_runs`, `q_price_full`, `q_memorable`, `q_coop_needed`, `q_bored_minute`, `q_after_demo`, `q_watch_or_play`, `q_lost_moment`); the map has at least 5 file references and filled sections for loop, economy, progression, controls, audio, accessibility (items, hazards, events, HUD, "what is not there" only warn); at least 3 screen rows graded and the three grades explained; at least 3 `## RUN N` sections with 5+ timestamps each and the dead/fun/frustration/quit marks; reviews (review_corpus), demo length and sources in the market file; proposals with hours, risk and evidence and a filled "Riapre la decisione" section. Sections that still hold only the template guidance or `(da compilare)` count as empty. Headings are matched by meaning, so the real wave-9 files of the reference project pass as they are.

`init` also writes `wNN-sintesi.md` (to fill after the panel: every row with the issue key and the proposal ID `P-wNN-n`). **Link with game-developer** (`references/dev-link.md`, project root = the folder above `launch/`, or `--project`): with `docs/design-review/changes-since-wMM.md` (MM = previous wave) the brief gets a "Da ricontrollare" section with the risks the development gates introduced and the design choices they changed; `wNN-mappa-gioco.md`, `wNN-schermate.md`, `wNN-runs.md` start from `game-map.md`, `screen-map.md`, `runs.md` (copied as they are, with "Partita da … (aggiornata al gate NN)"), and the screens file always has the shared ```` ```screens ```` block. Without those files the templates are the usual ones (runs: rows start with the time from the start of the run, shared tags `[MORTO] [TOP] [FRUSTRA] [ABBANDONO] [CONFUSO] [TROPPA-UI:n] [SPIRALE]`).
```bash
python wave_kit.py fixes --launch-dir launch --wave 10                       # print the `fixes` of changes-since (as they are, + gate_dev from its table)
python wave_kit.py fixes --launch-dir launch --wave 10 --write launch/fg/waves/w10-2026-10-25-beta.json   # append the missing ones, never remove or edit
python wave_kit.py fixes --launch-dir launch --wave 10 --from since.json     # or the output of gate_link.py since --json (issue, what, gate_dev, status)
```
Contract items of `check` only **warn**: changes-since present but not cited in the brief, fixes missing from the wave JSON, ```` ```screens ```` block missing / without root / with orphans not marked `hidden-ok`, runs without time-first rows and shared tags, proposals and sintesi without `P-wNN-n` and keys, reopenings not in the `Riapre la decisione: … — prove: … — proposta: … — costo: …` format, issues with `from_gate_dev` not written "nato col gate NN" in the sintesi, `risolto` keys back in the wave without "ricomparso dopo il gate NN".

## 4c. `review_corpus.py`: real reviews at scale, comparables and genre

```bash
python review_corpus.py --comps 1599600 728880 --genre-tag Roguelike Cooking --max-genre-games 20 \
    --my-features my_features.json -o corpus.json --md corpus.md --csv corpus_features.csv
```
Two groups: `comps` (your closest comparables) and `genre` (other games of the same type, from SteamSpy tag lists, or `--genre-ids` with ids or a `steam_discover.py` file). Per game it takes the same number of negative (`--neg-per-game`, default 150) and positive (`--pos-per-game`, 100) reviews of the last `--within-days` (730), then reports complaint themes and praise themes per group as a **macro-average across games** plus **breadth** (in how many games the theme is at least 10% of the sample). With `--my-features` (`{"cooking": "cook|recipe", "co-op": ["co-op", "coop"]}`) it counts how often each feature of YOUR game is mentioned in negative vs positive reviews (rewarded / punished / divisive / rarely discussed) and keeps the most helpful reviews that mention it (with URL) for you to read and paraphrase. Reviews are cached per game in `--cache-dir` (resume after interruption, `--refresh` to refetch).

**Limits:** non-random samples (`--sort`), English keyword themes, genre games come from the top ~100 SteamSpy list per tag (bias towards well-known titles).

## 4d. `store_bench.py`: store page and trailer benchmarks

```bash
python store_bench.py run 1599600 728880 --ids-file comps_ids.txt --frames-dir launch/_raw/hooks -o pages.json --md store_bench.md
python store_bench.py analyze pages.json --md store_bench.md
```
Per game, automatically: short and long description length and words, GIFs, other images, looping videos, headings, bullets, screenshots, trailers, languages, achievements, categories, demo, price; trailer **duration** (Steam now serves HLS `.m3u8` and DASH `.mpd` trailers instead of MP4: the tool classifies the URLs in the store answer by extension, reads the duration from the playlist or MPD, falls back to `ffprobe` and to the old MP4 header read for legacy files; `trailer_kind` and `trailer_formats` say what was found); with `ffmpeg` installed also time to first cut, cuts in the first 5 s and average shot length of the first 30 s, plus frames at 0/2/5/10/20/30 s in `--frames-dir`. Outcome: reviews, % positive and reviews per year since release. `analyze` gives quartiles, the best third vs the rest (medians) and Spearman correlations with log(reviews per year) and % positive, always with n.

**Limits:** the tool measures pacing; **what the hook is** must be judged by looking at the frames. Correlations over a few comparables are hints, not proof (budget, genre, timing, luck). Servers that ignore HTTP Range give no MP4 duration; without `ffmpeg` there are no cuts or frames (HLS and DASH need `ffmpeg` for cuts). Not yet checked against the live Steam CDN.

## 4d-bis. `trailer_kit.py`: the trailer system (references/08-trailer.md)

```bash
python trailer_kit.py tools --spec launch/trailer/v3/trailer.json                     # brag / hyperframes / ffmpeg versions into the spec
python trailer_kit.py measure "<steam HLS url>" --name "Balatro" --appid 2379780 -o launch/_raw/trailer_v3/measured.json
python trailer_kit.py bench launch/_raw/trailer_v3/store_pages_trailer.json --measured launch/_raw/trailer_v3/measured.json --spec launch/trailer/v3/trailer.json --md bench.md -o bench.json
python trailer_kit.py check launch/trailer/v3/trailer.json                            # storyboard rules, exit 1 on errors
python trailer_kit.py build launch/trailer/v3/trailer.json --bench bench.json         # PROMPT.md, storyboard, assets, ledger, brief, QA, kit.json
python trailer_kit.py qa render.mp4 --spec launch/trailer/v3/trailer.json --format main --md qa.md
python trailer_kit.py panel init --spec ... --render render.mp4 --out-dir launch/trailer/v3/panel ; python trailer_kit.py panel score results.json --key .../panel-key.json
python trailer_kit.py synth whoosh out.wav --seed 1 --ledger launch/trailer/v3/credits-ledger.csv --credit "Studio"
```
Knowledge base: `data/trailer_craft.json` (rules paraphrased from Derek Lieu, How To Market A Game, GameDiscoverCo, Steamworks docs and platform guides, each with URL, date and strength; platform specs; negative base list; clean asset sources). The single source of truth of a trailer is `launch/trailer/<v>/trailer.json`; `status_page.py` shows the newest `kit.json` in the **Trailer** tab (copy button for the prompt, storyboard cards, competitor table, QA).

**Limits:** it measures (cuts, loudness, stillness, tempo ±3 BPM with possible octave errors) but cannot judge whether a hook is funny or a shot readable; scene detection misses cuts between near-identical shots; safe zones and -14 LUFS are third-party references, not official specs; Steam's AI-disclosure rules for code-made assets are [DA VERIFICARE]. The panel refuses to run without a real render.

## 4e. `genre_bench.py`: genre benchmarks from public data

```bash
python genre_bench.py --tag Roguelike --tag Cooking --enrich 80 --mine price=14.99 --mine reviews_per_year=500 --md genre_bench.md -o genre_bench.json
```
Takes the ~100 most reviewed games of the tag(s) (SteamSpy), enriches them with release date, price and demo from the Steam store (1 request each, `--enrich N`), and reports distributions (p25 / median / p75 / p90) of reviews, reviews per year, % positive, price and age; cohorts by release year (how crowded the genre is and how recent releases do); price bands; demo vs no demo; Spearman price vs reviews per year; the visibility bar; and with `--mine` the percentile of your own values. Built at run time from public data, nothing local to maintain.

**Limit, quote it every time:** the list holds the MOST REVIEWED games of the tag, so the numbers describe the successful tail, not the median game. Reviews per year is a proxy for sales.

## 4e1. `cohort_bench.py`: base rate of new releases at your level

```bash
python cohort_bench.py volume --days 14                               # games released per day (store search, games only)
python cohort_bench.py fetch --from 2026-07-15 --to 2026-07-21        # every game of a 7-day window ~3 months ago (resumable)
python cohort_bench.py filter                                         # automatic junk rules, reason for every exclusion
python cohort_bench.py sheets --reference <your header_capsule.png>   # contact sheets + grades.csv to fill with A / B / C
python cohort_bench.py report --mine-price 7.99 --md launch/cohort.md # tiers x outcomes
python cohort_bench.py report --price-min 5 --price-max 15 --genres casual,simulation,rogue-lite,physics,comedy,party
```
Answers "of the games that come out every day, how many are at least at our level, and how many of those sell?". Outputs go to `launch/_raw/cohort/` (`--dir` to change): `volume.json`, `window_<from>_<to>.json`, `apps/<appid>.json` (one cached file per app: re-running `fetch` resumes and only asks what is missing), `cohort.json/.csv`, `filtered.csv`, `headers/`, `sheets/`, `grades.csv`, `report.json`.

- **volume**: store search sorted by release date (`category1=998`, DLC excluded), counts per day; long backoff on 429, and a window that could not be read completely is reported, never cached as complete.
- **fetch**: finds the window by binary search on the search offset, then `appdetails` (price, genres, screenshots, trailers, descriptions, languages, demo, Early Access, developer) and `appreviews` (total reviews) per game, plus the public review histogram (`appreviewhistogram`) for games with reviews: only reviews written from the release date on are counted, and a 1.0 launch of a game with years of Early Access reviews is marked `graduate` and left out of the base rate as "not new" (found live: an Early Access game from 2018 with 25,000 reviews looked like a July hit). `--no-histogram` skips it; `--steamspy` optional. Separate throttles for the two endpoints (`--rate` 1.6 s for appdetails, which allows ~200 calls per 5 minutes).
- **filter**: status `keep` / `junk` / `not_new` (graduates) / `missing`. Junk rules: `adult` (Adult Only descriptor or Hentai/NSFW tags), `free_thin` (free with no trailer / few screenshots / tiny description), `thin_page` (no trailer and < 5 screenshots), `flip_dev` (same developer with ≥ 3 titles in the window), `generic_name`, `short_desc`, `shovel_tags`. Thresholds are options.
- **sheets**: downloads the header capsules and builds numbered, labelled contact sheets (~30 per sheet, your own capsule first as `RIFERIMENTO`). Backend: Pillow if installed, else `ffmpeg`, else an HTML page per sheet (stdlib). `grades.csv` keeps grades already entered when re-run.
- **report**: per group (all, junk, non junk, A, B, C, A+B, ungraded): median / p75 / p90 reviews, share ≥ 100 / 1,000 / 10,000 copies and ≥ ~$800 gross, each as a range between ×20 and ×60 copies per review; "popular" = ≥ 500 reviews or ≥ 10,000 estimated copies (a definition, say so); "out of 20 at our level"; B-tier winners (≥ `--win-reviews`, default 50) vs losers (< 10) on trailer, screenshots, price, demo, languages, Early Access, publisher; Spearman inside A+B; with `--mine-price` the copies and gross of a typical game of `--mine-grade` (default B).

**Grading rule:** strict. A = clearly above your game, B = about your level, C = below. Your game is **B** unless the evidence says otherwise. **Limits, quote them:** Boxleiter is an order of magnitude; the grading is one rater on one capsule; logged-out search hides adult-only titles and delisted games are gone (junk is a lower bound); one week gives only tens of games per tier. Grading can drift between weeks: on the first real run the B share was 20 % (June) vs 28 % (July), one rater, so real variation and rater drift cannot be told apart; a second rater on a sample is the fix.

## 4e2. Data sources policy and your private keys file

**Used:** official Steam store endpoints (search, appdetails, appreviews, appreviewhistogram), the official Steam Web API (GetNumberOfCurrentPlayers, GetMostPlayedGames, GetNewsForApp), SteamSpy, the YouTube Data API, Reddit (OAuth when `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET` are set, otherwise the public RSS search, which Reddit often rate-limits with 429), Twitch Helix (only with `TWITCH_CLIENT_ID`/`TWITCH_CLIENT_SECRET`) and Gamalytic's public API (only with `GAMALYTIC_API_KEY`).

**Not scraped, on purpose:** SteamDB (its terms do not allow automated scraping and it sits behind Cloudflare), TikTok, Instagram and X (no official access without login or a paid API). For these the tools write the exact pages and searches to do by hand into `launch/ricerche-manuali.md` (`market_tracker.py manual`), and what you find comes back through a CSV (`market_tracker.py manual --import`). Do not "fix" this with a scraper. Followers and wishlists are not public: only proxies, always labelled as proxies.

**Your private keys file:** `~/.game-launch-strategist/.env` (outside the repository, so it can never be committed). Tools load it at run time; `--env-file PATH` or `GLS_ENV_FILE` point to another file; a variable already set in the environment wins. Keys used: `YOUTUBE_API_KEY`, `STEAM_WEB_API_KEY` (passed to Steam Web API calls when present), `REDDIT_USER_AGENT`, optional `REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`, `TWITCH_CLIENT_ID`/`TWITCH_CLIENT_SECRET`, `GAMALYTIC_API_KEY`. Only key NAMES are ever printed; values never go into logs, `launch/`, reports or tests (the repository `.gitignore` also excludes `.env` and `*.env` as a safety net). The install record may store the PATH to the file, never its content.

## 4e3. `cohort_bench.py update` / `calibrate`: the skill keeps learning from every release week

```bash
python cohort_bench.py update --import-dir launch/_raw/cohort --new-weeks 0      # seed the dataset with a cohort already fetched
python cohort_bench.py update --reference <your header capsule>                 # weekly: last full release week + re-checks at 30/90/180 days
python cohort_bench.py update --new-weeks 0                                     # after grading: imports grades.csv of the new week
python cohort_bench.py calibrate                                                # -> ~/.game-launch-strategist/calibration.json
```
`update` keeps one CSV per release week in `~/.game-launch-strategist/cohorts/` (`--dataset` to change). A new week is fetched, filtered and turned into contact sheets in `cohorts/_work/<week>/`; the grades written there are imported on the next run and accumulate. Every run re-checks the outcomes of older weeks when they reach 30, 90 and 180 days: reviews written from release to release+N days come from the public weekly review histogram, so a late check still gives the right count. Rate limited (`--rate-reviews`) and with a request budget per run (`--max-requests`); resumable. `store_prior` (0-100, store page only, adapted from GamesTracker's quality score without the review part, since reviews are the outcome) orders capsules and flags thin pages; it never replaces the A/B/C judgment.

`calibrate` writes `calibration.json`: per milestone (d30, d90, d180) and tier (A, B, C, A+B, all new) the reviews and copies quantiles (×20..×60), shares ≥100 / ≥1,000 / ≥10,000 copies and "popular" with 95 % intervals, the same per price band and genre bucket, the B-tier winners-vs-losers factors, recent real B winners and losers as **control capsules** for the waves, the market junk and tier shares, and (when `market_tracker.py` social data exists) the marketing patterns. `primary` is d90 once it covers at least half the d30 sample, otherwise d30 (labelled). `calc_econ.py --calibration --tier B` and the focus-group waves read it.

## 4e4. `market_tracker.py`: the whole market, sales signals, marketing timelines

```bash
python market_tracker.py discover --top-sellers 25 --most-played 25 --breakouts 15 --tag Casual --tag-top 25
python market_tracker.py discover --from-dataset B           # the B-tier games of the cohort dataset (for marketing patterns)
python market_tracker.py add 3808690 --role comp
python market_tracker.py snapshot --steamspy                  # due snapshots: +24h, +48h, +1 week, +1 month, +3 months (older games: weekly)
python market_tracker.py snapshot --players-only              # several times a day: the daily peak is the max sample
python market_tracker.py estimate --md launch/_raw/market_estimates.md
python market_tracker.py social --role comp --yt-quota 8000   # Steam news + YouTube + Reddit + Twitch, through entity_match
python market_tracker.py timeline --appid 3808690 --md launch/_raw/timeline.md
python market_tracker.py manual --role comp                   # writes the SteamDB / TikTok / IG / X checks into launch/ricerche-manuali.md
python market_tracker.py manual --import found.csv            # platform,url,date,views,likes,appid,note
python market_tracker.py market --md launch/_raw/market_shape.md
```
Data in `~/.game-launch-strategist/market/` (`tracked.json`, append-only `snapshots.csv` and `players.csv`, `social/<appid>.json`, `manual_posts.csv`). Breakouts are the new releases of the last `--days` with the most reviews per day (from the review summary of the release-date search, so no extra calls), at most `--max-price` (default $25, to leave out big-studio launches); free-to-play games and 1.0 launches of old Early Access games can still appear (their timeline shows it). Copies: Boxleiter (reviews ×20..60), SteamSpy owners range (left out when it is the uninformative "0 .. 20,000" bucket), peak players ×30..100 (heuristic); the combined range is the median of the methods, always **[STIMA]**. `manual` rewrites only its own marked section of `ricerche-manuali.md`. Without keys: YouTube and Twitch are skipped with a message, Reddit falls back to RSS.

Ideas and code adapted from **GamesTracker** (https://github.com/Kekko16004/GamesTracker, MIT, the owner's own project): the snapshot schedule, the Steam players and SteamSpy sources, growth / launch-health ideas, the YouTube and Reddit RSS collectors, the manual import. Not ported: its no-login scrapers for TikTok, Instagram and X, and its title-only social search.

## 4e5. `entity_match.py`: only results that really are about the game

A result counts only above a score threshold (50): the exact title as a phrase (or a link to the Steam page) is required; strong signals are the Steam URL / appid, the developer or publisher, an official channel; medium ones are the game's genre words and gaming context words in several languages; a result published before the game existed is rejected; results about another platform with the same name (a Roblox map) lose points. One-word or common-word titles ("Monitor", "SHARKS", "The Wanderer") need two kinds of evidence, unless the platform's own results show the title is distinctive (ambiguity measured on the batch: the share of results with no gaming signal).

Measured on real YouTube results of a bare-title search (what a title-only collector keeps), hand-labelled, 2026-10-13 (`tests/fixtures/entity_match_labels.json`, `entity_match_heldout.json`):

| Sample | Results | Really about the game | Precision before (keep all) | Precision after | Recall after |
|---|---|---|---|---|---|
| tuning set, 20 games | 196 | 99 | 0.51 | 1.00 | 0.73 |
| **held-out set, 12 other games, rules frozen first** | 119 | 76 | **0.64** | **1.00** | **0.91** |

One labeller (the agent that wrote the rules): a second independent labeller would make these figures stronger. `python entity_match.py eval <labels.json>` re-measures.

## 4e5b. The objective "metro": a pre-launch metric built on real outcomes

```bash
python cohort_bench.py --dir <cohort folder> news            # official Steam news per game (demo, Next Fest, playtest, Coming Soon length)
python cohort_bench.py metro                                  # fit + out-of-time backtest -> calibration.json["metro"]
python cohort_bench.py score --features launch/prelaunch.json --md launch/_raw/metro.md -o launch/_raw/metro.json
python cohort_bench.py score --appid 1234567                  # any game with a store page
```
Only what is visible BEFORE release: capsule tier (A/B/C), price, free, trailer and number of videos, screenshots, GIFs in the description, description length, languages, publisher, Early Access, demo / Next Fest / Steam playtest before release and number of official news items (from `ISteamNews`), how long the game was publicly visible before release (first news item -> release, a proxy of the Coming Soon length), crowding of the release day, broad genres. Target: estimated copies (reviews × 35, the geometric middle of Boxleiter 20..60) at 30 days, or at 90 days once the dataset covers it, in bands <100 / 100-1k / 1k-10k / >10k, plus P(≥100), P(≥1k), P(≥10k). Model: three standardized logistic regressions with L2, fitted with plain gradient descent (stdlib), probabilities made monotonic, inputs clipped to ±3 standard deviations (no wild extrapolation). Every factor's weight is shown in words: how many points of P(≥1,000) a typical B game gains when the factor goes from no to yes (or from the 25th to the 75th percentile). **Honest validation:** fit on the older release weeks, test on the newest one; AUC, Brier score against "base rate only", calibration in 4 bins, band accuracy against the most common band; the verdict is "utile", "debole" (read as a range, low confidence) or "non migliore del base rate" (do not use). With one week only, the backtest is impossible and the page says so. Factors that travel together (a demo, its news, a long Coming Soon) share their weight: read them as a group. Not used yet: trailer length (not in appdetails), developer track record (no clean public endpoint), pre-launch YouTube/Reddit coverage (collected only for part of the games; the winners' recipe shows it apart), release month (needs several months). `score` gives the band, the probabilities and the **levers**: how P(≥1k) changes if a missing factor is added (trailer, demo, Next Fest, playtest, 8 languages, 6 months of Coming Soon, news, GIFs, screenshots). The levers feed `top_moves.py`.

## 4e5c. Marketing dossier of any game

```bash
python cohort_bench.py dossier --appid 3808690                # same as market_tracker.py dossier; -> launch/_raw/dossier/dossier-<appid>.md / .json
```
One dated timeline across platforms, every item matched to the game with `entity_match.py`: Steam (official news and events with their kind: demo, Next Fest, playtest, launch, updates; links on the store page; price and players from the snapshots; weekly reviews), YouTube (official channel videos, creator videos with views, Shorts flagged), Reddit (OAuth or public RSS), Twitch (Helix with keys), TikTok **only legitimately**: the official oEmbed of video URLs found in the other sources (title, author; the date is decoded from the video id; views are not exposed), the game's own accounts linked from its store page or website; Instagram and X: links found and manual import (Instagram oEmbed needs a Meta token; the Graph API "Business Discovery" needs your own IG Business account and a Meta app: a future option; the X API is paid). No search-page scraping. Analysis: "what moved the needle" = review spikes (≥ 2× the 4 previous weeks) and the events of the 7 days before (correlation, never causation); the pattern before vs after launch per platform; the cadence of official news. Dossiers are shown in STATUS.html (Mercato reale, competitors) and `calibrate` aggregates the B-tier winners' and losers' social files into the winners' recipe.

## 4e5d. `top_moves.py`, `predictions.py` and the STATUS.html real-market tab

`top_moves.py apply` (every run, before `status_page.py`) computes the 3 moves with most impact now from the open focus-group issues (severity × testers, SIMULATO), the missing steps of the real B-tier winners' recipe (winners% − losers%), the metro levers (points of P(≥1k), merged with the recipe step of the same thing) and the TODO deadlines; at most 2 from the same source. It writes them into `TODO.md` (section "⭐ Le 3 mosse a più impatto", or marks a matching open line "⭐ mossa top") and `calendar.md` (marks a matching open step, or adds a dated 👤/🤖 step in the phase "⭐ Mosse a più impatto" with the next free number), never duplicating, removing the old marks first, and writes `launch/_raw/top_moves.json`.

`predictions.py sync` records the predictions of every wave (wishlist and buy shares, SIMULATO), of the economic plan (wishlists at launch, copies year 1, [STIMA]) and of the real base rate into `launch/predictions.json`; `eval` closes them with real metrics (`real_wishlist_pct`, `real_buy_pct`, `wishlists`, `copies_30d/90d/year1` recorded with `metrics_track.py` / `wl_track.py`) and computes the accuracy over time (a hit = inside the range; points ±10 % or ±10 points for shares).

STATUS.html (`status_page.py`, with `market_page.py`) now opens with a **summary written from the data** (3-7 plain sentences: data freshness first when old, latest wave score and trend [SIMULATO], base rate for our tier and price [STIMA], metro band, open serious issues, the 3 moves, next deadline, prediction accuracy; a status that changes with the situation; the traffic light is a small badge). A sixth tab **Mercato reale** shows the freshness badge (and the update command when older than 30 days), the metro (bands, levers, weights in words, honest backtest), daily releases split by tier per week with the "X out of 20" sentence, outcomes per tier / price / genre with sample sizes, head vs long tail, breakouts against a typical B, the winners' recipe in time order, competitors and comparables measured at 30/90 days like the cohort (`market_tracker.py comps`) with their dossiers, the weekly KPI board against the "if… then" thresholds, predictions vs reality, and the manual-checks checklist from `ricerche-manuali.md`. Cards link the other tabs: Riepilogo "Dove siamo rispetto al mercato reale", Gioco e test "the reality check" (real recent B winners and losers as control capsules), Marketing e store "the winners' recipe with OUR status" (from TODO.md and calendar.md), Piano e soldi "sales scenarios from the real market" next to the calc_econ ones. The page stays offline (no external images or scripts).

## 4e6. Weekly and daily routine

```bash
# weekly (e.g. Monday): new release week, re-checks, market head, snapshots, calibration
python cohort_bench.py update --reference <header capsule>     # then grade the new sheets strictly, and:
python cohort_bench.py update --new-weeks 0
python market_tracker.py discover --top-sellers 25 --most-played 25 --breakouts 15
python market_tracker.py snapshot --steamspy
python market_tracker.py social --role comp --yt-quota 8000
python cohort_bench.py --dir ~/.game-launch-strategist/cohorts/_work/<new week> news
python cohort_bench.py calibrate && python cohort_bench.py metro
python cohort_bench.py score --features launch/prelaunch.json -o launch/_raw/metro.json --md launch/_raw/metro.md
python market_tracker.py comps                                 # comparables measured like the cohort
python steam_events.py fetch && python steam_events.py export-window --csv launch/window.csv && python steam_events.py deadlines --launch-dir launch --launch <date>
python promo_events.py fetch && python promo_events.py export-window --csv launch/window.csv && python promo_events.py deadlines --launch-dir launch --page <date> --demo <date> --launch <date>
python predictions.py sync && python top_moves.py apply && python status_page.py
# daily (2-4 times a day): player samples for daily peaks
python market_tracker.py snapshot --players-only
```

## 4f. `watchlist.py`: comparables and competitors over time

```bash
python watchlist.py add 1599600 728880 --role comp
python watchlist.py add 2000000 --role competitor
python watchlist.py snap [--csv launch/watchlist.csv]   # whenever you like, weekly is plenty
python watchlist.py report --launch 2027-03-01 --window-days 30 --md launch/watchlist-report.md
```
Append-only snapshots in `launch/watchlist.csv` (store details, review summary, current players from `ISteamUserStats/GetNumberOfCurrentPlayers/v1/`: public endpoints; a missing value means the endpoint answered with `result` other than 1). The report gives reviews and growth over 7 and 30 days, and alerts: a game going viral (gain well above its own median), a discount (with the date it was first seen), a release, a drop in % positive, a player spike, and **a competitor releasing within N days of your launch date** (ALARM). Wishlists and sales of other games are not public.

## 4f1. `project_scan.py`: understand the project in a brand-new chat

```bash
python project_scan.py --root . -o launch/_raw/project_scan.json --md launch/_raw/project_scan.md
```
Read-only. Looks from the working directory and in the folders above it. **Engine and version**: Unreal (`.uproject`: engine association, enabled plugins incl. the MCP plugin, Steam, maps and asset counts, `gds_ue.py`), Unity (`ProjectVersion.txt`: version, render pipeline, packages, MCP packages, build scenes, GameDeveloperSkill files), Godot (version, name, addons, scenes), GameMaker, Defold, Ren'Py, RPG Maker, Construct, Love2D, Phaser, three.js, Babylon, Bevy, raylib and a few more. **Documents**, ranked (`CLAUDE.md`, `AGENTS.md`, GDD, `GAME_CONTEXT.md`, `GAME_TASKS.md`, README, pitch, roadmap, TODO, notes) with their first heading; build folders (`Intermediate`, `Saved`, `Library`, `node_modules`…) are skipped. **What other skills left**: GDD locked or not, task counts, gates, scene lint, asset ledger, screenshot index, and this skill's own `launch/` state. **Steam and itch**: `steam_appid.txt`, vdf files, `.itch.toml`. **Media**: screenshots, capsules and videos in the usual folders. **Git**: branch, last commits, remote (credentials removed). **Tools**: executables on the PC (names only), MCP servers configured in the project (`.mcp.json` and similar: name, kind and command or host, **never env values or keys**) and whether the Unreal MCP default port answers on localhost (`--no-probe` to skip; the port is a documented default [DA VERIFICARE]). **Link with game-developer** (`dev_link`): `mode` with the same rule as game-developer's `gate_link.py detect` (`linked` = `launch/` and the strategist skill installed, `launch-only` = `launch/` without it, `solo` = no `launch/`), `dev_skill`, `dev_work`, `DECISIONI.md` (count, last D-NNN), `docs/design-review/` (map, screens, runs, `changes-since-wNN.md`, "aggiornata al gate NN"), gates with the machine-readable header (count, last number, date, status, title), gate plans `plan-wNN.md`, and the `contract:` version of `references/dev-link.md` against game-developer's `launch-link.md`. **Genre hints**: keyword counts, to confirm with the owner. What the *chat* can call (MCP tools, skills) is not on disk: the skill checks it from the session (`references/00a-bootstrap.md`).

## 4f2. `steamdb_assist.py`: SteamDB without scraping

```bash
python steamdb_assist.py links 1599600 728880 --md launch/_raw/steamdb_links.md
python steamdb_assist.py add 1599600 --followers 12,400 --wishlist-rank 850 --peak-24h 310 --peak-all 4,100 --lowest-price 8.99
python steamdb_assist.py show --md launch/steamdb-status.md
```
SteamDB has no public API and does not allow automated scraping, so the tool never contacts it (a test fails if it tries). `links` lists the pages to open and what to read; `add` records what you read, one row per game and date in `launch/steamdb.csv` (append-only); `show` gives the latest values and the change in followers. Useful for what public Steam endpoints do not give: followers, the wishlist **rank** (never the wishlist count of other games), player peaks with history, price history. URL patterns are [DA VERIFICARE].

## 4f3. `launch_window.py`: competitors around your launch date

```bash
python launch_window.py add --date 2027-03-09 --name "Big Co" --kind big_release --weight 5 --source "steamdb upcoming, read 2026-10-07"
python launch_window.py plan --launch 2027-03-01 --from 2027-01-15 --to 2027-05-31 --md launch/window.md -o launch/_raw/window.json
```
Reads `launch/watchlist.csv` (competitors followed with `watchlist.py`, release date from the store) and `launch/window.csv` (what you add: `competitor`, `big_release`, `festival`, `sale`, `holiday`, with weight 1-5, source and note). Each week gets a crowding score: the weights of the items near it, discounted by distance (that week 1.0, one week away 0.5, two weeks 0.25). The report ranks the candidate weeks, lists the 5 quietest, and says whether your week is free, average or crowded and what weighs on it. Items without a usable date (for example "Q1 2027") are listed as not counted. **It only knows what is in the list**: public Steam data does not list every upcoming game, so a free week here is not a free week in the world, and the score is a heuristic for comparing weeks [OPINIONE], not a forecast.

## 4f4. `steam_events.py`: Steam's own event calendar

```bash
python steam_events.py fetch                                  # -> ~/.game-launch-strategist/steam_events.json (live page, else the curated fallback)
python steam_events.py list --from 2026-10-01 --to 2027-06-30
python steam_events.py export-window --csv launch/window.csv  # weekly rows, kind sale / festival; replaces only its own rows
python steam_events.py deadlines --launch-dir launch --launch 2027-05-13 [--next-fest nextfest_feb_2027] [--tags "Simulation"] [--local-coop yes]
```
Source: https://partner.steamgames.com/doc/marketing/upcoming_events (public, no login) plus the Next Fest edition pages (registration deadline and milestones). Themed-fest pages answered "Sorry, an error occurred" to anonymous reads on 2026-10-17, so their registration deadline is estimated as about 6 weeks before the start (Valve's general rule on the themed_sales page) and labelled [DA VERIFICARE]. When the main page fails or its layout changes, `scripts/research/data/steam_events_fallback.json` (hand-curated, with `read_on`) is used and the output says so; unpublished dates stay null with a `pattern`. `deadlines` picks the last Next Fest that ends before your launch (registration still open, start at least 3 weeks away), matches themed fests against your store tags (`launch/store_kit.json` + `--tags`; Couch Co-Op only with `--local-coop yes`), warns when the launch falls inside a seasonal sale or Next Fest (ALARM) or too late for the next sale (30-day release cooldown), writes `launch/steam-events.md`, `launch/_raw/steam_events_deadlines.json` (read by `top_moves.py`: "register for fest X by Y" within 45 days) and, without duplicates, the steps in `calendar.md` (phase "📆 Eventi Steam") and `TODO.md`. `launch_window.py plan` adds the same events by itself (`--no-steam-events` to leave them out). Weights [OPINIONE]: seasonal sale 4, Next Fest 4, themed fest 1. Tested offline with synthetic fixtures (`tests/test_steam_events.py`); run live on 2026-10-17 (24 events).

## 4f5. `promo_events.py`: online showcases and festivals outside Steam's own calendar

```bash
python promo_events.py fetch                                   # -> ~/.game-launch-strategist/promo_events.json (curated file + deadlines re-read where a page prints one)
python promo_events.py list --online-only [--kind showcase|steam_fest_3rd|itch|reddit_recurring|stream|newsletter|italian]
python promo_events.py match --launch-dir launch --page 2026-10-31 --itch 2026-11-10 --demo 2026-12-20 --launch 2027-05-13 [--tags "Cozy"] [--all]
python promo_events.py export-window --csv launch/window.csv   # dated online events as kind festival; never twice with steam_events.py rows
python promo_events.py deadlines --launch-dir launch --page ... --demo ... --launch ... [--max 12] [--md launch/eventi-online.md] [--replace-todo "festival di terzi"]
```
Source: `scripts/research/data/promo_events_fallback.json`, hand-curated from the organisers' pages and Zukowski's festival list (https://howtomarketagame.com/festivals/), every item with URL and `read_on`. Each item has a kind, online or physical, cost, requirements (`steam_page`, `itch_page`, `demo`, `build`, `trailer`, `unreleased`, `released`, `discount`), the stages it accepts (`coming_soon`, `demo`, `ea`, `released`), theme words (`match`, `exclude`, `requires_fit`; `fit: any` for general showcases), `reach_tier` (alta / media / piccola but reliable), `odds` for a small unknown team (bassa / media / alta) with `odds_why` (selectivity, games shown, fees, past line-ups), `next_step`, dated `editions` (only with a source) and a `pattern` with the usual months (`event_months`, `open_month`, `close_month`). Undated windows become reminders at the usual opening month, with the end of the usual closing month as an estimate, always labelled [DA VERIFICARE] / [STIMA]: no day is invented. `fetch` re-reads the `deadline_page` of each item and keeps a date only when a single future date follows a deadline word (status `LETTURA_AUTO`, "to confirm"); unreadable pages leave the curated data. Value score [OPINIONE] = reach (3/2/1) × odds (1/2/3) × fit (2 theme, 1 general), 1-18; priority alta ≥ 6, media ≥ 4; tier "fattibile" when odds are media/alta, "tentativo" (long shot) when bassa. Team-restricted events need `--eligible key` or `--country IT`. `deadlines` plans at most `--max` applications (default 12) in the next 12 months by value, with 2 slots reserved for long shots (odds bassa, score ≥ 3, one edition per show), plus up to 4 recurring habits; each step carries `[id promo:...]` so later runs never duplicate it, and a hand-written step naming the event and a date is respected. It writes `launch/_raw/promo_events_deadlines.json` (top_moves.py: the nearest feasible application with priority alta, 40 points within 21 days, 30 within 45) and the Markdown report (ranked tiers "fattibili" / "vale un tentativo", month by month, habits, discarded with the reason, optional physical events). Tested offline (`tests/test_promo_events.py`, synthetic `tests/fixtures/promo_events_sample.json`).

## 4g. `plan_steps.py`: the step-by-step calendar

Reads the `## ✅ Passi in ordine` section of `launch/calendar.md`: `### FASE n — title` headings and numbered steps `N. [ ] 👤 text · 📅 AAAA-MM-GG` (owner 👤 you, 🤖 Claude, 👤+🤖 together; indented lines are notes).

```bash
python plan_steps.py next --owner me          # what is next for you, overdue first
python plan_steps.py done 2 3                 # tick steps (idempotent); undo unticks
python plan_steps.py summary                  # progress per phase
python plan_steps.py check                    # duplicate numbers, missing owner, user steps without a date...
```

## 4h. `store_kit.py`: copy-ready Steam and itch.io pages

One source, `launch/store_kit.json` (shape in the script header): fields with declared character limits, the long description as blocks with **media slots that say what goes where** (which GIF, which screenshot, file, alt), ordered tags with the reason, tags to avoid, screenshots in order, capsules with sizes, trailer, settings to fill in, and a pre-publish checklist, for both platforms.

```bash
python store_kit.py check launch/store_kit.json
python store_kit.py render launch/store_kit.json --md launch/store_kit.md
python store_kit.py export launch/store_kit.json --dir launch/store_kit
```
`check` verifies required fields, characters against the limits written in the file (with their verification date: limits are never hard-coded), tag count and duplicates, screenshot order, slots without a description, leftover placeholders. The HTML status page shows the same data with a Copy button on every field.

- **Early Access** (`steam.early_access`): the six questions of Steam's EA questionnaire (keys `why`, `duration`, `full_vs_ea`, `current_state`, `pricing`, `community`; names read on partner.steamgames.com/doc/store/earlyaccess on 2026-10-09, re-check them and write `verified_on`). Empty answers are errors; above 1,200 characters (readability, Valve declares no limit) or a limit in `limits` is flagged; sentences that sound like promises of dates or features are warned (Valve rule); the long description must say "Early Access". Rendered, exported (`steam_early_access_<key>.txt`) and shown in STATUS.html with Copy buttons.
- **Accessibility** (`accessibility`: `intro` + `features` [{label, value}], Steam and itch): a pasteable list (BBCode / Markdown), exported as `<platform>_accessibility.txt` and shown in STATUS.html.
- **Live pages**: `freshness(launch_dir)` compares `store_kit.json` (`"updated"`, else the file date) with the latest decision heading in `00-intenzioni.md`, the latest wave and the latest `../docs/gates/*.md`; `check` prints "aggiornate al <date>" or "DA AGGIORNARE", STATUS.html shows it in the store tab and as an alert. Rule: Claude updates the kit after every decision, gate or wave that changes what the game is or promises.

## 4i. `metrics_track.py`: metrics and "if... then" plans

```bash
python metrics_track.py add --metric itch_views --value 412 --note "after the Reddit post"
python metrics_track.py status --md launch/metrics-status.md
python metrics_track.py check          # validate launch/_raw/contingencies.json
python metrics_track.py catalog        # usual metric names and where each number comes from
```
You record numbers (itch views and downloads, Discord members, demo players and median playtime, test sessions, reviews, refund rate...) in `launch/metrics.csv`; wishlists are read from `launch/wishlists.csv` automatically. `contingencies.json` holds scenarios (shape in the script header): signals (`level`, `gain`, `avg`, `drop`, `ratio` with window and threshold), start date, severity, diagnosis in order, actions from the cheapest, a decision and where the threshold comes from. `status` marks each scenario Triggered / Ok / No data / Not yet active; **exit code 2 if an ALARM scenario triggered**. Thresholds are opinions unless the scenario cites a benchmark.

## 4j. `calc_econ.py`: light economic plan

```bash
python calc_econ.py --price 14.99 --costs 3500 --hours 600 --hourly 12 --partners 2 \
    --wishlists 3000,8000,20000 --conv 0.10,0.20,0.30 --md launch/03-pricing-calc.md -o launch/_raw/econ.json
```
`net per copy = price x (1 - avg_discount) x (1 - vat_share) x (1 - refund) x (1 - steam_cut) x (1 - local_tax)`; break-even copies = total costs / net (cash costs, and cash costs plus time x hourly rate); wishlists needed at each conversion; three scenarios (copies = wishlists x conversion) with gross, net, profit (cash and with time), per partner, multiple of break-even; sensitivity (price -20% / +20%, double refunds). Defaults (steam-cut 0.30, vat-share 0.10, refund 0.06, avg-discount 0.15, local-tax 0) are **inputs to verify**, not facts; percentages above 1 are read as percent. `--config file.json` takes the same keys.

Early Access (optional): `--ea-price P [--full-price Q] [--ea-first-month 0.35] [--full-vs-ea 0.40]` adds a section "Accesso anticipato (Early Access) e poi 1.0": net per copy at the EA and 1.0 price, break-even at the EA price, and per scenario the net of the EA launch month and of the 1.0 launch month (default 40 % of the EA month, GameDiscoverCo Dec 2025 median, [DA VERIFICARE]). Off unless `--ea-price` is given. Rules and criteria in `references/02-audit-platform-pricing.md`.

## 4k. `wl_track.py`: wishlist tracker

Steam does not publish wishlists: type the total from Steamworks once a week.

```bash
python wl_track.py add --wishlists 1840 --followers 310 --note "Reddit post" --csv launch/wishlists.csv
python wl_track.py plan --launch 2027-03-01 --start 2026-10-01 --econ launch/_raw/econ.json \
    --tripwire "2026-12-01:1500:8 weeks after the page:cut paid ads" --event "2026-11-17:Next Fest" -o launch/_raw/wl_plan.json
python wl_track.py status --md launch/wishlist-status.md --json launch/_raw/wl_status.json
```
`status` reports current total, 1-week and 4-week velocity, position against the linear path of each scenario, wishlists per week still needed, tripwires (OK / ALARM / PENDING / NO DATA), and alerts (slowdown, drops over two records, stale data, unexplained spikes). **Exit code 2 when a tripwire has fired.** Targets are interpolated linearly: a simplification, real curves are spiky.

## 4k0. Criticalities and Q&A: `criticita.py`, `qa.py`

`status_page.py` (section "Criticità, ondata per ondata") and `report_html.py` (inside "Critiche e ondate") rebuild the criticalities at every run from `launch/fg/waves/wNN-*.json` (the files `fg_waves.py` reads). Waves of the two stages (`stage`: beta / full) are kept apart. Buttons: **one per wave** (every issue with severity, share of testers, change against the previous wave, status, gate, what to do; then the issues resolved in that wave with the fix from `fixes`), **Per cancello** (which issues belong to which gate 0/A/B/C, born in which wave, open or resolved) and **Evoluzione** (stacked chart already present / new / resolved, and an issue × wave heat table with sparklines). Status against the previous wave: new, persistent, rising or falling (more than 10 points, the noise level of `fg_waves.py delta`), back, resolved. Add optional `"gate"` and `"area"` to each issue of the wave file. Criticalities from other sources go in `launch/criticita.csv`:

```bash
python criticita.py add --key tester-lost --label "External testers get lost at the menu" --severity alta --source playtest --gate B --opened 2027-01-10 --note "5 of 20"
python criticita.py close tester-lost --date 2027-01-20     # list shows them all
```
`status.json` → `critiques_by_wave` (hand-written waves) is still read, for waves without a file. The section "Domande e risposte" has the owner's questions (`qa.py add --q … --a … --topic Cancelli --wave 2 --gate B`, or `status.json` → `qa`; the same question is updated, not duplicated), frequent questions answered from today's data (verdict and why, what to do now, what changed since the last wave, worst open criticalities, can I pay Steam Direct, when to launch, copies to break even, wishlists, what if it goes badly, does the full game hold) and suggested questions drawn from the state of the project, with a search box and topic filter. Neither section appears for the `publisher` audience.

## 4k1. Plain words and links: `glossary.py`, `md_enrich.py`

HTML pages (`status_page.py`, `report_html.py`) pass every section through `glossary.py`: the first time a technical term appears in a section (wishlist, gate, ICE, tripwire, break-even, percentile, median, hook, capsule, Next Fest, comparables, pre-mortem, focus group, wave, creator, refund… about 40 terms) it gets a one-sentence explanation in simple Italian, shown on hover, keyboard focus or tap; a mention of something that has its own section (creators, economy, gates, window, SteamDB, steps, store pages, full game, TODO…) links to that section, once per section and never to the section you are in; the page ends with a glossary of only the terms used. Code, links, buttons, headings, summaries and charts are left alone, text stays escaped. The explanations carry no figures that go out of date.

```bash
python md_enrich.py --launch-dir launch          # --dry-run to preview, --no-glossary to skip the glossary
```
Markdown documents in `launch/` (and `launch/history/`): the first mention of a topic that has its own file becomes a relative link (creator → `06-creators.md`, calendar → `calendar.md`, pages → `store_kit.md`, pre-mortem → `05c-premortem.md`, window → `window.md`…), a back-ticked file name becomes a link, and `REPORT.md` ends with a glossary between markers (replaced at each run). Nothing is changed in code blocks, inline code, headings, existing links, URLs or HTML; running it twice changes nothing more.

## 4k2. Charts: `report_html.py`, `charts_export.py`, `charts.py`, `report_charts.py`

```bash
python report_html.py --launch-dir launch            # launch/REPORT.html
python charts_export.py --launch-dir launch          # launch/charts/*.svg and index.md
```
`report_charts.py` builds the charts from files already in `launch/` (pillars from `01-dev.md`, read by column header: name, grade with its qualifier, one-line reason, what to do, hours only when credible; tester verdicts, latest-wave indicators incl. `would_buy`, criticisms from `fg/`; genre by year, price band, demo, your percentiles, comparables and trailer length from `_raw/genre_bench.json`, `comps.csv`, `_raw/store_pages.json`; complaint and praise themes and your features from `_raw/corpus.json`, with "your game" from `05b-critiche-reali.md` and tester shares from the latest beta / full-game wave; price-to-net, scenarios against break-even, sensitivity from `_raw/econ.json`; crowding per week from `_raw/window.json`; steps by phase from `calendar.md`; creators from `creators.csv`; gaps from `status.json`). A group whose source is missing is not drawn. `report_html.py` places each group next to the report section it belongs to (groups that match nothing go to a block at the top), `status_page.py` puts each group in its tab (the publisher audience gets only focus group, market, reviews and launch window), `charts_export.py` writes standalone light-theme SVGs. Every chart follows the light/dark theme, has a hover tooltip, a legend when there are two or more series, a one-line "what to read" and a table view. No network, no scripts from outside. Checked in Chromium at desktop and 390 px, light and dark, no horizontal overflow and no console errors.

## 4l. `status_page.py`: status page for the owner, partners or a publisher

**2026-10 update.** Seven tabs: a **Calendario** tab sits between Piano e soldi and Mercato reale (`calendar_view.py`): month grids from the current month (or the oldest overdue item) to the launch with every dated item — steps and dated table rows of `calendar.md` (struck rows skipped, "ogni lunedì dal…" kept as recurring), dated `TODO.md` lines that are not already a step, Next Fest / themed fests / sales / Valve deadlines (`_raw/steam_events_deadlines.json`), showcase application deadlines and air dates (`_raw/promo_events_deadlines.json`), waves already run (`fg/timeline.csv`), the launch and the roadmap milestones — coloured by owner (👤 / 🤖 / both / event), overdue in red, today ringed; click a day for a side panel (details, links, "open the step" link to `#step-N`), hover for a preview, month navigation, owner filter, a 14-day agenda and an "In ritardo" strip. Data travel as JSON inside `<script type="application/json">` with `<`, `>`, `&` escaped; item HTML is built escaped on the Python side. The **Roadmap** (`status.json` → `roadmap`, or guessed from the steps by keywords when missing) is drawn on top of Riepilogo (proportional rail with today + one card per milestone: date, "tra N giorni", what happens, what it needs, done / next / later / late) and, compact, on top of Calendario. The header shows the generation date ("Aggiornato il …") and the analysis date of `status.json` apart. The hero adds **"Cosa manca per passare al livello successivo"** computed from the same rules as the verdict (wave score vs threshold, open high-severity issues, metro P(≥1k) vs 25 % with the top positive levers, overdue steps, stale data, prediction accuracy). Every URL in text (TODO notes, sources, "[FATTO https://…]") becomes a short link (`weblinks.py`, domain + path, new tab), never inside code, attributes or scripts. Tool-written step notes (promo/steam events) are shown as chips (value, "serve", deadline, link), a one-line "→ next step" and collapsible details. Tests: `tests/test_calendar_links.py`.

Reads files already in `launch/` (`status.json`, `issue_status.json`, `calendar.md` with its steps, `TODO.md`, `store_kit.json`, `_raw/contingencies.json` + `metrics.csv`, `fg/timeline.csv` and the wave files, `05b-critiche-reali.md`, `_raw/corpus.json`, `wishlists.csv` + `_raw/wl_plan.json`, `watchlist.csv`, `_raw/econ.json`, `01-dev.md`, the main reports) and writes one self-contained `launch/STATUS.html`. No network requests, no external scripts, light and dark theme, status icons always paired with a word, all text escaped. Everything the owner reads is in plain Italian.

**Layout.** A wide page (max 1400 px, side padding `clamp(16px,3vw,40px)`, still clean at 390 px with tables scrolling inside their card, never the page) with a sticky bar of **five tabs** (WAI-ARIA tablist, arrow keys, last tab remembered in `localStorage` inside try/catch, links to a section in another tab switch tab first, print shows every tab):

| Tab | What is inside |
|---|---|
| Riepilogo | verdict with its 3 risks (each with the owner's decision) and the gates, "Adesso" (your turn / Claude's turn), key numbers (focus-group score for beta and full game kept apart, ceiling and headroom), alerts, wishlist and wave trends (beta line, full game as grey diamonds, ceiling as green diamonds), decision profile |
| Gioco e test | pillars by NAME (grade badge, one-line reason, what to do, hours only when `01-dev.md` gives a credible per-pillar figure), criticalities wave by wave, focus-group charts, one card per wave (beta / full game labelled, score vs threshold, change vs the previous wave of the same kind, ceiling and headroom, issues still to do), real reviews with "your game", beta vs full game, the documents of this area |
| Marketing e store | copy-ready Steam and itch.io pages (a Copy button on every field, dashed boxes where photos and GIFs go), creators table and chart, positioning / clips / store copy / creators / community documents |
| Piano e soldi | step-by-step calendar (progress, filter by owner, overdue), **live TODO**, gates, fixed dates, economics, "if... then" scenarios with live status, launch window, competitors, SteamDB numbers, market and comparables, platform / pricing / pre-mortem / contingency documents |
| Documenti | the full report and the remaining documents, Q&A, glossary of the words used |

**Live issue state: `launch/issue_status.json`.** The owner's decision on every issue key of the waves: `{"key": {"status": "...", "note": "...", "aliases": ["regex"]}}`, keys starting with `_` are comments. `aperto`, `in_lavorazione`, `da_verificare` = still **to do now**; `risolto`, `pianificato`, `accettato`, `non_problema` = **already decided**. An issue the testers raise that is not in the file shows as "Da decidere" (to do now). Wherever issues appear (criticalities per wave, per gate, evolution matrix, the "issues to tackle now" chart, the wave cards, verdict risks, rows of document tables such as the convergence matrix, real-review themes, the Q&A) the page shows the decision as a badge with an icon and the note, and splits "Da fare adesso" from "Già deciso" (collapsed). `status.json` -> `issue_aliases` `{key: [regex]}` (or `aliases` in the owner's file) links texts that name an issue with other words; a verdict risk may also be `{"text": ..., "issues": [keys]}`. Claude updates the file after every owner decision and every wave (`references/06-synthesis-output.md`).

**Waves.** Beta and full-game waves are never compared with each other: the kind comes from `"stage"`, else the file name (`-beta` / `-full`), else the label (`fg_waves.infer_stage`). The criticalities card opens on the latest beta wave.

**Real reviews: "does your game have it?"** For each complaint / praise theme the chart tooltip and a visible table say what `05b-critiche-reali.md` concluded about OUR game (`[SÌ]`, `[A RISCHIO] (alto)`, `[NO] per la beta`, `[NON VALUTABILE]`, `[IN PARTE]`/`[PARZIALE]`), the share of simulated testers who raised the linked issues in the latest beta and full-game wave (`theme_labels.THEME_ISSUES`, extendable per project in `launch/_raw/theme_issues.json`), and the owner's decision on them; e.g. "Il tuo gioco: a rischio (alto) · lo pensano 13% dei tester (beta), 2% (completo)".

**Live TODO.** `TODO.md` is parsed by `todo_track.py`: progress, open vs done per section (done collapsed), overdue, and a "Da aggiornare" warning when the file is older than the latest wave, `issue_status.json` or `calendar.md`.

`--audience private|partner|publisher` (default private) controls what is included; `--include`, `--exclude`, `--hide` refine it (publisher: no steps, economics, TODO, contingencies, competitors, creators, decision profile, full-game analysis, criticalities or Q&A). When there are no wave `.json` files the per-wave Markdown reports are shown instead. The tool never publishes anything: sharing the page is the user's decision.

## 4l1. `todo_track.py`: TODO.md kept alive

Lines `- [ ] 👤 **Action** — 2026-10-20 — 2 h — dependencies — metric` (`|` also works), sections are `## ` headings, 👤 owner / 🤖 Claude / 👤+🤖 both.
```
todo_track.py --file launch/TODO.md list [--open|--done] [--section TEXT]
todo_track.py --file launch/TODO.md stats
todo_track.py --file launch/TODO.md done "words of the line" [--by me|claude|both] [--note "gate 48"]   # or "#12"
todo_track.py --file launch/TODO.md reopen "words of the line"
todo_track.py --file launch/TODO.md drop "words of the line" --why "owner decision ..."   # made obsolete: [-], kept, not counted, shown under "Superate"
todo_track.py --file launch/TODO.md add --section "Dev e pilastri" --text "🤖 **Fix X** — 2026-10-20 — 2 h — nessuna — 0 errori"
```
`done` turns `[ ]` into `[x]`, appends "· fatto il DATE (da 🤖, note)" and refreshes `Aggiornato:`; a pattern matching zero or several lines changes nothing and prints the candidates. Rule of the skill: run it after every gate, wave and owner decision.

Link with game-developer (`references/dev-link.md` §4-5): development lines carry `(P-wNN-n, key:<key>[,<key>])` in the action text (parsed as `pid`, `keys`, `approved`); a pattern that is exactly a proposal ID finds the line that owns it, not lines that cite it.
```
todo_track.py --file launch/TODO.md approve "P-w10-1" --date 2026-10-19 [--status-file launch/issue_status.json]
todo_track.py --file launch/TODO.md sync-decisions --decisions DECISIONI.md [--intents launch/00-intenzioni.md] [--write]
```
`approve` writes `ok del proprietario DATE` in the Dependencies field (replacing "nessuna", or after a ";", or updating an older date) and, with `--status-file`, moves the line's keys to `in_lavorazione` with a note; owner decisions (accettato, non_problema, pianificato, sospeso) and `risolto` keys are not touched, and neither are the developer's `gate` / `resolved` fields. `sync-decisions` lists the `D-NNN` rows of `DECISIONI.md` cited neither in TODO.md nor in `00-intenzioni.md` (rows whose source is `launch/…` are not copied back) and with `--write` appends them under "Decisioni prese" as `- **Area:** decision (fonte: DECISIONI.md D-NNN, date)`. `DECISIONI.md` is never written.

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
| `cohort_bench.py` | Tested offline (`tests/test_cohort_bench.py`, fixture `tests/fixtures/cohort_bench.json`: per-day counts, binary search of the window, resume, every junk rule, HTML sheet fallback, grades kept, Boxleiter ranges, subsets). Run live on 2026-10-13 (14-day volume, 636-game cohort 2026-07-15..21, ffmpeg sheets). |
| `cohort_bench.py metro` / `score` / `news` / `dossier`, `top_moves.py`, `predictions.py`, `market_page.py` + `status_page.py` | Tested offline (`tests/test_metro_moves_page.py`: planted signal found by the out-of-time backtest, monotonic probabilities, levers, one-week case refused; 3 moves written into TODO.md and calendar.md twice without duplicates and with a valid calendar; predictions sync without duplicates and hit/miss; dossier with TikTok oEmbed and date from the id, accounts from the page only, CDN assets filtered, spikes; STATUS.html summary with old data said first, the Mercato reale tab and the four cards). Run live on 2026-10-13 on Buffet Panic. |
| `cohort_bench.py update` / `calibrate`, `market_tracker.py`, `entity_match.py` | Tested offline (`tests/test_market_calibrate.py`, `tests/test_entity_match.py`: keys loaded by name and never printed or written, dataset re-checks at 30/90/180 days, calibration and base rates, calc_econ scenarios, snapshot schedule, estimates, social matching, manual file, RSS parsing, marketing patterns; matching precision on two hand-labelled real samples). Run live on 2026-10-13: dataset seeded with the 592-game cohort, calibration written, discover (top sellers, most played, breakouts), snapshots, players, social for 3 comps (YouTube via key; Reddit anonymous RSS answered 429), timeline, manual checks. |
| `reddit_rules.py` anonymous | `403 Blocked` (expected: OAuth needed). |
| `yt_research.py --backend api` | Not tested (no `YOUTUBE_API_KEY`). |
| `steam_tags.py` | Tested offline (the reported Roguelite / Rogue-lite case, hyphen variants, typos, built-in fallback, unverifiable lists). **Not run against live SteamSpy.** |
| `steam_events.py` | Tested offline (`tests/test_steam_events.py`: sales, fests across the new year, Next Fest editions, edition milestones, fallback on a broken or missing page, merge, weekly window rows, hand rows kept, launch_window auto feed, deadlines, warnings, calendar/TODO written once, top_moves fest move, cp1252). Run live on 2026-10-17. |
| `promo_events.py` | Tested offline (`tests/test_promo_events.py`: curated file format incl. the real fallback, occurrences from editions and usual months with no invented day, stage / requirement / genre checks, value score and tiers, cap of applications and long shots, fetch deadline parsing and failures, window.csv without duplicates with hand rows or Steam's events, calendar/TODO once with stable ids, generic TODO line superseded, report, top_moves promo move, cp1252). Curated on 2026-10-17. |
| `launch_window.py`, `charts.py`, `report_charts.py`, `report_html.py`, `charts_export.py` | Tested offline (week scores checked by hand: same week 1.0, one week 0.5, two weeks 0.25; ranking, verdicts, bad rows, cp1252 console; every chart group from a synthetic `launch/` with hostile text, REPORT.html sections, standalone SVGs parsed as XML). Rendered and inspected in Chromium (desktop, phone, dark). |
| `criticita.py`, `qa.py` | Tested offline on a three-wave life cycle (new, falling, resolved with its fix, back, rising), gates, evolution matrix, the register CLI, the owner's `status.json` formats, Q&A CLI (same question updated), answers computed from data, links that all land on an existing id, tags balanced, publisher audience, escaping. Rendered and checked in Chromium. |
| `glossary.py`, `md_enrich.py` | Tested offline: tooltip once per section, skipped zones (code, links, headings, summaries, SVG), entities and hostile text kept escaped, no link to the section you are in, every internal link lands on an existing id, tags stay balanced, explanations short and without figures; Markdown links relative from subfolders, idempotent, glossary replaced not duplicated, cp1252 console. Checked in Chromium: tooltip on hover and focus, clamped inside a 390 px screen, link jumps to the section. |
| `project_scan.py` | Tested offline on synthetic Unreal, Unity (GameDeveloperSkill), Godot and web projects: version and name extraction, document ranking, build folders skipped, artifacts of other skills, parent-folder lookup, **secrets in MCP configs and credentials in the git remote never reach the output**, cp1252 console. Also run on a real skill repository (no engine found, as it should). Not run on a real Unreal or Unity project. |
| `steamdb_assist.py` | Tested offline (links, parsing of `12,400` / `12.9K`, append-only, delta, no network access). Never contacts steamdb.info by design. |
| `review_corpus.py`, `store_bench.py`, `genre_bench.py`, `watchlist.py`, `plan_steps.py`, `store_kit.py`, `metrics_track.py`, `calc_econ.py`, `wl_track.py`, `status_page.py` | Tested offline in `tests/` (canned API-shaped answers; real HLS and DASH trailers generated with `ffmpeg` and served locally (duration, cuts, frames, no MP4 present); a console test under cp1252 for the emoji output; arithmetic of the economic plan checked independently; the status page rendered in Chromium at desktop and 390 px width: no horizontal overflow, no script errors, hostile text stays inert). `plan_steps.py` was also checked on a real step list written by the project owner (30 steps, 6 phases). **Not yet run against the live Steam services.** |
| `wave_kit.py` | Tested offline (`tests/test_wave_kit.py`: seven templates, never overwrite, template-only sections fail, a filled Godot-like wave passes, each required item fails on its own, extra questions found in the JSON keys, limite-beta only warns, `--json`, exit codes, cp1252 console). Run on the real wave 9 of Buffet Panic on 2026-10-18: all ✅. |
| `steam_reviews.py`, `steam_discover.py`, `roster.py`, `fg_waves.py` | Tested **offline** against canned responses shaped like the documented APIs (paging, duplicate and cursor handling, filters, day-range cap, early stop on recent sort, theme tally, CSV output, tag ranking, roster determinism, stable jury and append-only behaviour, wave validation, metrics, delta and timeline on synthetic waves). **Not yet run against the live Steam endpoints**: do a first run with one app id and check the output before relying on it. |
