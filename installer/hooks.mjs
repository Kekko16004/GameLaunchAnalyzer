// game-launch-strategist hooks for the skillkit installer: Python check, script compile check, optional unit tests.
import fs from "node:fs";
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

// ---------------------------------------------------------------- Agent Reach (internal component: social platforms, read-only)
// https://github.com/Panniantong/agent-reach (MIT). Not a global program: the skill builds a PRIVATE copy, pinned by version and sha256,
// with scripts/research/reach_runtime.py (own Python venv, own state folder, local patches: browser language, state folder, no global
// skill). Real folder ~/.game-launch-strategist/reach, linked as <skill>/tools/agent-reach. `install.mjs update` refreshes and repairs
// it; an old global install (~/.agent-reach) is COPIED in once, never moved. Logins stay with the owner (reach.py login <canale>).
const skipped = (ctx) => String(ctx.flags.skip || "").split(/[,\s]+/).includes("agent-reach");
const runtimeScript = (ctx, base) => path.join(base, "scripts", "research", "reach_runtime.py");
const skillDir = (ctx) => path.join(ctx.CANON, "game-launch-strategist");
const gls = (ctx) => process.env.GLS_HOME || path.join(ctx.HOME || process.env.USERPROFILE || process.env.HOME || "", ".game-launch-strategist");
function jsonOut(out) {
  const s = String(out || ""); const i = s.indexOf("{"), j = s.lastIndexOf("}");
  if (i < 0 || j < i) return null;
  try { return JSON.parse(s.slice(i, j + 1)); } catch { return null; }
}
// state of the internal copy (installed, version, patches), read from the given skill folder (repo before install, canonical after)
function reachCheck(ctx, py, base) {
  const script = runtimeScript(ctx, base);
  if (!py || !ctx.exists(script)) return null;
  const r = ctx.runSync(py.exe, ["-B", script, "check", "--json"], { timeout: 60000, cwd: ctx.HOME, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  return jsonOut(r.out);
}
const oldGlobal = (ctx) => {
  const home = ctx.HOME || process.env.USERPROFILE || process.env.HOME || "";
  return ctx.which("agent-reach") || (ctx.exists(path.join(home, ".local", "bin", ctx.isWin ? "agent-reach.exe" : "agent-reach")) ? "~/.local/bin/agent-reach" : "");
};

export async function detect(ctx) {
  // the Python row itself comes from "requires" in skillkit.json; keep the real path for the checks below
  const py = findPython(ctx);
  ctx.vars.python = py?.exe || "";
  ctx.detected.python = py;
  const it = ctx.lang === "it";
  const c = reachCheck(ctx, py, ctx.ROOT);
  ctx.detected.reach = c?.installed ? c : null;
  ctx.ui.row(c?.installed ? (c.patches_ok ? "ok" : "warn") : "off", "Agent Reach", c?.installed ? `${c.version} ${ctx.c.faint(it ? "(interno)" : "(internal)")}` : ctx.c.faint(it ? "non installato" : "not installed"),
    ctx.c.dim(it ? "componente interno: social in sola lettura" : "internal component: social platforms, read-only"));
}

export async function questions(ctx) {
  if (ctx.detected.reach || skipped(ctx) || ctx.choices.agentReach === true) return;
  const it = ctx.lang === "it";
  ctx.choices.agentReach = await ctx.ui.confirm({ title: it ? "Installo Agent Reach dentro la skill (X, TikTok, Instagram, Reddit... in sola lettura)?" : "Install Agent Reach inside the skill (X, TikTok, Instagram, Reddit... read-only)?", yes: true, lang: ctx.lang });
}

// <skill>/tools/agent-reach -> the real folder (recreated after every mirror of the skill; never a copy)
function reachLink(ctx, real) {
  const at = path.join(skillDir(ctx), "tools", "agent-reach");
  try {
    if (ctx.exists(at) && !isLinkPath(at)) return at;   // a real folder put there by hand: left alone (reach_runtime uses it)
    ctx.link(real, at);
    return at;
  } catch { return ""; }
}
function isLinkPath(p) { try { return fs.lstatSync(p).isSymbolicLink(); } catch { return false; } }

async function reachTask(ctx, py) {
  const { ui, run, lang } = ctx;
  const it = lang === "it";
  await ui.task(it ? "Agent Reach (interno)" : "Agent Reach (internal)", async (t) => {
    if (ctx.DRY) return { state: "skip" };
    if (skipped(ctx) || (ctx.choices.agentReach === false && !ctx.detected.reach)) return { state: "skip", note: it ? "escluso" : "skipped" };
    if (!py) return { state: "warn", note: it ? "serve Python 3.10+" : "needs Python 3.10+" };
    const script = runtimeScript(ctx, skillDir(ctx));
    if (!ctx.exists(script)) return { state: "warn", note: "reach_runtime.py?" };
    const before = ctx.detected.reach?.version || "";
    const r = await run(py.exe, ["-B", script, "install", "--update", "--json"], { onLine: t.update, cwd: ctx.HOME, timeout: 1800000, env: { PYTHONIOENCODING: "utf-8" } });
    const j = jsonOut(r.out.split(/\r?\n/).filter((l) => l.trim().startsWith("{")).pop());
    if (!j || r.code !== 0 && !j.installed) {
      const last = r.out.trim().split(/\r?\n/).filter(Boolean).pop() || "install";
      return { state: "warn", note: last.slice(0, 140) };
    }
    const link = reachLink(ctx, j.root);
    ctx.detected.reach = reachCheck(ctx, py, skillDir(ctx)) || { installed: true, version: j.version };
    ctx.choices.agentReach = true;
    const bad = Object.entries(j.patches || {}).filter(([, v]) => !["ok", "patched"].includes(v)).map(([k]) => k);
    if (j.migration?.status === "copied") ctx.notes.push(it ? `Agent Reach: copiata la configurazione di ${j.migration.src} (${j.migration.files} file). L'originale resta com'era.`
                                                           : `Agent Reach: copied the setup of ${j.migration.src} (${j.migration.files} files). The original is untouched.`);
    const g = oldGlobal(ctx);
    if (g) ctx.footer.push(ctx.c.dim(it ? `Agent Reach globale ancora presente (${g}): la skill non lo usa più; si può togliere con uv tool uninstall agent-reach`
                                       : `A global Agent Reach is still installed (${g}): the skill no longer uses it; remove it with uv tool uninstall agent-reach`));
    const note = `${before && before !== j.version ? `${before} ${ctx.g.arrow} ` : ""}${j.version} ${ctx.g.dot} ${ctx.tilde(link || j.root)}`;
    return bad.length ? { state: "warn", note: `${note} ${ctx.g.dot} ${it ? "correzioni mancanti" : "patches missing"}: ${bad.join(", ")}` } : { note };
  });
}

// channels ready / not ready, through the skill's own adapter (same table as `reach.py doctor`)
function reachDoctor(ctx, py) {
  const script = path.join(skillDir(ctx), "scripts", "research", "reach.py");
  if (!py || !ctx.exists(script)) return null;
  const r = ctx.runSync(py.exe, ["-B", script, "doctor", "--json"], { timeout: 120000, cwd: ctx.HOME, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  return jsonOut(r.out);
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
  await reachTask(ctx, py);
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
  if (!ctx.detected.python) ctx.footer.push(`${ctx.c.warn(ctx.g.warn)} Python 3.10+  ${ctx.isWin ? "winget install --id Python.Python.3.12 -e" : "brew install python"}`);
  const r = ctx.detected.reach;
  rows.push(["Agent Reach", r ? `${r.version || "?"} ${it ? "(interno)" : "(internal)"}${ctx.detected.reachDoctor ? ` ${ctx.g.dot} ${(ctx.detected.reachDoctor.ready || []).length} ${it ? "canali pronti" : "channels ready"}` : ""}` : (it ? "non installato" : "not installed")]);
  const reachPy = path.join(skillDir(ctx), "scripts", "research", "reach.py").split(path.sep).join("/");
  if (r && (ctx.detected.reachDoctor?.not_ready || []).some((c) => ["twitter", "instagram", "tiktok", "reddit"].includes(c)))
    ctx.footer.push(ctx.c.dim(it ? `Social con login (li fai tu, nel browser dedicato): ! python ${reachPy} login twitter | instagram | reddit  ·  elenco completo: python ${reachPy} setup`
                                 : `Logged-in socials (you log in, in the dedicated browser): ! python ${reachPy} login twitter | instagram | reddit  ·  full list: python ${reachPy} setup`));
}

export async function doctor(ctx) {
  const it = ctx.lang === "it";
  const py = findPython(ctx);
  const c = reachCheck(ctx, py, skillDir(ctx));
  if (!c?.installed) { ctx.ui.row("off", "Agent Reach", ctx.c.faint(it ? "non installato (opzionale)" : "not installed (optional)"), ctx.c.dim("node installer/install.mjs update")); return 0; }
  const bad = Object.entries(c.patches || {}).filter(([, v]) => v !== "ok").map(([k]) => k);
  ctx.ui.row(bad.length || !c.up_to_date ? "warn" : "ok", "Agent Reach", `${c.version} ${it ? "(interno)" : "(internal)"}`,
    ctx.c.faint(`${ctx.tilde(c.root)}${bad.length ? ` ${ctx.g.dot} ${it ? "correzioni mancanti" : "patches missing"}: ${bad.join(", ")}` : ""}${c.up_to_date ? "" : ` ${ctx.g.dot} ${it ? "versione" : "version"} ${c.pinned}?`}`));
  if (!c.link_ok) ctx.ui.row("warn", it ? "collegamento" : "link", ctx.tilde(c.link), ctx.c.dim("node installer/install.mjs update"));
  const d = reachDoctor(ctx, py);
  if (d) ctx.ui.row(d.ready?.length ? "ok" : "warn", it ? "social pronti" : "social ready", (d.ready || []).join(", ") || "—",
    d.not_ready?.length ? ctx.c.faint(`${it ? "non pronti" : "not ready"}: ${d.not_ready.join(", ")}`) : "");
  else ctx.ui.row("warn", "reach.py", it ? "doctor non riuscito" : "doctor failed");
  return 0;   // optional component: never counted as a problem
}
