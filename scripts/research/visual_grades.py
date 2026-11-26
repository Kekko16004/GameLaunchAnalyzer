"""Offline visual rubric: immutable genre anchors, blind batches, independent QA and scoped exports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import common

TIERS = {"A", "B", "C"}
FIELDS = ["global_tier", "grade_scope", "anchor_pack", "visual_batch"]
RUBRIC = "capsule-v1"
MIN_CONF = .70


def require(condition, message):
    if not condition:
        raise ValueError(message)


def slug(text):
    require(isinstance(text, str) and re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", text)
            and text not in {"con", "nul", "prn", "aux", *(f"{s}{i}" for s in ("com", "lpt") for i in range(1, 10))},
            f"identificatore non valido: {text!r}")
    return text


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def root():
    return Path(common.user_dir("visual"))


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_csv(path, required):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        require(set(required) <= set(fields) and len(fields) == len(set(fields)),
                f"{path}: colonne mancanti/duplicate; richieste {', '.join(required)}")
        rows = list(reader)
        require(all(None not in r and None not in r.values() for r in rows), f"{path}: riga malformata")
        return fields, rows


@contextmanager
def new_dir(dest):
    """Publish immutable directories only after all images/records are ready."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    require(not dest.exists(), f"già presente (non sovrascritto): {dest}")
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        stage = Path(tmp) / "stage"
        stage.mkdir()
        yield stage
        stage.rename(dest)


def image(path):
    data = path.read_bytes()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return data, ".webp"
    raise ValueError(f"non è un header PNG, JPEG o WebP: {path}")


def freeze(a):
    """Freeze a curator's real, already labelled files; never infer an anchor from market outcomes."""
    spec = load(a.manifest)
    genre, version = slug(spec["genre"]), slug(spec["version"])
    dest = root() / "packs" / genre / version
    with new_dir(dest) as stage:
        anchors, hashes = [], set()
        curator = spec.get("curator")
        require(isinstance(curator, str) and curator.strip(), "curatore richiesto")
        for item in spec["anchors"]:
            require(all(isinstance(item.get(k), str) for k in ("tier", "note", "source", "image")),
                    "tier, nota visiva, provenienza e immagine devono essere stringhe")
            tier, note, source = (item[k].strip() for k in ("tier", "note", "source"))
            require(tier in TIERS and note and source, "ogni ancora richiede tier, nota visiva e provenienza")
            data, ext = image(a.manifest.parent / item["image"])
            digest = sha(data)
            require(digest not in hashes, "le ancore devono essere immagini distinte")
            hashes.add(digest)
            name = f"{tier}-{len(anchors)+1}{ext}"
            (stage / name).write_bytes(data)
            anchors.append(dict(tier=tier, image=name, sha256=digest, note=note, source=source))
        require({v["tier"] for v in anchors} == TIERS, "serve almeno un'ancora per ciascun tier A/B/C")
        save(stage / "pack.json", dict(genre=genre, version=version, rubric=RUBRIC, curator=curator, anchors=anchors))
    return str(dest)


def pack_dir(key):
    parts = key.split("/")
    require(len(parts) == 2, "--pack deve essere genere/versione")
    return root() / "packs" / slug(parts[0]) / slug(parts[1])


def week_rows(path):
    fields, rows = read_csv(path, ["appid", "status", "week", "genres", "tags", "header_sha256"])
    require(rows and all(r["week"] == path.stem for r in rows), "CSV non omogeneo: week deve coincidere con il nome del file")
    ids = [r["appid"] for r in rows]
    require(all(re.fullmatch(r"[1-9][0-9]*", i) for i in ids) and len(ids) == len(set(ids)),
            "appid mancanti, duplicati o non numerici")
    return fields, rows


def genre_match(row, genre):
    labels = (row["genres"] + ";" + row["tags"]).split(";")
    return genre in {re.sub(r"[^a-z0-9]+", "-", v.casefold()).strip("-") for v in labels}


def token():
    return secrets.token_hex(8)


def prepare(a):
    pack = pack_dir(a.pack)
    manifest = pack / "pack.json"
    spec = load(manifest)
    batch = token()
    dest = root() / "batches" / batch
    _, week = week_rows(a.week)
    if a.headers is None:
        a.headers = Path(a.week.with_suffix(".source").read_text(encoding="utf-8-sig").strip()) / "headers"
    require(a.headers.is_dir(), f"directory header assente: {a.headers}")
    require(a.size >= 1 and a.chunk >= 1, "size e chunk devono essere positivi")
    eligible = sorted((r for r in week if r["status"] == "keep" and genre_match(r, spec["genre"])),
                      key=lambda r: int(r["appid"]))
    selected = eligible[(a.chunk - 1) * a.size:a.chunk * a.size]
    require(selected, "nessuna riga del genere in questo blocco")
    with new_dir(dest) as stage:
        packet = stage / "blind"
        packet.mkdir()
        anchor_hashes, anchors = set(), []
        for item in spec["anchors"]:
            filename = item["image"]
            data, _ = image(pack / filename)
            require(sha(data) == item["sha256"], f"ancora alterata: {filename}")
            (packet / filename).write_bytes(data)
            anchors.append(dict(tier=item["tier"], image=filename, note=item["note"]))
            anchor_hashes.add(item["sha256"])
        cases, skipped = {}, {}
        for row in selected:
            appid = row["appid"]
            path = next((p for ext in (".jpg", ".png", ".webp", ".jpeg")
                         if (p := a.headers / (appid + ext)).is_file()), None)
            if not path:
                skipped[appid] = "header mancante"
                continue
            try:
                data, ext = image(path)
            except ValueError:
                skipped[appid] = "header illeggibile"
                continue
            digest = sha(data)
            if row["header_sha256"] != digest:
                skipped[appid] = "hash della raccolta assente o discordante"
                continue
            if digest in anchor_hashes:
                skipped[appid] = "è un'ancora"
                continue
            key = token()
            (packet / (key + ext)).write_bytes(data)
            cases[key] = dict(appid=appid, image=key + ext, sha256=digest)
        require(cases, f"nessuna immagine valutabile; escluse: {skipped}")
        save(packet / "packet.json", dict(batch=batch, rubric=RUBRIC, genre=spec["genre"], anchors=anchors,
             cases=[dict(id=k, image=cases[k]["image"]) for k in sorted(cases)]))
        # Precommit the sample independently of scores, confidence and sales.
        sample = secrets.SystemRandom().sample(sorted(cases), max(1, math.ceil(len(cases) * .15)))
        save(stage / "key.json", dict(batch=batch, week=a.week.stem, csv=str(a.week.resolve()),
             pack=a.pack + "@" + sha(manifest.read_bytes()), created_on=now(), sample=sample, cases=cases, skipped=skipped))
    return dict(batch=batch, blind=str(dest / "blind"), n=len(cases), skipped=skipped,
                chunk=a.chunk, chunks=math.ceil(len(eligible) / a.size))


def batch_data(batch):
    directory = root() / "batches" / slug(batch)
    return directory, load(directory / "key.json")


def check_week(key, path):
    require(key["week"] == path.stem, "il lotto non appartiene a questa settimana")
    fields, rows = week_rows(path)
    by_id = {r["appid"]: r for r in rows}
    for item in key["cases"].values():
        appid = item["appid"]
        row = by_id.get(appid)
        require(row is not None and row["status"] == "keep" and genre_match(row, key["pack"].split("/")[0]),
                f"{appid}: identità, status o genere cambiato")
        require(row["header_sha256"] == item["sha256"], f"{appid}: header_sha256 della settimana discordante o assente")
    return fields, rows, by_id


def check_packet(packet, key, mapping):
    """Do not import a vote against a different image, rubric or anchor."""
    name, digest = key["pack"].rsplit("@", 1)
    manifest = pack_dir(name) / "pack.json"
    require(sha(manifest.read_bytes()) == digest, "manifest ancore modificato")
    spec, doc = load(manifest), load(packet / "packet.json")
    expected = [dict(tier=x["tier"], image=x["image"], note=x["note"]) for x in spec["anchors"]]
    require(doc["anchors"] == expected and doc["batch"] == key["batch"] and doc["rubric"] == spec["rubric"]
            and doc["genre"] == spec["genre"], "istruzioni del pacchetto alterate")
    for anchor in spec["anchors"]:
        require(sha((packet / anchor["image"]).read_bytes()) == anchor["sha256"], "immagine ancora alterata")
    labels = {c["id"]: c["image"] for c in doc["cases"]}
    require(len(labels) == len(doc["cases"]) and set(labels) == set(mapping), "casi del pacchetto alterati")
    for label, k in mapping.items():
        ext = Path(key["cases"][k]["image"]).suffix
        require(labels[label] == label + ext and sha((packet / (label + ext)).read_bytes()) == key["cases"][k]["sha256"],
                f"{label}: immagine mostrata alterata")


def ratings(path, expected, labels, value="tier"):
    _, rows = read_csv(path, ["id", value, "confidence", "doubt", "note"])
    result = {}
    for row in rows:
        key = row["id"]
        require(key in expected and key not in result, f"id sconosciuto o duplicato: {key}")
        score = row[value].strip()
        confidence = float(row["confidence"])
        require(score in labels and 0 <= confidence <= 1 and row["doubt"] in ("0", "1") and row["note"].strip(),
                f"{key}: valore, confidenza 0..1, doubt 0/1 e osservazione visiva obbligatori")
        result[key] = {value: score, "confidence": confidence, "doubt": row["doubt"] == "1", "note": row["note"].strip()}
    require(set(result) == set(expected), f"lotto incompleto: mancano {len(set(expected) - set(result))} giudizi")
    return result


def make_review(stage, base, cases, wanted):
    """Independent reviewer sees neither the primary tier nor why a case was selected."""
    packet = stage / "blind"
    packet.mkdir()
    doc = load(base / "packet.json")
    for anchor in doc["anchors"]:
        shutil.copyfile(base / anchor["image"], packet / anchor["image"])
    mapping, doc["cases"] = {}, []
    for k in wanted:
        hidden = token()
        mapping[hidden] = k
        src = base / cases[k]["image"]
        dst = hidden + src.suffix
        data = src.read_bytes()
        require(sha(data) == cases[k]["sha256"], f"immagine del lotto alterata: {k}")
        (packet / dst).write_bytes(data)
        doc["cases"].append(dict(id=hidden, image=dst))
    doc["cases"].sort(key=lambda x: x["id"])
    save(packet / "packet.json", doc)
    save(stage / "mapping.json", mapping)


def rater_name(value):
    require(value.strip(), "identificatore del valutatore richiesto")
    return value.strip()


def import_votes(a):
    directory, key = batch_data(a.batch)
    check_week(key, Path(key["csv"]))
    check_packet(directory / "blind", key, {k: k for k in key["cases"]})
    votes = ratings(a.votes, key["cases"], TIERS | {"?"})
    wanted = set(key["sample"]) | {k for k, v in votes.items() if v["doubt"] or v["confidence"] < MIN_CONF or v["tier"] == "?"}
    with new_dir(directory / "initial") as stage:
        save(stage / "votes.json", dict(rater=rater_name(a.rater), imported_on=now(), votes=votes))
        make_review(stage, directory / "blind", key["cases"], wanted)
    return dict(qa=str(directory / "initial" / "blind"), required=len(wanted), total=len(votes))


def usable(v):
    return v["tier"] in TIERS and v["confidence"] >= MIN_CONF and not v["doubt"]


def qa(a):
    directory, key = batch_data(a.batch)
    initial = load(directory / "initial" / "votes.json")
    reviewer = rater_name(a.rater)
    require(reviewer.casefold() != initial["rater"].casefold(), "serve un secondo valutatore indipendente")
    escalated = (directory / "review" / "mapping.json").exists()
    source = directory / ("review" if escalated else "initial")
    if escalated:
        require(reviewer.casefold() == load(source / "votes.json")["rater"].casefold(),
                "la QA estesa va completata dal revisore del campione")
    mapping = load(source / "mapping.json")
    check_packet(source / "blind", key, mapping)
    votes = {mapping[k]: v for k, v in ratings(a.votes, mapping, TIERS | {"?"}).items()}
    dest = directory / ("extended" if escalated else "review")
    with new_dir(dest) as stage:
        save(stage / "votes.json", dict(rater=reviewer, imported_on=now(), votes=votes))
        remaining = set(key["cases"]) - set(votes)
        mismatch = any(not usable(votes[k]) or votes[k]["tier"] != initial["votes"][k]["tier"] for k in key["sample"] if k in votes)
        if not escalated and remaining and mismatch:
            make_review(stage, directory / "blind", key["cases"], remaining)
            return dict(extended_qa=str(dest / "blind"), remaining=len(remaining), verified=False)
    return dict(qa_complete=True)


def final_votes(directory, key):
    votes = load(directory / "initial" / "votes.json")["votes"]
    reviewed = load(directory / "review" / "votes.json")["votes"]
    if (directory / "review" / "mapping.json").exists():
        require((directory / "extended" / "votes.json").exists(), "QA estesa obbligatoria prima di applicare")
        reviewed.update(load(directory / "extended" / "votes.json")["votes"])
    return {k: (reviewed.get(k, votes[k]), "reread" if k in reviewed else "sampled_batch") for k in key["cases"]}


def apply_votes(a):
    directory, key = batch_data(a.batch)
    final = final_votes(directory, key)
    original = sha(a.week.read_bytes())
    fields, rows, by_id = check_week(key, a.week)
    accepted = withheld = 0
    for k, (vote, _) in final.items():
        appid = key["cases"][k]["appid"]
        row = by_id[appid]
        if not usable(vote):
            withheld += 1
            continue
        require(not row.get("global_tier") or row.get("visual_batch") == a.batch,
                f"{appid}: tier già presente da un altro lotto; nessuna sovrascrittura")
        row.update(global_tier=vote["tier"], grade_scope="global_verified", anchor_pack=key["pack"], visual_batch=a.batch)
        accepted += 1
    for row in rows:
        if row.get("grade") and not row.get("grade_scope"):
            row["grade_scope"] = "legacy"
    # Preserve fields unknown to this tool, outcomes, old grades and the sibling quality manifest.
    fields += [f for f in FIELDS if f not in fields]
    with tempfile.TemporaryDirectory(dir=a.week.parent) as tmp:
        path = Path(tmp) / "week.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as out:
            writer = csv.DictWriter(out, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        require(sha(a.week.read_bytes()) == original, "CSV cambiato durante apply; riprovare dopo l'aggiornamento")
        os.replace(path, a.week)
    initial = load(directory / "initial" / "votes.json")["votes"]
    exact = sum(initial[k]["tier"] == final[k][0]["tier"] and usable(final[k][0]) for k in key["sample"])
    return dict(global_verified=accepted, withheld=withheld, week=str(a.week), sample_size=len(key["sample"]),
                sample_exact=exact, reread=sum(origin == "reread" for _, origin in final.values()))


def compare(a):
    directory, key = batch_data(a.batch)
    # A project image is never introduced into the global ballot.
    final_votes(directory, key)
    check_packet(directory / "blind", key, {k: k for k in key["cases"]})
    digest = sha(image(a.reference)[0])
    votes = ratings(a.votes, key["cases"], {"close", "partial", "distant", "?"}, "similarity")
    dest = a.launch_dir / "visual_comparisons" / (a.batch + "-" + digest[:16])
    with new_dir(dest) as stage:
        save(stage / "comparison.json", dict(scope="project_similarity", batch=a.batch, reference_sha256=digest,
             rater=rater_name(a.rater), imported_on=now(),
             cases=[dict(appid=key["cases"][k]["appid"], image_sha256=key["cases"][k]["sha256"], **v) for k, v in votes.items()]))
    return str(dest / "comparison.json")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sp = p.add_subparsers(dest="command", required=True)
    freeze_p = sp.add_parser("freeze", help="congela le ancore locali A/B/C del curatore")
    freeze_p.add_argument("--manifest", type=Path, required=True)
    prep = sp.add_parser("prepare", help="prepara capsule locali anonimizzate, un genere per lotto")
    prep.add_argument("--pack", required=True)
    prep.add_argument("--week", type=Path, required=True)
    prep.add_argument("--headers", type=Path, help="default: <cartella dal file .source>/headers")
    prep.add_argument("--size", type=int, default=30)
    prep.add_argument("--chunk", type=int, default=1)
    for name in ("import", "qa", "apply", "compare"):
        cmd = sp.add_parser(name)
        cmd.add_argument("--batch", required=True)
        if name == "apply":
            cmd.add_argument("--week", type=Path, required=True)
        else:
            cmd.add_argument("--votes", type=Path, required=True)
            cmd.add_argument("--rater", required=True)
        if name == "compare":
            cmd.add_argument("--reference", type=Path, required=True)
            cmd.add_argument("--launch-dir", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        result = {"freeze": freeze, "prepare": prepare, "import": import_votes, "qa": qa,
                  "apply": apply_votes, "compare": compare}[a.command](a)
    except (KeyError, ValueError, TypeError, OSError, csv.Error) as e:
        p.exit(2, f"visual_grades: {e}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
