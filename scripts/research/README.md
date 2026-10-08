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
| `yt_research.py` | Search recent videos, group by channel, add subscribers, verify URLs | 8 |
| `social_verify.py` | Verify TikTok / YouTube (Shorts) / Instagram / Twitch URLs with official endpoints | 8 |
| `reddit_rules.py` | Subreddit rules, subscribers, self-promotion flags | 9 |
| `build_creators.py` | Merge everything into a prioritised creators CSV | 8 |
| `review_corpus.py` | Many real reviews of the comparables AND of the genre: punished/rewarded themes, what they say about your game's features | 2, 7 |
| `store_bench.py` | Store page and trailer analysis of the comparables (description, GIFs, trailer length, cuts, frames) vs how they performed | 2, 6, 6B |
| `genre_bench.py` | Genre benchmarks at runtime from public data: distributions, cohorts by year, price bands, demo, visibility bar, your numbers | 2, 5 |
| `project_scan.py` | Cold start: reads the project from disk (engine and version, ranked context documents, what other skills left, Steam, media, git, tools, configured MCP servers) | B |
| `steamdb_assist.py` | SteamDB as a manual lookup: links to open and an append-only record of followers, wishlist rank, player peaks, lowest price (no scraping) | 2, 7C |
| `watchlist.py` | Comparables and competitors over time: snapshots, growth, discounts, releases, collision with your window | 2, 7C |
| `plan_steps.py` | Step-by-step calendar: who does what (👤 / 🤖), due dates, ticking, summary, format check | 4 |
| `store_kit.py` | Copy-ready Steam and itch.io pages from `store_kit.json`: check, written sheet, files to paste | 6B |
| `metrics_track.py` | Metrics you record and "if... then" contingency scenarios with thresholds, diagnosis and actions | 7C |
| `calc_econ.py` | Light economic plan: gross to net, break-even, three scenarios, sensitivity | 5 |
| `wl_track.py` | Weekly wishlist records vs scenarios and pre-mortem tripwires, with alarms | 4, 7B |
| `launch_window.py` | Competitor calendar for your launch window: weekly crowding score, quietest weeks, where your date stands | 4, 7C |
| `charts.py`, `report_charts.py` | Inline SVG charts (bars, columns, stacked, bullets) and the chart groups built from the files in `launch/` | 11 |
| `glossary.py` | Plain-Italian tooltips, links to the section that deals with the thing mentioned, and a glossary, for the HTML pages | 11 |
| `md_enrich.py` | Links between the Markdown documents of `launch/` and a plain-Italian glossary at the end of `REPORT.md` | 11 |
| `report_html.py` | `REPORT.md` as one illustrated HTML page: charts next to each section | 11 |
| `charts_export.py` | Every report chart as a standalone `.svg` (for Markdown reports) | 11 |
| `status_page.py` | One self-contained HTML status page for partners or a publisher | 11 |
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

The simulated panel judges the game; this tool does the arithmetic, so scores and trends are reproducible. A *wave* is one run of the same roster on one state of the game, stored as `launch/fg/waves/wNN-YYYY-MM-DD.json` (schema in the script's header: per tester `verdict` WISHLIST/SALDI/IGNORO/REFUND, `click`, `pitch_ok`, `issues`; a list of issues with stable keys, severity and recommendation; optional `controls` and, from wave 2, `fixes`).

```bash
python fg_waves.py metrics launch/fg/waves/w01-2026-10-06.json --roster launch/fg/roster.json -o launch/fg/waves/w01-metrics.md
python fg_waves.py delta launch/fg/waves/w01-2026-10-06.json launch/fg/waves/w02-2026-10-27.json --roster launch/fg/roster.json -o launch/fg/waves/w02-delta.md
python fg_waves.py timeline launch/fg/waves --roster launch/fg/roster.json -o launch/fg/timeline.md --csv launch/fg/timeline.csv
```

- `metrics`: validates (tester IDs against the roster, verdict values, duplicates, issue keys), then computes verdict counts, the wishlist score `((W*1.0)+(S*0.4)-(I*0.2)-(R*0.8))/N*100` (range -80..100, not a percentage), A vs B score and gap (flagged above 15), first-glance click, pitch comprehension, and the issue matrix ranked by frequency x severity. Gate A threshold: `--gate N`, else 80% of the success control (min 30), else 35.
- `delta`: score on the **same testers only** (new IDs are listed but excluded from the like-for-like score), verdict movements, effect of each issue (RESOLVED / IMPROVED / WORSE / NEW / UNCHANGED, noise band `--noise`, default 10 points), fixes applied, per-tester changes with an empty "attributed cause" column.
- `timeline`: all waves in a folder (`wNN-*.json`) with score trend and sparkline, verdict shares, click, pitch, A/B scores, number of high-severity issues, top issue and Gate A status.

**Limits:** the panel is simulated with the same biases every time, so deltas are directional, not proof; differences of a few points are noise (with N = 54 a percentage carries roughly +-13 points of uncertainty). Confirm important changes with real testers.

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

## 4e. `genre_bench.py`: genre benchmarks from public data

```bash
python genre_bench.py --tag Roguelike --tag Cooking --enrich 80 --mine price=14.99 --mine reviews_per_year=500 --md genre_bench.md -o genre_bench.json
```
Takes the ~100 most reviewed games of the tag(s) (SteamSpy), enriches them with release date, price and demo from the Steam store (1 request each, `--enrich N`), and reports distributions (p25 / median / p75 / p90) of reviews, reviews per year, % positive, price and age; cohorts by release year (how crowded the genre is and how recent releases do); price bands; demo vs no demo; Spearman price vs reviews per year; the visibility bar; and with `--mine` the percentile of your own values. Built at run time from public data, nothing local to maintain.

**Limit, quote it every time:** the list holds the MOST REVIEWED games of the tag, so the numbers describe the successful tail, not the median game. Reviews per year is a proxy for sales.

## 4f. `watchlist.py`: comparables and competitors over time

```bash
python watchlist.py add 1599600 728880 --role comp
python watchlist.py add 2000000 --role competitor
python watchlist.py snap                      # whenever you like, weekly is plenty
python watchlist.py report --launch 2027-03-01 --window-days 30 --md launch/watchlist-report.md
```
Append-only snapshots in `launch/watchlist.csv` (store details, review summary, current players from `ISteamUserStats/GetNumberOfCurrentPlayers/v1/`: public endpoints; a missing value means the endpoint answered with `result` other than 1). The report gives reviews and growth over 7 and 30 days, and alerts: a game going viral (gain well above its own median), a discount (with the date it was first seen), a release, a drop in % positive, a player spike, and **a competitor releasing within N days of your launch date** (ALARM). Wishlists and sales of other games are not public.

## 4f1. `project_scan.py`: understand the project in a brand-new chat

```bash
python project_scan.py --root . -o launch/_raw/project_scan.json --md launch/_raw/project_scan.md
```
Read-only. Looks from the working directory and in the folders above it. **Engine and version**: Unreal (`.uproject`: engine association, enabled plugins incl. the MCP plugin, Steam, maps and asset counts, `gds_ue.py`), Unity (`ProjectVersion.txt`: version, render pipeline, packages, MCP packages, build scenes, GameDeveloperSkill files), Godot (version, name, addons, scenes), GameMaker, Defold, Ren'Py, RPG Maker, Construct, Love2D, Phaser, three.js, Babylon, Bevy, raylib and a few more. **Documents**, ranked (`CLAUDE.md`, `AGENTS.md`, GDD, `GAME_CONTEXT.md`, `GAME_TASKS.md`, README, pitch, roadmap, TODO, notes) with their first heading; build folders (`Intermediate`, `Saved`, `Library`, `node_modules`…) are skipped. **What other skills left**: GDD locked or not, task counts, gates, scene lint, asset ledger, screenshot index, and this skill's own `launch/` state. **Steam and itch**: `steam_appid.txt`, vdf files, `.itch.toml`. **Media**: screenshots, capsules and videos in the usual folders. **Git**: branch, last commits, remote (credentials removed). **Tools**: executables on the PC (names only), MCP servers configured in the project (`.mcp.json` and similar: name, kind and command or host, **never env values or keys**) and whether the Unreal MCP default port answers on localhost (`--no-probe` to skip; the port is a documented default [DA VERIFICARE]). **Genre hints**: keyword counts, to confirm with the owner. What the *chat* can call (MCP tools, skills) is not on disk: the skill checks it from the session (`references/00a-bootstrap.md`).

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

## 4k. `wl_track.py`: wishlist tracker

Steam does not publish wishlists: type the total from Steamworks once a week.

```bash
python wl_track.py add --wishlists 1840 --followers 310 --note "Reddit post" --csv launch/wishlists.csv
python wl_track.py plan --launch 2027-03-01 --start 2026-10-01 --econ launch/_raw/econ.json \
    --tripwire "2026-12-01:1500:8 weeks after the page:cut paid ads" --event "2026-11-17:Next Fest" -o launch/_raw/wl_plan.json
python wl_track.py status --md launch/wishlist-status.md --json launch/_raw/wl_status.json
```
`status` reports current total, 1-week and 4-week velocity, position against the linear path of each scenario, wishlists per week still needed, tripwires (OK / ALARM / PENDING / NO DATA), and alerts (slowdown, drops over two records, stale data, unexplained spikes). **Exit code 2 when a tripwire has fired.** Targets are interpolated linearly: a simplification, real curves are spiky.

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
`report_charts.py` builds the charts from files already in `launch/` (pillars from `01-dev.md`; tester verdicts, latest-wave indicators incl. `would_buy`, criticisms from `fg/`; genre by year, price band, demo, your percentiles, comparables and trailer length from `_raw/genre_bench.json`, `comps.csv`, `_raw/store_pages.json`; complaint and praise themes and your features from `_raw/corpus.json`; price-to-net, scenarios against break-even, sensitivity from `_raw/econ.json`; crowding per week from `_raw/window.json`; steps by phase from `calendar.md`; creators from `creators.csv`; gaps from `status.json`). A group whose source is missing is not drawn. `report_html.py` places each group next to the report section it belongs to (groups that match nothing go to a block at the top), `status_page.py` shows them in "Quadro d'insieme" (the publisher audience gets only focus group, market, reviews and launch window), `charts_export.py` writes standalone light-theme SVGs. Every chart follows the light/dark theme, has a hover tooltip, a legend when there are two or more series, a one-line "what to read" and a table view. No network, no scripts from outside. Checked in Chromium at desktop and 390 px, light and dark, no horizontal overflow and no console errors.

## 4l. `status_page.py`: status page for partners or a publisher

Reads files already in `launch/` (`status.json`, `calendar.md` with its steps, `store_kit.json`, `_raw/contingencies.json` + `metrics.csv`, `fg/timeline.csv`, `wishlists.csv` + `_raw/wl_plan.json`, `watchlist.csv`, `_raw/econ.json`, `TODO.md`, the main reports) and writes one self-contained `launch/STATUS.html`: verdict, decision profile (with "valutato come: beta / completo"), key numbers, alerts, a collapsible **creators table** from `creators.csv` (sorted A/B/C, hidden for `publisher`), a "Beta today and the full game" table when `status.json` carries `full_game`, **step-by-step calendar** (progress bar, "your turn now" and "Claude's turn" boxes, filter by owner, overdue flagged), charts with hover tooltips and a table view, gates, **copy-ready store pages with a Copy button on every field and dashed boxes marking where photos and GIFs go**, **"if... then" scenarios with live status**, competitors, TODOs, documents. No network requests, no external scripts, light and dark theme, readable on a phone, status icons always paired with a label, all text escaped. `--audience private|partner|publisher` (default private) controls what is included; `--include`, `--exclude`, `--hide` refine it. Beyond the sections above the page has a sticky index, the verdict with the gates at a glance, an "Adesso" box (your turn / Claude's turn), the launch-window table, the SteamDB numbers you recorded, per-wave focus-group reports and the extra documents (simulated and real critiques, clips, economic calculation). The tool never publishes anything: sharing the page is the user's decision.

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
| `steam_tags.py` | Tested offline (the reported Roguelite / Rogue-lite case, hyphen variants, typos, built-in fallback, unverifiable lists). **Not run against live SteamSpy.** |
| `launch_window.py`, `charts.py`, `report_charts.py`, `report_html.py`, `charts_export.py` | Tested offline (week scores checked by hand: same week 1.0, one week 0.5, two weeks 0.25; ranking, verdicts, bad rows, cp1252 console; every chart group from a synthetic `launch/` with hostile text, REPORT.html sections, standalone SVGs parsed as XML). Rendered and inspected in Chromium (desktop, phone, dark). |
| `glossary.py`, `md_enrich.py` | Tested offline: tooltip once per section, skipped zones (code, links, headings, summaries, SVG), entities and hostile text kept escaped, no link to the section you are in, every internal link lands on an existing id, tags stay balanced, explanations short and without figures; Markdown links relative from subfolders, idempotent, glossary replaced not duplicated, cp1252 console. Checked in Chromium: tooltip on hover and focus, clamped inside a 390 px screen, link jumps to the section. |
| `project_scan.py` | Tested offline on synthetic Unreal, Unity (GameDeveloperSkill), Godot and web projects: version and name extraction, document ranking, build folders skipped, artifacts of other skills, parent-folder lookup, **secrets in MCP configs and credentials in the git remote never reach the output**, cp1252 console. Also run on a real skill repository (no engine found, as it should). Not run on a real Unreal or Unity project. |
| `steamdb_assist.py` | Tested offline (links, parsing of `12,400` / `12.9K`, append-only, delta, no network access). Never contacts steamdb.info by design. |
| `review_corpus.py`, `store_bench.py`, `genre_bench.py`, `watchlist.py`, `plan_steps.py`, `store_kit.py`, `metrics_track.py`, `calc_econ.py`, `wl_track.py`, `status_page.py` | Tested offline in `tests/` (canned API-shaped answers; real HLS and DASH trailers generated with `ffmpeg` and served locally (duration, cuts, frames, no MP4 present); a console test under cp1252 for the emoji output; arithmetic of the economic plan checked independently; the status page rendered in Chromium at desktop and 390 px width: no horizontal overflow, no script errors, hostile text stays inert). `plan_steps.py` was also checked on a real step list written by the project owner (30 steps, 6 phases). **Not yet run against the live Steam services.** |
| `steam_reviews.py`, `steam_discover.py`, `roster.py`, `fg_waves.py` | Tested **offline** against canned responses shaped like the documented APIs (paging, duplicate and cursor handling, filters, day-range cap, early stop on recent sort, theme tally, CSV output, tag ranking, roster determinism, stable jury and append-only behaviour, wave validation, metrics, delta and timeline on synthetic waves). **Not yet run against the live Steam endpoints**: do a first run with one app id and check the output before relying on it. |
