---
description: Strategia di lancio per un gioco indie - analisi di mercato con dati reali, posizionamento, focus group, critiche reali, pre-mortem e piano operativo
argument-hint: "[Completa | Rapida | Mirata <area> | Aggiornamento]"
---

Carica la skill `game-launch-strategist` e applicala al progetto nella directory corrente. Richiesta dell'utente: $ARGUMENTS

1. Leggi la data di sistema e `references/01-discovery.md` della skill, poi esegui la Fase 0 ispezionando la directory (codice, GDD, asset, configurazioni, Steamworks).
2. Se la richiesta indica una modalità (Completa, Rapida, Mirata, Aggiornamento) o un'area (es. "solo prezzo", "solo testi dello store"), applicala subito. Se è vuota o ambigua usa **Completa** e dichiaralo.
3. Segui la skill fase per fase: leggi il file di `references/` di ciascuna fase, usa gli script in `scripts/research/` per comparabili Steam, recensioni reali, creator e regole subreddit, scrivi i file in `launch/` e chiudi con il debriefing in chat.
