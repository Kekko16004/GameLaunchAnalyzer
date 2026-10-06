# DECISIONS & DEAD ENDS
## Scelte Scartate (Cosa NON fare)
- Non ricreare scraper da zero in ogni sessione: usiamo il bundle deterministico in scripts/research/.
- Non salvare chiavi API o credenziali nei file di configurazione o codice (solo variabili d'ambiente).
- Non bloccare l'esecuzione in assenza di chiavi (fallback su backend html o flag [DA VERIFICARE]).

## Vincoli Architetturali
- Standardizzazione SKILL.md come file primario per compatibilità cross-IDE (Antigravity, Claude Code, Kilo, Agents Hub).
- Mantenimento di scripts/research/ all'interno della cartella skill in modo che junction/copia portino con sé tutti i tool.
- Script compatibili Python >= 3.9 solo standard library (zero dipendenze esterne obbligatorie).
