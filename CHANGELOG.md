# Changelog

## 2026-11-03 (5): copy the login from the owner's normal browser (X blocks the dedicated one)

### Added
- `reach.py login <channel|tutti> --dal-mio-browser [--profilo ID]`: maps to Agent Reach's `login <ch> --import-existing` (cookies of that site only, read from the owner's Chrome/Edge through the OpenCLI Browser Bridge extension), then checks the channel. `tutti` = every channel with a browser login (twitter, instagram, reddit, facebook, xiaohongshu, linkedin, boss, xueqiu) plus tiktok.com (own import in the private Python, same code path); one Italian line each: copiato / nessun login trovato / errore. bilibili is explained (it reuses the login by itself). Never prints cookie values.
- The source profile is always chosen by the owner: it refuses to run (exit 5) without `browser use ID` or `--profilo ID`, even with a single connected profile; it prints the profile before copying and fails if that profile is not connected now.
- `reach.py browser profiles|use ID` (Italian output, `<== SCELTO` mark; the bridge only knows an id, shown in the extension popup) and `reach.py collega-browser` (steps: extension from the Web Store or unpacked from `~/.game-launch-strategist/reach/home/browser/extension`, only in the chosen profile; the folder is only replaced by an explicit extension upgrade, then press "Ricarica" in chrome://extensions). The bridge daemon only runs while the dedicated browser is open: the commands start it invisibly when it is off.
- `doctor`: rows have an `alt` field and the table adds `--dal-mio-browser` for every login channel that is not ready; `NEED_LOGIN` / `NOT_READY` hints and `setup` mention it.
- `tests/test_reach_browser.py`.

## 2026-11-03 (4): Agent Reach becomes an internal component of the skill

### Changed
- Agent Reach is no longer a global program (`uv tool install`, `agent-reach` on PATH). The installer builds a **private copy** with `scripts/research/reach_runtime.py`: release 1.6.1 pinned and checked by sha256, own Python environment (uv venv, or `python -m venv` without uv) in `~/.game-launch-strategist/reach/venv`, own state folder `.../reach/home` (browser profile and logins, sessions, config, OpenCLI, CloakBrowser), linked inside the skill as `tools/agent-reach` (gitignored, never committed). `install.mjs update` refreshes and repairs it; `install.mjs doctor` checks version, patches and link.
- `reach.py` runs only that copy (lookup: env `GLS_REACH_HOME` → `~/.game-launch-strategist/config.json` `reach.path` → `<skill>/tools/agent-reach` → default), never an `agent-reach` found on PATH. Every owner command is now a `reach.py` command: `install`, `login`, `logout`, `add`, `configure` (hidden input), `browser status|stop`, `doctor --live`, `setup`.
- Local patches applied by the installer to the installed copy, idempotent (`GLS-PATCH:<id>`): `home` (state folder from `AGENT_REACH_HOME`), `locale` (browser language from `REACH_BROWSER_LOCALE` or the system language, never a fixed zh-CN), `subs` (YouTube subtitles English first, then Italian), `embedded` (no global skill or links in other AIs, no self-update / self-uninstall).
- `fix-lang` no longer edits files: the language fix is in the installed copy; it checks the patch and sets the browser profile languages (kept for compatibility).
- Messages Agent Reach prints in Chinese are replaced by Italian ones (by error code) before they reach the owner.
- Migration: an existing `~/.agent-reach` is COPIED once into the private folder (profile, logins, state, OpenCLI, Chromium; caches and locks skipped; absolute paths rewritten; global skill links dropped; pip tools reinstalled privately). The old folder is never moved by the skill.

### Added
- `THIRD_PARTY_NOTICES.md` (Agent Reach: repository, version, sha256, licence, modifications).
- `tests/test_reach_runtime.py`: lookup order, never a global agent-reach, private environment, patches on LF/CRLF sources, sha256-checked install, migration by copy.

## 2026-11-03 (3): social login through the skill, Agent Reach browser in your language

### Added
- `reach.py login <channel>` (twitter, instagram, reddit, tiktok, ...): runs `fix-lang`, then Agent Reach's own `login`, then checks that channel (`--check` = only the check, `--lang`, `--no-wait`). tiktok = the X window, then open tiktok.com/login in the same window. The owner still types user and password himself.
- `reach.py fix-lang [--lang it-IT] [--stop]`: Agent Reach opens its dedicated browser with `locale="zh-CN"` written in `browser_watcher.py`. The value now comes from the env `REACH_BROWSER_LOCALE` (default: the system language, else en-US); backup `browser_watcher.py.orig`; idempotent. It also sets the browser profile languages (`Preferences`, backup `Preferences.gls-backup`) but only when the browser is not running; `--stop` closes it with `agent-reach browser stop`.
- The installer runs `fix-lang` after every install/update (`agent-reach update` puts the Chinese value back).

### Changed
- `reach.py setup`, the `next` column of `doctor`, error hints, SKILL.md, README, bootstrap and the installer footer now show `! python <installed path>/reach.py login <channel>` instead of `! agent-reach login ...`.

## 2026-11-03 (2): status colours, Reels and X in the plan, "why games flop" with reasons

### Changed
- One palette for the whole page: **to do = neutral grey, in progress = orange, done = green, red only for overdue and problems** (`status_page.py`, `marketing_glance.py`, `criticita.py`, `calendar_view.py`). The "Da fare" icon, the open-count badge on the tabs, the criticality owner statuses (aperto / da verificare / da decidere) and the channel pills are grey; owner chips (me / Claude / together) moved off orange and green to violet / blue / teal so they never read as a status.
- `social_content.py moments --from-registry launch/clips.json`: one moment per clip with its own hooks, caption and platforms. `plan` uses only a clip's own hooks when it has two or more, drops hashtags on X, and puts a clip only where it is made for. Reels and X are in the plan and in the Canali card (no longer "non usare").
- `social_content.py flopcheck`: an answer can be `true` / `false` or `{"status": "ok|fail|na", "why": one line, "proof": file, "action": what to do}`. `na` = not applicable yet (e.g. no trailer): left out of the risk, shown as "Non applicabile ancora". New `--launch launch/` reads store text, languages and release timing from the launch folder; the default `--page` (comparables) is no longer taken for the game's own page.
- STATUS.html "Perche' i giochi floppano": reason, proof and action per item; the saved result is recomputed when the answers file is newer; the social plan (all platforms, A/B hooks) is shown week by week.
- `top_moves.py`: failed flop items enter heaviest first, with the custom action; `na` never.

## 2026-11-03: STATUS.html, a clearer Marketing e social tab

### Changed
- The tab is now **Marketing e social**. At the top, at a glance (`scripts/research/marketing_glance.py`):
  - what to do now: the 3 moves with deadline and owner (👤/🤖), taken from `top_moves.json` and the matching step;
  - channels: ready / to connect / not used, with the case reference "wishlist per 1,000 views";
  - our numbers against the real cases (above / below / to measure), with a "Come si legge" line under the meters;
  - the "why games flop" check as a traffic light, one action per item; some items are filled from the plan (store text, languages, timing, wishlists).
- Everything else is folded (details): store pages, recipe, weekly kit, clips, social, creators, plus new folds: social plan week by week, hooks, subreddit rules, evidence and sources, linked real cases.
- Whole page: one token set (2 accents, 3 status colours with one meaning: green done/ok, orange in progress, red to do/problem), one type scale, flat cards, theme button that remembers the choice, print opens every fold, phone header and section index fixed.
- Plain words in the tab: no file names or commands on screen.
- Test: `tests/test_marketing_glance.py`.

## 2026-11-03: social platforms through Agent Reach, Reddit that works

### Added
- `scripts/research/reach.py`: adapter for [Agent Reach](https://github.com/Panniantong/agent-reach) 1.6 (MIT, read-only CLI).
  - `doctor`: channel by channel, ready or not, with the command that unlocks it; `--live` re-checks on the network.
  - `setup`: the `!` commands the owner runs himself (logins happen in his own browser window).
  - `search`, `read`, `comments`, `profile`, `posts`, `transcript`, `rss` and `run` on X, TikTok, Instagram, Facebook, Reddit, YouTube (subtitles and transcription), Bilibili, XiaoHongShu, GitHub, V2EX, LinkedIn, BOSS, Xueqiu, Xiaoyuzhou, the web and RSS.
  - TikTok is experimental: OpenCLI's read-only commands run in Agent Reach's browser; otherwise tiktok.com is searched through the public web.
  - Results are cached in `launch/_raw/reach/`.
  - Each channel has its own interval between calls and exponential backoff. After `RATE_LIMITED` or `PLATFORM_BLOCKED` the channel pauses.
  - Block and login pages are never taken as content.
  - A channel that is not ready gives `[DA VERIFICARE]` and a dated manual step.
- `scripts/research/reddit_backends.py`: Reddit through a chain of backends. The first one that answers wins, and the result names it.
  - The order: Agent Reach with the owner's login, OAuth, public JSON, the Arctic Shift archive, RSS, ThreadSnoop (with `THREADSNOOP_API_KEY`), the public page text.
  - `thread` (post with comments), `rules` (the archive's sidebar when there are no rules), `listing` (top/new), `search` and `doctor`.
  - Scores are labelled `real`, `archive` or `none`; a hidden score is unknown, never 1.
- Tests: `tests/test_reach.py` and `tests/test_reddit_backends.py`, both offline, with fixtures `reach_fake.json` and `reach_feed.xml`.

### Changed
- `social_verify.py`: real followers and post numbers for TikTok, Instagram and X when the channel is ready, marked `[FATTO]` with source and date. X URLs are recognised.
- `market_tracker.py`: X, TikTok and Instagram (search, the official accounts from the store page, their posts with numbers) now go into the dated marketing timeline. Reddit falls back along the chain.
- `social_content.py`: `track fetch` and `learn --fetch` read views, likes, comments and shares from the posts. Wishlists are never fetched.
- `reddit_trends.py`: a "reach" mode with real upvotes. When RSS is blocked it falls back to the chain (Arctic Shift).
- `reddit_rules.py`: when the anonymous JSON is blocked it uses the chain and writes `backend` and `completeness` in the row.
- `yt_research.py`: `reach` backend (yt-dlp, exact dates, no quota) and `transcript` (subtitles; `--whisper` with the owner's key).
- `case_studies.py fetch`: reads a post-mortem with its comments into a draft, which is never merged on its own.
- `entity_match.py`: `filter_reach` for social results.
- `SKILL.md`, rule 24: TikTok, Instagram and X can be read when `reach.py doctor` says they are ready, always as `[FATTO]` with URL and date. SteamDB is still never scraped.
- `references/00a-bootstrap.md`: the inventory now includes `reach.py doctor` and `reddit_backends.py doctor`.
- Installer:
  - Agent Reach is an optional dependency. It is installed with `uv` from the GitHub release, never from PyPI, followed by `agent-reach setup`.
  - `install.mjs update` refreshes it with `agent-reach update`.
  - `doctor` shows its version and which channels are ready.
  - `uv` is offered as an optional requirement.
  - `--skip agent-reach` leaves it out.
- `tests/run_all.py` runs with `GLS_REACH=off`, so the offline tests never call the Agent Reach installed on the machine.
