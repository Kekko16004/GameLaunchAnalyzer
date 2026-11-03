# Changelog

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
