"""LangGraph server client — connection screen and job queue types."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

logger = logging.getLogger("langshark")


@dataclass
class LangGraphJob:
    call: Callable[[Any], Awaitable[Any]]
    on_result: Callable[[Any], None]
    on_error: Callable[[Exception], None] | None = None


class ConnectResult:
    def __init__(self, url: str, client: Any) -> None:
        self.url = url
        self.client = client


class ConnectScreen(ModalScreen[ConnectResult | None]):
    """Modal screen that connects to a LangGraph server and reports progress."""

    CSS = """
    ConnectScreen {
        align: center middle;
    }
    #connect-dialog {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #connect-status {
        height: 3;
        content-align: center middle;
    }
    #connect-error {
        height: auto;
        content-align: center middle;
        color: $error;
    }
    #connect-retry {
        height: 3;
        content-align: center middle;
    }
    """

    def __init__(self, url: str, initial_error: str | None = None) -> None:
        self._url = url
        self._client: Any = None
        self._error: str | None = initial_error
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="connect-dialog"):
            yield Static("Connecting to LangGraph server…", id="connect-status")
            yield Static("", id="connect-error")
            yield Static("", id="connect-retry")

    def on_mount(self) -> None:
        logger.info("Connecting to langgraph server: %s", self._url)
        if self._error:
            self.query_one("#connect-status", Static).update(
                "[bold red]Connection failed[/bold red]"
            )
            self.query_one("#connect-error", Static).update(f"Error: {self._error}")
            self.query_one("#connect-retry", Static).update(
                "Press [bold]Enter[/bold] to retry, [bold]Escape[/bold] to cancel"
            )
        else:
            self._do_connect()

    @work(thread=False, group="connect")
    async def _do_connect(self) -> None:
        try:
            from langgraph_sdk import get_client

            client = get_client(url=self._url)
            await client.assistants.search()
            self._client = client
            self._error = None
            logger.info("Connected to langgraph server: %s", self._url)
            self.dismiss(ConnectResult(url=self._url, client=client))
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            logger.error("Connection failed: %s", exc)
            self.query_one("#connect-status", Static).update(
                "[bold red]Connection failed[/bold red]"
            )
            self.query_one("#connect-error", Static).update(f"Error: {exc}")
            self.query_one("#connect-retry", Static).update(
                "Press [bold]Enter[/bold] to retry, [bold]Escape[/bold] to cancel"
            )

    def on_key(self, event) -> None:
        if self._error:
            if event.key == "enter":
                self._error = None
                self.query_one("#connect-status", Static).update(
                    "Connecting to LangGraph server…"
                )
                self.query_one("#connect-error", Static).update("")
                self.query_one("#connect-retry", Static).update("")
                self._do_connect()
            elif event.key == "escape":
                self.dismiss(None)
