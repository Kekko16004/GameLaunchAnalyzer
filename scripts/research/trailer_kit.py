#!/usr/bin/env python3
"""Trailer system: from the owner's interview and real competitor/craft data to a LONG master prompt (positive + negative),
a shot-by-shot storyboard, the asset plan with a credits ledger, the recording brief for the developer side, automatic QA
of a render and a blind viewer panel. Stdlib only; ffmpeg/ffprobe for measuring videos (optional, degrades with a note).

Single source of truth: launch/trailer/<version>/trailer.json (written by Claude after the interview, references/08-trailer.md).
Knowledge base: data/trailer_craft.json (rules with source + date, platform specs, negative base list, clean asset sources).

Commands
  craft   [--topic hook|structure|pacing|steam|social|audio|text|legal|...] [--applies main|short|vertical|gif]   print the rules
  tools   [--spec trailer.json] [--no-npx]           brag / hyperframes / ffmpeg versions (skill lock file, npx), written into the spec
  measure SRC [SRC...] [--name N] [-o out.json] [--max-s 120]   duration, all cuts, shot length per third, loudness, true peak,
                                                     frozen stretches, black, tempo estimate. SRC = file or URL (HLS works)
  bench   PAGES.json [--measured M.json] [--spec trailer.json] [--md out.md]   competitor trailer table (store_bench numbers +
                                                     measure numbers + the hand-judged columns kept in the spec)
  check   trailer.json                               storyboard rules (first cut, first gameplay, static UI, end card, words/s,
                                                     threes, safe zone, text size, forbidden words, credit, voice, ledger)
  build   trailer.json [--out-dir D] [--bench B.json]  writes PROMPT.md, storyboard.md, storyboard.json, assets-plan.md,
                                                     credits-ledger.csv, recording-brief.md/.json, qa-checklist.md, kit.json
  qa      RENDER --spec trailer.json --format main [-o qa.json] [--md qa.md]   automatic checks of a real render
  panel   init --spec trailer.json --render R --out-dir D   blind viewer-panel brief with real anchors (no render = refuses)
  panel   score RESULTS.json [--md out.md]           raw and anchor-normalised scores, drift guard (8 points)
  synth   whoosh|pop|riser|hit|tick|stinger|music OUT.wav [--seed 1] [--bpm 132] [--bars 8] [--ledger credits-ledger.csv]
                                                     code-made sounds (deterministic synthesis, no models), logged in the ledger

Honest limits: the tools MEASURE pacing, loudness and stillness; they cannot judge whether a hook is funny or a shot is
readable: that is the frames + panel + owner. Third-party platform numbers (safe zones, loudness) are references, not specs.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import json
import math
import os
import random
import re
import shutil
import struct
import subprocess
import wave

from common import load_json, log, write_json

HERE = os.path.dirname(os.path.abspath(__file__))
CRAFT = os.path.join(HERE, "data", "trailer_craft.json")
LEDGER_FIELDS = ["id", "file", "kind", "title", "author", "source_url", "licence", "attribution_required", "credit_line",
                 "made_by", "how_made", "date", "used_in", "status", "notes"]
OK_LICENCES = ("CC0", "CC-BY", "own", "game-ledger", "Pixabay", "OFL")
SHOT_FIELDS = ("id", "t0", "t1", "section", "source", "screen", "camera", "text", "audio")
SOURCES = ("gameplay", "rig", "ui", "card")


def craft() -> dict:
    return load_json(CRAFT)


def rule_ids() -> set:
    return {r["id"] for r in craft()["rules"]}


# ----------------------------------------------------------------------------- tools check
def tools_versions(use_npx: bool = True) -> dict:
    """Versions of the tools the trailer pipeline depends on. Never fails: missing = None with a note."""
    out = {"checked": dt.date.today().isoformat()}
    lock = os.path.join(os.path.expanduser("~"), ".agents", ".skill-lock.json")
    lk = load_json(lock) if os.path.exists(lock) else {}
    skills = (lk or {}).get("skills", lk) or {}
    for name in ("brag", "hyperframes"):
        s = skills.get(name) if isinstance(skills, dict) else None
        out[name] = ({"source": s.get("source"), "hash": (s.get("skillFolderHash") or "")[:12], "updated": (s.get("updatedAt") or "")[:10],
                      "how_to_update": f"npx skills update {name} -g -y"} if s else None)
    for d in (os.path.join(os.path.expanduser("~"), ".claude", "skills", "brag"), os.path.join(os.path.expanduser("~"), ".agents", "skills", "brag")):
        sk = os.path.join(d, "SKILL.md")
        if os.path.exists(sk) and out.get("brag") is not None:
            txt = open(sk, encoding="utf-8", errors="replace").read()
            out["brag"]["slim_auto"] = "brag-slim" in txt or "slim.md" in txt
            out["brag"]["full_flag"] = "--full" in txt
            break
    if use_npx and shutil.which("npx"):
        try:
            p = subprocess.run("npx --yes hyperframes --version", shell=True, capture_output=True, text=True, timeout=180)
            v = (p.stdout or "").strip().splitlines()
            out["hyperframes_cli"] = v[-1] if p.returncode == 0 and v else None
        except Exception as e:  # noqa: BLE001
            out["hyperframes_cli"] = None; out["hyperframes_cli_note"] = str(e)[:120]
    for exe in ("ffmpeg", "ffprobe"):
        if shutil.which(exe):
            p = subprocess.run([exe, "-version"], capture_output=True, text=True)
            m = re.search(r"version (\S+)", p.stdout or "")
            out[exe] = m.group(1) if m else "?"
        else:
            out[exe] = None
    return out


# ----------------------------------------------------------------------------- measuring a video
def _run(cmd: list, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def probe(src: str) -> dict:
    if not shutil.which("ffprobe"):
        return {}
    p = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,bit_rate,sample_rate",
              "-of", "json", src], 180)
    try:
        j = json.loads(p.stdout or "{}")
    except ValueError:
        return {}
    out = {"duration_s": float(j.get("format", {}).get("duration") or 0) or None}
    for s in j.get("streams", []):
        if s.get("codec_type") == "video" and "width" not in out:
            num, _, den = (s.get("r_frame_rate") or "0/1").partition("/")
            out.update(width=s.get("width"), height=s.get("height"), vcodec=s.get("codec_name"),
                       fps=round(float(num) / float(den or 1), 2) if float(den or 1) else None)
        if s.get("codec_type") == "audio" and "acodec" not in out:
            out.update(acodec=s.get("codec_name"), audio_hz=int(s.get("sample_rate") or 0) or None)
    return out


def cuts_full(src: str, max_s: float = 120, threshold: float = 0.3) -> list[float] | None:
    if not shutil.which("ffmpeg"):
        return None
    p = _run(["ffmpeg", "-hide_banner", "-nostats", "-t", str(max_s), "-i", src, "-an", "-vf",
              f"scale=320:-2,select=gt(scene\\,{threshold}),showinfo", "-f", "null", "-"], 900)
    return [round(float(x), 2) for x in re.findall(r"pts_time:([0-9.]+)", p.stderr) if float(x) > 0.1]


def shot_stats(cuts: list[float], duration: float) -> dict:
    """Shot lengths overall and per third of the trailer (open / middle / end)."""
    edges = [0.0] + [c for c in cuts if c < duration] + [duration]
    shots = [round(b - a, 2) for a, b in zip(edges, edges[1:]) if b - a > 0.04]
    thirds = []
    for i in range(3):
        lo, hi = duration * i / 3, duration * (i + 1) / 3
        n = sum(1 for c in cuts if lo <= c < hi)
        thirds.append(round((hi - lo) / (n + 1), 2))
    return dict(cuts=len(cuts), shots=len(shots), avg_shot_s=round(duration / max(1, len(shots)), 2) if duration else None,
                median_shot_s=sorted(shots)[len(shots) // 2] if shots else None, avg_shot_by_third=thirds,
                first_cut_s=cuts[0] if cuts else None, cuts_first_5s=sum(1 for c in cuts if c <= 5),
                cuts_per_min=round(len(cuts) / duration * 60, 1) if duration else None)


def loudness(src: str, max_s: float = 120) -> dict:
    if not shutil.which("ffmpeg"):
        return {}
    p = _run(["ffmpeg", "-hide_banner", "-nostats", "-t", str(max_s), "-i", src, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], 900)
    tail = p.stderr[p.stderr.rfind("Summary:"):] if "Summary:" in p.stderr else ""
    i = re.search(r"I:\s+(-?[0-9.]+) LUFS", tail); tp = re.search(r"Peak:\s+(-?[0-9.]+|-inf) dBFS", tail); lra = re.search(r"LRA:\s+([0-9.]+) LU", tail)
    f = lambda m: (None if not m or m.group(1) == "-inf" else float(m.group(1)))
    return dict(lufs_i=f(i), true_peak_dbtp=f(tp), lra_lu=f(lra))


def stills(src: str, max_s: float = 120, min_d: float = 1.0) -> dict:
    """Frozen stretches (nothing moves for >= min_d s) and black stretches."""
    if not shutil.which("ffmpeg"):
        return {}
    p = _run(["ffmpeg", "-hide_banner", "-nostats", "-t", str(max_s), "-i", src, "-an", "-vf",
              f"scale=320:-2,freezedetect=n=0.002:d={min_d},blackdetect=d=0.25:pix_th=0.08", "-f", "null", "-"], 900)
    fr = [(float(a), float(b)) for a, b in re.findall(r"freeze_start: ([0-9.]+).*?freeze_end: ([0-9.]+)", p.stderr, re.S)]
    bl = [(float(a), float(b)) for a, b in re.findall(r"black_start:([0-9.]+) black_end:([0-9.]+)", p.stderr)]
    return dict(frozen=[[round(a, 2), round(b, 2)] for a, b in fr], black=[[round(a, 2), round(b, 2)] for a, b in bl])


def tempo_from_pcm(samples: list[float], sr: int) -> float | None:
    """Tempo estimate (BPM 70-180) from an onset-strength envelope + autocorrelation. Rough: +-3 BPM, octave errors possible."""
    hop = sr // 100                                                 # 10 ms frames
    if len(samples) < sr * 6:
        return None
    env = [math.sqrt(sum(x * x for x in samples[i:i + hop]) / hop) for i in range(0, len(samples) - hop, hop)]
    on = [max(0.0, b - a) for a, b in zip(env, env[1:])]
    m = sum(on) / len(on)
    on = [x - m for x in on]
    best, best_v = None, -1e18
    for bpm10 in range(700, 1801, 5):
        lag = 6000.0 / (bpm10 / 10.0)                               # frames per beat
        L = int(round(lag))
        v = sum(on[i] * on[i + L] for i in range(len(on) - L)) / max(1, len(on) - L)
        L2 = int(round(lag * 2))
        if L2 < len(on):
            v += 0.5 * sum(on[i] * on[i + L2] for i in range(len(on) - L2)) / max(1, len(on) - L2)
        if v > best_v:
            best, best_v = bpm10 / 10.0, v
    return best


def tempo(src: str, start: float = 0, dur: float = 30) -> float | None:
    if not shutil.which("ffmpeg"):
        return None
    sr = 8000
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-t", str(dur), "-i", src, "-vn", "-ac", "1", "-ar", str(sr),
                        "-f", "s16le", "-"], capture_output=True, timeout=600)
    raw = p.stdout
    if len(raw) < sr * 12:
        return None
    n = len(raw) // 2
    s = struct.unpack(f"<{n}h", raw[:n * 2])
    return tempo_from_pcm([x / 32768.0 for x in s], sr)


def measure(src: str, name: str | None = None, max_s: float = 120) -> dict:
    info = probe(src)
    dur = min(info.get("duration_s") or max_s, max_s)
    cuts = cuts_full(src, max_s)
    out = dict(name=name or os.path.basename(src.split("?")[0]), src=src if not src.startswith("http") else src.split("?")[0], measured=dt.date.today().isoformat(), **info)
    if cuts is None:
        out["note"] = "ffmpeg missing: only metadata"
        return out
    out.update(shot_stats(cuts, dur)); out["cut_times"] = cuts
    out.update(loudness(src, max_s)); out.update(stills(src, max_s))
    mid = max(0.0, dur / 2 - 15)
    out["tempo_bpm_est"] = tempo(src, mid, 30)
    return out


# ----------------------------------------------------------------------------- competitor table
def bench_rows(pages: list, measured: list | None, spec: dict | None) -> list[dict]:
    ms = {str(m.get("appid") or m.get("name")): m for m in (measured or [])}
    hand = {str(c.get("appid") or c.get("name")): c for c in ((spec or {}).get("competitors") or [])}
    rows = []
    for p in pages:
        k = str(p.get("appid"))
        m, h = ms.get(k, {}), hand.get(k, {})
        rows.append(dict(name=p.get("name"), appid=p.get("appid"), reviews=p.get("reviews_total"), pct=p.get("pct_positive"),
                         trailer_s=p.get("trailer_s"), first_cut_s=m.get("first_cut_s", p.get("time_to_first_cut_s")),
                         cuts_first_5s=m.get("cuts_first_5s", p.get("cuts_first_5s")), avg_shot_s=m.get("avg_shot_s", p.get("avg_shot_s_first_30s")),
                         avg_shot_by_third=m.get("avg_shot_by_third"), lufs_i=m.get("lufs_i"), true_peak=m.get("true_peak_dbtp"),
                         bpm=m.get("tempo_bpm_est"), frozen_n=len(m.get("frozen") or []) if m else None,
                         role=h.get("role", ""), hook_0_3s=h.get("hook_0_3s", ""), text_cards=h.get("text_cards", ""), music=h.get("music", ""),
                         structure=h.get("structure", ""), ending=h.get("ending", ""), lesson=h.get("lesson", "")))
    for k, h in hand.items():                                       # hand rows without store numbers (e.g. our own trailer)
        if not any(str(r["appid"]) == k for r in rows):
            m = ms.get(k, {})
            rows.append(dict(name=h.get("name"), appid=h.get("appid"), reviews=None, pct=None, trailer_s=m.get("duration_s"), first_cut_s=m.get("first_cut_s"),
                             cuts_first_5s=m.get("cuts_first_5s"), avg_shot_s=m.get("avg_shot_s"), avg_shot_by_third=m.get("avg_shot_by_third"),
                             lufs_i=m.get("lufs_i"), true_peak=m.get("true_peak_dbtp"), bpm=m.get("tempo_bpm_est"), frozen_n=len(m.get("frozen") or []) if m else None,
                             **{x: h.get(x, "") for x in ("role", "hook_0_3s", "text_cards", "music", "structure", "ending", "lesson")}))
    return rows


def _med(v):
    v = sorted(x for x in v if isinstance(x, (int, float)))
    return None if not v else (v[len(v) // 2] if len(v) % 2 else round((v[len(v) // 2 - 1] + v[len(v) // 2]) / 2, 2))


def bench_md(rows: list[dict]) -> str:
    f = lambda x: "—" if x is None or x == "" else (f"{x:g}" if isinstance(x, float) else str(x))
    L = ["| Gioco | Recensioni | Durata (s) | 1° taglio (s) | Tagli nei primi 5 s | Inquadratura media (s) | per terzo (s) | LUFS | BPM stimati |",
         "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['name']} | {f(r['reviews'])} | {f(r['trailer_s'])} | {f(r['first_cut_s'])} | {f(r['cuts_first_5s'])} | {f(r['avg_shot_s'])} | "
                 f"{' / '.join(f(x) for x in (r['avg_shot_by_third'] or [])) or '—'} | {f(r['lufs_i'])} | {f(r['bpm'])} |")
    store = [r for r in rows if r.get("reviews")]
    L.append(f"| **Mediana ({len(store)} giochi)** | | {f(_med([r['trailer_s'] for r in store]))} | {f(_med([r['first_cut_s'] for r in store]))} | "
             f"{f(_med([r['cuts_first_5s'] for r in store]))} | {f(_med([r['avg_shot_s'] for r in store]))} | | {f(_med([r['lufs_i'] for r in store]))} | {f(_med([r['bpm'] for r in store]))} |")
    hand = [r for r in rows if r.get("hook_0_3s")]
    if hand:
        L += ["", "| Gioco | Primi 3 secondi | Scritte | Musica | Struttura | Finale | Lezione per noi |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['name']} | {r['hook_0_3s']} | {r['text_cards']} | {r['music']} | {r['structure']} | {r['ending']} | {r['lesson']} |" for r in hand]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- storyboard checks
def _words(t: str) -> int:
    return len(re.findall(r"[\w'!?]+", t or ""))


def check_spec(spec: dict) -> list[tuple[str, str]]:
    """(level, message) list; level ERROR blocks build --strict, WARN is advice."""
    C = craft(); P = C["specs"]["pacing"]; T = C["specs"]["text"]; SZ = C["specs"]["vertical"]["safe_px"]
    issues: list[tuple[str, str]] = []
    E = lambda m: issues.append(("ERROR", m)); W = lambda m: issues.append(("WARN", m))
    brand = spec.get("brand") or {}
    fmts = {f["id"]: f for f in spec.get("formats") or []}
    if not fmts:
        E("no formats")
    shots = spec.get("shots") or []
    ids = set()
    for s in shots:
        miss = [k for k in SHOT_FIELDS if s.get(k) in (None, "")]
        if miss:
            E(f"{s.get('id', '?')}: missing {', '.join(miss)}")
        if s.get("id") in ids:
            E(f"duplicate shot id {s.get('id')}")
        ids.add(s.get("id"))
        if s.get("source") not in SOURCES:
            E(f"{s.get('id')}: source must be one of {SOURCES}")
        if s.get("source") in ("gameplay", "rig", "ui") and not (s.get("record") or {}).get("scene"):
            E(f"{s.get('id')}: gameplay shot without record.scene (how to film it)")
        if s.get("format") not in fmts:
            E(f"{s.get('id')}: unknown format {s.get('format')}")
    re_forbid = [re.compile(w) for w in brand.get("forbidden_patterns", [r"\bAI\b", r"(?i)\bgenerated\b", r"(?i)artificial intelligence"])]
    names = brand.get("forbidden_names") or []
    for fid, f in fmts.items():
        fs = sorted([s for s in shots if s.get("format") == fid], key=lambda s: s["t0"])
        if not fs:
            if not f.get("derive_from"):
                W(f"format {fid}: no shots")
            continue
        vertical = f.get("aspect") == "9:16"
        if abs(fs[0]["t0"]) > 0.01:
            E(f"{fid}: first shot does not start at 0")
        for a, b in zip(fs, fs[1:]):
            if abs(a["t1"] - b["t0"]) > 0.05 and not b.get("xfade"):
                E(f"{fid}: gap/overlap between {a['id']} ({a['t1']}) and {b['id']} ({b['t0']})")
        total = fs[-1]["t1"]
        tgt = f.get("target_s")
        if tgt and abs(total - tgt) > max(1.0, tgt * 0.1):
            E(f"{fid}: length {total:.1f} s vs target {tgt} s")
        first = fs[0]
        fc_max = P["vertical_first_cut_max_s"] if vertical else P["first_cut_max_s"]
        if first["t1"] - first["t0"] > fc_max and not first.get("oner_beats"):
            E(f"{fid}: first cut at {first['t1'] - first['t0']:.2f} s > {fc_max} s (or give the oner its beats in oner_beats)")
        if first.get("oner_beats") and min(first["oner_beats"]) > fc_max:
            E(f"{fid}: first decisive beat of the oner after {fc_max} s")
        gp = next((s for s in fs if s["source"] in ("gameplay", "rig")), None)
        if not gp or gp["t0"] > P["first_gameplay_max_s"]:
            E(f"{fid}: first gameplay after {P['first_gameplay_max_s']} s")
        if any(s["source"] == "card" and s["t0"] < (gp["t0"] if gp else 99) for s in fs):
            E(f"{fid}: a card/logo comes before the first gameplay")
        run, prev = 1, None
        for s in fs:
            g = s.get("similar_group")
            run = run + 1 if g and g == prev else 1
            prev = g
            if run > P["max_similar_run"]:
                W(f"{fid}: more than {P['max_similar_run']} similar shots in a row ({g}) at {s['id']}")
        end = fs[-1]
        d_end = end["t1"] - end["t0"]
        if end["source"] != "card":
            E(f"{fid}: does not end on a card (title + call to action)")
        elif not (P["end_card_s"][0] - 0.6 <= d_end <= P["end_card_s"][1] + 0.01):
            W(f"{fid}: end card {d_end:.1f} s (aim {P['end_card_s'][0]}-{P['end_card_s'][1]} s)")
        credit = brand.get("credit")
        if credit and credit not in (end.get("text") or "") and fid in ("main", "vertical30"):
            E(f"{fid}: end card without the credit line '{credit}'")
        for s in fs:
            d = s["t1"] - s["t0"]
            txt = s.get("text") or ""
            shown = s.get("text_hold_s") or d
            if txt and txt != "-" and not txt.startswith("(game"):
                w = _words(re.sub(r"\(.*?\)", "", txt))
                if w and shown / w < T["s_per_word"] - 1e-6:
                    E(f"{s['id']}: '{txt}' needs {w * T['s_per_word']:.1f} s, has {shown:.1f} s")
                if w > T["max_words_card"] + 2:
                    W(f"{s['id']}: {w} words on screen (keep to ~{T['max_words_card']})")
            for rx in re_forbid:
                for fld in ("text", "screen"):
                    if s.get(fld) and rx.search(s[fld]) and fld == "text":
                        E(f"{s['id']}: forbidden word in public text: {rx.pattern}")
            for nm in names:
                if nm and nm.lower() in txt.lower():
                    E(f"{s['id']}: name '{nm}' in public text (credit only {credit})")
            if s.get("static_s", 0) > P["static_max_s"]:
                E(f"{s['id']}: still UI {s['static_s']} s > {P['static_max_s']} s")
            if s["source"] == "ui" and not s.get("action"):
                E(f"{s['id']}: UI shot without an action (what moves / gets chosen)")
            if vertical and s.get("text_box"):
                x, y, w_, h = s["text_box"]
                if x < SZ["left"] or y < SZ["top"] or x + w_ > 1080 - SZ["right"] or y + h > 1920 - SZ["bottom"]:
                    E(f"{s['id']}: text box {s['text_box']} outside the vertical safe zone")
            if s.get("text_cap_px"):
                hgt = 1920 if vertical else 1080
                need = (T["min_cap_height_vertical"] if vertical else T["min_cap_height_wide"]) * hgt
                if s["text_cap_px"] < need:
                    E(f"{s['id']}: text {s['text_cap_px']} px tall < {need:.0f} px (phone legibility)")
    m = spec.get("music") or {}
    if m.get("voice"):
        E("voice-over is on: the owner said no voice")
    for a in spec.get("assets") or []:
        lic = a.get("licence") or ""
        if "NC" in lic.upper().replace("CONTENT", "") and "CC" in lic.upper():
            E(f"asset {a.get('id')}: non-commercial licence {lic}")
        elif not any(lic.startswith(x) for x in OK_LICENCES) and "[DA VERIFICARE]" not in lic:
            W(f"asset {a.get('id')}: licence '{lic}' not in the clean list {OK_LICENCES}")
        if "[DA VERIFICARE]" in lic and a.get("status") == "final":
            E(f"asset {a.get('id')}: final but licence still [DA VERIFICARE]")
    rid = rule_ids()
    for r in (spec.get("prompt") or {}).get("rules_applied", []):
        if r not in rid:
            W(f"rules_applied: unknown craft rule {r}")
    if not (spec.get("prompt") or {}).get("negative_extra") and not C.get("negative_base"):
        E("no negative prompt")
    return issues


# ----------------------------------------------------------------------------- build outputs
def fmt_t(x: float) -> str:
    return f"{x:05.2f}"


def negative_list(spec: dict) -> list[str]:
    seen, out = set(), []
    for x in craft()["negative_base"] + ((spec.get("prompt") or {}).get("negative_extra") or []):
        if x.lower() not in seen:
            seen.add(x.lower()); out.append(x)
    return out


def shots_of(spec: dict, fid: str) -> list[dict]:
    return sorted([s for s in spec.get("shots") or [] if s.get("format") == fid], key=lambda s: s["t0"])


def prompt_text(spec: dict) -> str:
    """The master prompt (English): long, explicit, drives brag --full / HyperFrames. Built from the spec + craft rules."""
    C = craft(); R = {r["id"]: r for r in C["rules"]}
    p = spec.get("prompt") or {}; b = spec.get("brand") or {}; mu = spec.get("music") or {}
    L = []
    L += [f"# MASTER TRAILER PROMPT: {spec['game']} trailer {spec['version']}", ""]
    L += p.get("intro", [])
    L += ["", "## 1. Mission and audience"] + p.get("mission", [])
    L += ["", "## 2. The concept in one breath"] + [f"- {x}" for x in (spec.get("concept") or {}).get("five_lines", [])]
    L += ["", "## 3. Deliverables"]
    for f in spec.get("formats") or []:
        L.append(f"- **{f['id']}**: {f.get('label', '')}, {f.get('res')} {f.get('aspect')} @ {f.get('fps', 60)} fps, {f.get('target_s')} s, for {', '.join(f.get('platforms', []))}. {f.get('note', '')}".rstrip())
    L += ["", "## 4. Tool invocation (mandatory)"] + p.get("tooling", [])
    L += ["", "## 5. Story, beat by beat (main cut)"] + p.get("story", [])
    for fid in [f["id"] for f in spec.get("formats") or []]:
        fs = shots_of(spec, fid)
        if not fs:
            continue
        L += ["", f"### Shot list: {fid}"]
        for s in fs:
            rec = s.get("record") or {}
            L.append(f"- **{s['id']} [{fmt_t(s['t0'])}-{fmt_t(s['t1'])}] {s['section']}** ({s['source']}). ON SCREEN: {s['screen']} CAMERA: {s['camera']} "
                     f"TEXT: {s['text']} AUDIO: {s['audio']}" + (f" ACTION: {s['action']}" if s.get("action") else "")
                     + (f" FOOTAGE: take `{rec.get('take')}`." if rec.get("take") else "") + (f" WHY: {s['why']}" if s.get("why") else ""))
    L += ["", "## 6. Editing rules"] + [f"- {x}" for x in p.get("edit_rules", [])]
    L += ["", "## 7. Camera and framing rules"] + [f"- {x}" for x in p.get("camera_rules", [])]
    L += ["", "## 8. Look of the footage (current game build)"] + [f"- {x}" for x in p.get("look", [])]
    L += ["", "## 9. Typography, colour and brand"] + [f"- {x}" for x in p.get("typography", [])]
    if b.get("palette"):
        L.append("- Palette tokens: " + ", ".join(f"{k} {v}" for k, v in b["palette"].items()) + ".")
    L.append(f"- The only credit anywhere (video, metadata, description, share copy): **{b.get('credit', '')}**.")
    L += ["", "## 10. Music and sound design"] + [f"- {x}" for x in mu.get("rules", [])]
    if mu.get("sync"):
        L += ["", "### Sync points (main cut)"] + [f"- {x['t']:05.2f} s: {x['what']}" for x in mu["sync"]]
    L += ["", "## 11. Formats and cut-downs"] + [f"- {x}" for x in p.get("formats_rules", [])]
    L += ["", "## 12. Craft rules this trailer must satisfy (from real sources)"]
    for rid in p.get("rules_applied", []):
        r = R.get(rid)
        if r:
            L.append(f"- [{rid}] {r['rule']} (source: {r['sources'][0]['what']}, {r['sources'][0].get('published') or r['sources'][0]['date']})")
    L += ["", "## 13. Owner's mandatory notes (non-negotiable)"] + [f"- {x}" for x in p.get("owner_notes", [])]
    L += ["", "## 14. Assets"] + [f"- {x}" for x in p.get("assets_rules", [])]
    L += ["", "## 15. Done means"] + [f"- {x}" for x in p.get("done", [])]
    return "\n".join(L).strip() + "\n"


def negative_text(spec: dict) -> str:
    return "NEGATIVE PROMPT (never do any of this):\n" + "\n".join(f"- {x}" for x in negative_list(spec)) + "\n"


def qa_list(spec: dict) -> list[dict]:
    C = craft(); P = C["specs"]["pacing"]; L = C["specs"]["loudness"]
    auto = [("first_cut", f"Primo taglio o colpo deciso entro {P['first_cut_max_s']} s (verticale {P['vertical_first_cut_max_s']} s)", "qa"),
            ("first_gameplay", f"Gioco vero entro {P['first_gameplay_max_s']} s, niente logo prima", "check"),
            ("shot_length", "Inquadratura media per terzo del trailer misurata e confrontata con i concorrenti", "qa"),
            ("loudness", f"Volume {L['integrated_lufs']} LUFS ± {L['tolerance_lu']} e picchi ≤ {L['true_peak_dbtp']} dBTP", "qa"),
            ("static", f"Nessuna immagine ferma o schermata UI immobile oltre {P['static_max_s']} s", "qa"),
            ("black", "Nessun fotogramma nero nei primi 10 s", "qa"),
            ("spec", "1920x1080 60 fps H.264/AAC (Steam), 1080x1920 per il verticale", "qa"),
            ("text_phone", "Scritte leggibili su un telefono (altezza minima, 0,3 s per parola, una alla volta)", "check"),
            ("safe_zone", "Testi verticali dentro la zona sicura di TikTok/Reels/Shorts", "check"),
            ("end_card", "Cartello finale 3-4 s con titolo, invito giusto per la data e solo il credito ufficiale", "check"),
            ("negative", "Niente di quello che c'è nel prompt negativo (controllo fotogramma per fotogramma)", "manuale"),
            ("muted", "Si capisce tutto a volume zero", "manuale + panel"),
            ("owner_notes", "Ogni nota obbligatoria del proprietario rispettata", "manuale"),
            ("ledger", "Ogni musica, suono e immagine nel registro dei crediti con licenza pulita", "check"),
            ("panel", "Panel di spettatori alla cieca con trailer veri del genere come ancore", "panel")]
    out = [dict(id=i, what=w, how=h) for i, w, h in auto]
    out += [dict(id=f"x{i + 1}", what=x, how="manuale") for i, x in enumerate(spec.get("qa_extra") or [])]
    return out


def storyboard_md(spec: dict) -> str:
    L = [f"# {spec['game']}: storyboard del trailer {spec['version']} ({spec.get('date', '')})", "",
         "Una riga per inquadratura. Tempi in secondi. Fonte: `trailer.json` (non modificare questo file a mano: rigeneralo con `trailer_kit.py build`).", ""]
    for f in spec.get("formats") or []:
        fs = shots_of(spec, f["id"])
        if not fs:
            if f.get("derive_from"):
                L += [f"## {f['id']} · {f.get('label', '')}", "", f"Derivato da `{f['derive_from']}`: {f.get('note', '')}", ""]
            continue
        L += [f"## {f['id']} · {f.get('label', '')} · {f.get('res')} · {fs[-1]['t1']:.1f} s", "",
              "| # | Tempo | Parte | Cosa si vede | Camera | Testo | Audio | Come girarla |", "|---|---|---|---|---|---|---|---|"]
        for s in fs:
            r = s.get("record") or {}
            how = "; ".join(x for x in (r.get("scene"), r.get("setup"), r.get("camera"), r.get("events")) if x) or "—"
            L.append(f"| {s['id']} | {s['t0']:.2f}-{s['t1']:.2f} | {s['section']} | {s['screen']} | {s['camera']} | {s['text']} | {s['audio']} | {how} |")
        L.append("")
    return "\n".join(L)


def assets_md(spec: dict) -> str:
    C = craft()
    L = [f"# Piano degli asset del trailer {spec['version']}", "",
         "Regola: prima gli asset del gioco (già in licenza), poi quelli fatti da noi con il codice, poi quelli trovati online con licenza pulita. "
         "Ogni file va nel registro `credits-ledger.csv` **prima** di entrare nel montaggio.", "",
         "| ID | Tipo | Cosa | Come | Fonte | Licenza | Credito | Stato |", "|---|---|---|---|---|---|---|---|"]
    for a in spec.get("assets") or []:
        L.append(f"| {a.get('id')} | {a.get('kind')} | {a.get('what')} | {a.get('plan')} | {a.get('source', '')} | {a.get('licence')} | {a.get('credit', '')} | {a.get('status', 'todo')} |")
    L += ["", "## Dove cercare (licenze verificate il " + C["generated"] + ")", "", "| Fonte | Tipo | Licenza | Uso commerciale | Credito | Note |", "|---|---|---|---|---|---|"]
    for s in C["asset_sources"]:
        L.append(f"| [{s['name']}]({s['url']}) | {', '.join(s['kind'])} | {s['licence']} | {s['commercial']} | {s['attribution']} | {s['notes']} |")
    L += ["", "## Da non usare", ""] + [f"- **{x['what']}**: {x['why']}" for x in C["avoid_sources"]]
    L += ["", "## Creare con il codice (come farebbe una persona)", "",
          "```bash", "python3 <skill>/scripts/research/trailer_kit.py synth whoosh launch/trailer/<v>/audio/whoosh_01.wav --seed 1 --ledger launch/trailer/<v>/credits-ledger.csv",
          "python3 <skill>/scripts/research/trailer_kit.py synth stinger launch/trailer/<v>/audio/stinger_end.wav --bpm 132 --ledger ...", "```", "",
          "Sintesi deterministica (onde, rumore filtrato, inviluppi), nessun modello generativo. Si possono anche ritoccare a mano in un editor audio. "
          "Per le immagini: carte e adesivi disegnati in HTML/CSS/SVG dentro HyperFrames con i token del gioco, o renderizzati dal gioco stesso.", "",
          "**Steam e l'AI [DA VERIFICARE]:** Steam chiede di dichiarare i contenuti generati con l'AI anche nel marketing. Non è scritto se musica o immagini "
          "scritte con codice da un assistente contino: controllare la pagina Steamworks del questionario dei contenuti il giorno della pubblicazione e far decidere il proprietario. "
          "Se il dubbio resta, usare solo asset del gioco e CC0 trovati online.", ""]
    return "\n".join(L)


def ledger_rows(spec: dict) -> list[dict]:
    out = []
    for a in spec.get("assets") or []:
        out.append({k: a.get(k, "") for k in LEDGER_FIELDS} | {"id": a.get("id"), "kind": a.get("kind"), "title": a.get("what"),
                    "source_url": a.get("source", ""), "made_by": a.get("made_by", ""), "how_made": a.get("plan", ""), "used_in": spec["version"],
                    "credit_line": a.get("credit", ""), "date": a.get("date", spec.get("date", "")), "status": a.get("status", "todo")})
    return out


def write_ledger(path: str, rows: list[dict], keep_existing: bool = True) -> None:
    old = []
    if keep_existing and os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            old = list(csv.DictReader(f))
    by = {r["id"]: r for r in old}
    for r in rows:
        by[r["id"]] = {**by.get(r["id"], {}), **{k: v for k, v in r.items() if v not in (None, "")}}
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in by.values():
            w.writerow(r)


def recording_brief(spec: dict) -> dict:
    takes = {}
    for s in spec.get("shots") or []:
        if s["source"] not in ("gameplay", "rig", "ui"):
            continue
        r = s.get("record") or {}
        k = r.get("take") or s["id"]
        t = takes.setdefault(k, dict(take=k, scene=r.get("scene"), setup=r.get("setup"), camera=r.get("camera"), hud=r.get("hud"),
                                     events=r.get("events"), duration_s=0.0, handles_s=r.get("handles_s", 1.5), takes=r.get("takes", 3),
                                     notes=r.get("notes"), used_by=[], look=r.get("look") or (spec.get("recording") or {}).get("look")))
        t["used_by"].append(f"{s['format']}:{s['id']}")
        t["duration_s"] = round(max(t["duration_s"], (r.get("duration_s") or (s["t1"] - s["t0"]))), 2)
    rec = spec.get("recording") or {}
    return dict(game=spec["game"], version=spec["version"], date=spec.get("date"), contract="launch -> dev handoff (references/08-trailer.md §H)",
                rules=rec.get("rules", []), capture=rec.get("capture", {}), takes=list(takes.values()))


def brief_md(b: dict) -> str:
    L = [f"# Brief di registrazione: trailer {b['version']} di {b['game']}", "",
         "Per chi gira le riprese nel gioco (skill `game-developer` o una persona). Il lato lancio scrive questo file; il lato sviluppo lo legge e registra. "
         "Le riprese partono **solo** quando il proprietario lo chiede.", "", "## Regole per ogni ripresa", ""] + [f"- {x}" for x in b["rules"]]
    if b.get("capture"):
        L += ["", "## Impostazioni di cattura", ""] + [f"- **{k}**: {v}" for k, v in b["capture"].items()]
    L += ["", "## Riprese", "", "| Ripresa | Scena | Preparazione | Camera | HUD | Eventi da marcare | Durata (s) | Prese | Usata in | Note |", "|---|---|---|---|---|---|---|---|---|---|"]
    for t in b["takes"]:
        L.append(f"| `{t['take']}` | {t['scene']} | {t['setup'] or '—'} | {t['camera'] or '—'} | {t['hud'] or '—'} | {t['events'] or '—'} | "
                 f"{t['duration_s']} + {t['handles_s']} | {t['takes']} | {', '.join(t['used_by'])} | {t['notes'] or ''} |")
    return "\n".join(L) + "\n"


def qa_md(items: list[dict]) -> str:
    return "# Controlli di qualità del trailer\n\n" + "\n".join(f"- [ ] **{x['id']}** {x['what']} _({x['how']})_" for x in items) + "\n"


def prompt_md(spec: dict, bench: list | None) -> str:
    oq = spec.get("open_questions") or []
    L = [f"# Trailer {spec['version']} di {spec['game']}: PROMPT", "",
         f"Aggiornato il {spec.get('date', '')}. Stato: **{spec.get('status', 'prompt')}** (nessuna ripresa, nessun render). "
         "Il prompt è in inglese perché lo leggono brag e HyperFrames; il resto è in italiano.", ""]
    if oq:
        L += ["## Domande aperte (con la mia scelta di default)", "", "| # | Domanda | Default che uso se non rispondi | Perché |", "|---|---|---|---|"]
        L += [f"| {i} | {q['q']} | {q['default']} | {q.get('why', '')} |" for i, q in enumerate(oq, 1)]
        L.append("")
    c = spec.get("concept") or {}
    if c:
        L += ["## Il concetto in 5 righe", ""] + [f"{i}. {x}" for i, x in enumerate(c.get("five_lines", []), 1)] + [""]
    if spec.get("hook_current"):
        h = spec["hook_current"]
        L += ["## Il nostro aggancio oggi, contro i concorrenti (onesto)", ""] + [f"- {x}" for x in h.get("points", [])] + [""]
    if spec.get("interview"):
        L += ["## Intervista (risposte e consigli)", "", "| Tema | Domanda | Risposta | Consiglio e compromesso | Fonte |", "|---|---|---|---|---|"]
        L += [f"| {x.get('topic', '')} | {x['q']} | {x['answer']} | {x.get('advice', '')} | {x.get('source', '')} |" for x in spec["interview"]] + [""]
    if spec.get("tools"):
        t = spec["tools"]
        L += ["## Strumenti (controllati il " + str(t.get("checked")) + ")", ""]
        for k in ("brag", "hyperframes"):
            v = t.get(k)
            L.append(f"- **{k}**: " + (f"{v.get('source')} @ {v.get('hash')} (aggiornato {v.get('updated')}); aggiornare con `{v.get('how_to_update')}`" if v else "non trovato"))
        L.append(f"- **HyperFrames CLI**: {t.get('hyperframes_cli') or 'non controllato'} · **ffmpeg** {t.get('ffmpeg') or 'assente'}")
        if (t.get("brag") or {}).get("slim_auto"):
            L.append("- brag passa da solo a brag-slim su Opus 5.5: per il trailer si usa **sempre `--full`**, senza `--voice`.")
        L.append("")
    if bench:
        L += ["## Concorrenti: i loro trailer misurati", "", bench_md(bench)]
    L += ["## MASTER PROMPT (positivo)", "", "Copia tutto il blocco qui sotto.", "", "````markdown", prompt_text(spec).rstrip(), "````", "",
          "## NEGATIVE PROMPT", "", "````text", negative_text(spec).rstrip(), "````", "",
          "## Fonti delle regole", ""]
    R = {r["id"]: r for r in craft()["rules"]}
    for rid in (spec.get("prompt") or {}).get("rules_applied", []):
        r = R.get(rid)
        if r:
            L.append(f"- **{rid}** ({r['strength']}): {r['rule_it']} " + " · ".join(f"[{s['what']}]({s['url']}) (letto {s['date']})" for s in r["sources"]))
    L += ["", "Gli altri file: `storyboard.md` (inquadrature), `assets-plan.md` e `credits-ledger.csv` (musica, suoni, immagini), "
          "`recording-brief.md` (riprese per il lato sviluppo), `qa-checklist.md` (controlli).", ""]
    return "\n".join(L)


def _rel(path: str) -> str:
    try:
        r = os.path.relpath(path)
        return (path if r.startswith("..") else r).replace("\\", "/")
    except ValueError:                                   # other drive on Windows
        return path.replace("\\", "/")


def build(spec: dict, out_dir: str, bench: list | None) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    w = lambda name, txt: open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n").write(txt)
    w("PROMPT.md", prompt_md(spec, bench))
    w("storyboard.md", storyboard_md(spec))
    sb = dict(game=spec["game"], version=spec["version"], date=spec.get("date"), formats=spec.get("formats"), shots=spec.get("shots"))
    write_json(sb, os.path.join(out_dir, "storyboard.json"))
    w("assets-plan.md", assets_md(spec))
    write_ledger(os.path.join(out_dir, "credits-ledger.csv"), ledger_rows(spec))
    b = recording_brief(spec)
    write_json(b, os.path.join(out_dir, "recording-brief.json")); w("recording-brief.md", brief_md(b))
    qa = qa_list(spec); w("qa-checklist.md", qa_md(qa))
    kit = dict(game=spec["game"], version=spec["version"], date=spec.get("date"), status=spec.get("status", "prompt"),
               concept=spec.get("concept"), open_questions=spec.get("open_questions"), hook_current=spec.get("hook_current"),
               prompt=prompt_text(spec), negative=negative_text(spec), formats=spec.get("formats"), shots=spec.get("shots"),
               bench=bench, qa=qa, tools=spec.get("tools"), issues=[list(x) for x in check_spec(spec)], dir=_rel(out_dir))
    write_json(kit, os.path.join(out_dir, "kit.json"))
    return kit


# ----------------------------------------------------------------------------- QA of a real render
def qa_render(m: dict, spec: dict, fid: str) -> list[dict]:
    C = craft(); P = C["specs"]["pacing"]; LD = C["specs"]["loudness"]; S = C["specs"]["steam"]
    f = next((x for x in spec.get("formats") or [] if x["id"] == fid), {})
    vertical = f.get("aspect") == "9:16"
    res = []
    add = lambda k, ok, val, need: res.append(dict(id=k, ok=ok, value=val, need=need))
    fc = m.get("first_cut_s")
    lim = P["vertical_first_cut_max_s"] if vertical else P["first_cut_max_s"]
    add("first_cut", fc is not None and fc <= lim, fc, f"<= {lim} s")
    if f.get("target_s") and m.get("duration_s"):
        add("duration", abs(m["duration_s"] - f["target_s"]) <= max(1.0, f["target_s"] * 0.1), m["duration_s"], f"{f['target_s']} s ±10%")
    add("avg_shot_by_third", True, m.get("avg_shot_by_third"), "info: compare with bench")
    if m.get("lufs_i") is not None:
        add("loudness", abs(m["lufs_i"] - LD["integrated_lufs"]) <= LD["tolerance_lu"], m["lufs_i"], f"{LD['integrated_lufs']} ± {LD['tolerance_lu']} LUFS")
    if m.get("true_peak_dbtp") is not None:
        add("true_peak", m["true_peak_dbtp"] <= LD["true_peak_dbtp"] + 0.05, m["true_peak_dbtp"], f"<= {LD['true_peak_dbtp']} dBTP")
    end_s = (m.get("duration_s") or 0) - (P["end_card_s"][1] + 0.5)
    frozen = [fr for fr in (m.get("frozen") or []) if fr[0] < end_s]
    add("static", not frozen, frozen, f"no still > {P['static_max_s']} s before the end card")
    early_black = [b for b in (m.get("black") or []) if b[0] < 10]
    add("black", not early_black, early_black, "no black in the first 10 s")
    if vertical:
        add("spec", (m.get("width"), m.get("height")) == (1080, 1920), f"{m.get('width')}x{m.get('height')}", "1080x1920")
    else:
        add("spec", (m.get("width"), m.get("height")) == (1920, 1080) and (m.get("fps") or 0) in (30, 29.97, 60, 59.94) and m.get("vcodec") == "h264",
            f"{m.get('width')}x{m.get('height')} {m.get('fps')} fps {m.get('vcodec')}/{m.get('acodec')}", f"{S['max_res']} 30/60 fps H.264/AAC")
    return res


# ----------------------------------------------------------------------------- blind viewer panel
def panel_init(spec: dict, render: str, out_dir: str) -> dict:
    if not render or not os.path.exists(render):
        raise SystemExit("panel: no render on disk yet. The viewer panel judges a real video, never a storyboard.")
    anchors = (spec.get("panel") or {}).get("anchors") or []
    if len(anchors) < 3:
        raise SystemExit("panel: need at least 3 real anchors (2+ strong genre trailers and 1 weak) in spec.panel.anchors")
    items = [dict(code=None, kind="ours", name=spec["game"], src=render)] + [dict(code=None, kind="anchor", **a) for a in anchors]
    rnd = random.Random(spec.get("version", "v"))
    rnd.shuffle(items)
    for i, it in enumerate(items):
        it["code"] = f"T{i + 1}"
    os.makedirs(out_dir, exist_ok=True)
    key = dict(items=items, created=dt.date.today().isoformat())
    write_json(key, os.path.join(out_dir, "panel-key.json"))
    q = (spec.get("panel") or {}).get("questions") or [
        "Dopo 5 secondi: che gioco è e cosa fai? (una frase)", "Hook 0-10: ti fermi a guardare?", "Chiarezza 0-10: hai capito il giro di una partita?",
        "Divertimento visto 0-10", "Ritmo 0-10", "Lo metteresti in wishlist? sì / forse / no", "Il momento che ricordi", "Cosa ti ha confuso o annoiato"]
    brief = ["# Panel di spettatori: trailer alla cieca (SIMULATO)", "",
             "Stesso metodo del focus group (`references/04-focus-group.md` 7.0b-7.0e): gli stessi tester del roster, giocatori veri del genere, non critici. "
             "Vedono i trailer con un codice, in ordine casuale, senza sapere quale è il nostro. Prima a volume zero (i primi 10 s), poi con l'audio.", "",
             "Ancore: trailer veri del genere con il loro esito reale. Se il punteggio medio di un'ancora si sposta di oltre 8 punti dalla sua fascia, "
             "il panel è starato: si ricalibra prima di leggere il nostro voto.", "", "## Trailer da guardare", ""]
    brief += [f"- **{it['code']}**: {it['src']}" for it in items]
    brief += ["", "## Domande per ogni trailer", ""] + [f"{i}. {x}" for i, x in enumerate(q, 1)]
    brief += ["", "## Formato dei risultati (`panel-results.json`)", "", "```json",
              '{"scores": [{"tester": "A01", "code": "T1", "hook": 7, "clarity": 6, "fun": 7, "pace": 6, "wishlist": "forse", "remember": "...", "confused": "..."}]}', "```", ""]
    open(os.path.join(out_dir, "panel-brief.md"), "w", encoding="utf-8").write("\n".join(brief))
    return key


def panel_score(results: dict, key: dict) -> dict:
    by = {it["code"]: it for it in key["items"]}
    agg: dict = {}
    for s in results.get("scores", []):
        nums = [s.get(k) for k in ("hook", "clarity", "fun", "pace") if isinstance(s.get(k), (int, float))]
        if not nums:
            continue
        a = agg.setdefault(s["code"], dict(n=0, sum=0.0, wish=0))
        a["n"] += 1; a["sum"] += sum(nums) / len(nums) * 10; a["wish"] += {"sì": 1.0, "si": 1.0, "yes": 1.0, "forse": 0.5, "maybe": 0.5}.get(str(s.get("wishlist", "")).lower(), 0)
    rows, drift = [], []
    for code, a in agg.items():
        it = by.get(code, {})
        raw = round(a["sum"] / a["n"], 1)
        row = dict(code=code, kind=it.get("kind"), name=it.get("name"), n=a["n"], raw=raw, wishlist_pct=round(100 * a["wish"] / a["n"]))
        if it.get("kind") == "anchor" and it.get("band"):
            mid = sum(it["band"]) / 2
            row["band"] = it["band"]; row["drift"] = round(raw - mid, 1)
            drift.append(raw - mid)
        rows.append(row)
    shift = round(sum(drift) / len(drift), 1) if drift else 0.0
    for r in rows:
        r["normalised"] = round(r["raw"] - shift, 1)
    bad = [r for r in rows if r.get("drift") is not None and abs(r["drift"]) > 8]
    return dict(rows=sorted(rows, key=lambda r: -r["normalised"]), anchor_shift=shift, recalibrate=bool(bad),
                note="SIMULATO: ordina i problemi del trailer, non prevede le wishlist.")


# ----------------------------------------------------------------------------- code-made audio (stdlib synthesis)
SR = 44100


def _env(n: int, a: float, d: float) -> list[float]:
    out = []
    for i in range(n):
        t = i / SR
        out.append(min(1.0, t / max(a, 1e-4)) * math.exp(-max(0.0, t - a) / max(d, 1e-4)))
    return out


def _lp(x: list[float], k: float) -> list[float]:
    y, o = 0.0, []
    for v in x:
        y += k * (v - y); o.append(y)
    return o


def synth(kind: str, seed: int = 1, bpm: float = 132, bars: int = 8) -> list[float]:
    rnd = random.Random(seed)
    noise = lambda n: [rnd.uniform(-1, 1) for _ in range(n)]
    if kind == "whoosh":
        n = int(0.55 * SR); x = noise(n); o, y = [], 0.0
        for i, v in enumerate(x):
            p = i / n; k = 0.02 + 0.25 * math.sin(math.pi * p) ** 2
            y += k * (v - y); o.append(y * math.sin(math.pi * p) ** 1.5 * 2.2)
        return o
    if kind == "pop":
        n = int(0.12 * SR); e = _env(n, 0.002, 0.03)
        return [math.sin(2 * math.pi * (900 - 600 * i / n) * i / SR) * e[i] * 0.9 for i in range(n)]
    if kind == "tick":
        n = int(0.05 * SR); e = _env(n, 0.0005, 0.008); x = noise(n)
        return [(0.6 * math.sin(2 * math.pi * 2400 * i / SR) + 0.4 * x[i]) * e[i] for i in range(n)]
    if kind == "hit":
        n = int(0.7 * SR); e = _env(n, 0.002, 0.18); x = _lp(noise(n), 0.08); ph, o = 0.0, []
        for i in range(n):
            f = 40 + 110 * math.exp(-i / SR / 0.05); ph += 2 * math.pi * f / SR
            o.append((0.9 * math.sin(ph) + 0.5 * x[i] * math.exp(-i / SR / 0.04)) * e[i])
        return o
    if kind == "riser":
        n = int(1.6 * SR); x = noise(n); o, y, ph = [], 0.0, 0.0
        for i, v in enumerate(x):
            p = i / n; y += (0.01 + 0.3 * p * p) * (v - y); ph += 2 * math.pi * (200 * 2 ** (3 * p)) / SR
            o.append((0.6 * y + 0.25 * math.sin(ph)) * p ** 1.8)
        return o
    if kind in ("stinger", "music"):
        beat = 60.0 / bpm
        prog = [(0, 4, 7, 11), (5, 9, 12, 16), (2, 5, 9, 12), (7, 11, 14, 17)]          # Imaj7 IVmaj7 ii V7 (C major)
        base = 261.63 / 2
        if kind == "stinger":
            n = int(beat * 3 * SR); o = [0.0] * n
            for j, step in enumerate((0, 4, 7, 12)):
                st = int(j * beat / 4 * SR); e = _env(n - st, 0.004, 0.35 if j < 3 else 1.1)
                f = base * 2 * 2 ** (step / 12)
                for i in range(n - st):
                    t = i / SR; o[st + i] += 0.25 * e[i] * (math.sin(2 * math.pi * f * t) + 0.3 * math.sin(4 * math.pi * f * t))
            return o
        total = int(bars * 4 * beat * SR); o = [0.0] * total
        for bar in range(bars):
            ch = prog[bar % 4]
            for b_ in range(4):
                swing = 0.0 if b_ % 2 == 0 else beat * 0.08
                t0 = (bar * 4 + b_) * beat + swing
                st = int(t0 * SR)
                f = base / 2 * 2 ** ((ch[(b_ * 3) % 4] if b_ else ch[0]) / 12)       # walking-ish bass
                e = _env(int(beat * SR), 0.005, beat * 0.5)
                for i in range(len(e)):
                    if st + i < total:
                        o[st + i] += 0.35 * e[i] * math.sin(2 * math.pi * f * i / SR)
                if b_ in (1, 3):                                                       # chord stabs on 2 and 4
                    e2 = _env(int(beat * 0.6 * SR), 0.003, beat * 0.18)
                    for i in range(len(e2)):
                        if st + i < total:
                            t = i / SR
                            o[st + i] += 0.07 * e2[i] * sum(math.sin(2 * math.pi * base * 2 * 2 ** (s / 12) * t) for s in ch)
                for h in (0.0, beat * 0.66):                                           # swung hi-hat
                    hs = int((t0 + h) * SR); hn = int(0.04 * SR); x = noise(hn); e3 = _env(hn, 0.0005, 0.012)
                    for i in range(hn):
                        if hs + i < total:
                            o[hs + i] += 0.08 * x[i] * e3[i]
        return o
    raise SystemExit(f"unknown synth kind {kind}")


def write_wav(path: str, x: list[float]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    peak = max(1e-9, max(abs(v) for v in x))
    g = 0.89 / peak                                                                     # about -1 dBFS sample peak
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, v * g)) * 32767)) for v in x))


# ----------------------------------------------------------------------------- status page section
def latest_kit(root: str) -> dict | None:
    kits = []
    for p in glob.glob(os.path.join(root, "trailer", "*", "kit.json")):
        try:
            k = load_json(p)
            kits.append((str(k.get("date") or ""), k.get("version") or "", k))
        except Exception:  # noqa: BLE001
            pass
    return sorted(kits, key=lambda x: (x[0], x[1]))[-1][2] if kits else None


def status_section(root: str, esc, copy_btn) -> str | None:
    k = latest_kit(root)
    if not k:
        return None
    H = [f'<h2>Trailer {esc(k["version"])}: il prompt</h2><div class="card"><p>Stato: <strong>{esc(k.get("status"))}</strong> · aggiornato il {esc(k.get("date"))} · '
         f'file in <code>{esc(k.get("dir", ""))}</code>. Il prompt è in inglese (lo leggono brag e HyperFrames).</p>'
         f'<p>{copy_btn(k["prompt"] + chr(10) + k["negative"])} <span class="note">copia prompt positivo + negativo, pronti da incollare</span></p>'
         f'<details><summary>Leggi il prompt ({len(k["prompt"].split())} parole)</summary><pre style="white-space:pre-wrap">{esc(k["prompt"])}</pre></details>'
         f'<details><summary>Prompt negativo</summary><pre style="white-space:pre-wrap">{esc(k["negative"])}</pre></details></div>']
    if k.get("concept"):
        H.append('<h2>Il concetto in 5 righe</h2><div class="card"><ol>' + "".join(f"<li>{esc(x)}</li>" for x in k["concept"].get("five_lines", [])) + "</ol></div>")
    if k.get("open_questions"):
        H.append('<h2>Domande aperte</h2><div class="card wrap"><table><thead><tr><th>Domanda</th><th>Default</th></tr></thead><tbody>'
                 + "".join(f'<tr><td>{esc(q["q"])}</td><td>{esc(q["default"])}</td></tr>' for q in k["open_questions"]) + "</tbody></table></div>")
    for f in k.get("formats") or []:
        fs = sorted([s for s in k.get("shots") or [] if s.get("format") == f["id"]], key=lambda s: s["t0"])
        if not fs:
            continue
        cards = []
        for s in fs:
            r = s.get("record") or {}
            cards.append(f'<div class="card"><p class="sub"><strong>{esc(s["id"])}</strong> · {s["t0"]:.2f}-{s["t1"]:.2f} s · {esc(s["section"])}</p>'
                         f'<p><strong>Si vede:</strong> {esc(s["screen"])}</p><p><strong>Camera:</strong> {esc(s["camera"])}</p>'
                         f'<p><strong>Testo:</strong> {esc(s["text"])}</p><p><strong>Audio:</strong> {esc(s["audio"])}</p>'
                         f'<p class="note"><strong>Come girarla:</strong> {esc("; ".join(x for x in (r.get("scene"), r.get("setup"), r.get("camera"), r.get("events")) if x) or "—")}</p></div>')
        H.append(f'<h2>Storyboard {esc(f["id"])}: {esc(f.get("label", ""))} ({fs[-1]["t1"]:.0f} s)</h2><div class="grid g4">{"".join(cards)}</div>')
    if k.get("bench"):
        fm = lambda x: "—" if x is None or x == "" else esc(f"{x:g}" if isinstance(x, float) else x)
        rows = "".join(f'<tr><td>{esc(r["name"])}</td><td class="n">{fm(r["trailer_s"])}</td><td class="n">{fm(r["first_cut_s"])}</td><td class="n">{fm(r["avg_shot_s"])}</td>'
                       f'<td class="n">{fm(r["lufs_i"])}</td><td class="n">{fm(r["bpm"])}</td><td>{esc(r.get("hook_0_3s", ""))}</td><td>{esc(r.get("lesson", ""))}</td></tr>' for r in k["bench"])
        H.append('<h2>Trailer dei concorrenti</h2><div class="card wrap"><table><thead><tr><th>Gioco</th><th class="n">Durata (s)</th><th class="n">1° taglio (s)</th>'
                 '<th class="n">Inquadratura media (s)</th><th class="n">LUFS</th><th class="n">BPM</th><th>Primi 3 secondi</th><th>Lezione</th></tr></thead><tbody>'
                 + rows + '</tbody></table><p class="note">Durata, tagli, volume e tempo misurati con store_bench.py e trailer_kit.py measure; i primi 3 secondi e la lezione sono giudicati dai fotogrammi [OPINIONE]. BPM stimati: ±3, possibili errori di doppio/metà.</p></div>')
    if k.get("qa"):
        H.append('<h2>Controlli di qualità</h2><div class="card"><ul class="clean">' + "".join(f'<li>☐ <span><strong>{esc(x["what"])}</strong> <span class="note">({esc(x["how"])})</span></span></li>' for x in k["qa"]) + "</ul>"
                 + ("<p class='note'>Avvisi del controllo dello storyboard: " + esc("; ".join(f"{a}: {b}" for a, b in k["issues"])) + "</p>" if k.get("issues") else "<p class='note'>Controllo dello storyboard: nessun errore.</p>") + "</div>")
    return "".join(H)


# ----------------------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("craft"); s.add_argument("--topic"); s.add_argument("--applies")
    s = sub.add_parser("tools"); s.add_argument("--spec"); s.add_argument("--no-npx", action="store_true")
    s = sub.add_parser("measure"); s.add_argument("src", nargs="+"); s.add_argument("--name", action="append"); s.add_argument("--appid", action="append")
    s.add_argument("-o", "--out"); s.add_argument("--max-s", type=float, default=120)
    s = sub.add_parser("bench"); s.add_argument("pages"); s.add_argument("--measured"); s.add_argument("--spec"); s.add_argument("--md"); s.add_argument("-o", "--out")
    s = sub.add_parser("check"); s.add_argument("spec")
    s = sub.add_parser("build"); s.add_argument("spec"); s.add_argument("--out-dir"); s.add_argument("--bench"); s.add_argument("--strict", action="store_true")
    s = sub.add_parser("qa"); s.add_argument("render"); s.add_argument("--spec", required=True); s.add_argument("--format", default="main"); s.add_argument("-o", "--out"); s.add_argument("--md")
    s = sub.add_parser("panel"); s.add_argument("action", choices=["init", "score"]); s.add_argument("file", nargs="?"); s.add_argument("--spec"); s.add_argument("--render")
    s.add_argument("--out-dir"); s.add_argument("--key"); s.add_argument("--md")
    s = sub.add_parser("synth"); s.add_argument("kind"); s.add_argument("out"); s.add_argument("--seed", type=int, default=1); s.add_argument("--bpm", type=float, default=132)
    s.add_argument("--bars", type=int, default=8); s.add_argument("--ledger"); s.add_argument("--credit", default=""); s.add_argument("--used-in", default="")
    a = ap.parse_args()

    if a.cmd == "craft":
        for r in craft()["rules"]:
            if (not a.topic or r["topic"] == a.topic) and (not a.applies or a.applies in r["applies_to"]):
                print(f"[{r['id']}] ({r['strength']}) {r['rule_it']}\n    {r['rule']}\n    " + " | ".join(f"{x['url']} ({x['date']})" for x in r["sources"]))
    elif a.cmd == "tools":
        t = tools_versions(not a.no_npx)
        print(json.dumps(t, ensure_ascii=False, indent=1))
        if a.spec:
            sp = load_json(a.spec); sp["tools"] = t; write_json(sp, a.spec)
    elif a.cmd == "measure":
        res = []
        for i, src in enumerate(a.src):
            m = measure(src, (a.name or [None] * len(a.src))[i] if a.name and i < len(a.name) else None, a.max_s)
            if a.appid and i < len(a.appid):
                m["appid"] = int(a.appid[i]) if a.appid[i].isdigit() else a.appid[i]
            log(f"{m['name']}: {m.get('duration_s')} s, first cut {m.get('first_cut_s')}, avg shot {m.get('avg_shot_s')}, {m.get('lufs_i')} LUFS, ~{m.get('tempo_bpm_est')} BPM")
            res.append(m)
        if a.out:
            old = load_json(a.out) if os.path.exists(a.out) else []
            keep = [x for x in old if x.get("name") not in {m["name"] for m in res}]
            write_json(keep + res, a.out)
        else:
            print(json.dumps(res, ensure_ascii=False, indent=1))
    elif a.cmd == "bench":
        rows = bench_rows(load_json(a.pages), load_json(a.measured) if a.measured else None, load_json(a.spec) if a.spec else None)
        if a.md:
            open(a.md, "w", encoding="utf-8").write(f"# Trailer dei concorrenti (misurati il {dt.date.today()})\n\n" + bench_md(rows))
        write_json(rows, a.out) if a.out else print(bench_md(rows))
    elif a.cmd == "check":
        iss = check_spec(load_json(a.spec))
        for lv, m in iss:
            print(f"{lv} {m}")
        print(f"{sum(1 for x in iss if x[0] == 'ERROR')} errors, {sum(1 for x in iss if x[0] == 'WARN')} warnings")
        raise SystemExit(1 if any(x[0] == "ERROR" for x in iss) else 0)
    elif a.cmd == "build":
        sp = load_json(a.spec)
        iss = check_spec(sp)
        if a.strict and any(x[0] == "ERROR" for x in iss):
            for lv, m in iss:
                print(f"{lv} {m}")
            raise SystemExit("build --strict: fix the errors first")
        k = build(sp, a.out_dir or os.path.dirname(os.path.abspath(a.spec)), load_json(a.bench) if a.bench else None)
        log(f"wrote PROMPT.md ({len(k['prompt'].split())} words in the master prompt, {len(negative_list(sp))} negative items), storyboard, assets plan, "
            f"credits ledger, recording brief, QA list, kit.json in {k['dir']} · {sum(1 for x in iss if x[0] == 'ERROR')} errors, {sum(1 for x in iss if x[0] == 'WARN')} warnings")
    elif a.cmd == "qa":
        sp = load_json(a.spec); m = measure(a.render)
        res = qa_render(m, sp, a.format)
        out = dict(render=a.render, format=a.format, measured=m, checks=res, manual=[x for x in qa_list(sp) if "manuale" in x["how"] or x["how"] == "panel"])
        if a.out:
            write_json(out, a.out)
        txt = f"# QA automatico: {os.path.basename(a.render)} ({a.format})\n\n| Controllo | Esito | Valore | Serve |\n|---|---|---|---|\n" + "".join(
            f"| {c['id']} | {'OK' if c['ok'] else 'NO'} | {c['value']} | {c['need']} |\n" for c in res) + "\nControlli a mano: " + "; ".join(x["what"] for x in out["manual"]) + "\n"
        open(a.md, "w", encoding="utf-8").write(txt) if a.md else print(txt)
    elif a.cmd == "panel":
        if a.action == "init":
            k = panel_init(load_json(a.spec), a.render, a.out_dir or ".")
            log(f"panel brief with {len(k['items'])} trailers (codes shuffled) in {a.out_dir}")
        else:
            r = panel_score(load_json(a.file), load_json(a.key))
            txt = "| Codice | Tipo | Nome | n | Grezzo | Normalizzato | Wishlist % | Deriva |\n|---|---|---|---|---|---|---|---|\n" + "".join(
                f"| {x['code']} | {x['kind']} | {x['name']} | {x['n']} | {x['raw']} | {x['normalised']} | {x['wishlist_pct']} | {x.get('drift', '')} |\n" for x in r["rows"])
            txt += f"\nSpostamento delle ancore: {r['anchor_shift']} punti." + (" **RICALIBRARE: un'ancora deriva oltre 8 punti.**" if r["recalibrate"] else "") + f"\n{r['note']}\n"
            open(a.md, "w", encoding="utf-8").write(txt) if a.md else print(txt)
    elif a.cmd == "synth":
        x = synth(a.kind, a.seed, a.bpm, a.bars)
        write_wav(a.out, x)
        log(f"wrote {a.out} ({len(x) / SR:.2f} s, {a.kind}, seed {a.seed})")
        if a.ledger:
            write_ledger(a.ledger, [dict(id=f"SYN-{a.kind}-{a.seed}", file=a.out.replace("\\", "/"), kind="music" if a.kind == "music" else "sfx", title=f"{a.kind} (code-made)",
                                         author=a.credit, source_url="trailer_kit.py synth", licence="own", attribution_required="no", credit_line=a.credit,
                                         made_by=a.credit or "studio", how_made=f"deterministic synthesis, seed {a.seed}, bpm {a.bpm:g}", date=dt.date.today().isoformat(),
                                         used_in=a.used_in, status="draft", notes="no generative model")])


if __name__ == "__main__":
    main()
