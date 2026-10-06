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

### Interview first

Before any number, the skill **interviews you about your intentions in several rounds** (goals and what success means, capacity, money and risk, channels and style, what is non-negotiable, "what if it goes badly" scenarios, then a confirmation), gives advice with trade-offs after each round, flags tensions between your answers, and keeps a decision log. Thresholds, calendar, channels and contingency plans follow **your** decisions; when the data contradicts them it asks again instead of changing them silently.

### Data, planning and monitoring tools

Beyond the phases, the skill ships tools that turn guesses into reproducible numbers and keep the plan alive:

- **Real benchmarks.** `genre_bench.py` (how the most reviewed games of your tag do, by year, price and demo, built from public data at run time), `store_bench.py` (store page and trailer of the comparables: description, GIFs, trailer duration, cuts, hook frames, and how they relate to performance), `review_corpus.py` (thousands of real reviews of the comparables **and** of the genre, and what they say about the features of your game).
- **Step-by-step calendar.** `calendar.md` lists the steps in order, split into phases, each marked 👤 (you) or 🤖 (Claude) with a due date; `plan_steps.py` tells you what is next and ticks what is done.
- **Copy-ready store pages.** `store_kit.json` holds the Steam and itch.io pages (fields, long description with the exact places for photos and GIFs, ordered tags, screenshots, capsules, settings, checklist); `store_kit.py` checks and exports them.
- **"If... then" plans.** `metrics_track.py` follows the numbers you record (itch views and downloads, demo, Discord...) against scenarios with thresholds, diagnosis and actions, for example "one week on itch went badly". `wl_track.py` does the same for wishlists and the pre-mortem tripwires; `watchlist.py` follows comparables and competitors and warns when one releases in your launch window.
- **Economics.** `calc_econ.py`: gross to net, break-even and three scenarios from stated assumptions.
- **Status page.** `status_page.py` builds one HTML file (verdict, decision profile, steps, charts, gates, store pages with Copy buttons, contingencies, competitors) for partners or a publisher. The skill never publishes it by itself.

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
  00-intervista.md            phase 0A: multi-round intention interview, advice, decision log
  07-contingenze.md           phase 7C: "if... then" plans, metrics, variable matrix
scripts/research/             research, planning and monitoring tools (see its README)
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
