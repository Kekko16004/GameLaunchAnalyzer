// game-launch-strategist hooks for the skillkit installer: Python check, script compile check, optional unit tests.
import path from "node:path";

// the real interpreter (py.exe and the Store alias are launchers). A Store python reports an exe inside
// "Program Files\WindowsApps" that cannot be spawned directly (EPERM): keep its alias as a last resort.
function findPython(ctx) {
  let alias = null;
  for (const launcher of ["python", "python3", "py"]) {
    const exe = ctx.which(launcher) || (ctx.isWin && launcher === "python" ? "python" : "");
    if (!exe) continue;
    const r = ctx.runSync(exe, ["-c", "import sys; print(sys.executable); print('%d.%d' % sys.version_info[:2])"]);
    const [exePath, ver] = r.out.trim().split(/\r?\n/).slice(-2).map((s) => s.trim());
    if (r.code !== 0 || !exePath) continue;
    if (/[\\/]WindowsApps[\\/]/i.test(exePath)) { alias = alias || { exe, ver }; continue; }
    if (ctx.exists(exePath)) return { exe: exePath, ver };
  }
  return alias;
}
const okVer = (v) => { const [a, b] = String(v || "0.0").split(".").map(Number); return a > 3 || (a === 3 && b >= 9); };

export async function detect(ctx) {
  // the Python row itself comes from "requires" in skillkit.json; keep the real path for the checks below
  const py = findPython(ctx);
  ctx.vars.python = py?.exe || "";
  ctx.detected.python = py;
}

export async function after(ctx) {
  const { ui, run, lang, CANON, ROOT, flags } = ctx;
  const it = lang === "it";
  const py = ctx.detected.python || findPython(ctx);
  const dir = path.join(CANON, "game-launch-strategist", "scripts", "research");
  await ui.task(it ? "script Python" : "Python scripts", async (t) => {
    if (ctx.DRY) return {};
    if (!py) return { state: "warn", note: it ? "Python 3.9+ non trovato: gli script di ricerca non partono" : "Python 3.9+ not found: the research scripts will not run" };
    // compile only, nothing is executed; -B keeps __pycache__ out of the installed copy
    const r = await run(py.exe, ["-B", "-c", "import sys, pathlib, py_compile\nbad = []\nfor f in sorted(pathlib.Path(sys.argv[1]).glob('*.py')):\n    try: compile(f.read_text(encoding='utf-8'), str(f), 'exec')\n    except Exception as e: bad.append(f'{f.name}: {e}')\nprint(len(list(pathlib.Path(sys.argv[1]).glob('*.py'))), len(bad)); [print(b) for b in bad]", dir], { onLine: t.update });
    const [n, nbad] = (r.out.trim().split(/\r?\n/)[0] || "0 0").split(" ").map(Number);
    if (r.code !== 0 || nbad) { for (const l of r.out.trim().split(/\r?\n/).slice(1, 6)) ui.detail(l, "err"); return { state: "warn", note: `${nbad || "?"} ${it ? "con errori" : "with errors"}` }; }
    return { note: `${n} ${it ? "compilano" : "compile"} ${ctx.g.dot} Python ${py.ver}` };
  });
  if (flags.test) {
    await ui.task(it ? "test" : "tests", async (t) => {
      if (ctx.DRY || !py) return { state: "skip" };
      const runner = path.join(ROOT, "tests", "run_all.py");
      if (!ctx.exists(runner)) return { state: "skip", note: it ? "tests/ non presente" : "no tests/" };
      const r = await run(py.exe, ["-B", runner], { cwd: ROOT, onLine: t.update, env: { PYTHONIOENCODING: "utf-8" }, timeout: 900000 });
      const last = r.out.trim().split(/\r?\n/).filter(Boolean).pop() || "";
      return r.code === 0 ? { note: last } : { state: "fail", note: last };
    });
  }
}

export async function summary(ctx, rows) {
  const it = ctx.lang === "it";
  rows.push([it ? "Usa" : "Use", "/game-launch-strategist [Completa | Rapida | Mirata <area> | Ondata | Aggiornamento | Trailer]"]);
  if (!ctx.detected.python) ctx.footer.push(`${ctx.c.warn(ctx.g.warn)} Python 3.9+  ${ctx.isWin ? "winget install --id Python.Python.3.12 -e" : "brew install python"}`);
}

