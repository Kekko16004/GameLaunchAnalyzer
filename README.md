# game-launch-strategist

An agent skill (Claude Code, Antigravity IDE, Kilo, Agents Hub) that builds a launch strategy for an indie video game. It reads the game project in the current directory, recognises genre and development stage, gathers real market data from Steam, YouTube and Reddit with bundled scripts, and writes a set of working documents to `launch/`: positioning, dev audit, Go/No-Go gates, Steam/Next Fest calendar, pricing and scenarios, store copy, a simulated focus group kept separate from real critiques taken from actual reviews, a pre-mortem with measurable tripwires, creator outreach, legal and tax checklist, dated TODOs and an executive debrief.

The skill itself is written in **Italian** (instructions and generated reports); store copy and outreach texts are produced in the target audience's language, usually English. Research is done in English as well.

## What it does

| Mode | Use it for |
|---|---|
| **Completa** (default) | Every phase and file, full script pipeline, 54 simulated testers. |
| **Rapida** | Verdict, 5 high-impact levers and a 14-day TODO from a reduced panel (24 testers). |
| **Mirata** | One area only, e.g. "just the store copy", "just pricing", "just creators". |
| **Ondata** | `launch/fg/` already exists: runs the next focus-group wave with the **same testers** on the current state of the game, then delta and timeline. |
| **Aggiornamento** | `launch/` already exists: re-runs the affected phases (including a new wave, with your OK) and reports what changed. |

### Data and planning tools

Beyond the phases, the skill ships tools that turn guesses into reproducible numbers:

- **Real benchmarks.** `store_bench.py` measures store page and trailer of the comparables (description length, GIFs, trailer duration, cuts, hook frames) and relates them to how the games performed; `review_corpus.py` reads thousands of real reviews of the comparables **and** of the genre, and what they say about the features of your game.
- **GamesTracker.** If you run [GamesTracker](https://github.com/Kekko16004/GamesTracker), `gt_corpus.py` reads its database (read-only, local) and computes genre benchmarks, launch curves, marketing timeline and the release window from hundreds of tracked games. The database never leaves your machine.
- **Economics and wishlists.** `calc_econ.py` gives gross-to-net, break-even and three scenarios from stated assumptions; `wl_track.py` takes your weekly wishlist total and raises an alarm when a pre-mortem tripwire fires.
- **Status page.** `status_page.py` builds one HTML file (verdict, charts, gates, calendar, TODOs) for partners or a publisher. The skill never publishes it by itself.

Run the offline tests with `python tests/run_all.py`.

### Focus group in waves

The simulated focus group follows a conversational format (casting with mandatory diversity, independent first impressions, a lively jury debate, a structured report) and runs **early**, right after the dev audit:

1. **Wave 1** judges the current state of the game; a **problem report** goes to you in chat as soon as it ends.
2. You fix what you decide to fix and say so: only then does the skill launch the **next wave**, with the same testers and the same 10-person jury, seeing only the current state (never the old critiques or the list of fixes).
3. `fg_waves.py` computes score, delta per tester and per issue, and a **timeline** across waves, so changes over time are visible and reproducible.

Simulated testers rank problems; they never replace real playtests.

Principles: honest verdicts, every number carries a source or a label (`[FATTO]`, `[STIMA]`, `[OPINIONE]`, `[DA VERIFICARE]`), simulated and real critiques are never mixed, no deceptive tactics, nothing outside `launch/` is modified.

## Install

Requirements: Python ≥ 3.9 (standard library only) for the research scripts.

```bash
# Linux / macOS
./install.sh                 # interactive; or --all, --claude, --antigravity, --kilo, --agents
./install.sh --all --mode copy   # copy instead of symlink
./install.sh --uninstall
```

```bat
:: Windows
installer.bat
:: or: powershell -ExecutionPolicy Bypass -File install.ps1 -All
```

Only `SKILL.md`, `references/` and `scripts/` are installed, plus the `/game-launch-strategist` slash command. In `link` mode (default) edits to this repository are picked up immediately.

## Use

Open your game project and run `/game-launch-strategist`, optionally with a mode: `/game-launch-strategist Rapida`, `/game-launch-strategist Mirata solo prezzo`. Outputs go to `<project>/launch/`; start from `launch/REPORT.md` and `launch/TODO.md`.

## Layout

```
SKILL.md                      role, rules, modes, verdict criteria, phase index (kept short on purpose)
references/
  01-discovery.md             phases 0, 1, 2, 2B   brief, genre router, comparables, positioning
  02-audit-platform-pricing.md  phases 3, 4, 5     dev audit, gates, calendar, pricing
  03-store-clips.md           phases 6, 6B         hooks, capsule, store copy, trailer
  04-focus-group.md           phases 7, 7B         simulated panel, real critiques, pre-mortem
  05-outreach-community-legal.md  phases 8, 9, 10  creators, community, real-test kit, legal/tax
  06-synthesis-output.md      phase 11             report, TODO, status, debrief, QA checklist
  playbooks.md                21 genre playbooks + default thresholds
scripts/research/             research and planning tools (see its README)
tests/                        offline tests (python tests/run_all.py)
commands/                     slash command
install.sh / install.ps1 / installer.bat
```

`SKILL.md` is loaded whenever the skill triggers; each phase file is read only when that phase runs.

## Research tools

`scripts/research/` holds stdlib-only tools with rate limiting and exponential backoff: `steam_discover.py` (find comparables), `steam_comps.py` (store data, reviews, sales estimates), `steam_reviews.py` (real negative/positive reviews with themes), `roster.py` (stable simulated testers), `fg_waves.py` (waves, deltas, timeline), `yt_research.py`, `social_verify.py`, `reddit_rules.py`, `build_creators.py`. Details, options and known limits are in [`scripts/research/README.md`](scripts/research/README.md).

Optional environment variables (never stored in files): `YOUTUBE_API_KEY`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `IG_OEMBED_TOKEN`. Without them the tools degrade gracefully and the skill records what has to be checked by hand.

## Scope and limits

- Simulated testers are opinions with heuristic rigour, not market data: they rank problems, they do not predict sales.
- Sales estimates (Boxleiter, SteamSpy, Gamalytic) are ranges from third parties and rules of thumb.
- Platform rules, fees, festival dates and tax rules change; the skill must verify them with a consultation date every time.
- Legal and tax sections are checklists, not advice. The fiscal part is parameterised by country (Italy is the worked example).
