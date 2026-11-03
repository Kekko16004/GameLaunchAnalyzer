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

// ---------------------------------------------------------------- Agent Reach (optional dependency: social platforms, read-only)
// https://github.com/Panniantong/agent-reach . Installed with uv from the GitHub release (never from PyPI: the PyPI package with
// the same name is not this project), refreshed by `install.mjs update` with `agent-reach update`. Logins stay with the owner.
const REACH_ZIP = "https://github.com/Panniantong/Agent-Reach/releases/latest/download/agent-reach.zip";
function findReach(ctx) {
  const home = ctx.HOME || process.env.USERPROFILE || process.env.HOME || "";
  const local = path.join(home, ".local", "bin", ctx.isWin ? "agent-reach.exe" : "agent-reach");
  return ctx.which("agent-reach") || (ctx.exists(local) ? local : "");
}
function findUv(ctx) {
  const home = ctx.HOME || process.env.USERPROFILE || process.env.HOME || "";
  const local = path.join(home, ".local", "bin", ctx.isWin ? "uv.exe" : "uv");
  return ctx.which("uv") || (ctx.exists(local) ? local : "");
}
// agent-reach prints one JSON object per command (1.6+); a plain line means 1.5 or older
function reachJson(out) {
  for (const l of String(out || "").trim().split(/\r?\n/).reverse()) { const s = l.trim(); if (s.startsWith("{")) { try { return JSON.parse(s); } catch { return null; } } }
  return null;
}
function reachVersion(ctx, exe) {
  if (!exe) return "";
  const r = ctx.runSync(exe, ["version"], { timeout: 30000, cwd: ctx.HOME });
  return reachJson(r.out)?.result?.version || (/(\d+\.\d+\.\d+)/.exec(r.out || "")?.[1] ? `${/(\d+\.\d+\.\d+)/.exec(r.out)[1]} (1.5)` : "");
}
const skipped = (ctx) => String(ctx.flags.skip || "").split(/[,\s]+/).includes("agent-reach");
const isUpdate = () => process.argv.slice(2).some((a) => a.toLowerCase() === "update");

export async function detect(ctx) {
  // the Python row itself comes from "requires" in skillkit.json; keep the real path for the checks below
  const py = findPython(ctx);
  ctx.vars.python = py?.exe || "";
  ctx.detected.python = py;
  const it = ctx.lang === "it";
  const exe = findReach(ctx);
  const v = reachVersion(ctx, exe);
  ctx.detected.reach = exe ? { exe, version: v } : null;
  ctx.detected.uv = findUv(ctx);
  ctx.ui.row(exe ? "ok" : "off", "Agent Reach", exe ? v || "?" : ctx.c.faint(it ? "non installato" : "not installed"),
    ctx.c.dim(it ? "opzionale: social in sola lettura" : "optional: social platforms, read-only"));
}

export async function questions(ctx) {
  if (ctx.detected.reach || skipped(ctx)) return;
  const it = ctx.lang === "it";
  ctx.choices.agentReach = await ctx.ui.confirm({ title: it ? "Installo Agent Reach (X, TikTok, Instagram, Reddit... in sola lettura)?" : "Install Agent Reach (X, TikTok, Instagram, Reddit... read-only)?", yes: true, lang: ctx.lang });
}

async function reachTask(ctx) {
  const { ui, run, lang } = ctx;
  const it = lang === "it";
  await ui.task("Agent Reach", async (t) => {
    if (ctx.DRY) return { state: "skip" };
    if (skipped(ctx) || ctx.choices.agentReach === false) return { state: "skip", note: it ? "escluso" : "skipped" };
    let exe = ctx.detected.reach?.exe || findReach(ctx);
    if (exe) {
      const before = reachVersion(ctx, exe);
      if (!isUpdate()) return { note: `${before || "?"} ${ctx.g.dot} ${it ? "già installato" : "already installed"}` };
      if (/\(1\.5\)$/.test(before)) {
        const uv = findUv(ctx);
        if (!uv) return { state: "warn", note: it ? "1.5 da aggiornare: serve uv" : "1.5 needs uv to upgrade" };
        await run(uv, ["tool", "install", "--force", REACH_ZIP], { onLine: t.update, cwd: ctx.HOME, timeout: 900000 });
      } else {
        const r = await run(exe, ["update"], { onLine: t.update, cwd: ctx.HOME, timeout: 900000, env: { PYTHONIOENCODING: "utf-8" } });
        const j = reachJson(r.out);
        if (j && j.ok === false) return { state: "warn", note: (j.error?.hint || j.error?.message || "update").slice(0, 120) };
      }
      const after = reachVersion(ctx, findReach(ctx) || exe);
      ctx.detected.reach = { exe, version: after };
      return { note: after === before ? `${after} ${ctx.g.dot} ${it ? "già aggiornato" : "up to date"}` : `${before} ${ctx.g.arrow} ${after}` };
    }
    const uv = findUv(ctx);
    if (!uv) {
      ctx.footer.push(`${ctx.c.warn(ctx.g.warn)} Agent Reach: ${ctx.isWin ? "winget install --id astral-sh.uv -e" : "curl -LsSf https://astral.sh/uv/install.sh | sh"}  ${ctx.g.arrow}  uv tool install ${REACH_ZIP}`);
      return { state: "warn", note: it ? "serve uv (vedi sotto)" : "needs uv (see below)" };
    }
    const r = await run(uv, ["tool", "install", REACH_ZIP], { onLine: t.update, cwd: ctx.HOME, timeout: 900000 });
    exe = findReach(ctx);
    if (!exe) return { state: "warn", note: it ? `installazione non riuscita (${r.code}): uv tool update-shell, poi riprova` : `install failed (${r.code}): uv tool update-shell, then retry` };
    // default channels only (no logins): GitHub, YouTube, Bilibili, V2EX, web
    await run(exe, ["setup"], { onLine: t.update, cwd: ctx.HOME, timeout: 900000, env: { PYTHONIOENCODING: "utf-8" } });
    const v = reachVersion(ctx, exe);
    ctx.detected.reach = { exe, version: v };
    ctx.choices.agentReach = true;
    return { note: `${v} ${ctx.g.dot} ${it ? "installato" : "installed"}` };
  });
}

// channels ready / not ready, through the skill's own adapter (same table as `reach.py doctor`)
function reachDoctor(ctx, py) {
  const script = path.join(ctx.CANON, "game-launch-strategist", "scripts", "research", "reach.py");
  if (!py || !ctx.exists(script)) return null;
  const r = ctx.runSync(py.exe, ["-B", script, "doctor", "--json"], { timeout: 120000, cwd: ctx.HOME, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  try { return JSON.parse(r.out.slice(r.out.indexOf("{"), r.out.lastIndexOf("}") + 1)); } catch { return null; }
}

// Agent Reach opens its dedicated browser in Chinese (locale written in the code); `agent-reach update` puts that back, so the fix runs after every install/update
async function reachLangTask(ctx, py) {
  const { ui, run, CANON } = ctx;
  const it = ctx.lang === "it";
  const script = path.join(CANON, "game-launch-strategist", "scripts", "research", "reach.py");
  await ui.task(it ? "Agent Reach: lingua del browser" : "Agent Reach: browser language", async (t) => {
    if (ctx.DRY || !py || !ctx.exists(script)) return { state: "skip" };
    const r = await run(py.exe, ["-B", script, "fix-lang"], { onLine: t.update, cwd: ctx.HOME, timeout: 120000, env: { PYTHONIOENCODING: "utf-8" } });
    const lines = r.out.trim().split(/\r?\n/).filter(Boolean);
    if (r.code !== 0) return { state: "warn", note: (lines.find((l) => /non riconosciuto|non trovo|non modificabile/.test(l)) || lines.pop() || "fix-lang").slice(0, 140) };
    return { note: (lines[0] || "").replace(/^Lingua del browser: /, "").slice(0, 140) };
  });
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
  await reachTask(ctx);
  if (ctx.detected.reach && !ctx.DRY) await reachLangTask(ctx, py);
  if (ctx.detected.reach && !ctx.DRY) {
    const d = reachDoctor(ctx, py);
    ctx.detected.reachDoctor = d;
    if (d) ui.row(d.ready?.length ? "ok" : "warn", it ? "social pronti" : "social ready", (d.ready || []).join(", ") || "—",
      d.not_ready?.length ? ctx.c.faint(`${it ? "non pronti" : "not ready"}: ${d.not_ready.join(", ")}`) : "");
  }
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
  const r = ctx.detected.reach;
  rows.push(["Agent Reach", r ? `${r.version || "?"}${ctx.detected.reachDoctor ? ` ${ctx.g.dot} ${(ctx.detected.reachDoctor.ready || []).length} ${it ? "canali pronti" : "channels ready"}` : ""}` : (it ? "non installato" : "not installed")]);
  if (r && (ctx.detected.reachDoctor?.not_ready || []).some((c) => ["twitter", "instagram", "tiktok", "reddit"].includes(c)))
    ctx.footer.push(ctx.c.dim(it ? "Social con login (li fai tu, nel browser dedicato): ! python reach.py login twitter | instagram | reddit  ·  percorso e elenco: python reach.py setup"
                                 : "Logged-in socials (you log in, in the dedicated browser): ! python reach.py login twitter | instagram | reddit  ·  full path and list: python reach.py setup"));
}

export async function doctor(ctx) {
  const it = ctx.lang === "it";
  const exe = findReach(ctx);
  if (!exe) { ctx.ui.row("off", "Agent Reach", ctx.c.faint(it ? "non installato (opzionale)" : "not installed (optional)"), ctx.c.dim("node installer/install.mjs update")); return 0; }
  const v = reachVersion(ctx, exe);
  ctx.ui.row(v ? "ok" : "warn", "Agent Reach", v || "?", ctx.c.faint(ctx.tilde(exe)));
  const d = reachDoctor(ctx, findPython(ctx));
  if (d) ctx.ui.row(d.ready?.length ? "ok" : "warn", it ? "social pronti" : "social ready", (d.ready || []).join(", ") || "—",
    d.not_ready?.length ? ctx.c.faint(`${it ? "non pronti" : "not ready"}: ${d.not_ready.join(", ")}`) : "");
  else ctx.ui.row("warn", "reach.py", it ? "doctor non riuscito" : "doctor failed");
  return 0;   // optional dependency: never counted as a problem
}

