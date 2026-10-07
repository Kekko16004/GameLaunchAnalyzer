"""Scripts that print emoji or arrows must not crash on a cp1252 console or when piped on Windows (PYTHONIOENCODING=cp1252)."""
import os, sys, json, subprocess, tempfile
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research")
d = tempfile.mkdtemp()
cal = os.path.join(d, "calendar.md"); open(cal, "w", encoding="utf-8").write("## ✅ Passi in ordine\n### FASE 1 — Adesso\n1. [ ] 👤 **Crea il modulo** → apri `form.md`. · 📅 2026-10-20\n2. [ ] 🤖 Lo collego (≥ 1 volta).\n")
kit = os.path.join(d, "kit.json"); json.dump({"game": "G", "steam": {"fields": [{"key": "title", "label": "Nome → titolo", "value": "Buffet · Panic ≥ 1"}], "long_description": {"blocks": [{"type": "text", "value": "→ ok"}]}, "tags": [{"tag": "Co-op"}]}}, open(kit, "w", encoding="utf-8"), ensure_ascii=False)
cases = [["plan_steps.py", "--calendar", cal, "list"], ["plan_steps.py", "--calendar", cal, "next", "--owner", "me"], ["plan_steps.py", "--calendar", cal, "summary"],
         ["store_kit.py", "render", kit], ["store_kit.py", "check", kit], ["metrics_track.py", "catalog"], ["roster.py", "--help"]]
for args in cases:
    for mode in ("pipe", "file"):   # captured through a pipe, and redirected to a file
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        env.pop("PYTHONUTF8", None)
        r = subprocess.run([sys.executable, os.path.join(R, args[0])] + args[1:], capture_output=True, env=env)
        assert r.returncode in (0, 1), (args, mode, r.stderr.decode("utf-8", "replace")[-300:])
        assert b"UnicodeEncodeError" not in r.stderr and b"Traceback" not in r.stderr, (args, r.stderr.decode("utf-8", "replace")[-300:])
        r.stdout.decode("utf-8")   # output is valid UTF-8
out = subprocess.run([sys.executable, os.path.join(R, "plan_steps.py"), "--calendar", cal, "list"], capture_output=True, env=dict(os.environ, PYTHONIOENCODING="cp1252")).stdout.decode("utf-8")
assert "👤" in out and "🤖" in out and "→" in out, out
print("ALL WINDOWS_CONSOLE TESTS PASSED")
