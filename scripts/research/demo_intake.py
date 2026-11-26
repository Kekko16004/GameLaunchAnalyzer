#!/usr/bin/env python3
"""Curator-only census of *listed Steam demos*, not a ranking or a scorer.

Keep only the release date and Steam id. Never pass this registry or a store
page to the blinded judge. A partial page is not evidence that a day was empty.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import re
import secrets
import tempfile
from urllib.parse import urlencode

import common
from cohort_bench import parse_date


class DemoRows(HTMLParser):
    """Only read the release-date cell of a result; ignore tooltips, titles and scores."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.in_date = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "a" and "search_result_row" in classes:
            aid = attrs.get("data-ds-appid") or ""
            self.row = [aid if re.fullmatch(r"[1-9]\d*", aid) else None, ""]
        elif tag == "div" and self.row is not None and "search_released" in classes:
            self.in_date = True

    def handle_endtag(self, tag):
        if tag == "div":
            self.in_date = False
        elif tag == "a" and self.row is not None:
            self.rows.append((self.row[0], parse_date(self.row[1])))
            self.row = None
            self.in_date = False

    def handle_data(self, data):
        if self.row is not None and self.in_date:
            self.row[1] += data


def collect(start, end, cc, max_pages, fetch=common.safe_json, page_size=50):
    candidates, warnings, seen_pages = {}, [], set()
    offset = 0
    for _ in range(max_pages):
        query = urlencode(dict(category1=10, sort_by="Released_DESC", start=offset,
                               count=page_size, cc=cc, l="english", infinite=1))
        data = fetch("https://store.steampowered.com/search/results/?" + query)
        if not isinstance(data, dict) or not isinstance(data.get("results_html"), str):
            warnings.append("source_unavailable")
            break
        try:
            total = int(data["total_count"])
        except (KeyError, TypeError, ValueError):
            warnings.append("unknown_total")
            break
        parser = DemoRows()
        parser.feed(data["results_html"])
        parser.close()
        rows = parser.rows
        if not rows:
            if data["results_html"].strip() or offset < total:
                warnings.append("unreadable_page")
            break
        fingerprint = tuple(rows)
        if fingerprint in seen_pages:
            warnings.append("repeated_page")
            break
        seen_pages.add(fingerprint)
        for aid, date in rows:
            if not aid or not date:
                if "unclassified_rows" not in warnings:
                    warnings.append("unclassified_rows")
            elif start <= date <= end:
                candidates[aid] = date.isoformat()
        offset += len(rows)
        dates = [date for _, date in rows if date]
        if offset >= total or (len(dates) == len(rows) and max(dates) < start):
            break
    else:
        warnings.append("page_budget_exhausted")
    return dict(source="Steam search: listed demos, release date (category1=10)", country=cc,
                window=[start.isoformat(), end.isoformat()], observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                complete=not warnings, warnings=warnings, candidates=[
                    dict(appid=int(k), release_date=v) for k, v in
                    sorted(candidates.items(), key=lambda item: (item[1], int(item[0])))])


def expected_cases(snapshot: Path):
    """Authoritative ordered aliases for matching the full Steam registry at admission."""
    raw = snapshot.read_bytes()
    data = json.loads(raw)
    if data.get("source") != "Steam search: listed demos, release date (category1=10)" or data.get("complete") is not True:
        raise ValueError("censimento incompleto: riprovare, non selezionare solo i casi arrivati")
    key_path = Path(common.user_dir("demo-intake")) / ".group-key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(key_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        key = key_path.read_bytes()
    else:
        key = secrets.token_bytes(32)
        with os.fdopen(fd, "wb") as f:
            f.write(key)
    if len(key) != 32:
        raise ValueError("chiave privata gruppi non valida")
    cases = []
    for case in data["candidates"]:
        group = hmac.new(key, ("demo:" + str(case["appid"])).encode(), hashlib.sha256).hexdigest()[:24]
        cases.append(dict(group=group, released=case["release_date"], status="insufficient",
                          reason="Manca una prova anonima della demo.", trace=[], media=[]))
    return hashlib.sha256(raw).hexdigest(), cases


def prepare_roster(snapshot, out):
    """Write the curator's editable draft, not the judge's pack. Never overwrite annotations."""
    digest, cases = expected_cases(snapshot)
    with out.open("x", encoding="utf-8") as f:
        json.dump(dict(snapshot=digest, complete=True, cases=cases),
                  f, ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=7, help="giorni interi fino a ieri (UTC)")
    p.add_argument("--end", type=dt.date.fromisoformat)
    p.add_argument("--max-pages", type=int, default=30)
    p.add_argument("--cc", default="US", help="regione del catalogo Steam")
    p.add_argument("--prepare-roster", type=Path, metavar="SNAPSHOT", help="solo curatore, nessuna rete")
    p.add_argument("--out", type=Path, help="nuova bozza di roster per demo_blind.py")
    args = p.parse_args()
    if args.prepare_roster or args.out:
        if not (args.prepare_roster and args.out):
            p.error("--prepare-roster e --out vanno dati insieme")
        try:
            prepare_roster(args.prepare_roster, args.out)
        except (OSError, ValueError, KeyError) as exc:
            p.error(str(exc))
        print("Bozza privata creata. Anonimizza le prove prima dell'ammissione; non rimuovere le demo senza materiale.")
        return 0
    today = dt.datetime.now(dt.timezone.utc).date()
    end = args.end or today - dt.timedelta(days=1)
    if not 1 <= args.days <= 366 or not 1 <= args.max_pages <= 200 or end >= today or not re.fullmatch("[a-zA-Z]{2}", args.cc):
        p.error("servono 1–366 giorni conclusi, 1–200 pagine e un paese di due lettere")
    start, cc = end - dt.timedelta(days=args.days - 1), args.cc.upper()
    dest = Path(common.user_dir("demo-intake")) / f"{cc}_{start}_{end}.json"
    if dest.exists():
        prev = json.loads(dest.read_text(encoding="utf-8"))
        if prev["complete"]:
            print(f"Censimento curatore già acquisito: {len(prev['candidates'])} candidati ({dest}).")
            return 0
    data = collect(start, end, cc, args.max_pages)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=dest.parent, delete=False) as f:
        tmp = Path(f.name)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        except BaseException:
            f.close()
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    state = "completo per la fonte" if data["complete"] else "PARZIALE: " + ", ".join(data["warnings"])
    print(f"Solo curatore: {len(data['candidates'])} candidati; {state}. {dest}")
    return 0 if data["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
