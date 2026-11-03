#!/usr/bin/env python3
"""Run every offline test (no network needed): python tests/run_all.py"""
import glob, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
failed = []
# offline: never call the real internal Agent Reach copy of this machine (the reach tests use fake runners)
env = dict(os.environ, GLS_REACH="off")
env.pop("GLS_REACH_FAKE", None)
for t in sorted(glob.glob(os.path.join(here, "test_*.py"))):
    r = subprocess.run([sys.executable, "-W", "error::DeprecationWarning", t], capture_output=True, text=True, env=env)
    last = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    print(("PASS " if r.returncode == 0 else "FAIL ") + os.path.basename(t) + " | " + last)
    if r.returncode:
        failed.append(t); print(r.stdout[-1500:], r.stderr[-1500:])
sys.exit(1 if failed else 0)
