#!/usr/bin/env python
"""Simulate agent activity to visually verify the in-input progress indicator.

Usage:
    python devtools/activity_demo.py [--output PATH]

Captures two snapshots:
  1. idle   — normal placeholder visible
  2. active — spinner + progress label inside the input

Useful for verifying WebUI-parity progress styling without a real agent run.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

_OUT_DIR = Path(__file__).resolve().parent / "snapshots"


async def _demo(out_dir: Path) -> None:
    from agent_zero_cli.app import AgentZeroCLI
    from agent_zero_cli.config import CLIConfig
    from agent_zero_cli.widgets.chat_input import ChatInput

    app = AgentZeroCLI(
        config=CLIConfig(instance_url="http://127.0.0.1:19999", api_key="demo-mode")
    )

    async with app.run_test(size=(120, 36)) as pilot:
        await pilot.pause(delay=0.5)

        # --- Snapshot 1: idle state ---
        svg_idle = app.export_screenshot()
        idle_path = out_dir / "tui_idle.svg"
        idle_path.parent.mkdir(parents=True, exist_ok=True)
        idle_path.write_text(svg_idle, encoding="utf-8")
        print(f"Idle snapshot   → {idle_path}")

        # --- Trigger activity ---
        chat_input = app.query_one("#message-input", ChatInput)
        chat_input.set_activity("Using tool", "web_search")
        await pilot.pause(delay=0.6)  # let spinner tick a few frames

        # --- Snapshot 2: active state ---
        svg_active = app.export_screenshot()
        active_path = out_dir / "tui_activity.svg"
        active_path.write_text(svg_active, encoding="utf-8")
        print(f"Active snapshot  → {active_path}")

        # --- Reset ---
        chat_input.set_idle()
        await pilot.pause(delay=0.3)

        svg_reset = app.export_screenshot()
        reset_path = out_dir / "tui_reset.svg"
        reset_path.write_text(svg_reset, encoding="utf-8")
        print(f"Reset snapshot   → {reset_path}")


def main() -> None:
    _demo_dir = _OUT_DIR
    asyncio.run(_demo(_demo_dir))


if __name__ == "__main__":
    main()
