# GameLaunchStrategist Skill Installer
# Compatible with Windows PowerShell 5.1+ and PowerShell 7+
[CmdletBinding()]
param(
    [switch]$All,
    [switch]$Claude,
    [switch]$Antigravity,
    [switch]$Kilo,
    [switch]$Agents,
    [switch]$Uninstall,
    [ValidateSet("link", "copy")]
    [string]$Mode = "link"
)

$ErrorActionPreference = "Stop"
$SkillName = "game-launch-strategist"
$SourceDir = $PSScriptRoot
$User = $env:USERPROFILE
$CmdSource = Join-Path $SourceDir "commands\game-launch-strategist.md"
$SkillFile = Join-Path $SourceDir "SKILL.md"
# Only these items are part of the skill (no .git, installers, README, command file)
$Payload = @("SKILL.md", "references", "scripts")

if (-not (Test-Path -LiteralPath $SkillFile)) {
    Write-Error "SKILL.md not found in $SourceDir"
    exit 1
}

$Targets = [ordered]@{
    claude = @{
        Label = "Claude Code"
        Skills = @("$User\.claude\skills\$SkillName")
        Commands = @("$User\.claude\commands\$SkillName.md")
    }
    antigravity = @{
        Label = "Antigravity IDE"
        Skills = @("$User\.gemini\config\skills\$SkillName")
        Commands = @("$User\.gemini\config\global_workflows\$SkillName.md")
    }
    kilo = @{
        Label = "Kilo / Kilocode"
        Skills = @(
            "$User\.kilo\skills\$SkillName",
            "$User\.config\kilo\skills\$SkillName",
            "$User\.kilocode\skills\$SkillName"
        )
        Commands = @(
            "$User\.kilo\commands\$SkillName.md",
            "$User\.kilo\command\$SkillName.md",
            "$User\.config\kilo\commands\$SkillName.md",
            "$User\.config\kilo\command\$SkillName.md",
            "$User\.kilocode\commands\$SkillName.md",
            "$User\.kilocode\command\$SkillName.md"
        )
    }
    agents = @{
        Label = "Agents Hub"
        Skills = @("$User\.agents\skills\$SkillName")
        Commands = @()
    }
}

$LegacyNames = @("game_launch_strategist", "launch-strategist", "gamelaunchstrategist")

function Remove-ExistingPath([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $item = Get-Item -LiteralPath $Path -Force
    $isLink = [bool]($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
    if ($item.PSIsContainer -and -not $isLink) {
        # Delete links inside first (non-recursive) so a recursive delete can never follow them into the source repo
        foreach ($child in Get-ChildItem -LiteralPath $Path -Force) {
            if ($child.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                if ($child.PSIsContainer) { [System.IO.Directory]::Delete($child.FullName, $false) }
                else { [System.IO.File]::Delete($child.FullName) }
            }
        }
        Remove-Item -LiteralPath $Path -Recurse -Force
    } elseif ($item.PSIsContainer) {
        [System.IO.Directory]::Delete($Path, $false)
    } else {
        Remove-Item -LiteralPath $Path -Force
    }
}

function Copy-SkillPayload([string]$Dest) {
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    foreach ($name in $Payload) {
        $src = Join-Path $SourceDir $name
        if (Test-Path -LiteralPath $src) { Copy-Item -LiteralPath $src -Destination (Join-Path $Dest $name) -Recurse -Force }
    }
    Get-ChildItem -LiteralPath $Dest -Recurse -Directory -Force -Filter "__pycache__" -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
}

function Link-SkillPayload([string]$Dest) {
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    foreach ($name in $Payload) {
        $src = Join-Path $SourceDir $name
        $dst = Join-Path $Dest $name
        if (-not (Test-Path -LiteralPath $src)) { continue }
        if ((Get-Item -LiteralPath $src).PSIsContainer) {
            New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
        } else {
            try { New-Item -ItemType SymbolicLink -Path $dst -Target $src -ErrorAction Stop | Out-Null }
            catch {
                try { New-Item -ItemType HardLink -Path $dst -Target $src -ErrorAction Stop | Out-Null }
                catch { Copy-Item -LiteralPath $src -Destination $dst -Force }
            }
        }
    }
}

function Install-Target([string]$Key) {
    $conf = $Targets[$Key]
    Write-Host "[+] Configuring: $($conf.Label)"

    foreach ($skillPath in $conf.Skills) {
        $parent = Split-Path -Path $skillPath -Parent
        if (-not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        foreach ($legacy in $LegacyNames) {
            $legacySkill = $skillPath -replace [regex]::Escape($SkillName), $legacy
            Remove-ExistingPath $legacySkill
        }
        Remove-ExistingPath $skillPath
        if ($Mode -eq "link") {
            try {
                Link-SkillPayload $skillPath
                Write-Host "    Link (updated): $skillPath -> $SourceDir"
            } catch {
                Write-Host "    Fallback to copy for: $skillPath"
                Remove-ExistingPath $skillPath
                Copy-SkillPayload $skillPath
            }
        } else {
            Copy-SkillPayload $skillPath
            Write-Host "    Copy (updated): $skillPath"
        }
    }

    if (Test-Path -LiteralPath $CmdSource) {
        foreach ($cmdPath in $conf.Commands) {
            $parent = Split-Path -Path $cmdPath -Parent
            if (-not (Test-Path -LiteralPath $parent)) {
                New-Item -ItemType Directory -Path $parent -Force | Out-Null
            }
            foreach ($legacy in $LegacyNames) {
                $legacyCmd = $cmdPath -replace [regex]::Escape($SkillName), $legacy
                if (Test-Path -LiteralPath $legacyCmd) {
                    Remove-Item -LiteralPath $legacyCmd -Force
                    Write-Host "    Cleaned legacy command: $legacyCmd"
                }
            }
            Copy-Item -Path $CmdSource -Destination $cmdPath -Force
            Write-Host "    Command (updated): $cmdPath"
        }
    }
}

function Uninstall-Target([string]$Key) {
    $conf = $Targets[$Key]
    Write-Host "[-] Removing from: $($conf.Label)"
    foreach ($skillPath in $conf.Skills) {
        if (Test-Path -LiteralPath $skillPath) {
            Remove-ExistingPath $skillPath
            Write-Host "    Removed skill: $skillPath"
        }
    }
    foreach ($cmdPath in $conf.Commands) {
        if (Test-Path -LiteralPath $cmdPath) {
            Remove-Item -LiteralPath $cmdPath -Force
            Write-Host "    Removed command: $cmdPath"
        }
    }
}

if ($Uninstall) {
    foreach ($key in $Targets.Keys) {
        Uninstall-Target $key
    }
    Write-Host "`nUninstallation completed."
    exit 0
}

$selected = @()
if ($All) {
    $selected = @("claude", "antigravity", "kilo", "agents")
} else {
    if ($Claude) { $selected += "claude" }
    if ($Antigravity) { $selected += "antigravity" }
    if ($Kilo) { $selected += "kilo" }
    if ($Agents) { $selected += "agents" }
}

if ($selected.Count -eq 0) {
    Clear-Host
    Write-Host "============================================================"
    Write-Host "Game Launch Strategist Skill Installer"
    Write-Host "============================================================"
    Write-Host "Select target environments:`n"
    Write-Host "  [1] Claude Code       (~/.claude)"
    Write-Host "  [2] Antigravity IDE   (~/.gemini/config)"
    Write-Host "  [3] Kilo / Kilocode   (~/.kilo, ~/.config/kilo, ~/.kilocode)"
    Write-Host "  [4] Agents Hub        (~/.agents)"
    Write-Host "  [5] All environments (Recommended)"
    Write-Host "  [6] Uninstall from all environments"
    Write-Host "  [0] Exit"
    Write-Host "============================================================"
    $choice = Read-Host "Choice [0-6]"

    switch ($choice) {
        "1" { $selected = @("claude") }
        "2" { $selected = @("antigravity") }
        "3" { $selected = @("kilo") }
        "4" { $selected = @("agents") }
        "5" { $selected = @("claude", "antigravity", "kilo", "agents") }
        "6" {
            foreach ($k in $Targets.Keys) { Uninstall-Target $k }
            Write-Host "`nUninstallation completed."
            exit 0
        }
        "0" {
            Write-Host "Operation cancelled."
            exit 0
        }
        default {
            Write-Host "Invalid choice."
            exit 1
        }
    }
}

Write-Host "`nStarting installation...`n"
foreach ($key in $selected) {
    Install-Target $key
}

Write-Host "`nInstallation completed successfully."
Write-Host "Command available: /game-launch-strategist"
