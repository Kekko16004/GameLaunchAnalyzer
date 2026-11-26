#!/usr/bin/env python3
"""Importa conteggi aggregati del proprietario e prepara un confronto post-lancio locale."""
import argparse
import csv
from datetime import date
import io
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

from common import setup_stdio

INPUT = ["start", "end", "source", "segment", "metric", "value"]
OUTPUT = ["date", "metric", "value", "note"]
PREFIX = "post_"
STAMP = "post-launch/v1"
SOURCES = {"steamworks", "itch", "telemetry", "playtest"}
SEGMENT = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
# numerator, denominator, must be a subset, smaller is better, one reversible intervention
STAGES = (
    ("Visibilità su Steam: visite per 100 impression", "store_visits", "impressions", False, False,
     "Prova una sola capsula alternativa sulla stessa superficie; non cambiare tag o prezzo."),
    ("Interesse: aggiunte alle wishlist per 100 visite", "wishlist_adds", "store_visits", False, False,
     "Cambia la prima immagine della pagina mostrando il gesto centrale del gioco."),
    ("Acquisto: copie lorde per 100 visite", "units_sold", "store_visits", False, False,
     "Prova una prima riga della pagina che chiarisca cosa si fa nel gioco; mantieni il prezzo."),
    ("Acquisto dalla wishlist (%)", "wishlist_buyers", "wishlist_eligible", True, False,
     "Verifica il messaggio di uscita con lettori già interessati; prova una sola nuova apertura."),
    ("Interesse su itch: download per 100 visite", "itch_downloads", "itch_views", False, False,
     "Rendi riconoscibile il pulsante di download senza cambiare copertina o build."),
    ("Demo completata dai giocatori osservati (%)", "demo_completions", "demo_players", True, False,
     "Osserva dove i giocatori si fermano e prova un solo suggerimento in quel punto."),
    ("Rimborsi nella coorte matura (%)", "refunds", "refund_eligible", True, True,
     "Leggi i motivi aggregati; se emerge un errore ripetibile, verifica una sola correzione."),
    ("Ritorno al giorno 7 nella coorte matura (%)", "returned_d7", "eligible_d7", True, False,
     "Osserva la fine della prima sessione; prova un solo obiettivo visibile per la seconda."),
    ("Recensioni positive tra le nuove recensioni (%)", "positive_reviews", "reviews", True, False,
     "Leggi un campione delle recensioni negative; verifica in gioco un problema ricorrente."),
)
METRICS = {m for _, num, den, *_ in STAGES for m in (num, den)}
PLAY = {"demo_completions", "demo_players", "returned_d7", "eligible_d7"}
BY_SOURCE = {
    "steamworks": METRICS - {"itch_downloads", "itch_views"},
    "itch": {"itch_downloads", "itch_views"},
    "telemetry": PLAY,
    "playtest": PLAY,
}


def day(text):
    try:
        parsed = date.fromisoformat(text)
        if parsed.isoformat() == text:
            return parsed
    except ValueError:
        pass
    raise ValueError("data non valida: serve AAAA-MM-GG")


def context(start, end, source, segment):
    if day(start) > day(end):
        raise ValueError("inizio successivo alla fine della finestra")
    if source not in SOURCES or not SEGMENT.fullmatch(segment):
        raise ValueError("fonte o segmento non valido")
    return start, end, source, segment


def count(value):
    # metrics_track legge float: conserva gli interi rappresentabili esattamente.
    if not re.fullmatch(r"[0-9]{1,16}", value) or int(value) > 2**53 - 1:
        raise ValueError("serve un conteggio intero non negativo; se il dato manca, ometti la riga")
    return int(value)


def rows(data, fields):
    reader = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    if next(reader, None) != fields:
        raise ValueError("intestazione richiesta: " + ",".join(fields))
    for row in reader:
        if not row:
            continue
        if len(row) != len(fields):
            raise ValueError(f"riga {reader.line_num}: numero di colonne errato")
        yield reader.line_num, row


def normalized(data):
    result = {}
    for n, (start, end, source, segment, metric, value) in rows(data, INPUT):
        try:
            context(start, end, source, segment)
            if metric not in BY_SOURCE[source]:
                raise ValueError("metrica non prevista per questa fonte")
            key = end, PREFIX + metric
            point = str(count(value)), "|".join((STAMP, start, source, segment))
            if result.setdefault(key, point) != point:
                raise ValueError("due valori o contesti per la stessa data/metrica")
        except ValueError as exc:
            raise ValueError(f"riga {n}: {exc}") from None
    if not result:
        raise ValueError("nessun conteggio da importare")
    return result


def local_path(path):
    if str(path).startswith(("\\\\", "//")) or "://" in str(path):
        raise ValueError("usa un percorso locale, non un URL o un percorso di rete")
    return Path(path).resolve()


def file_bytes(path):
    if path.is_symlink():
        raise ValueError("file di destinazione collegato: operazione rifiutata")
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def replace(path, data):
    tmp = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
        os.replace(tmp, path)
    finally:
        if tmp:
            tmp.unlink(missing_ok=True)


def import_counts(folder, source_file):
    incoming = normalized(local_path(source_file).read_bytes())
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "metrics.csv"
    lock = folder / ".post-launch-import.lock"
    try:
        lock.open("x").close()
    except FileExistsError:
        raise ValueError("import già in corso (o lock residuo): controlla prima di riprovare") from None
    try:
        old = file_bytes(path)
        needed = dict(incoming)
        if old is not None:
            for n, (end, metric, value, note) in rows(old, OUTPUT):
                key = end, metric.strip()
                if key in incoming:
                    if (value, note) != incoming[key]:
                        raise ValueError(f"metrics.csv riga {n}: conflitto su {key[0]}/{key[1]}; nessuna modifica")
                    needed.pop(key, None)
        if needed:
            buf = io.StringIO(newline="")
            writer = csv.writer(buf)
            if old is None:
                writer.writerow(OUTPUT)
            for key, point in sorted(needed.items()):
                writer.writerow((*key, *point))
            prefix = old if old is not None else b"\xef\xbb\xbf"
            if old and not old.endswith((b"\r", b"\n")):
                prefix += b"\r\n"
            if file_bytes(path) != old:
                raise ValueError("metrics.csv è cambiato durante la lettura; riprova")
            replace(path, prefix + buf.getvalue().encode("utf-8"))
        return len(needed), len(incoming) - len(needed)
    finally:
        lock.unlink()


def collect(data, dates):
    """Non inferire finestre o provenienza dalle note libere del tracker."""
    windows = {}
    seen = {}
    if data is not None:
        for n, (end, name, value, note) in rows(data, OUTPUT):
            if end not in dates or not name.startswith(PREFIX) or name[len(PREFIX):] not in METRICS:
                continue
            try:
                if seen.setdefault((end, name), (value, note)) != (value, note):
                    raise ValueError("righe discordanti per data e metrica")
                if not note.startswith(STAMP + "|"):
                    continue
                _, start, source, segment = note.split("|")
                ctx = context(start, end, source, segment)
                windows.setdefault(ctx, {})[name[len(PREFIX):]] = count(value)
            except ValueError as exc:
                raise ValueError(f"metrics.csv riga {n}: contesto o valore ambiguo ({exc})") from None
    return windows


def measure(values, num, den, subset):
    missing = [k for k in (num, den) if k not in values]
    if missing:
        return None, "manca " + ", ".join(missing)
    a, b = values[num], values[den]
    why = f"{a}/{b}"
    if not b:
        return None, why + ": denominatore zero"
    if subset and a > b:
        return None, why + ": il numeratore supera la coorte; verifica le definizioni"
    return a * 100 / b, why


def diagnose(folder, end, previous):
    if previous and day(previous) >= day(end):
        raise ValueError("la finestra di confronto deve finire prima di quella corrente")
    day(end)
    windows = collect(file_bytes(folder / "metrics.csv"), {end, previous})
    current = sorted(k for k in windows if k[1] == end)
    text = [f"# Post-lancio privato · finestra chiusa il {end}", "",
            "Fonte: conteggi aggregati dichiarati dal proprietario in `metrics.csv`, non verificati da terzi.",
            "Le righe senza contesto di import non entrano nei rapporti. Un dato assente non è zero."]
    if not current:
        text += ["", "**[DA VERIFICARE] Nessuna finestra documentata per questa data.** "
                 "Esporta i conteggi del periodo dal pannello del proprietario e importali; non decidere sul gioco."]
    for start, _, source, segment in current:
        values = windows[start, end, source, segment]
        text += ["", f"## {source} / {segment} · {start} — {end} (estremi inclusi)", "",
                 "Conteggi [FATTO, dichiarati]: " + ", ".join(f"`{k}` = {v}" for k, v in sorted(values.items())) + "."]
        baseline = None
        if previous:
            matches = [k for k in windows if k[1:] == (previous, source, segment)
                       and k[1] < start and day(k[1]) - day(k[0]) == day(end) - day(start)]
            if matches:
                baseline = windows[matches[0]]
                text.append(f"Confronto descrittivo con {matches[0][0]} — {previous}; verifica anche prezzo, "
                            "build, sconti, campagne, mix del traffico e definizioni.")
            else:
                text.append("[DA VERIFICARE] Nessuna finestra precedente comparabile: servono stessa durata, "
                            "fonte e segmento, senza sovrapposizione.")
        if baseline is not None:
            for metric in ("impressions", "store_visits", "itch_views"):
                if metric in values and metric in baseline and values[metric] < baseline[metric]:
                    text.append(f"- Meno esposizione o arrivi: `{metric}` da {baseline[metric]} a {values[metric]}. "
                                "Prima di cambiare pagina, verifica posizione e provenienza del traffico; "
                                "prova un solo canale con link tracciato a budget fisso.")
        for label, num, den, subset, lower_better, test in STAGES:
            if num not in BY_SOURCE[source]:
                continue
            val, detail = measure(values, num, den, subset)
            if val is None:
                text.append(f"- {label}: [DA VERIFICARE] {detail}.")
                continue
            text.append(f"- {label}: **{val:.2f}** ({detail}).")
            if baseline is not None:
                ref, why = measure(baseline, num, den, subset)
                if ref is None:
                    text.append(f"  - Confronto non calcolabile: {why}.")
                else:
                    diff = val - ref
                    unit = "punti percentuali" if subset else "per 100"
                    text.append(f"  - Prima {ref:.2f} ({why}); differenza {diff:+.2f} {unit}, non una prova di effetto.")
                    if (diff > 0 if lower_better else diff < 0):
                        text.append(f"  - [OPINIONE] Peggioramento osservato: prima escludi cambi nel pubblico. {test}")
            else:
                condition = "i rimborsi superano il limite" if lower_better else "il risultato è sotto le attese"
                text.append(f"  - [OPINIONE] Se {condition} del piano: {test}")
    text += ["", "## Decisione del proprietario", "",
             "I rapporti per 100 descrivono volumi: non sono conversioni individuali. "
             "Con pochi casi anche una persona sposta il risultato. Nessuna differenza dimostra una causa.",
             "- **Continua** se il risultato soddisfa la soglia concordata e rispetta il budget; replica prima di ampliare.",
             "- **Cambia** una sola cosa se lo stesso passaggio mostra un peggioramento in finestre confrontabili. "
             "Fissa prima variante, pubblico, metrica/denominatore, campione minimo, data di lettura e tetto di ore/euro.",
             "- **Stop** alla prova o alla spesa se si raggiunge il tetto concordato, oppure la perdita massima; "
             "non è un verdetto sul gioco. Se mancano dati o campione, esito inconcludente: misura, non scalare.",
             "", "Registra in `TODO.md` chi verifica, entro quale data e quale scelta approva il proprietario."]
    return "\n".join(text) + "\n"


def main():
    setup_stdio()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--launch-dir", required=True, help="cartella launch del progetto del gioco")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("import", help="importa un CSV normalizzato locale").add_argument("csv")
    diag = sub.add_parser("diagnose", help="scrive post-launch.md, report derivato e privato")
    diag.add_argument("--end", required=True, help="ultimo giorno della finestra inclusa")
    diag.add_argument("--compare-end", help="ultimo giorno della finestra precedente")
    args = p.parse_args()
    try:
        folder = local_path(args.launch_dir)
        scripts = Path(__file__).resolve().parent
        if folder == scripts or scripts in folder.parents:
            raise ValueError("destinazione nella cartella degli script: indica la cartella launch del gioco")
        if args.cmd == "import":
            new, same = import_counts(folder, args.csv)
            print(f"Import locale: {new} nuove righe, {same} già presenti.")
        else:
            report = diagnose(folder, args.end, args.compare_end)
            path = folder / "post-launch.md"
            if path.is_symlink():
                raise ValueError("report collegato: operazione rifiutata")
            folder.mkdir(parents=True, exist_ok=True)
            replace(path, report.encode("utf-8"))
            print("Report privato aggiornato: post-launch.md")
    except (ValueError, csv.Error, OSError) as exc:
        p.exit(1, f"Errore: {exc}\n")


if __name__ == "__main__":
    main()
