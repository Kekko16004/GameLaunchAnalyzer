"""project_scan.py: engine and version, context docs ranking, artifacts of other skills, MCP configs without secrets, git remote without credentials, parent lookup, no network."""
import os, sys, json, tempfile, subprocess, shutil
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research")
sys.path.insert(0, R)
import common
def no_net(*a, **k): raise AssertionError("project_scan must not use the network")
common.http_get = no_net
import project_scan as ps

def W(root, rel, text=""):
    p = os.path.join(root, *rel.split("/")); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w", encoding="utf-8").write(text); return p

# ---- Unreal project with the official MCP plugin, Steam, docs, MCP config holding a secret
u = tempfile.mkdtemp()
W(u, "Buffet.uproject", json.dumps({"FileVersion": 3, "EngineAssociation": "5.8", "Modules": [{"Name": "Buffet", "Type": "Runtime"}], "Plugins": [{"Name": "ModelContextProtocol", "Enabled": True}, {"Name": "AllToolsets", "Enabled": True}, {"Name": "PythonScriptPlugin", "Enabled": True}, {"Name": "Off", "Enabled": False}]}))
W(u, "Config/DefaultGame.ini", "[/Script/EngineSettings.GeneralProjectSettings]\nProjectName=Buffet Panic\nProjectVersion=0.3.1\n")
W(u, "Config/DefaultEngine.ini", "[OnlineSubsystem]\nDefaultPlatformService=Steam\n[/Script/EngineSettings.GameMapsSettings]\nGameDefaultMap=/Game/Maps/Kitchen\n; OnlineSubsystemSteam\n")
W(u, "Content/Maps/Kitchen.umap", "x"); W(u, "Content/Hero.uasset", "x"); W(u, "Content/Python/gds_ue.py", "# gds")
W(u, "CLAUDE.md", "# Buffet Panic project\nCo-op roguelite where you run a buffet. Roguelite roguelite co-op co-op.\n"); W(u, "README.md", "# Buffet\nA frantic co-op cooking roguelike.\n")
W(u, "docs/GDD.md", "# GDD\nstatus: locked\n"); W(u, "GDD.md", "# Buffet GDD\nstatus: locked\n"); W(u, "GAME_TASKS.md", "- [x] a\n- [x] b\n- [ ] c\n- [!] d\n"); W(u, "GAME_CONTEXT.md", "# ctx\n")
W(u, "docs/gates/greybox.md", "PASS"); W(u, "docs/lint/scene-lint.json", '{"issues": 0}'); W(u, "ASSET-LEDGER.md", "# assets"); W(u, "screenshots/000-index.md", "# shots"); W(u, "screenshots/001.png", "png"); W(u, "marketing/capsule.png", "png"); W(u, "marketing/teaser.mp4", "mp4")
W(u, "launch/STATUS.md", "# STATUS"); W(u, "launch/status.json", json.dumps({"mode": "Completa", "updated": "2026-10-05", "product": {"kind": "beta"}}))
W(u, "steam_appid.txt", "480\n"); W(u, "Intermediate/junk.md", "# junk"); W(u, "Saved/log.md", "# junk")
W(u, ".mcp.json", json.dumps({"mcpServers": {"unreal": {"type": "http", "url": "http://127.0.0.1:8000/mcp"}, "terminal": {"command": "node", "args": ["/home/me/TerminalMCP/index.js"], "env": {"API_KEY": "SUPERSECRET123"}}}}))
subprocess.run(["git", "init", "-q", u], check=True); subprocess.run(["git", "-C", u, "remote", "add", "origin", "https://user:ghp_TOKEN999@github.com/me/buffet.git"], check=True)
subprocess.run(["git", "-C", u, "-c", "user.email=a@b.c", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "first"], check=True)

r = ps.scan(u, 40, probe=False)
e = r["engines"][0]
assert r["primary_engine"] == "unreal" and e["version"] == "5.8" and e["name"] == "Buffet Panic" and e["project_version"] == "0.3.1" and e["cpp"] is True, e
assert e["mcp_plugin_enabled"] == ["ModelContextProtocol"] or set(e["mcp_plugin_enabled"]) == {"ModelContextProtocol", "AllToolsets"}, e["mcp_plugin_enabled"]
assert "Off" not in e["plugins_enabled"] and e["steam"] is True and e["has_gds_ue"] is True and e["maps"] == 1 and e["assets"] == 1 and e["default_map"] == "/Game/Maps/Kitchen"
paths = [d["path"] for d in r["docs"]]
assert paths[0] == "CLAUDE.md" and "README.md" in paths and "GDD.md" in paths and "Intermediate/junk.md" not in paths and "Saved/log.md" not in paths, paths
a = r["artifacts"]
assert a["gdd"]["locked"] is True and a["game_tasks"] == dict(path="GAME_TASKS.md", done=2, open=1, blocked=1) and a["gates"] == ["greybox.md"] and a["scene_lint"]["issues"] == "0"
assert a["launch"]["mode"] == "Completa" and a["launch"]["product"] == "beta" and a["asset_ledger"] and a["screenshot_index"] and a["game_context"]
assert r["store"]["app_ids"] == ["480"] and r["media"]["images"] == 2 and r["media"]["videos"] == 1
assert r["genre_hints"][0]["genre"] in ("roguelike", "co-op") and any(g["genre"] == "roguelike" for g in r["genre_hints"])
assert r["git"]["branch"] and r["git"]["commits"] == "1" and r["git"]["remote"] == "github.com/me/buffet.git" and "ghp_TOKEN999" not in json.dumps(r) and "user:" not in json.dumps(r)
srv = {s["name"]: s for s in r["tools"]["mcp_configured_in_project"]}
assert srv["unreal"]["kind"] == "http" and srv["unreal"]["target"] == "127.0.0.1:8000" and srv["terminal"]["kind"] == "stdio" and srv["terminal"]["target"] == "node" and srv["terminal"]["env_keys_hidden"] is True
dump = json.dumps(r) + ps.to_md(r)
assert "SUPERSECRET123" not in dump and "/home/me/" not in dump          # env values and local paths never reach the output
assert r["tools"]["ports"] == {} and "Buffet Panic" in ps.to_md(r) and "unreal 5.8" in ps.to_md(r)

# the working directory may be inside the project: the scan finds the engine in a parent
sub = os.path.join(u, "docs"); r2 = ps.scan(sub, 10, probe=False); assert r2["primary_engine"] == "unreal"

# ---- Unity project made by GameDeveloperSkill
g = tempfile.mkdtemp()
W(g, "ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.3.2f1\nm_EditorVersionWithRevision: 6000.3.2f1 (abc)\n")
W(g, "ProjectSettings/ProjectSettings.asset", "PlayerSettings:\n  companyName: Studio X\n  productName: Village Quest\n  bundleVersion: 0.1.0\n")
W(g, "ProjectSettings/EditorBuildSettings.asset", "m_Scenes:\n- enabled: 1\n  path: Assets/_Game/Scenes/MainMenu.unity\n- enabled: 1\n  path: Assets/_Game/Scenes/MainGame.unity\n")
W(g, "Packages/manifest.json", json.dumps({"dependencies": {"com.unity.render-pipelines.universal": "17.0", "com.unity.pipeline": "1.0", "com.coplaydev.unity-mcp": "git", "com.rlabrecque.steamworks.net": "1"}}))
W(g, "Assets/_Game/Scenes/MainGame.unity", "x"); W(g, "Assets/_Game/Editor/GDS/World.cs", "//")
ru = ps.scan(g, 10, probe=False); eu = ru["engines"][0]
assert eu["engine"] == "unity" and eu["version"] == "6000.3.2f1" and eu["name"] == "Village Quest" and eu["company"] == "Studio X" and eu["render_pipeline"] == "urp" and eu["has_gds"] is True and eu["steam"] is True
assert eu["build_scenes"][0].endswith("MainMenu.unity") and set(eu["mcp_packages"]) == {"com.unity.pipeline", "com.coplaydev.unity-mcp"} and eu["scene_files"] == 1

# ---- Godot, web framework, nothing
go = tempfile.mkdtemp(); W(go, "project.godot", 'config/name="Dungeon Hop"\nconfig/features=PackedStringArray("4.3", "Forward Plus")\n'); W(go, "addons/godot_mcp/plugin.cfg", ""); W(go, "main.gd", ""); W(go, "main.tscn", "")
eg = ps.scan(go, 10, probe=False)["engines"][0]; assert eg["engine"] == "godot" and eg["version"] == "4.3" and eg["name"] == "Dungeon Hop" and eg["mcp_addons"] == ["godot_mcp"] and eg["scenes"] == 1
web = tempfile.mkdtemp(); W(web, "package.json", '{"name": "tiny-game", "dependencies": {"phaser": "^3.80.0"}}')
assert ps.scan(web, 10, probe=False)["engines"][0]["engine"] == "phaser"
empty = tempfile.mkdtemp(); re_ = ps.scan(empty, 10, probe=False)
assert re_["engines"] == [] and re_["primary_engine"] is None and re_["docs"] == [] and "Nessun progetto di motore riconosciuto" in ps.to_md(re_)

# ---- CLI (cp1252 console, writes files, probe path runs without crashing)
out = os.path.join(tempfile.mkdtemp(), "x", "scan.json")
r = subprocess.run([sys.executable, os.path.join(R, "project_scan.py"), "--root", u, "-o", out, "--md", out.replace(".json", ".md")], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
assert r.returncode == 0, r.stderr.decode("utf-8", "replace"); j = json.load(open(out)); assert j["primary_engine"] == "unreal" and j["tools"]["ports"]["unreal_mcp_default_8000"] in ("listening", "not listening", "unknown")
print("ALL PROJECT_SCAN TESTS PASSED")
