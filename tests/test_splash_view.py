from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent_zero_cli.widgets import SplashView
from agent_zero_cli.widgets.splash_view import _validate_connection_target


@pytest.mark.parametrize(
    "host",
    [
        "https://webmasters-ink-tribe-zope.trycloudflare.com",
        "https://webmasters-ink-tribe-zope.trycloudflare.com:443",
        "http://localhost",
    ],
)
def test_validate_connection_target_accepts_standard_urls_without_explicit_port(host: str) -> None:
    valid, message = _validate_connection_target(host)

    assert valid is True
    assert message.startswith("URL format looks valid.")


def test_error_back_button_requests_navigation_to_host() -> None:
    view = SplashView()
    messages: list[object] = []
    view.post_message = lambda message: messages.append(message)  # type: ignore[method-assign]

    view.on_button_pressed(
        SimpleNamespace(button=SimpleNamespace(id="splash-status-back"))  # type: ignore[arg-type]
    )

    assert len(messages) == 1
    assert isinstance(messages[0], SplashView.ActionRequested)
    assert messages[0].action == "back"
