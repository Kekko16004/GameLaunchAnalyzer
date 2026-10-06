#!/usr/bin/env bash
# game-launch-strategist skill installer for Linux / macOS (bash 3.2+).
# Windows: use installer.bat / install.ps1.
#
#   ./install.sh                 interactive menu
#   ./install.sh --all           every supported environment
#   ./install.sh --claude        Claude Code only (also --antigravity --kilo --agents)
#   ./install.sh --all --mode copy      copy files instead of symlinking (default: link)
#   ./install.sh --uninstall     remove from every environment
#
# Only the skill itself is installed (SKILL.md, references/, scripts/) plus the slash command;
# .git, installers and the README are left out.
set -euo pipefail
: "${HOME:?HOME is not set: refusing to install into the filesystem root}"

SKILL="game-launch-strategist"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD="SKILL.md references scripts"
CMD_SRC="$SRC/commands/$SKILL.md"
LEGACY="game_launch_strategist launch-strategist gamelaunchstrategist"
MODE="link"
UNINSTALL=0
SELECTED=""

label() {
  case "$1" in
    claude) echo "Claude Code" ;; antigravity) echo "Antigravity IDE" ;;
    kilo) echo "Kilo / Kilocode" ;; agents) echo "Agents Hub" ;;
  esac
}

skill_paths() {
  case "$1" in
    claude) echo "$HOME/.claude/skills/$SKILL" ;;
    antigravity) echo "$HOME/.gemini/config/skills/$SKILL" ;;
    kilo) echo "$HOME/.kilo/skills/$SKILL"; echo "$HOME/.config/kilo/skills/$SKILL"; echo "$HOME/.kilocode/skills/$SKILL" ;;
    agents) echo "$HOME/.agents/skills/$SKILL" ;;
  esac
}

command_paths() {
  case "$1" in
    claude) echo "$HOME/.claude/commands/$SKILL.md" ;;
    antigravity) echo "$HOME/.gemini/config/global_workflows/$SKILL.md" ;;
    kilo)
      for d in "$HOME/.kilo" "$HOME/.config/kilo" "$HOME/.kilocode"; do
        echo "$d/commands/$SKILL.md"; echo "$d/command/$SKILL.md"
      done ;;
    agents) : ;;
  esac
}

remove_path() { # rm -rf never follows symlinks, so links into the source repo are safe to delete
  if [ -e "$1" ] || [ -L "$1" ]; then rm -rf -- "$1"; fi
}

install_skill_dir() {
  dest="$1"
  mkdir -p "$dest"
  for item in $PAYLOAD; do
    [ -e "$SRC/$item" ] || continue
    if [ "$MODE" = "link" ]; then ln -s "$SRC/$item" "$dest/$item"; else cp -R "$SRC/$item" "$dest/$item"; fi
  done
  if [ "$MODE" = "copy" ]; then find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true; fi
}

install_target() {
  echo "[+] Configuring: $(label "$1")"
  for p in $(skill_paths "$1" | tr ' ' '\037'); do
    p="$(printf '%s' "$p" | tr '\037' ' ')"
    mkdir -p "$(dirname "$p")"
    for legacy in $LEGACY; do remove_path "${p//$SKILL/$legacy}"; done
    remove_path "$p"
    install_skill_dir "$p"
    echo "    $MODE: $p"
  done
  [ -f "$CMD_SRC" ] || return 0
  for c in $(command_paths "$1" | tr ' ' '\037'); do
    c="$(printf '%s' "$c" | tr '\037' ' ')"
    mkdir -p "$(dirname "$c")"
    for legacy in $LEGACY; do remove_path "${c//$SKILL/$legacy}"; done
    cp "$CMD_SRC" "$c"
    echo "    command: $c"
  done
}

uninstall_target() {
  echo "[-] Removing from: $(label "$1")"
  for p in $(skill_paths "$1" | tr ' ' '\037'); do
    p="$(printf '%s' "$p" | tr '\037' ' ')"; [ -e "$p" ] || [ -L "$p" ] && { remove_path "$p"; echo "    removed skill: $p"; }
  done
  for c in $(command_paths "$1" | tr ' ' '\037'); do
    c="$(printf '%s' "$c" | tr '\037' ' ')"; [ -e "$c" ] && { remove_path "$c"; echo "    removed command: $c"; }
  done
  return 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --all) SELECTED="claude antigravity kilo agents" ;;
    --claude) SELECTED="$SELECTED claude" ;;
    --antigravity) SELECTED="$SELECTED antigravity" ;;
    --kilo) SELECTED="$SELECTED kilo" ;;
    --agents) SELECTED="$SELECTED agents" ;;
    --uninstall) UNINSTALL=1 ;;
    --mode) shift; MODE="${1:-}" ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
case "$MODE" in link|copy) ;; *) echo "--mode must be link or copy" >&2; exit 2 ;; esac
[ -f "$SRC/SKILL.md" ] || { echo "SKILL.md not found in $SRC" >&2; exit 1; }

if [ "$UNINSTALL" = 1 ]; then
  for k in claude antigravity kilo agents; do uninstall_target "$k"; done
  echo; echo "Uninstallation completed."; exit 0
fi

if [ -z "${SELECTED// /}" ]; then
  echo "Select target environments:"
  echo "  [1] Claude Code       (~/.claude)"
  echo "  [2] Antigravity IDE   (~/.gemini/config)"
  echo "  [3] Kilo / Kilocode   (~/.kilo, ~/.config/kilo, ~/.kilocode)"
  echo "  [4] Agents Hub        (~/.agents)"
  echo "  [5] All environments (recommended)"
  echo "  [6] Uninstall from all environments"
  echo "  [0] Exit"
  read -r -p "Choice [0-6]: " choice
  case "$choice" in
    1) SELECTED="claude" ;; 2) SELECTED="antigravity" ;; 3) SELECTED="kilo" ;; 4) SELECTED="agents" ;;
    5) SELECTED="claude antigravity kilo agents" ;;
    6) for k in claude antigravity kilo agents; do uninstall_target "$k"; done; echo "Uninstallation completed."; exit 0 ;;
    0) echo "Operation cancelled."; exit 0 ;;
    *) echo "Invalid choice." >&2; exit 1 ;;
  esac
fi

echo
for k in $SELECTED; do install_target "$k"; done
echo
echo "Installation completed. Command available: /$SKILL"
