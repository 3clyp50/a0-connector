"""Animated single-line activity indicator widget."""

from __future__ import annotations

from textual.app import RenderResult
from textual.reactive import reactive
from textual.widget import Widget

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_IDLE_TEXT = "Waiting for input"


class ActivityBar(Widget):
    """A one-row bar that shows an animated spinner + label while the agent
    is active, and a static idle message when it is not.

    Call ``set_activity(label, detail)`` to update the displayed text.
    Call ``set_idle()`` to return to the idle state and stop the animation.
    """

    DEFAULT_CSS = """
    ActivityBar {
        height: 1;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
        overflow: hidden hidden;
    }
    """

    _frame: reactive[int] = reactive(0, repaint=True)
    _label: reactive[str] = reactive(_IDLE_TEXT, repaint=True)
    _detail: reactive[str] = reactive("", repaint=True)
    _active: reactive[bool] = reactive(False, repaint=True)

    def on_mount(self) -> None:
        self.set_interval(0.1, self._tick)

    def _tick(self) -> None:
        if self._active:
            self._frame = (self._frame + 1) % len(_SPINNER)

    def set_activity(self, label: str, detail: str = "") -> None:
        """Switch to animated mode with the given label and optional detail."""
        self._label = label
        self._detail = detail
        self._active = True

    def set_idle(self) -> None:
        """Return to idle state."""
        self._label = _IDLE_TEXT
        self._detail = ""
        self._active = False
        self._frame = 0

    def render(self) -> RenderResult:
        if not self._active:
            return f"[dim]{_IDLE_TEXT}[/dim]"
        spinner = _SPINNER[self._frame]
        label = self._label
        detail = f" [{self._detail}]" if self._detail else ""
        return f"[dim]{spinner} {label}{detail}[/dim]"
