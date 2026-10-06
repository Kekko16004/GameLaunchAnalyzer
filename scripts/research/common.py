"""Shared helpers: polite HTTP with retries/backoff/throttle, JSON/CSV output, input loading.

Stdlib only. Every tool in this folder imports from here.
"""
from __future__ import annotations

import csv
import datetime
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research-scrapers/1.0"


class Throttle:
    """Guarantees at least `min_interval` seconds between consecutive requests (thread-safe)."""

    def __init__(self, min_interval: float = 1.0):
        self.min_interval = max(0.0, float(min_interval))
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            delta = self._last + self.min_interval - now
            if delta > 0:
                time.sleep(delta)
            self._last = time.monotonic()


_GLOBAL_THROTTLE = Throttle(1.0)


def set_rate(min_interval: float):
    _GLOBAL_THROTTLE.min_interval = max(0.0, float(min_interval))


def http_get(url: str, *, headers: dict | None = None, data: bytes | None = None, retries: int = 3,
             timeout: float = 30, throttle: Throttle | None = None, method: str | None = None) -> bytes:
    """GET (or POST if data) with throttle + exponential backoff. Honors Retry-After on 429/503.

    Raises the last error if all attempts fail. 4xx other than 408/429 are not retried.
    """
    th = throttle or _GLOBAL_THROTTLE
    h = {"User-Agent": DEFAULT_UA, "Accept-Language": "en-US,en;q=0.9"}
    if headers:
        h.update(headers)
    last = None
    for attempt in range(retries + 1):
        th.wait()
        try:
            req = urllib.request.Request(url, headers=h, data=data, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (408, 429, 500, 502, 503, 504):
                raise
            ra = e.headers.get("Retry-After") if e.headers else None
            wait = float(ra) if ra and ra.isdigit() else (2 ** attempt) + random.random()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            wait = (2 ** attempt) + random.random()
        if attempt < retries:
            time.sleep(min(wait, 60))
    raise last  # type: ignore[misc]


def get_json(url: str, **kw):
    return json.loads(http_get(url, **kw).decode("utf-8", "ignore"))


def get_text(url: str, **kw) -> str:
    return http_get(url, **kw).decode("utf-8", "ignore")


def safe_json(url: str, default=None, **kw):
    """get_json that returns `default` (and logs to stderr) instead of raising."""
    try:
        return get_json(url, **kw)
    except Exception as e:  # noqa: BLE001
        log(f"WARN {url}: {e}")
        return {} if default is None else default


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def read_list(values: list[str] | None, file: str | None) -> list[str]:
    """Merge CLI values with lines of a text file (blank lines and #comments skipped)."""
    out = list(values or [])
    if file:
        with open(file, encoding="utf-8") as f:
            out += [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    return out


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(obj, path: str | None):
    s = json.dumps(obj, ensure_ascii=False, indent=1)
    if not path or path == "-":
        print(s)
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)
    log(f"wrote {path}")


def write_csv(rows: list[dict], path: str, fieldnames: list[str] | None = None):
    """CSV with UTF-8 BOM (opens cleanly in Excel). Lists are joined with '; '."""
    if not rows:
        log(f"no rows, {path} not written")
        return
    fields = fieldnames or list(dict.fromkeys(k for r in rows for k in r))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("; ".join(map(str, v)) if isinstance(v, (list, tuple)) else v) for k, v in r.items()})
    log(f"wrote {path} ({len(rows)} rows)")


def write_output(obj, out: str | None, csv_rows: list[dict] | None = None):
    """Write JSON to `out`; if `out` ends with .csv write CSV of csv_rows (or obj if it is a list)."""
    if out and out.lower().endswith(".csv"):
        write_csv(csv_rows if csv_rows is not None else obj, out)
    else:
        write_json(obj, out)


def ts_to_date(ts) -> str:
    """Unix seconds -> 'YYYY-MM-DD' (UTC)."""
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%d")


def q(s: str) -> str:
    return urllib.parse.quote(s, safe="")


def parse_count(s) -> int | None:
    """'1.2K' / '3,456' / '2M subscribers' / '4,037,925 views' -> int."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return int(s)
    s = str(s).strip().split(" ")[0].replace(",", "")
    if not s:
        return None
    mul = {"K": 1e3, "M": 1e6, "B": 1e9}.get(s[-1].upper(), 1)
    try:
        return int(float(s.rstrip("KMBkmb")) * mul)
    except ValueError:
        return None
