# SYSTEM MAP
## Directory Structure
- SKILL.md: skill principale per l'analisi e strategia di lancio
- game-launch-playbooks.md: appendice dei playbook specifici per genere
- commands/game-launch-strategist.md: slash command shortcut (/game-launch-strategist)
- scripts/research/: scraper e utilità per ricerca di mercato (Steam, YouTube, Social, Reddit, Creators)
- tools/scrapers/: sorgenti/mirror degli scraper di ricerca
- installer.bat: launcher batch per installazione rapida su Windows
- install.ps1: script PowerShell multi-IDE (Claude Code, Antigravity IDE, Kilo, Agents Hub)
- .ai_context/: memoria persistente della sessione di sviluppo

## Tech Stack & Invariants
- Runtime: Python 3.9+ (stdlib only)
- Shell: PowerShell 5.1+ / pwsh, cmd
- Formati dati: JSON, CSV (UTF-8 con BOM), Markdown
