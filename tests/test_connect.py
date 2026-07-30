"""Regression tests for the ConnectedApp connection-failure flow.

When the LangGraph server is unreachable, the app must replace the splash
with the ConnectScreen error dialog. The splash dismisses itself on any
keypress, so by the time a failed connection attempt reports back it may
already be gone — ``_on_connect_failure`` used to pop it unconditionally,
crashing with ``ScreenStackError`` instead of showing the dialog.
"""

import asyncio
from typing import Any

import langgraph_sdk

from langshark.app import ConnectedApp
from langshark.client import ConnectScreen
from langshark.splash import SplashScreen


class _FailingAssistants:
    def __init__(self, delay: float = 0.0) -> None:
        self._delay = delay

    async def search(self, *args: Any, **kwargs: Any) -> None:
        if self._delay:
            await asyncio.sleep(self._delay)
        raise RuntimeError("connection refused")


class _FailingClient:
    def __init__(self, delay: float = 0.0) -> None:
        self.assistants = _FailingAssistants(delay)


def _patch_get_client(monkeypatch: Any, delay: float = 0.0) -> None:
    """Make langgraph_sdk.get_client return a client that always fails."""
    monkeypatch.setattr(langgraph_sdk, "get_client", lambda url: _FailingClient(delay))


async def test_connect_failure_shows_error_dialog(monkeypatch: Any) -> None:
    """Server unreachable with the splash still up -> error dialog appears."""
    _patch_get_client(monkeypatch, delay=0.3)
    app = ConnectedApp(url="http://127.0.0.1:1")
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        assert isinstance(app.screen, SplashScreen)
        await pilot.pause(0.5)
        assert isinstance(app.screen, ConnectScreen)


async def test_connect_failure_after_splash_dismissed_shows_error_dialog(
    monkeypatch: Any,
) -> None:
    """Regression: user dismissed the splash before the failure fires.

    The error dialog must still appear (no ScreenStackError from popping
    the already-gone splash).
    """
    _patch_get_client(monkeypatch, delay=0.3)
    app = ConnectedApp(url="http://127.0.0.1:1")
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        assert isinstance(app.screen, SplashScreen)
        await pilot.press("space")  # splash dismisses on any keypress
        await pilot.pause(0.1)
        assert not isinstance(app.screen, SplashScreen)
        await pilot.pause(0.5)
        assert isinstance(app.screen, ConnectScreen)
