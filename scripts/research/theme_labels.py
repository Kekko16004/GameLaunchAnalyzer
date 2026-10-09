"""Plain-language Italian labels for the review themes and the game's features.

The scripts count reviews with English keyword patterns (steam_reviews.py, review_corpus.py) and keep short technical keys
such as `repetitive_shallow`. Charts and reports must never show those keys to a person: they show the label and, on demand,
what the theme actually counts. Everything a non-expert reads should be clear without knowing the code.

A game's own features come from launch/_raw/my_features.json (key -> regex). Give each one a readable name in
launch/_raw/feature_labels.json ({"key": {"label": "...", "means": "..."}}); without it the key is turned into words.

"Does OUR game have it?" for every review theme (used by report_charts.reviews and STATUS.html):
  - THEME_ISSUES maps a theme to the focus-group issue keys that talk about the same thing (so the page can say how many
    simulated testers raised it in the latest beta and full-game wave). A project can add or override entries in
    launch/_raw/theme_issues.json ({"theme": ["issue-key", ...]}).
  - THEME_05B finds the row of the theme in the tables of launch/05b-critiche-reali.md and reads its verdict tag
    ([SÌ] / [A RISCHIO] / [NO] / [NON VALUTABILE] / [IN PARTE] / [PARZIALE]); several tags in one cell (e.g. "[NO] per la beta, [A RISCHIO] per il
    gioco a pagamento") are all kept.
"""
from __future__ import annotations

import json
import os
import re

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


# review theme -> focus-group issue keys about the same thing (stable keys used by the waves; extend per project in _raw/theme_issues.json)
THEME_ISSUES = {
    "repetitive_shallow": ["run-variety", "repetition"],
    "content_depth": ["content-short", "run-variety"],
    "price_value_length": ["price-value", "content-short"],
    "ui_ux_controls": ["controls-complexity", "tray-feel", "tilt-locks-camera"],
    "multiplayer_netcode": ["no-coop", "new-coop-scope-risk"],
    "performance": ["perf-unknown"],
    "bugs_crashes": ["perf-unknown", "new-ui-polish-bugs", "new-data-inconsistency"],
    "steam_deck": ["perf-unknown"],
    "onboarding_tutorial": ["slow-opening", "text-walls"],
    "difficulty_balance": ["new-quota-wall", "rng-unfair"],
    "art_visuals": ["kit-look"],
    "story_writing_audio": ["new-languages-it-en-only"],
    "story_writing": ["new-languages-it-en-only"],
    "monetization_dlc": ["gambling-optics", "new-beta-upsell-locks"],
    # praise: the issue says we are MISSING it
    "coop_friends": ["no-coop"],
    "art_style": ["kit-look"],
    "depth_variety": ["run-variety", "new-perks-shown-are-stat-tweaks"],
    "replayability": ["run-variety", "repetition"],
    "content_amount": ["content-short"],
    "value_for_money": ["price-value"],
    "polish_feel": ["tray-feel", "serve-feedback"],
    "easy_to_learn": ["controls-complexity", "slow-opening"],
    "fun_addictive": ["repetition"],
}

# review theme -> regex that finds its row (first column) in the tables of 05b-critiche-reali.md
THEME_05B = {
    "repetitive_shallow": r"ripetitiv|monoton|superficial",
    "content_depth": r"poco contenut|troppo cort|contenuto",
    "price_value_length": r"prezzo|valore|cort",
    "ui_ux_controls": r"controll|comand|fisica goff",
    "multiplayer_netcode": r"co-?op|multiplayer",
    "performance": r"prestazion|bug|crash",
    "bugs_crashes": r"bug|crash",
    "steam_deck": r"deck",
    "onboarding_tutorial": r"onboarding|tutorial",
    "difficulty_balance": r"fortuna|bilanciament|difficolt|stress",
    "art_visuals": r"grafic|asset",
    "dev_support": r"sviluppator",
    "story_writing_audio": r"storia|testi|audio",
    "fun_addictive": r"divertent|dipendenz|ancora una",
    "coop_friends": r"amici|giocare con altri|co-?op|risate",
    "art_style": r"stile|grafic|fascino",
    "value_for_money": r"qualit[aà]\s*/\s*prezzo|prezzo|valore",
    "depth_variety": r"sinergi|build|profondit|variet",
    "challenge_rewarding": r"sfida|bravura",
    "replayability": r"rigioc|variet|ancora una",
    "relaxing_cozy": r"rilass|cozy",
    "polish_feel": r"rifinit|feel|controll",
    "content_amount": r"tanto contenut|contenut",
    "easy_to_learn": r"facile|intuitiv",
}

TAG_IT = {"SÌ": "sì", "SI": "sì", "A RISCHIO": "a rischio", "NO": "no", "NON VALUTABILE": "non valutabile", "IN PARTE": "in parte", "PARZIALE": "in parte"}
_TAG = re.compile(r"\[(NON VALUTABILE|A RISCHIO|IN PARTE|PARZIALE|SÌ|SI|NO)([^\]]*)\]", re.I)


def theme_issues(root: str | None = None) -> dict:
    """THEME_ISSUES plus the project's launch/_raw/theme_issues.json (its entries replace the defaults)."""
    out = dict(THEME_ISSUES)
    if root:
        try:
            with open(os.path.join(root, "_raw", "theme_issues.json"), encoding="utf-8") as f:
                extra = json.load(f)
            out.update({k: [str(x) for x in v] for k, v in extra.items() if isinstance(v, list)})
        except (OSError, ValueError, AttributeError):
            pass
    return out


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", t or "")).strip()


def read_05b(root: str) -> dict:
    """Rows of the tables of 05b-critiche-reali.md that carry a verdict tag on OUR game:
    {"punished": [{name, tags:[...], text}], "rewarded": [...]}. A table is "rewarded" when its header talks about praise
    ("premiat", "ce l'ha", "piace"), otherwise "punished". Missing file: empty lists."""
    out = {"punished": [], "rewarded": []}
    try:
        lines = open(os.path.join(root, "05b-critiche-reali.md"), encoding="utf-8").read().splitlines()
    except OSError:
        return out
    kind, head = None, None
    for i, ln in enumerate(lines):
        if not ln.lstrip().startswith("|"):
            kind, head = None, None
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if kind is None:   # header row
            h = " ".join(cells).lower()
            kind = "rewarded" if re.search(r"premiat|ce l.ha|piace|lod", h) else "punished"
            head = cells
            continue
        if re.match(r"^[\s:|-]+$", ln.strip().strip("|")):
            continue
        tag_cell = next((c for c in reversed(cells) if _TAG.search(c)), None)
        if not tag_cell:
            continue
        name_cell = next((c for c in cells if not re.fullmatch(r"\d+", c.strip())), "")
        tags = []
        clean = re.sub(r"[*_`]", "", tag_cell)
        for m in _TAG.finditer(clean):
            t = TAG_IT.get(m.group(1).upper(), m.group(1).lower()) + (m.group(2).strip(" ,") and (", " + m.group(2).strip(" ,").lower()) or "")
            after = clean[m.end():]
            lvl = re.match(r"\s*\(((?:alto|alta|medio|media|basso|bassa)(?:-(?:alto|alta|medio|media|basso|bassa))?|lieve)[^)]*\)", after, re.I)
            per = re.match(r"\s*(per [^.(;:,\[]{3,40})", after, re.I)
            t += (f" ({lvl.group(1).lower()})" if lvl else "") + (" " + per.group(1).strip().rstrip(",") if per else "")
            if t not in tags:
                tags.append(t)
        text = _clean(_TAG.sub("", tag_cell)).lstrip(" .,;:")
        text = re.sub(r"^\((alto|alta|medio|media|basso|bassa|lieve)[^)]*\)[.,;:]?\s*", "", text, flags=re.I)
        out[kind].append(dict(name=_clean(name_cell), tags=tags, text=text if len(text) <= 220 else text[:219].rstrip() + "…"))
    return out


def ours(theme: str, kind: str, table05b: dict) -> dict | None:
    """The 05b row about this theme (first match of THEME_05B in the table of the same kind), or None."""
    rx = THEME_05B.get(theme)
    if not rx:
        return None
    for r in table05b.get(kind, []):
        if re.search(rx, r["name"], re.I):
            return r
    return None
