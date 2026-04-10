from __future__ import annotations

from datetime import datetime

import pytest
from textual.app import App, ComposeResult
from textual.widgets import ListView, Static

from agent_zero_cli.screens.chat_list import ChatListScreen, _build_entry, _format_timestamp

pytestmark = pytest.mark.anyio


class ChatListHarnessApp(App[None]):
    def __init__(self, contexts: list[dict[str, object]]) -> None:
        super().__init__()
        self._contexts = contexts

    def compose(self) -> ComposeResult:
        yield Static("root")

    def on_mount(self) -> None:
        self.push_screen(ChatListScreen(self._contexts))


def test_format_timestamp_compacts_recent_dates() -> None:
    now = datetime.fromisoformat("2026-04-10T03:00:00+02:00")

    assert _format_timestamp(datetime.fromisoformat("2026-04-10T02:44:44+02:00"), now=now) == "Today 02:44"
    assert _format_timestamp(datetime.fromisoformat("2026-04-09T16:01:05+02:00"), now=now) == "Yesterday 16:01"
    assert _format_timestamp(datetime.fromisoformat("2026-04-08T19:50:19+02:00"), now=now) == "Apr 08 19:50"


def test_build_entry_normalizes_generated_names_and_timestamp_previews() -> None:
    entry = _build_entry(
        {
            "id": "ctx-2",
            "name": "YJSsvto3",
            "created_at": "2026-04-09T16:01:05+02:00",
            "last_message": "2026-04-09T16:01:05+02:00",
            "running": True,
        },
        2,
        now=datetime.fromisoformat("2026-04-10T03:00:00+02:00"),
    )

    assert entry.context_id == "ctx-2"
    assert entry.title == "Chat 2"
    assert entry.preview == ""
    assert entry.meta == "Started Yesterday 16:01 | Running now | ID YJSsvto3"


def test_build_entry_keeps_human_titles_and_preview_text() -> None:
    entry = _build_entry(
        {
            "id": "ctx-1",
            "name": "AI Governance Research",
            "created_at": "2026-04-08T08:32:55+02:00",
            "last_message": "Compare the EU AI Act and the NIST AI RMF for enterprise policy guardrails.",
        },
        1,
        now=datetime.fromisoformat("2026-04-10T03:00:00+02:00"),
    )

    assert entry.title == "AI Governance Research"
    assert entry.meta == "Started Apr 08 08:32"
    assert entry.preview == "Compare the EU AI Act and the NIST AI RMF for enterprise policy guardrails."


async def test_chat_list_focuses_the_list_view_on_mount() -> None:
    app = ChatListHarnessApp(
        [
            {
                "id": "ctx-1",
                "name": "Chat Initialization",
                "created_at": "2026-04-10T02:44:44+02:00",
                "last_message": "Set up the connector workspace and verify the TUI layout.",
            }
        ]
    )

    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ChatListScreen)
        assert screen.query_one("#chat-list", ListView).has_focus
        assert screen.query_one(".chat-list-item-title", Static).render().plain == "Chat Initialization"
