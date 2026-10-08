"""Plain-language Italian labels for the review themes and the game's features.

The scripts count reviews with English keyword patterns (steam_reviews.py, review_corpus.py) and keep short technical keys
such as `repetitive_shallow`. Charts and reports must never show those keys to a person: they show the label and, on demand,
what the theme actually counts. Everything a non-expert reads should be clear without knowing the code.

A game's own features come from launch/_raw/my_features.json (key -> regex). Give each one a readable name in
launch/_raw/feature_labels.json ({"key": {"label": "...", "means": "..."}}); without it the key is turned into words.
"""
from __future__ import annotations

import json
import os

# key -> (short label, what the theme counts, in everyday words)
THEMES = {
    # complaints (negative reviews)
    "onboarding_tutorial": ("Non si capisce cosa fare", "tutorial poco chiaro, confusione, il gioco non spiega"),
    "repetitive_shallow": ("Ripetitivo, stufa presto", "sempre uguale, noioso, grind, poca profondità"),
    "difficulty_balance": ("Difficoltà sbilanciata", "troppo facile o troppo difficile, ingiusto, troppa fortuna"),
    "bugs_crashes": ("Bug e crash", "errori, blocchi, salvataggi persi"),
    "performance": ("Prestazioni", "lag, FPS bassi, scatti, caricamenti lenti"),
    "price_value_length": ("Troppo caro o troppo corto", "non vale il prezzo, dura poco, meglio aspettare i saldi"),
    "content_depth": ("Poco contenuto", "sembra incompiuto, vuoto, serve più roba"),
    "ui_ux_controls": ("Comandi, menu e telecamera scomodi", "controlli goffi, menu confusi, pad o telecamera fastidiosi"),
    "multiplayer_netcode": ("Multiplayer: manca o non funziona", "co-op assente, server, partite online con problemi"),
    "story_writing_audio": ("Storia, testi e audio", "trama, dialoghi, doppiaggio, traduzioni, musica e suoni (tutto insieme)"),
    "story_writing": ("Storia e testi", "trama, dialoghi, scrittura, traduzioni"),
    "audio_music": ("Musica e suoni", "musica, effetti sonori, doppiaggio"),
    "art_visuals": ("Grafica brutta o 'fatta con asset presi'", "grafica povera, asset flip, poco curata, animazioni"),
    "ai_generated_assets": ("Contenuti fatti con l'AI", "immagini, voci o testi generati con l'AI"),
    "ai_behavior": ("Personaggi poco intelligenti", "nemici o NPC stupidi, si bloccano"),
    "monetization_dlc": ("DLC e acquisti interni", "DLC, microtransazioni, 'cash grab'"),
    "dev_support": ("Sviluppatori spariti", "niente aggiornamenti, gioco abbandonato"),
    "steam_deck": ("Steam Deck", "come gira o si gioca su Steam Deck"),
    "refund_mentions": ("Parla di rimborso", "il recensore dice di aver chiesto o voler chiedere il rimborso"),
    # praise (positive reviews)
    "fun_addictive": ("Divertente, 'ancora una partita'", "divertente, crea dipendenza, non riesci a smettere"),
    "art_style": ("Grafica e stile belli", "bello da vedere, stile carino o originale"),
    "music_sound": ("Musica e suoni belli", "colonna sonora, effetti sonori"),
    "depth_variety": ("Profondità e varietà", "tante scelte, build, sinergie, strategie diverse"),
    "replayability": ("Si rigioca volentieri", "ogni partita è diversa, tante ore"),
    "value_for_money": ("Vale il prezzo", "costa poco per quello che dà"),
    "story_characters": ("Storia e personaggi", "trama, personaggi, dialoghi, mondo"),
    "polish_feel": ("Rifinito e piacevole da controllare", "controlli precisi, soddisfacente, 'feel' curato"),
    "coop_friends": ("Bello con gli amici", "co-op, multiplayer, serate in compagnia"),
    "content_amount": ("Tanto contenuto", "tanta roba da fare, molte ore"),
    "dev_support_positive": ("Sviluppatori presenti", "aggiornamenti, ascoltano la community"),
    "easy_to_learn": ("Facile da imparare", "intuitivo, adatto a chi inizia"),
    "relaxing_cozy": ("Rilassante", "tranquillo, cozy, senza stress"),
    "challenge_rewarding": ("Sfida che ripaga", "difficile ma soddisfacente, conta l'abilità"),
}

VERDICTS = {
    "rewarded": "premiata: se ne parla più nelle recensioni positive",
    "punished": "punita: se ne parla più nelle recensioni negative",
    "divisive": "divide: compare sia nelle positive sia nelle negative",
    "rarely discussed": "se ne parla poco: dato poco affidabile",
}


def label(key: str) -> str:
    return THEMES.get(key, (key.replace("_", " ").capitalize(), ""))[0]


def means(key: str) -> str:
    return THEMES.get(key, ("", ""))[1]


def verdict_it(v: str | None) -> str:
    return VERDICTS.get(v or "", v or "")


def feature_labels(root: str) -> dict:
    """Readable names for the game's own features (launch/_raw/feature_labels.json); falls back to the key in words."""
    p = os.path.join(root, "_raw", "feature_labels.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def feature_label(key: str, labels: dict) -> tuple[str, str]:
    v = labels.get(key)
    if isinstance(v, dict):
        return v.get("label") or key, v.get("means", "")
    if isinstance(v, str):
        return v, ""
    return key.replace("_", " ").capitalize(), ""
