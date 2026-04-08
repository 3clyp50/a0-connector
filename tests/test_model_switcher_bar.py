from __future__ import annotations

from types import SimpleNamespace

from agent_zero_cli.widgets.model_switcher_bar import ModelSwitcherBar


def _select_event(value: str, *, widget_id: str = "model-switcher-preset") -> SimpleNamespace:
    return SimpleNamespace(
        select=SimpleNamespace(id=widget_id),
        value=value,
    )


def test_select_changed_emits_message_for_new_value() -> None:
    bar = ModelSwitcherBar(id="model-switcher-bar")
    posted: list[object] = []
    bar.post_message = lambda message: posted.append(message)  # type: ignore[method-assign]

    bar.on_select_changed(_select_event("Max Power"))

    assert len(posted) == 1
    assert posted[0].value == "Max Power"


def test_select_changed_ignores_events_while_busy() -> None:
    bar = ModelSwitcherBar(id="model-switcher-bar")
    posted: list[object] = []
    bar.post_message = lambda message: posted.append(message)  # type: ignore[method-assign]
    bar._selected_value = "Max Power"
    bar.set_busy(True)

    bar.on_select_changed(_select_event(""))

    assert posted == []
    assert bar._selected_value == "Max Power"


def test_select_changed_ignores_same_value() -> None:
    bar = ModelSwitcherBar(id="model-switcher-bar")
    posted: list[object] = []
    bar.post_message = lambda message: posted.append(message)  # type: ignore[method-assign]
    bar._selected_value = "Max Power"

    bar.on_select_changed(_select_event("Max Power"))

    assert posted == []
