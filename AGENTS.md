# Agent Zero Connector — AGENTS.md

[Generated: 2026-04-03]

## Quick Reference

Tech Stack: Python 3.10+ | Textual 8+ | httpx | python-socketio (Engine.IO)
Run TUI: `agentzero` (or `python -m agent_zero_cli`)
**UI preview in browser: `python devtools/serve.py` → http://localhost:8566**
Run tests: `pytest tests/ -v`
Docs: `docs/` | Architecture: `docs/architecture.md` | TUI: `docs/tui-frontend.md`

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Repo Structure](#repo-structure)
3. [Dev Workflow — Browser Preview](#dev-workflow--browser-preview)
4. [Project Structure & Key Files](#project-structure--key-files)
5. [TUI Architecture](#tui-architecture)
6. [Plugin Backend](#plugin-backend)
7. [Development Patterns & Conventions](#development-patterns--conventions)
8. [Tests](#tests)
9. [Safety & Permissions](#safety--permissions)
10. [Troubleshooting](#troubleshooting)

---

## Project Overview

**a0-connector** has two parts that live in the same repo and work together:

1. **`agentzero` CLI** — a Textual terminal UI that connects to an Agent Zero
   instance, streams live agent events, and lets the user chat via a WebSocket
   protocol (`a0-connector.v1`).

2. **`plugin/a0_connector`** — the Agent Zero plugin (symlinked into
   `usr/plugins/`) that exposes the HTTP + Socket.IO API the CLI talks to.

Both must be running for a live end-to-end session. For **UI-only work** the
browser preview (see below) launches just the CLI against any available backend
(or none — the disconnected screen is still fully renderable).

---

## Dev Workflow — Browser Preview

> **This is the primary development loop for any UI work.**
> `textual-serve` and the project are already installed in `.venv`. Just run the
> server and open the browser.

### Start the preview

```bash
./.venv/bin/python devtools/serve.py          # http://localhost:8566
```

The TUI renders live in the browser tab. You can interact with it exactly as in
a terminal. Screenshots can be taken by the AI assistant at any time to verify
visual changes.

### Options

```bash
./.venv/bin/python devtools/serve.py --port 9000          # custom port
./.venv/bin/python devtools/serve.py --debug               # enable Textual devtools
```

Append `?fontsize=14` to the URL to adjust the rendered font size.

### Stop the server

`Ctrl+C` in the terminal running `serve.py`, or kill the background process.

### Other devtools scripts

| Script | Purpose | Output |
|--------|---------|--------|
| `devtools/snapshot.py` | SVG screenshot without a live backend | `devtools/snapshots/tui_snapshot.svg` |
| `devtools/activity_demo.py` | Simulate agent activity states (idle / busy / reset) | Three SVGs in `devtools/snapshots/` |

```bash
./.venv/bin/python devtools/snapshot.py       # quick layout check
./.venv/bin/python devtools/activity_demo.py  # verify progress indicator
```

### Typical UI change cycle

1. `python devtools/serve.py` — start the preview server (keep it running).
2. Edit `.tcss` or widget `.py` files.
3. Reload the browser tab (Textual hot-reload is *not* active via serve; tab
   refresh spawns a new process automatically).
4. Take a screenshot to verify, or ask the AI assistant to do it.
5. Run `pytest tests/test_app.py` to confirm no regressions.

---

## Project Structure & Key Files

```
a0-connector/
├── src/agent_zero_cli/          # CLI package
│   ├── app.py                   # AgentZeroCLI — main App, BINDINGS, compose(), event handlers
│   ├── client.py                # A0Client — HTTP + Socket.IO transport
│   ├── config.py                # CLIConfig, load_config(), save_env()
│   ├── __main__.py              # Entry point (python -m agent_zero_cli)
│   ├── widgets/
│   │   └── chat_input.py        # ChatInput — multi-line TextArea with spinner progress
│   ├── screens/
│   │   ├── host_input.py        # HostInputScreen — first-run host prompt
│   │   ├── login.py             # LoginScreen — username/password + save checkbox
│   │   └── chat_list.py         # ChatListScreen — switch between contexts
│   └── styles/
│       └── app.tcss             # All TUI CSS (colors, borders, layout, .progress-active)
├── plugin/a0_connector/         # Agent Zero plugin (backend)
├── devtools/                    # UI development tools (browser preview, snapshots)
│   ├── serve.py                 # textual-serve wrapper → browser at :8566
│   ├── snapshot.py              # SVG snapshot capture
│   ├── activity_demo.py         # Progress state demo
│   └── README.md                # Devtools usage guide
├── tests/
│   ├── test_app.py              # App logic, FakeInput/FakeRichLog stubs, lifecycle tests
│   ├── test_client.py           # A0Client HTTP + WS tests
│   └── test_plugin_backend.py   # Plugin import validation
├── docs/
│   ├── architecture.md          # Protocol, HTTP routes, WebSocket events, event bridge
│   ├── configuration.md         # Env vars, resolution order, persisted .env
│   ├── development.md           # Setup instructions, dev patterns
│   └── tui-frontend.md          # TUI file map, IDE terminal notes
├── pyproject.toml               # Package metadata and dependencies
└── requirements.txt             # Extra transitive deps (aiohttp, socketio extras)
```

---

## TUI Architecture

### Screen composition (`app.py:96-99`)

```
Screen
├── RichLog       #chat-log     — scrollable chat history
├── ChatInput     #message-input — multi-line input + progress placeholder
└── Footer                      — key bindings + command palette slot
```

### Key bindings (`app.py:61-79`)

| Key | Action | `show` | Why |
|-----|--------|--------|-----|
| `Ctrl+C` | Quit | `True` | |
| `F5` | clear_chat | `True` | |
| `F6` | list_chats | `True` | |
| `F7` | nudge_agent | `True` | |
| `F8` | pause_agent | `True` | |
| `Ctrl+P` | command_palette | **`False`** | Footer appends the palette slot itself; `show=True` duplicates it |

> **Never change `ctrl+p` to `show=True`** — it will produce two `^P Commands`
> entries in the footer bar.

### In-input progress (`chat_input.py`, `app.tcss:21-24`)

While the agent is busy and the input is empty:
- `ChatInput.set_activity(label, detail)` sets `_activity_active = True`,
  adds CSS class `progress-active`, starts a 0.1s spinner tick
- Placeholder becomes `|>  ⠋ Using tool [web_search]` (WebUI-parity format)
- Border subtly brightens via `.progress-active { border: round #1886c9; }`
- `ChatInput.set_idle()` clears all of the above

Routing from the app:
```python
# app.py:107-115
def _set_activity(self, label, detail=""):
    self.query_one("#message-input", ChatInput).set_activity(label, detail)

def _set_idle(self):
    self.query_one("#message-input", ChatInput).set_idle()
```

### CSS (`styles/app.tcss`)

- `#chat-log` — `height: 1fr`, no explicit `#status-bar` (removed)
- `#message-input` — `border: round #0f6db8`
- `#message-input.progress-active` — `border: round #1886c9` (brighter while busy)
- `#message-input:focus` — `border: round #00b4ff`
- `Footer` — `background: #101a24`

When editing `.tcss`, reload the browser tab to see changes (no hot-reload).

### ChatInput sizing (`chat_input.py:158-163`)

Height auto-adjusts: `styles.height = min(line_count, 4) + 2` (the `+2` is for
the rounded border). Avoid setting a hard `height` on `#message-input` in
`.tcss` — it will fight the dynamic sizing and clip content.

### Screens

Screens are pushed modally with `push_screen_wait()` and return a value:

| Screen | Returns | When shown |
|--------|---------|------------|
| `HostInputScreen` | `str` (URL) or `""` | No host configured |
| `LoginScreen` | `LoginResult` or `None` | Server advertises `"login"` auth |
| `ChatListScreen` | `str` (context ID) or `None` | User presses F6 |

---

## Plugin Backend

The plugin lives in `plugin/a0_connector/` and is symlinked into the Agent Zero
`usr/plugins/` directory. It provides:

- HTTP handlers under `/api/plugins/a0_connector/v1/`
- Socket.IO events on the `/ws` namespace (all prefixed `connector_`)
- `helpers/event_bridge.py` — maps Agent Zero log types to connector events
- `helpers/ws_runtime.py` — SID/context subscription state, file-op futures

See `docs/architecture.md` for the full protocol and event tables.

**Import discipline in plugin code:**

```python
# NEVER at module level — causes deadlocks during Agent Zero init
from agent import AgentContext   # BAD

# Always inside the handler method
async def process(self, ...):
    from agent import AgentContext  # GOOD
```

---

## Development Patterns & Conventions

### Querying widgets

Always use the typed form to avoid silent `None` issues:

```python
# Good
input_widget = self.query_one("#message-input", ChatInput)
log = self.query_one("#chat-log", RichLog)

# Avoid
widget = self.query_one("#message-input")  # untyped → no IDE help
```

### Activity state routing

Always go through the app-level helpers, never call widget methods directly
from event handlers:

```python
self._set_activity("Using tool", "web_search")  # correct
self._set_idle()                                  # correct

# Don't reach into the widget directly from outside _set_activity/_set_idle
self.query_one("#message-input", ChatInput).set_activity(...)  # avoid
```

### Test stubs (`tests/test_app.py`)

`FakeInput` mirrors the `ChatInput` API used by the app:
```python
class FakeInput:
    def focus(self): ...
    def set_activity(self, label, detail=""): ...
    def set_idle(self): ...
```

`dummy_app` replaces `app.query_one` so all widget calls hit fakes — no real
Textual event loop needed. When adding new widget interactions to `app.py`,
add the corresponding method to `FakeInput`.

### No `#status-bar`

The `ActivityBar` widget and `#status-bar` were removed. Do not re-introduce
them. The single source of truth for activity state is `#message-input`.

### aiohttp shim

`client.py` patches `aiohttp.ClientWSTimeout` if missing (older aiohttp
versions). Do not remove this shim without verifying all supported versions.

---

## Tests

```bash
# Run all tests
./.venv/bin/python -m pytest tests/ -v

# Scope to TUI logic only
./.venv/bin/python -m pytest tests/test_app.py -v

# Force asyncio backend if trio errors appear
./.venv/bin/python -m pytest tests/ -v -p anyio --anyio-backends=asyncio
```

Tests use `anyio` with the asyncio backend. Async test fixtures use
`@pytest.mark.asyncio`.

---

## Safety & Permissions

### Allowed without asking
- Read any file.
- Edit files under `src/`, `tests/`, `devtools/`, `docs/`, `styles/`, `.tcss`.
- Run `devtools/serve.py`, `snapshot.py`, `activity_demo.py`.
- Run `pytest`.

### Ask before doing
- `pip install` (new dependencies not already in `.venv`).
- Editing `plugin/a0_connector/` backend files.
- Deleting files outside of the above allowed paths.
- Making git commits or pushes.

### Never do
- Hardcode API keys, tokens, or secrets.
- Change `ctrl+p` binding `show=False` → `show=True` (duplicates footer entry).
- Remove the `aiohttp` compatibility shim from `client.py` without version testing.
- Import `agent`, `initialize`, or `helpers.projects` at module level in plugin code.

---

## Troubleshooting

### Browser preview shows blank / "Application failed to start"

The subprocess launched by `serve.py` failed. Common causes:
- `.venv` not activated — `serve.py` auto-detects `.venv/bin/python` but check
  the path printed at startup.
- Import error in `app.py` or a widget — run `python -m agent_zero_cli` directly
  in the terminal to see the traceback.

### `No module named textual_serve`

```bash
./.venv/bin/pip install textual-serve
```

### Footer shows two `^P Commands` entries

The `ctrl+p` binding has been changed to `show=True`. Revert to `show=False`.
See `app.py:67-78` and `D3` in the decisions log.

### WebSocket connection fails in tests

```bash
pytest -p anyio --anyio-backends=asyncio
```

### `aiohttp.ClientWSTimeout` AttributeError

The compat shim in `client.py` should handle this. If it doesn't, upgrade
`aiohttp`: `./.venv/bin/pip install "aiohttp>=3.11.0"`.
