# Third-party notices

game-launch-strategist installs and runs the MIT-licensed project below as an internal component. Its source is **not** stored in this repository: the skill installer (`node installer/install.mjs install | update`, through `scripts/research/reach_runtime.py`) downloads the pinned release from GitHub, checks it by sha256, installs it into a private Python environment and applies the local modifications listed below.

## 1. Agent Reach

- Repository: https://github.com/Panniantong/agent-reach
- Version: `1.6.1` (release `v1.6.1`, 2026-11-01), file `agent_reach-1.6.1-py3-none-any.whl`, sha256 `6a1085cae53118c5f1271ab24041e55ec17c509932612b919208f04d10183acb`
- License: MIT. Copyright (c) 2025 Agent Eyes
- Installed in: `~/.game-launch-strategist/reach/` (`venv/` = the package and its dependencies, `home/` = its state), linked inside the skill as `tools/agent-reach`. Its own dependencies (requests, loguru, PyYAML, yt-dlp; and, when a channel needs them, OpenCLI, CloakBrowser, bilibili-cli) keep their own licences and are installed into that private folder, never globally.
- Used by: `scripts/research/reach.py` (adapter) and `scripts/research/reach_runtime.py` (install, patches, check, migration).
- Modifications (applied to the installed copy after every install/update, idempotent, each marked `GLS-PATCH:<id>`; `reach_runtime.py check` and `install.mjs doctor` verify them):
  - `home`: the state folder comes from the env `AGENT_REACH_HOME` (set by the skill to its private folder) instead of the fixed `~/.agent-reach` (`utils/paths.py`, `config.py`, `runtime/browser.py`, `runtime/sessions.py`, `runtime/state.py`).
  - `locale`: the dedicated browser takes its language from the env `REACH_BROWSER_LOCALE`, else the system language, else `en-US`, instead of the fixed `zh-CN` (`runtime/browser_watcher.py`).
  - `subs`: default YouTube subtitle languages `en,en-orig,it` instead of `zh-Hans,zh,en,en-orig` (`channels/youtube.py`).
  - `embedded`: when run by the skill (`AGENT_REACH_EMBEDDED`), no skill file or links are written into other AI tools, and `update` / `uninstall` are refused (the skill installer owns the copy) (`runtime/manage.py`).
- Messages that Agent Reach prints in Chinese are replaced by Italian text in `reach.py` before they are shown; the upstream code is not changed for that.

---

## License texts

### Agent Reach

```
MIT License

Copyright (c) 2025 Agent Eyes

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
