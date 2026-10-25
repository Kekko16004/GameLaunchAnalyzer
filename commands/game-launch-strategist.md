---
description: Strategia di lancio per un gioco indie - analisi di mercato con dati reali, posizionamento, focus group, critiche reali, pre-mortem e piano operativo
argument-hint: "[Completa | Rapida | Mirata <area> | Ondata | Aggiornamento]"
---

Carica la skill `game-launch-strategist` e applicala al progetto nella directory corrente. Se il tuo ambiente non ha uno strumento per caricare le skill (per esempio Codex), leggi tu `SKILL.md` dalla cartella della skill (`~/.agents/skills/game-launch-strategist/`, o il link `~/.claude/skills/game-launch-strategist/`) e seguila alla lettera. Richiesta dell'utente: $ARGUMENTS

0. **Fase B, avvio a freddo** (`references/00a-bootstrap.md`): anche in una chat nuova, controlla gli strumenti che hai, scansiona il progetto con `scripts/research/project_scan.py`, leggi i documenti giusti e scrivi `launch/00-contesto.md`.
1. Leggi la data di sistema e `references/01-discovery.md` della skill, poi esegui la Fase 0 a partire dal Context Pack (codice, GDD, asset, configurazioni, Steamworks).
2. Se la richiesta indica una modalità (Completa, Rapida, Mirata, Ondata, Aggiornamento) o un'area (es. "solo prezzo", "solo testi dello store"), applicala subito. Se è vuota o ambigua usa **Completa** e dichiaralo.
3. Segui la skill fase per fase: leggi il file di `references/` di ciascuna fase, usa gli script in `scripts/research/` per comparabili Steam, recensioni reali, creator e regole subreddit, scrivi i file in `launch/` e chiudi con il debriefing in chat. Esegui l'Ondata 1 del focus group subito dopo l'audit e manda la segnalazione problemi; lancia ondate successive solo con l'ok dell'utente.
