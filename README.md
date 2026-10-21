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

### Beta or full game: always asked first

The very first question, in every mode, is whether you are showing a **beta / demo / vertical slice** or a **full game**, because it changes how everything is judged. If it is a beta and you already have the TODO or plan of the full game, the skill first analyses it **as a beta** (planned content that is not there yet is a gap, not a defect), then asks questions about the full game, then runs a quick full-game analysis (gaps per pillar, scope against capacity, length and price, review risk, what to improve now). The two verdicts stay separate and the full-game one is always provisional.

A free beta is judged on one more thing: **does it make you want to pay when the full game comes out?** The panel is asked whether they would pay the planned launch price (`would_buy`), and the report names the conversion point and the levers to raise it.

### Interview first

Before any number, the skill **interviews you about your intentions in several rounds** (goals and what success means, capacity, money and risk, channels and style, what is non-negotiable, "what if it goes badly" scenarios, then a confirmation), gives advice with trade-offs after each round, flags tensions between your answers, and keeps a decision log. Thresholds, calendar, channels and contingency plans follow **your** decisions; when the data contradicts them it asks again instead of changing them silently.

### Data, planning and monitoring tools

Beyond the phases, the skill ships tools that turn guesses into reproducible numbers and keep the plan alive:

- **Real benchmarks.** `genre_bench.py` (how the most reviewed games of your tag do, by year, price and demo, built from public data at run time), `store_bench.py` (store page and trailer of the comparables: description, GIFs, trailer duration, cuts, hook frames, and how they relate to performance), `review_corpus.py` (thousands of real reviews of the comparables **and** of the genre, and what they say about the features of your game).
- **Criticalities in order, and a Q&A.** `STATUS.html` shows the criticalities found by the focus group **wave by wave** (pick wave 1, 2, 3…), **gate by gate** and as an **evolution** (new, persistent, falling, resolved, back), together with the ones that come from the real test or the reviews; it is rebuilt from the wave files at each run. A **Questions and answers** section keeps the owner's own questions (searchable, tagged with wave and gate), answers to the frequent ones computed from today's data, and questions worth asking now.
- **Plain words, everywhere.** Every technical term (wishlist, gate, ICE, break-even, percentile…) has a one-sentence explanation in simple Italian: as a tooltip in the HTML pages (hover, focus or tap) and in a glossary at the end of each page and of `REPORT.md`. Mentions of things that have their own section or file are links (creators → the creators section, the calendar → `calendar.md`). `md_enrich.py` does this for the Markdown documents.
- **Cold start in any chat.** A new chat knows nothing, so the skill first rebuilds the context: it inventories the tools of the session (engine-editor MCP, terminal, browser, image reading), scans the project (`project_scan.py`: Unreal, Unity, Godot, Nucleon and more, with version, plugins and configured MCP servers), reads the right documents (`CLAUDE.md`, GDD, `GAME_CONTEXT.md`, `GAME_TASKS.md`, README…), reuses what other skills such as `game-developer` already produced, and writes a Context Pack (`00-contesto.md`). If an Unreal editor MCP is connected it looks at the real build (read-only); if not, it says how to connect it and goes on. It asks only what no file says.
- **Charts everywhere they help.** `report_html.py` turns `REPORT.md` into an illustrated page (pillars, tester verdicts per wave, criticisms, genre and price benchmarks, real-review themes, economics against break-even, crowding per launch week, steps by phase, creators), `status_page.py` has a chart overview, and `charts_export.py` writes each chart as an SVG for the Markdown reports. Light and dark, phone-friendly, every chart with a table view.
- **Launch window.** `launch_window.py` scores each week by the competitors, big releases, festivals and sales around it, lists the quietest weeks and says where your date falls.
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
./install.sh                 # interactive; or --all, --claude, --antigravity, --kilo, --agents, --codex
./install.sh --all --mode copy   # copy instead of symlink
./install.sh --uninstall
```

```bat
:: Windows
installer.bat
:: or: powershell -ExecutionPolicy Bypass -File install.ps1 -All
```

**Codex**: `--codex` (PowerShell: `-Codex`) installs the skill in `$CODEX_HOME/skills` (default `~/.codex/skills`) and the command as a prompt in `~/.codex/prompts`, used as `/prompts:game-launch-strategist` [verify the paths against your Codex version]. Where an environment lacks a tool the skill uses (structured questions, sub-agents, tool search), `SKILL.md` says what to do instead.

Only `SKILL.md`, `references/` and `scripts/` are installed, plus the `/game-launch-strategist` slash command. In `link` mode (default) edits to this repository are picked up immediately (`SKILL.md` is a symlink with Developer Mode on, otherwise a copy that `update.bat` refreshes). Every install records its choices in `~/.game-launch-strategist/install.json`; `install.ps1 -Reuse` repeats them without questions.

## Update (one click)

```bat
update.bat              :: download from GitHub, check the scripts, reinstall in every IDE with the last choices, verify
update.bat -Test        :: also run the unit tests before installing
update.bat -NoSelf      :: no download, only reinstall        update.bat -NoInstall   :: download only
update.bat -Mode copy   :: install as copies                  update.bat -Branch dev  :: follow another branch
```

What it does: (0) installed copies that differ from this folder (edits made inside an IDE's skills folder) are saved to `~/.game-launch-strategist/backups/<date>/` before anything is overwritten; (1) `git pull --ff-only --autostash`, or the latest zip from GitHub if this folder is not a git clone (the previous files are backed up); (2) finds Python 3.9+, compiles every script; (3) `install.ps1 -Reuse` (first time: every IDE found on the PC); (4) checks that every installed `SKILL.md` matches. Exit code 1 if anything needs a look; the warnings are listed at the end.

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
