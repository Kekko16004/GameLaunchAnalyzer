---
description: Analizza un progetto indie game e produce strategia di lancio, analisi mercato con scraper, focus group e piano operativo
argument-hint: "[opzioni: modalita Completa, Rapida, Mirata, Aggiornamento]"
---

Carica la skill `game-launch-strategist` ed esegui la strategia di lancio per il progetto corrente: $ARGUMENTS

1. Ispeziona la directory di lavoro corrente (codice sorgente, GDD, asset, configurazioni, Steamworks). Se $ARGUMENTS specifica una modalita (Completa, Rapida, Mirata, Aggiornamento) o un focus particolare, applicala immediatamente.
2. Esegui la pipeline della skill sfruttando gli strumenti di ricerca in `scripts/research/` per comparabili Steam, creator YouTube/social e regole subreddit, producendo i file operativi in `/launch/` e il debriefing finale.
