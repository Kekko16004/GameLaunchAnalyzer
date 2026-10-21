#!/usr/bin/env python3
"""Understand a game project from its files, in a brand-new chat: engine and version, context documents, state, media, tools.

Why: a fresh chat knows nothing. The skill must not depend on what was said before, nor assume that the project is a "generic
game". This scan reads the disk (read-only, nothing is written unless you pass -o/--md) and reports:
  engine        Unreal (.uproject), Unity (ProjectSettings/ProjectVersion.txt), Godot (project.godot), Nucleon (project.ncproject),
                GameMaker, Defold, Love2D,
                Ren'Py, RPG Maker, Construct, and web/native frameworks (Phaser, three.js, Bevy, raylib, ...), with the version and
                engine-specific facts (plugins, render pipeline, scenes, Steamworks, MCP plugin enabled, GameDeveloperSkill files)
  docs          the Markdown/text files that explain the game, ranked (CLAUDE.md, AGENTS.md, GDD, GAME_CONTEXT, GAME_TASKS, README,
                roadmap, TODO...), with their first heading, so you read the right ones first
  artifacts     what other skills left behind: GDD.md (locked?), GAME_CONTEXT.md, GAME_TASKS.md (done/open), docs/gates, ASSET-LEDGER.md,
                screenshots/000-index.md, and this skill's own launch/ (STATUS.md, status.json)
  dev_link      the game-developer contract (references/dev-link.md): mode linked / launch-only / solo (same rule as
                game-developer's `gate_link.py detect`), DECISIONI.md (D-NNN count), docs/design-review/ (game-map, screen-map,
                runs, changes-since-wNN, "aggiornata al gate NN"), gates with the machine-readable header (last number, date,
                status), gate plans plan-wNN.md, and whether the two copies of the contract carry the same `contract:` version
  steam / itch  steam_appid.txt, vdf files, Steamworks plugin or package, .itch.toml
  media         screenshots, capsules and videos found in the usual folders (newest first)
  git           branch, last commits, remote host (credentials in the URL are removed)
  tools         executables on this machine (unity, UnrealEditor, godot, blender, ffmpeg, git, node, python, uvx, dotnet, steamcmd,
                butler), MCP servers CONFIGURED in the project (.mcp.json and similar: names and commands only, never env values or
                keys) and whether the Unreal MCP port answers on localhost (--no-probe to skip)
  genre hints   keyword counts over the documents: hints to confirm with the owner, never a verdict
The tools list is what the DISK says. What THIS chat can actually call (MCP tools, skills) must also be checked from the session
itself: see references/00a-bootstrap.md.

  python project_scan.py [--root .] [--max-docs 40] [-o launch/_raw/project_scan.json] [--md launch/_raw/project_scan.md] [--no-probe]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from urllib.parse import urlsplit

import common  # noqa: F401  (side effect: UTF-8 stdout)

SKIP_DIRS = {".git", "node_modules", "Library", "Intermediate", "Binaries", "Saved", "DerivedDataCache", "Temp", "obj", "bin", "Build", "Builds", "Logs",
             "UserSettings", ".vs", ".idea", "__pycache__", ".venv", "venv", "ThirdParty", "Plugins", "Packages", "PackageCache", ".godot", ".import", "target", "dist"}
DOC_EXT = (".md", ".txt", ".rst")
DOC_RANK = [  # (regex on lower-case file name, kind, score)
    (r"^claude\.md$", "claude", 100), (r"^agents\.md$", "agents", 95), (r"^gdd", "gdd", 98), (r"game[_ -]?design|design[_ -]?doc", "gdd", 90), (r"^game_context", "game_context", 97),
    (r"^game_tasks", "game_tasks", 96), (r"^readme", "readme", 85), (r"pitch|one[_ -]?pager|vision", "pitch", 80), (r"roadmap|milestone", "roadmap", 75), (r"^todo|backlog", "todo", 72),
    (r"changelog|release[_ -]?notes", "changelog", 60), (r"^status\.md$", "status", 70), (r"asset[_-]?ledger|credits|licen[sc]e", "assets", 55), (r"playtest|feedback", "playtest", 50),
    (r"design|lore|story|narrative|mechanic|level|economy|balance|marketing|press|steam|store", "design", 45), (r"notes?|ideas?|plan", "notes", 35)]
GENRES = {"roguelike": r"rogue-?like|rogue-?lite|permadeath|run-based", "platformer": r"platformer|jump(ing)? puzzle|metroidvania", "fps": r"\bfps\b|first[- ]person shooter|boomer shooter",
          "survival": r"survival|crafting|base building", "horror": r"horror|scary|jump ?scare", "puzzle": r"puzzle", "rpg": r"\brpg\b|jrpg|crpg|party-based", "strategy": r"strategy|rts|4x|tower defen[cs]e|tactics",
          "simulation": r"simulation|management|tycoon|colony|farming sim|city ?builder", "adventure": r"adventure|point[- ]and[- ]click|walking simulator", "racing": r"racing|driving",
          "deckbuilder": r"deck-?build|card game|roguelike deckbuilder", "co-op": r"\bco-?op\b|multiplayer", "narrative": r"visual novel|narrative|story[- ]rich", "action": r"action|hack and slash|beat 'em up|souls-?like"}
EXECS = {"unity": ["unity", "Unity.exe"], "unreal_editor": ["UnrealEditor", "UnrealEditor-Cmd", "UE4Editor"], "godot": ["godot", "godot4", "Godot"], "blender": ["blender"], "ffmpeg": ["ffmpeg"], "ffprobe": ["ffprobe"],
         "git": ["git"], "node": ["node"], "python": ["python3", "python"], "uvx": ["uvx"], "dotnet": ["dotnet"], "steamcmd": ["steamcmd"], "butler": ["butler"]}
MCP_FILES = [".mcp.json", ".cursor/mcp.json", ".vscode/mcp.json", ".claude/settings.json", ".claude/settings.local.json", "opencode.json", ".kilocode/mcp.json"]
MEDIA_DIRS = {"screenshots", "screenshot", "shots", "capsules", "capsule", "marketing", "press", "media", "trailer", "trailers", "art", "docs", "promo", "store"}
IMG, VID = (".png", ".jpg", ".jpeg", ".webp", ".gif"), (".mp4", ".mov", ".webm", ".mkv")


def read(path: str, limit: int = 60000) -> str:
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def walk(root: str, max_depth: int):
    root = os.path.abspath(root)
    base = root.count(os.sep)
    for d, dirs, files in os.walk(root):
        depth = d.count(os.sep) - base
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not (x.startswith(".") and x not in (".claude", ".cursor", ".vscode", ".kilocode"))] if depth < max_depth else []
        yield d, dirs, files


def count_ext(root: str, exts: tuple, cap: int = 200000) -> int:
    n = 0
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in (".git", "Library", "Intermediate", "Binaries", "Saved", "DerivedDataCache", "node_modules", ".godot")]
        n += sum(1 for f in files if f.lower().endswith(exts))
        if n > cap:
            break
    return n


# ---------------------------------------------------------------- engines
def detect_unreal(path: str) -> dict:
    j = {}
    try:
        j = json.loads(read(path))
    except ValueError:
        pass
    root = os.path.dirname(path)
    plugins = {p.get("Name"): p.get("Enabled", True) for p in j.get("Plugins", []) if isinstance(p, dict)}
    ini = read(os.path.join(root, "Config", "DefaultGame.ini"))
    eng = read(os.path.join(root, "Config", "DefaultEngine.ini"))
    pick = lambda txt, key: (re.search(rf"(?mi)^{key}=(.+)$", txt) or [None, None])[1]
    mcp = [n for n in plugins if n and re.search(r"ModelContext|MCP|AllToolsets", n, re.I) and plugins[n]]
    return dict(engine="unreal", version=j.get("EngineAssociation"), name=pick(ini, "ProjectName") or os.path.splitext(os.path.basename(path))[0], project_file=path, project_version=pick(ini, "ProjectVersion"),
                modules=[m.get("Name") for m in j.get("Modules", []) if isinstance(m, dict)], cpp=bool(j.get("Modules")), plugins_enabled=sorted(n for n, e in plugins.items() if n and e)[:40],
                mcp_plugin_enabled=mcp, steam=bool(re.search(r"OnlineSubsystemSteam|SteamSockets", eng + json.dumps(list(plugins)))),
                has_gds_ue=os.path.exists(os.path.join(root, "Content", "Python", "gds_ue.py")), maps=count_ext(os.path.join(root, "Content"), (".umap",)) if os.path.isdir(os.path.join(root, "Content")) else 0,
                assets=count_ext(os.path.join(root, "Content"), (".uasset",)) if os.path.isdir(os.path.join(root, "Content")) else 0,
                default_map=pick(eng, "GameDefaultMap") or pick(eng, "EditorStartupMap"))


def detect_unity(path: str) -> dict:
    root = os.path.dirname(os.path.dirname(path))
    ver = (re.search(r"m_EditorVersion:\s*(\S+)", read(path)) or [None, None])[1]
    ps = read(os.path.join(root, "ProjectSettings", "ProjectSettings.asset"), 200000)
    man = read(os.path.join(root, "Packages", "manifest.json"))
    deps = {}
    try:
        deps = json.loads(man).get("dependencies", {})
    except ValueError:
        pass
    pipeline = "urp" if "render-pipelines.universal" in man else "hdrp" if "render-pipelines.high-definition" in man else "built-in or unknown"
    ebs = read(os.path.join(root, "ProjectSettings", "EditorBuildSettings.asset"))
    scenes = re.findall(r"path:\s*(Assets/\S+\.unity)", ebs)
    pick = lambda key: (re.search(rf"(?m)^\s*{key}:\s*(.+)$", ps) or [None, None])[1]
    return dict(engine="unity", version=ver, name=pick("productName"), company=pick("companyName"), project_file=path, project_version=pick("bundleVersion"), render_pipeline=pipeline,
                packages=sorted(deps)[:60], mcp_packages=[d for d in deps if re.search(r"coplay|unity-mcp|mcp|com\.unity\.pipeline|ai\.assistant", d, re.I)],
                steam=any("steamworks" in d.lower() for d in deps) or os.path.exists(os.path.join(root, "steam_appid.txt")), build_scenes=scenes[:20],
                scene_files=count_ext(os.path.join(root, "Assets"), (".unity",)) if os.path.isdir(os.path.join(root, "Assets")) else 0,
                has_gds=os.path.isdir(os.path.join(root, "Assets", "_Game", "Editor", "GDS")))


def detect_godot(path: str) -> dict:
    root, txt = os.path.dirname(path), read(path, 100000)
    feats = (re.search(r'config/features=PackedStringArray\(([^)]*)\)', txt) or [None, ""])[1]
    ver = (re.search(r'"(\d+\.\d+)"', feats) or [None, None])[1]
    name = (re.search(r'(?m)^config/name="([^"]*)"', txt) or [None, None])[1]
    addons = sorted(os.listdir(os.path.join(root, "addons"))) if os.path.isdir(os.path.join(root, "addons")) else []
    return dict(engine="godot", version=ver, name=name, project_file=path, features=feats.replace('"', ""), addons=addons[:30], mcp_addons=[a for a in addons if re.search(r"mcp", a, re.I)],
                scenes=count_ext(root, (".tscn",)), scripts=count_ext(root, (".gd", ".cs")), steam=any("steam" in a.lower() for a in addons) or os.path.exists(os.path.join(root, "steam_appid.txt")))


def detect_nucleon(path: str) -> dict:
    """Nucleon Engine (project.ncproject, a Lua table): engine facts + what game-developer left (GDS harnesses, telemetry)."""
    root, txt = os.path.dirname(path), read(path, 100000)
    pick = lambda key: (re.search(rf'(?m)\b{key}\s*=\s*"([^"]*)"', txt) or [None, None])[1]
    gfx = (re.search(r"graphics\s*=\s*\{([^}]*)\}", txt) or [None, ""])[1]
    gpick = lambda key: (re.search(rf'\b{key}\s*=\s*"([^"]*)"', gfx) or [None, None])[1]
    content, scripts_dir = os.path.join(root, "Content"), os.path.join(root, "Content", "Scripts")
    scripts = sorted(f for f in os.listdir(scripts_dir) if f.endswith(".lua")) if os.path.isdir(scripts_dir) else []
    ui_dir = os.path.join(root, "UI")
    tele = os.path.join(root, "Saved", "telemetry")
    cfg = read(os.path.join(root, "Config", "BuildConfigurations.lua"))
    return dict(engine="nucleon", version=None, name=pick("name") or os.path.basename(root), project_file=path,
                project_version=pick("projectVersion"), company=pick("company"), startup_level=pick("startupLevel"),
                graphics_api=gpick("api"), lighting=gpick("lighting"), gi=gpick("globalIllumination"),
                levels=count_ext(content, (".nclevel",)) if os.path.isdir(content) else 0,
                actors=count_ext(content, (".ncactor",)) if os.path.isdir(content) else 0,
                blueprints=count_ext(content, (".ncbp",)) if os.path.isdir(content) else 0,
                scripts=scripts[:40], verb_tests=[f for f in scripts if f.startswith("test_")],
                ui_documents=sorted(f for f in os.listdir(ui_dir) if f.endswith(".rml"))[:20] if os.path.isdir(ui_dir) else [],
                landscapes=count_ext(content, (".land",)) if os.path.isdir(content) else 0,
                build_configs=re.findall(r'name\s*=\s*"([^"]+)"', cfg)[:10],
                has_gds=os.path.exists(os.path.join(scripts_dir, "gds_test.lua")),
                gds_capture=os.path.exists(os.path.join(scripts_dir, "gds_capture.lua")),
                telemetry_sessions=len(glob.glob(os.path.join(tele, "*.csv"))),
                mcp="built into the editor (Editor Preferences > AI; game-developer drives it with scripts/ncli.py)",
                steam=bool(re.search(r"steam", txt + cfg, re.I)) or os.path.exists(os.path.join(root, "steam_appid.txt")))


def detect_other(root: str) -> list[dict]:
    out = []
    for pat, engine in (("*.yyp", "gamemaker"), ("game.project", "defold"), ("*.rmmzproject", "rpgmaker-mz"), ("*.rmmvproject", "rpgmaker-mv"), ("*.c3p", "construct"), ("game/script.rpy", "renpy"), ("conf.lua", "love2d")):
        hits = glob.glob(os.path.join(root, pat))
        if hits:
            out.append(dict(engine=engine, version=None, name=os.path.splitext(os.path.basename(hits[0]))[0], project_file=hits[0]))
    pkg = read(os.path.join(root, "package.json"))
    for key, eng in (("phaser", "phaser"), ("three", "three.js"), ("babylonjs", "babylon.js"), ("pixi.js", "pixi.js"), ("excalibur", "excalibur"), ("kaboom", "kaboom")):
        if re.search(rf'"{re.escape(key)}"\s*:', pkg):
            out.append(dict(engine=eng, version=(re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]+)"', pkg) or [None, None])[1], name=(re.search(r'"name"\s*:\s*"([^"]+)"', pkg) or [None, None])[1], project_file=os.path.join(root, "package.json")))
    html = read(os.path.join(root, "index.html"), 20000)
    if html and not any(o["engine"] in ("phaser", "three.js", "babylon.js", "pixi.js", "excalibur", "kaboom") for o in out):
        kind = "html5-canvas" if re.search(r"<canvas|getContext\(|WebGL", html + read(os.path.join(root, "main.js"), 20000) + read(os.path.join(root, "game.js"), 20000), re.I) else "website"
        out.append(dict(engine=kind, version=None, name=(re.search(r"(?is)<title>(.*?)</title>", html) or [None, None])[1], project_file=os.path.join(root, "index.html")))
    cargo = read(os.path.join(root, "Cargo.toml"))
    for key in ("bevy", "macroquad", "ggez", "fyrox"):
        if re.search(rf"(?m)^{key}\s*=", cargo):
            out.append(dict(engine=key, version=(re.search(rf'(?m)^{key}\s*=\s*"?([\d.]+)', cargo) or [None, None])[1], name=(re.search(r'(?m)^name\s*=\s*"([^"]+)"', cargo) or [None, None])[1], project_file=os.path.join(root, "Cargo.toml")))
    cm = read(os.path.join(root, "CMakeLists.txt"))
    for key, eng in (("raylib", "raylib"), ("SDL2", "sdl2"), ("SFML", "sfml"), ("sokol", "sokol")):
        if re.search(key, cm):
            out.append(dict(engine=eng, version=None, name=(re.search(r"(?i)project\(\s*(\w+)", cm) or [None, None])[1], project_file=os.path.join(root, "CMakeLists.txt")))
    return out


def find_engines(root: str) -> list[dict]:
    found, seen = [], set()
    start = os.path.abspath(root)
    cands = [start]
    p = start
    for _ in range(4):   # the project may be a parent of the working directory
        q = os.path.dirname(p)
        if q == p:
            break
        cands.append(q)
        p = q
    for base in cands:
        for d, dirs, files in walk(base, 3 if base == start else 0):
            for f in files:
                path = os.path.join(d, f)
                if f.endswith(".uproject") and path not in seen:
                    seen.add(path); found.append(detect_unreal(path))
                elif f == "project.godot" and path not in seen:
                    seen.add(path); found.append(detect_godot(path))
                elif f.endswith(".ncproject") and path not in seen:
                    seen.add(path); found.append(detect_nucleon(path))
            if os.path.basename(d) == "ProjectSettings" and "ProjectVersion.txt" in files:
                path = os.path.join(d, "ProjectVersion.txt")
                if path not in seen:
                    seen.add(path); found.append(detect_unity(path))
    for base in cands[:1]:
        found += detect_other(base)
    return found


# ---------------------------------------------------------------- documents and artifacts
def first_heading(text: str) -> str:
    for ln in text.splitlines():
        if ln.startswith("#"):
            return ln.lstrip("# ").strip()[:100]
    return next((ln.strip()[:100] for ln in text.splitlines() if ln.strip()), "")


def scan_docs(root: str, limit: int) -> list[dict]:
    docs = []
    for d, dirs, files in walk(root, 4):
        for f in files:
            if not f.lower().endswith(DOC_EXT):
                continue
            path = os.path.join(d, f)
            rel = os.path.relpath(path, root)
            low = f.lower()
            kind, score = next(((k, s) for rx, k, s in DOC_RANK if re.search(rx, low)), ("other", 10))
            if "launch" + os.sep in rel + os.sep and rel.startswith("launch"):
                kind, score = "launch", max(score, 65)
            depth = rel.count(os.sep)
            try:
                size, mtime = os.path.getsize(path), os.path.getmtime(path)
            except OSError:
                continue
            if score <= 10 and depth > 1:
                continue
            docs.append(dict(path=rel.replace(os.sep, "/"), kind=kind, score=score - depth * 3, bytes=size, mtime=int(mtime), heading=first_heading(read(path, 4000))))
    docs.sort(key=lambda x: (-x["score"], -x["mtime"]))
    return docs[:limit]


def artifacts(root: str) -> dict:
    j = lambda *p: os.path.join(root, *p)
    out = {}
    gdd = read(j("GDD.md"), 200000)
    if gdd:
        out["gdd"] = dict(path="GDD.md", locked=bool(re.search(r"(?mi)^\W*status\W*:?\s*\W*locked|status:\s*locked", gdd)), heading=first_heading(gdd))
    tasks = read(j("GAME_TASKS.md"), 400000)
    if tasks:
        out["game_tasks"] = dict(path="GAME_TASKS.md", done=len(re.findall(r"\[x\]", tasks, re.I)), open=len(re.findall(r"\[ \]", tasks)), blocked=len(re.findall(r"\[!\]", tasks)))
    for name, key in (("GAME_CONTEXT.md", "game_context"), ("ASSET-LEDGER.md", "asset_ledger"), ("art/reference/BOARD.md", "art_board"), ("screenshots/000-index.md", "screenshot_index"), ("docs/scene-map.md", "scene_map"), ("docs/playtest.md", "playtest")):
        if os.path.exists(j(*name.split("/"))):
            out[key] = dict(path=name)
    gates = sorted(glob.glob(j("docs", "gates", "*.md")))
    if gates:
        out["gates"] = [os.path.basename(g) for g in gates][:40]
    lint = j("docs", "lint", "scene-lint.json")
    if os.path.exists(lint):
        out["scene_lint"] = dict(path="docs/lint/scene-lint.json", issues=(re.search(r'"issues"\s*:\s*(\d+)', read(lint)) or [None, None])[1])
    ls = j("launch")
    if os.path.isdir(ls):
        st = {}
        try:
            st = json.loads(read(j("launch", "status.json")))
        except ValueError:
            pass
        out["launch"] = dict(path="launch/", status_md=os.path.exists(j("launch", "STATUS.md")), mode=st.get("mode"), updated=st.get("updated"), product=(st.get("product") or {}).get("kind"),
                             files=sorted(os.listdir(ls))[:60])
    return out


def _gate_header(path: str) -> dict | None:
    """gate / date / status / title of the machine-readable header of a development gate (dev-link.md §7), None without one."""
    lines = read(path, 20000).splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    head = {}
    for ln in lines[1:200]:
        if ln.strip() == "---":
            break
        m = re.match(r"^(gate|date|status|title|wave)\s*:\s*(.*?)\s*(?:#.*)?$", ln)
        if m:
            head[m.group(1)] = m.group(2).strip().strip("\"'")
    else:
        return None
    return head if str(head.get("gate", "")).isdigit() else None


def _skill_installed(name: str) -> str | None:
    home = os.path.expanduser("~")
    for base in (os.path.join(home, ".claude", "skills"), os.path.join(home, ".agents", "skills")):
        if os.path.exists(os.path.join(base, name, "SKILL.md")):
            return os.path.join(base, name)
    return None


def _contract_version(path: str | None) -> str | None:
    m = re.search(r"(?m)^contract:\s*(\S+)", read(path, 4000)) if path and os.path.exists(path) else None
    return m.group(1) if m else None


def dev_link(root: str) -> dict:
    """The game-developer side of the project, read-only (references/dev-link.md §1). mode: linked when launch/ exists and the
    strategist skill is installed, launch-only when launch/ exists without it, solo without launch/ (gate_link.py detect)."""
    j = lambda *p: os.path.join(root, *p)
    launch = os.path.isdir(j("launch"))
    strategist = _skill_installed("game-launch-strategist")
    dev = _skill_installed("game-developer")
    out = dict(mode="linked" if launch and strategist else "launch-only" if launch else "solo", launch_dir=launch,
               strategist_skill=bool(strategist), dev_skill=bool(dev),
               dev_work=any(os.path.exists(j(*x.split("/"))) for x in ("docs/gates", "GAME_TASKS.md", "DECISIONI.md")))
    dec = read(j("DECISIONI.md"), 400000)
    if dec:
        ids = re.findall(r"(?m)^\s*(?:\|\s*|[-*]\s*\**)(D-\d{2,})\b", dec)
        out["decisions"] = dict(path="DECISIONI.md", count=len(set(ids)), last=max(ids, key=lambda x: int(x[2:])) if ids else None)
    rd = j("docs", "design-review")
    if os.path.isdir(rd):
        files = sorted(os.listdir(rd))
        cs = sorted((f for f in files if re.match(r"changes-since-w\d+\.md$", f)), key=lambda f: int(re.search(r"\d+", f).group(0)))
        gm = re.search(r"aggiornat[ao]\s+al\s+gate\s+(\d+)", read(j("docs", "design-review", "game-map.md"), 3000), re.I)
        out["design_review"] = dict(path="docs/design-review/", game_map="game-map.md" in files, screen_map="screen-map.md" in files,
                                    runs="runs.md" in files, changes_since=cs, latest_changes_since=cs[-1] if cs else None,
                                    map_gate=int(gm.group(1)) if gm else None)
    heads = []
    for g in glob.glob(j("docs", "gates", "*.md")):
        h = _gate_header(g)
        if h:
            heads.append(dict(gate=int(h["gate"]), date=h.get("date"), status=h.get("status"), title=h.get("title"),
                              file=os.path.basename(g)))
    if heads:
        last = max(heads, key=lambda h: h["gate"])
        out["gates_with_header"] = dict(count=len(heads), last=last["gate"], last_date=last["date"], last_status=last["status"],
                                        last_title=last["title"], last_file=last["file"])
    plans = sorted(os.path.basename(p) for p in glob.glob(j("docs", "gates", "plan-w*.md")))
    if plans:
        out["gate_plans"] = plans
    ours = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "references", "dev-link.md")
    theirs = os.path.join(dev, "references", "launch-link.md") if dev else None
    cv = dict(ours=_contract_version(ours), theirs=_contract_version(theirs))
    cv["match"] = None if not (cv["ours"] and cv["theirs"]) else cv["ours"] == cv["theirs"]
    out["contract"] = cv
    return out


def scan_steam(root: str) -> dict:
    ids = []
    for f in ("steam_appid.txt", os.path.join("Binaries", "Win64", "steam_appid.txt")):
        t = read(os.path.join(root, f), 100).strip()
        if t.isdigit():
            ids.append(t)
    vdf = [os.path.relpath(p, root).replace(os.sep, "/") for p in glob.glob(os.path.join(root, "**", "*.vdf"), recursive=True)[:10] if "node_modules" not in p and ".git" not in p]
    return dict(app_ids=sorted(set(ids)), vdf_files=vdf, itch=os.path.exists(os.path.join(root, ".itch.toml")))


def scan_media(root: str) -> dict:
    imgs, vids = [], []
    for d, dirs, files in walk(root, 4):
        parts = {p.lower() for p in os.path.relpath(d, root).split(os.sep)}
        if not (parts & MEDIA_DIRS) and os.path.abspath(d) != os.path.abspath(root):
            continue
        for f in files:
            path = os.path.join(d, f)
            low = f.lower()
            try:
                item = (os.path.getmtime(path), os.path.relpath(path, root).replace(os.sep, "/"))
            except OSError:
                continue
            (imgs if low.endswith(IMG) else vids if low.endswith(VID) else []).append(item)
    top = lambda xs: [p for _, p in sorted(xs, reverse=True)[:12]]
    return dict(images=len(imgs), videos=len(vids), newest_images=top(imgs), newest_videos=top(vids))


def scan_git(root: str) -> dict:
    if not shutil.which("git") or not os.path.isdir(os.path.join(root, ".git")):
        return {}
    run = lambda *a: subprocess.run(["git", "-C", root] + list(a), capture_output=True, text=True, timeout=8).stdout.strip()
    try:
        url = run("remote", "get-url", "origin")
        sp = urlsplit(url) if "://" in url else None
        host = (sp.hostname + sp.path) if sp and sp.hostname else re.sub(r"^[^@]*@", "", url)   # credentials removed
        return dict(branch=run("rev-parse", "--abbrev-ref", "HEAD"), commits=run("rev-list", "--count", "HEAD"), last=run("log", "-5", "--pretty=%h %ad %s", "--date=short").splitlines(), remote=host)
    except (subprocess.SubprocessError, OSError):
        return {}


# ---------------------------------------------------------------- tools on this machine
def scan_tools(root: str, probe: bool) -> dict:
    exe = {}
    for key, names in EXECS.items():
        hit = next((shutil.which(n) for n in names if shutil.which(n)), None)
        exe[key] = os.path.basename(hit) if hit else None   # name only: paths can reveal user names
    for pat in (r"C:\Program Files\Epic Games\UE_*\Engine\Binaries\Win64\UnrealEditor.exe", "/Users/Shared/Epic Games/UE_*/Engine/Binaries/Mac/UnrealEditor.app", os.path.expanduser("~/UnrealEngine*/Engine/Binaries/Linux/UnrealEditor")):
        hits = glob.glob(pat)
        if hits and not exe["unreal_editor"]:
            exe["unreal_editor"] = "installed: " + ", ".join(sorted(re.search(r"UE_([\d.]+)", h).group(1) for h in hits if re.search(r"UE_([\d.]+)", h)) or ["found"])
    servers = []
    for rel in MCP_FILES:
        try:
            data = json.loads(read(os.path.join(root, rel)))
        except ValueError:
            continue
        for name, cfg in ((data.get("mcpServers") or data.get("servers") or data.get("mcp") or {}).items() if isinstance(data, dict) else []):
            if not isinstance(cfg, dict):
                continue
            url = cfg.get("url") or cfg.get("serverUrl")
            cmd = cfg.get("command")
            servers.append(dict(name=name, file=rel, kind="http" if url else "stdio", target=(urlsplit(url).netloc if url else (os.path.basename(cmd[0] if isinstance(cmd, list) and cmd else str(cmd or "")))), env_keys_hidden=bool(cfg.get("env"))))
    ports = {}
    if probe:
        for label, port in (("unreal_mcp_default_8000", 8000),):   # documented default of the Unreal MCP plugin [DA VERIFICARE]
            s = socket.socket()
            s.settimeout(0.4)
            try:
                ports[label] = "listening" if s.connect_ex(("127.0.0.1", port)) == 0 else "not listening"
            except OSError:
                ports[label] = "unknown"
            finally:
                s.close()
    return dict(executables=exe, mcp_configured_in_project=servers, ports=ports)


def genre_hints(root: str, docs: list[dict]) -> list[dict]:
    text = " ".join(read(os.path.join(root, d["path"]), 20000).lower() for d in docs[:15] if d["kind"] not in ("launch", "changelog"))
    hits = sorted(((len(re.findall(rx, text)), g) for g, rx in GENRES.items()), reverse=True)
    return [dict(genre=g, mentions=n) for n, g in hits if n][:5]


def scan(root: str, max_docs: int, probe: bool) -> dict:
    root = os.path.abspath(root)
    eng = find_engines(root)
    docs = scan_docs(root, max_docs)
    return dict(root=os.path.basename(root), engines=eng, primary_engine=(eng[0]["engine"] if eng else None), docs=docs, artifacts=artifacts(root), dev_link=dev_link(root), store=scan_steam(root), media=scan_media(root), git=scan_git(root),
                tools=scan_tools(root, probe), genre_hints=genre_hints(root, docs))


def to_md(r: dict) -> str:
    L = ["# Scansione automatica del progetto (`project_scan.py`)", "", "Cosa dice il **disco**. Cosa può chiamare **questa chat** (strumenti MCP, skill) si controlla dalla sessione: `references/00a-bootstrap.md`.", ""]
    if not r["engines"]:
        L += ["## Motore", "", "Nessun progetto di motore riconosciuto da questa cartella. Chiedi il percorso, oppure è un progetto personalizzato: leggi i documenti qui sotto.", ""]
    for e in r["engines"]:
        L += [f"## Motore: {e['engine']} {e.get('version') or '(versione non trovata)'}", "", f"- Nome: {e.get('name') or 'n/d'} · file: `{os.path.basename(e.get('project_file', ''))}`"]
        for k, v in e.items():
            if k in ("engine", "version", "name", "project_file") or v in (None, [], "", False):
                continue
            L.append(f"- {k.replace('_', ' ')}: {', '.join(map(str, v)) if isinstance(v, list) else v}")
        L.append("")
    if r["genre_hints"]:
        L += ["## Indizi di genere (da confermare, non un verdetto)", "", ", ".join(f"{g['genre']} ({g['mentions']})" for g in r["genre_hints"]), ""]
    L += ["## Documenti da leggere, in ordine", "", "| File | Tipo | Titolo |", "|---|---|---|"] + [f"| `{d['path']}` | {d['kind']} | {d['heading']} |" for d in r["docs"][:25]] + [""]
    if r["artifacts"]:
        L += ["## Lasciato da altre skill o dal progetto", ""] + [f"- {k}: {json.dumps(v, ensure_ascii=False)}" for k, v in r["artifacts"].items()] + [""]
    dl = r.get("dev_link") or {}
    if dl:
        mode_it = {"linked": "insieme (launch + game-developer)", "launch-only": "launch senza la skill launch installata", "solo": "solo sviluppo (niente launch/)"}
        L += ["## Collegamento con game-developer (`references/dev-link.md`)", "",
              f"- modo: **{dl['mode']}** ({mode_it.get(dl['mode'], dl['mode'])}) · skill game-developer: {'sì' if dl['dev_skill'] else 'no'} · lavoro dev nel progetto: {'sì' if dl['dev_work'] else 'no'}"]
        if dl.get("decisions"):
            L.append(f"- `DECISIONI.md`: {dl['decisions']['count']} decisioni (ultima {dl['decisions']['last']}): importa quelle che mancano con `todo_track.py sync-decisions`")
        if dl.get("gates_with_header"):
            g = dl["gates_with_header"]
            L.append(f"- gate con intestazione: {g['count']} · ultimo **gate {g['last']}** ({g['last_date']}, {g['last_status']}): {g['last_title']}")
        if dl.get("gate_plans"):
            L.append("- piani dei gate: " + ", ".join(dl["gate_plans"]))
        if dl.get("design_review"):
            d = dl["design_review"]
            L.append(f"- `docs/design-review/`: mappa {'sì' if d['game_map'] else 'no'}" + (f" (gate {d['map_gate']})" if d.get("map_gate") else "")
                     + f", schermate {'sì' if d['screen_map'] else 'no'}, run {'sì' if d['runs'] else 'no'}, changes-since: {d['latest_changes_since'] or 'nessuno'}")
        c = dl.get("contract") or {}
        if c.get("match") is False:
            L.append(f"- ⚠️ versioni del contratto diverse: qui {c['ours']}, game-developer {c['theirs']}: dillo al proprietario una volta e segui la regola più prudente")
        L.append("")
    st = r["store"]
    L += ["## Steam e itch", "", f"- steam_appid: {', '.join(st['app_ids']) or 'non trovato'} · vdf: {', '.join(st['vdf_files']) or '-'} · itch: {'sì' if st['itch'] else 'no'}", ""]
    m = r["media"]
    L += ["## Immagini e video", "", f"- {m['images']} immagini, {m['videos']} video nelle cartelle di screenshot, capsule, press, art. Più recenti: {', '.join(m['newest_images'][:5]) or '-'}", ""]
    if r["git"]:
        L += ["## Git", "", f"- ramo {r['git']['branch']}, {r['git']['commits']} commit, remote {r['git']['remote']}"] + [f"  - {x}" for x in r["git"]["last"]] + [""]
    t = r["tools"]
    L += ["## Strumenti sul disco", "", "- eseguibili: " + ", ".join(f"{k}={v or 'no'}" for k, v in t["executables"].items()), "- MCP configurati nel progetto: " + (", ".join(f"{s['name']} ({s['kind']}: {s['target']})" for s in t["mcp_configured_in_project"]) or "nessuno"),
          "- porte: " + (", ".join(f"{k}: {v}" for k, v in t["ports"].items()) or "non controllate"), ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="."); ap.add_argument("--max-docs", type=int, default=40); ap.add_argument("-o", "--out"); ap.add_argument("--md"); ap.add_argument("--no-probe", action="store_true")
    a = ap.parse_args()
    res = scan(a.root, a.max_docs, not a.no_probe)
    for path, text in ((a.out, json.dumps(res, ensure_ascii=False, indent=1)), (a.md, to_md(res))):
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text + "\n")
            print("wrote", path, file=sys.stderr)
    if not a.out and not a.md:
        print(to_md(res))


if __name__ == "__main__":
    main()
