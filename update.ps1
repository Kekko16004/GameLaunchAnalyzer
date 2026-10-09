<#
  game-launch-strategist - one-click update from GitHub, then reinstall in every IDE

    update.bat                    everything: safety backup, download, check, reinstall, verify
    update.bat -NoSelf            skip the download (only reinstall this folder)
    update.bat -NoInstall         download only
    update.bat -Test              also run the skill's unit tests (tests/run_all.py) before installing
    update.bat -Mode copy         install as copies instead of links
    update.bat -Branch dev        follow another branch (default: the one checked out, else main)

  Steps
    0. safety: installed copies that differ from this folder (edits made inside an IDE's skills folder) are saved to
       ~/.game-launch-strategist/backups/<date>/ before anything is overwritten, with the list of changed files
    1. download: git pull --ff-only --autostash if this is a git clone, otherwise the latest zip from GitHub
    2. check: Python found, every script compiles (and -Test runs the unit tests)
    3. reinstall with the last install's choices (install.ps1 -Reuse): Claude Code, Antigravity, Kilo, Agents, Codex
    4. verify: every installed SKILL.md matches this folder
#>
param([switch]$NoSelf, [switch]$NoInstall, [switch]$Test, [ValidateSet("link", "copy")][string]$Mode, [string]$Branch)

$ErrorActionPreference = "Stop"
$Repo = "Kekko16004/GameLaunchAnalyzer"
$SkillName = "game-launch-strategist"
$Root = $PSScriptRoot
$User = $env:USERPROFILE
$StateDir = if ($env:GLS_HOME) { $env:GLS_HOME } else { Join-Path $User ".game-launch-strategist" }
$Payload = @("SKILL.md", "references", "scripts")
$warn = New-Object System.Collections.Generic.List[string]

function Step([string]$t) { Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
function Warn([string]$t) { Write-Host "WARN $t" -ForegroundColor Yellow; $warn.Add($t) }

# Every place an install can live (same list as install.ps1).
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "$User\.codex" }
$Installed = @(
  "$User\.claude\skills\$SkillName", "$User\.gemini\config\skills\$SkillName",
  "$User\.kilo\skills\$SkillName", "$User\.config\kilo\skills\$SkillName", "$User\.kilocode\skills\$SkillName",
  "$User\.agents\skills\$SkillName", "$CodexHome\skills\$SkillName"
) | Where-Object { Test-Path -LiteralPath (Join-Path $_ "SKILL.md") }

function Hash([string]$f) {
  # .NET directly: Get-FileHash is missing on some Windows PowerShell setups
  $sha = [Security.Cryptography.SHA1]::Create(); $st = [IO.File]::OpenRead($f)
  try { return [BitConverter]::ToString($sha.ComputeHash($st)) } finally { $st.Dispose(); $sha.Dispose() }
}
function Get-Rel([string]$base, [string]$full) { return $full.Substring($base.TrimEnd('\').Length + 1) }
function Get-PayloadFiles([string]$dir) {
  $out = @{}
  foreach ($n in $Payload) {
    $p = Join-Path $dir $n
    if (-not (Test-Path -LiteralPath $p)) { continue }
    Get-ChildItem -LiteralPath $p -Recurse -File -Force -ErrorAction SilentlyContinue |
      Where-Object { $_.FullName -notmatch '\\__pycache__\\' -and $_.Extension -notin @('.pyc', '.bak', '.bak2', '.orig') } |
      ForEach-Object { $out[(Get-Rel $dir $_.FullName)] = Hash $_.FullName }
  }
  return $out
}

# ---------- 0. safety backup of edited installed copies ----------
Step "0/4 Controllo delle copie installate"
$src = Get-PayloadFiles $Root
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$seen = @{}
foreach ($dir in $Installed) {
  $real = (Get-Item -LiteralPath (Join-Path $dir "references") -Force -ErrorAction SilentlyContinue)
  if ($real -and $real.LinkType) {
    $tgt = @($real.Target)[0]
    if ($tgt -and ([IO.Path]::GetFullPath($tgt).TrimEnd('\') -ne [IO.Path]::GetFullPath((Join-Path $Root "references")).TrimEnd('\'))) { Warn "$dir è collegato a un'altra cartella ($tgt): verrà ricollegato a questa" }
    $sk = Join-Path $dir "SKILL.md"
    $ski = Get-Item -LiteralPath $sk -Force
    $skh = Hash $sk
    if ($ski.LinkType -ne "SymbolicLink" -and $skh -ne (Hash (Join-Path $Root "SKILL.md")) -and $seen.ContainsKey($skh)) {
      Write-Host "old   $dir (SKILL.md già salvato da $($seen[$skh]))"
    } elseif ($ski.LinkType -ne "SymbolicLink" -and $skh -ne (Hash (Join-Path $Root "SKILL.md"))) {
      $seen[$skh] = $dir
      # a copy (or a stale hard link) of SKILL.md: may hold edits made inside the IDE folder
      $dest = Join-Path $StateDir ("backups\$stamp\" + ($dir.Replace($User, "").Trim('\') -replace '[\\/:]', '_'))
      New-Item -ItemType Directory -Force -Path $dest | Out-Null
      Copy-Item -LiteralPath $sk -Destination $dest -Force
      Warn "$sk era diverso da quello della cartella: salvato in $dest (confrontalo se ci avevi scritto qualcosa)"
    } else { Write-Host "link  $dir" }
    continue
  }
  $inst = Get-PayloadFiles $dir
  $changed = @($inst.Keys | Where-Object { -not $src.ContainsKey($_) -or $src[$_] -ne $inst[$_] } | Sort-Object)
  if ($changed.Count -eq 0) { Write-Host "ok    $dir"; continue }
  $sig = ($changed | ForEach-Object { "$_=$($inst[$_])" }) -join "|"
  if ($seen.ContainsKey($sig)) { Write-Host "same  $dir (stesse modifiche di $($seen[$sig]))"; continue }
  $seen[$sig] = $dir
  $dest = Join-Path $StateDir ("backups\$stamp\" + ($dir.Replace($User, "").Trim('\') -replace '[\\/:]', '_'))
  foreach ($rel in $changed) {
    $to = Join-Path $dest $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $to) | Out-Null
    Copy-Item -LiteralPath (Join-Path $dir $rel) -Destination $to -Force
  }
  Warn "$dir aveva $($changed.Count) file diversi da questa cartella: salvati in $dest"
  $changed | Select-Object -First 12 | ForEach-Object { Write-Host "        $_" }
  if ($changed.Count -gt 12) { Write-Host "        ... e altri $($changed.Count - 12)" }
}

# ---------- 1. download ----------
if (-not $NoSelf) {
  Step "1/4 Download da GitHub ($Repo)"
  $git = Get-Command git -ErrorAction SilentlyContinue
  if ($git -and (Test-Path -LiteralPath (Join-Path $Root ".git"))) {
    $before = (& git -C $Root rev-parse --short HEAD).Trim()
    $cur = (& git -C $Root rev-parse --abbrev-ref HEAD).Trim()
    $want = if ($Branch) { $Branch } elseif ($cur -ne "HEAD") { $cur } else { "main" }
    if ($cur -ne $want) { & git -C $Root checkout $want; if ($LASTEXITCODE -ne 0) { Warn "impossibile passare al ramo $want" } }
    & git -C $Root pull --ff-only --autostash origin $want
    if ($LASTEXITCODE -ne 0) {
      Warn "git pull non riuscito (rami divergenti o conflitti con modifiche locali). Sistemalo con GitHub Desktop e rilancia update.bat. Continuo con la versione locale."
    } else {
      $after = (& git -C $Root rev-parse --short HEAD).Trim()
      if ($before -eq $after) { Write-Host "Già aggiornato ($after)." }
      else { Write-Host "Aggiornato ${before} -> ${after}:"; & git -C $Root log --oneline "$before..$after" | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" } }
    }
    $dirty = & git -C $Root status --porcelain
    if ($dirty) { Write-Host "Nota: ci sono modifiche locali non salvate in git (restano, non vengono perse):"; $dirty | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" } }
  } else {
    $b = if ($Branch) { $Branch } else { "main" }
    $zip = Join-Path $env:TEMP "gls-$stamp.zip"; $tmp = Join-Path $env:TEMP "gls-$stamp"
    Write-Host "Questa cartella non è un clone git: scarico lo zip del ramo $b."
    try {
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$Repo/archive/refs/heads/$b.zip" -OutFile $zip
      Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
      $top = Get-ChildItem -LiteralPath $tmp -Directory | Select-Object -First 1
      if (-not (Test-Path -LiteralPath (Join-Path $top.FullName "SKILL.md"))) { throw "lo zip non contiene SKILL.md" }
      $bk = Join-Path $StateDir "backups\$stamp\source"
      New-Item -ItemType Directory -Force -Path $bk | Out-Null
      foreach ($n in $Payload) { $p = Join-Path $Root $n; if (Test-Path -LiteralPath $p) { Copy-Item -LiteralPath $p -Destination $bk -Recurse -Force } }
      Get-ChildItem -LiteralPath $top.FullName -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $Root -Recurse -Force }
      Write-Host "Aggiornato dallo zip. Versione precedente salvata in $bk"
    } catch { Warn "download non riuscito ($($_.Exception.Message)). Continuo con la versione locale." }
    finally { Remove-Item -LiteralPath $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue }
  }
}

# ---------- 2. check ----------
Step "2/4 Controllo degli script"
$py = $null; $pyArgs = @()
foreach ($c in @(@("py", "-3"), @("python"), @("python3"))) {
  if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
  $extra = @($c | Select-Object -Skip 1)
  try { $out = (& $c[0] @extra -c "import sys; print(sys.version.split()[0])" 2>$null | Out-String).Trim() } catch { $out = "" }
  if ($out -match '^3\.(\d+)' -and [int]$Matches[1] -ge 9) { $py = $c[0]; $pyArgs = $extra; $ver = $out; break }
}
if (-not $py) { Warn "Python 3.9+ non trovato: gli script della skill non gireranno finché non lo installi (python.org)." }
else {
  $env:PYTHONIOENCODING = "utf-8"
  Write-Host "Python $ver ($py)"
  & $py @pyArgs -m compileall -q (Join-Path $Root "scripts") | Out-Null
  if ($LASTEXITCODE -ne 0) { Warn "alcuni script non compilano con Python ${ver}: controlla l'output sopra." } else { Write-Host "Tutti gli script compilano." }
  Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  if ($Test -and (Test-Path -LiteralPath (Join-Path $Root "tests\run_all.py"))) {
    & $py @pyArgs (Join-Path $Root "tests\run_all.py")
    if ($LASTEXITCODE -ne 0) { Warn "alcuni test non passano: installo lo stesso, ma guarda l'output." }
  }
}

# ---------- 3. reinstall ----------
if (-not $NoInstall) {
  Step "3/4 Reinstallazione negli IDE"
  $a = @{ Reuse = $true }
  if ($Mode) { $a.Mode = $Mode }
  & (Join-Path $Root "install.ps1") @a
  # ---------- 4. verify ----------
  Step "4/4 Verifica"
  $want = Hash (Join-Path $Root "SKILL.md")
  $last = Join-Path $StateDir "install.json"
  $hosts = if (Test-Path -LiteralPath $last) { (Get-Content -Raw -LiteralPath $last | ConvertFrom-Json).hosts } else { @() }
  $check = @(
    "$User\.claude\skills\$SkillName", "$User\.gemini\config\skills\$SkillName",
    "$User\.kilo\skills\$SkillName", "$User\.config\kilo\skills\$SkillName", "$User\.kilocode\skills\$SkillName",
    "$User\.agents\skills\$SkillName", "$CodexHome\skills\$SkillName"
  ) | Where-Object { Test-Path -LiteralPath (Join-Path $_ "SKILL.md") }
  foreach ($d in $check) {
    $h = Hash (Join-Path $d "SKILL.md")
    if ($h -eq $want) { Write-Host "ok    $d" } else { Warn "$d non è aggiornato (forse è di un IDE non scelto all'installazione: install.bat per aggiungerlo)" }
  }
  if ($hosts) { Write-Host "IDE configurati: $($hosts -join ', ')" }
}

Write-Host ""
if ($warn.Count -eq 0) { Write-Host "Fatto. Riavvia gli IDE aperti (o apri una nuova chat) per caricare la skill aggiornata." -ForegroundColor Green }
else { Write-Host "Fatto con $($warn.Count) avvisi:" -ForegroundColor Yellow; $warn | ForEach-Object { Write-Host "  - $_" }; exit 1 }
