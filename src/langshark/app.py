"""Langshark application — shared base class and App subclasses.

The base ``LangsharkApp`` provides the async job queue machinery; concrete
subclasses implement the two run modes:

* ``TraceViewer`` — browse local JSONL trace files.
* ``ConnectedApp`` — connect to a LangGraph server and browse threads.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Input, Label, RichLog

from langshark.client import ConnectResult, ConnectScreen, LangGraphJob
from langshark.helpers import (
    strip_ansi,
    summarise_short,
    to_uuid,
    truncate_id,
)
from langshark.screens.help import HelpScreen
from langshark.splash import SplashScreen

logger = logging.getLogger("langshark")

SHARED_CSS = """
#header-bar {
    height: 1;
    background: $primary;
    color: $text;
}
#header-bar > Label {
    padding: 0 1;
}
#filter-input {
    width: 100%;
}
#event-table {
    height: 1fr;
}
#detail-panel {
    height: 40%;
    border: solid $primary;
    display: none;
    overflow-y: auto;
}
#detail-panel.-visible {
    display: block;
}
#detail-content {
    height: 100%;
}
#status-bar {
    height: 1;
    background: $surface;
    color: $text;
    padding: 0 1;
}
DataTable > .datatable--header {
    display: none;
}
"""


class LangsharkApp(App):
    """Base class that provides the async job queue shared by all modes.

    Subclasses override ``compose()`` and may add their own bindings.
    The ``_queue_worker`` coroutine and ``submit_job`` method are available
    to any screen that calls ``self.app.submit_job(...)``.
    """

    TITLE = "Langshark - a friendly LangGraph inspector"

    def __init__(self) -> None:
        self._task_queue: asyncio.Queue[LangGraphJob] = asyncio.Queue()
        self._langgraph_client: Any = None
        super().__init__()

    @work(thread=False, group="langgraph-worker", exclusive=True)
    async def _queue_worker(self) -> None:
        while True:
            job = await self._task_queue.get()
            try:
                result = await job.call(self._langgraph_client)
                job.on_result(result)
            except Exception as e:  # noqa: BLE001
                if job.on_error:
                    job.on_error(e)

    def submit_job(
        self,
        call: Callable[[Any], Awaitable[Any]],
        on_result: Callable[[Any], None],
        *,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._task_queue.put_nowait(LangGraphJob(call, on_result, on_error))


# ══════════════════════════════════════════════════════════════════════════════
# TRACE VIEWER (local JSONL file)
# ══════════════════════════════════════════════════════════════════════════════


class TraceViewer(LangsharkApp):
    """Browse a local JSONL trace file."""

    CSS = (
        SHARED_CSS
        + """
    TraceViewer {
        layout: vertical;
    }
    #server-url-bar {
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
        dock: bottom;
    }
    """
    )

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j", "cursor_down", "Down", show=True),
        Binding("k", "cursor_up", "Up", show=True),
        Binding("ctrl+d", "page_down", "Page Dn", show=True),
        Binding("ctrl+u", "page_up", "Page Up", show=True),
        Binding("g", "jump", "Jump to", show=True),
        Binding("slash", "focus_filter", "Filter", show=True),
        Binding("enter", "toggle_detail", "Expand", show=True),
        Binding("escape", "close_detail", "Close", show=True),
        Binding("c", "copy_event", "Copy", show=True),
        Binding("t", "view_thread", "Thread", show=True),
        Binding("h", "show_help", "Help", show=True),
        Binding("q", "quit", "Quit", show=True, priority=True),
    ]

    def __init__(
        self,
        events: list[dict[str, Any]],
        server_url: str | None = None,
        thread_id: str | None = None,
    ) -> None:
        self._all_events = events
        self._filtered_events = list(events)
        self._expanded_event_index: int | None = None
        self._jump_mode: bool = False
        self._server_url = server_url
        self._trace_thread_id = thread_id
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(
            Label(f"Trace: {len(self._all_events)} events"), id="header-bar"
        )
        yield Input(
            placeholder="Filter by type (e.g. updates, messages, custom) or clear to show all",
            id="filter-input",
        )
        yield DataTable(id="event-table")
        with Vertical(id="detail-panel"):
            yield RichLog(id="detail-content", highlight=True, markup=True, wrap=True)
        if self._server_url:
            yield Label(
                f"Server: {self._server_url}  |  Thread: {truncate_id(self._trace_thread_id) if self._trace_thread_id else '—'}",
                id="server-url-bar",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(SplashScreen(), callback=self._on_splash_done)

    def _on_splash_done(self, _: None) -> None:
        table = self.query_one("#event-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "Type", "Source", "Detail", "Time")
        table.focus()
        self._populate_table()
        self._queue_worker()

    def _populate_table(self) -> None:
        table = self.query_one("#event-table", DataTable)
        table.clear()
        for idx, event in enumerate(self._filtered_events):
            typ = event.get("type", "?")
            ns = event.get("ns", [])
            ts = event.get("ts", 0)
            source = "supervisor" if not ns else f"subagent:{ns[0]}"
            detail = summarise_short(event)
            table.add_row(str(idx + 1), typ, source, detail, f"{ts:.2f}s")

    def action_cursor_down(self) -> None:
        self.query_one("#event-table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#event-table", DataTable).action_cursor_up()

    def action_page_down(self) -> None:
        table = self.query_one("#event-table", DataTable)
        for _ in range(20):
            table.action_cursor_down()

    def action_page_up(self) -> None:
        table = self.query_one("#event-table", DataTable)
        for _ in range(20):
            table.action_cursor_up()

    def action_jump(self) -> None:
        self._jump_mode = True
        self.query_one("#filter-input", Input).value = ""
        self.query_one(
            "#filter-input", Input
        ).placeholder = "Enter event number to jump to..."
        self.query_one("#filter-input", Input).focus()

    def action_focus_filter(self) -> None:
        self._jump_mode = False
        self.query_one(
            "#filter-input", Input
        ).placeholder = "Filter by type (e.g. updates, messages, custom)"
        self.query_one("#filter-input", Input).focus()

    def action_close_detail(self) -> None:
        panel = self.query_one("#detail-panel", Vertical)
        panel.display = False
        self._expanded_event_index = None
        self.query_one("#event-table", DataTable).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        input_widget = self.query_one("#filter-input", Input)
        input_widget.value = ""
        input_widget.placeholder = "Filter by type (e.g. updates, messages, custom)"
        self._jump_mode = False
        table = self.query_one("#event-table", DataTable)
        if not value:
            self._filtered_events = list(self._all_events)
            self._populate_table()
            table.focus()
            return
        if value.isdigit():
            n = int(value)
            table.focus()
            if 1 <= n <= len(self._filtered_events):
                self.call_after_refresh(
                    lambda t=table, r=n - 1: setattr(
                        t, "cursor_coordinate", Coordinate(r, 0)
                    )
                )
            return
        self._filtered_events = [
            e for e in self._all_events if value.lower() in e.get("type", "").lower()
        ]
        self._populate_table()

    def on_input_changed(self, event: Input.Changed) -> None:
        if self._jump_mode:
            return
        value = event.value.strip()
        if not value:
            self._filtered_events = list(self._all_events)
            self._populate_table()
            return
        self._filtered_events = [
            e for e in self._all_events if value.lower() in e.get("type", "").lower()
        ]
        self._populate_table()

    def _update_detail(self) -> None:
        table = self.query_one("#event-table", DataTable)
        cursor = table.cursor_row
        if cursor is None:
            return
        event_index = cursor
        if event_index >= len(self._filtered_events):
            return
        detail = self.query_one("#detail-content", RichLog)
        detail.auto_scroll = False
        detail.clear()
        ev = self._filtered_events[event_index]
        clean = strip_ansi(ev)
        formatted = json.dumps(clean, indent=2, default=str)
        detail.write(formatted)
        detail.scroll_home(animate=False)

    def action_toggle_detail(self) -> None:
        panel = self.query_one("#detail-panel", Vertical)
        table = self.query_one("#event-table", DataTable)
        cursor = table.cursor_row
        if cursor is None:
            return
        event_index = cursor
        if event_index >= len(self._filtered_events):
            return
        if self._expanded_event_index == event_index:
            panel.display = False
            self._expanded_event_index = None
        else:
            self._update_detail()
            panel.display = True
            self._expanded_event_index = event_index

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_toggle_detail()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if self._expanded_event_index is not None:
            self._update_detail()

    def action_copy_event(self) -> None:
        table = self.query_one("#event-table", DataTable)
        cursor = table.cursor_row
        if cursor is None:
            return
        event_index = cursor
        if event_index >= len(self._filtered_events):
            return
        ev = self._filtered_events[event_index]
        clean = strip_ansi(ev)
        formatted = json.dumps(clean, indent=2, default=str)
        self.copy_to_clipboard(formatted)
        self.notify("Event copied to clipboard")

    def action_view_thread(self) -> None:
        if not self._server_url or not self._trace_thread_id:
            self.notify(
                "No server URL or thread_id available for this trace",
                severity="error",
                timeout=10,
            )
            return
        uuid_str = to_uuid(self._trace_thread_id)
        if uuid_str is None:
            self.notify(
                f"Invalid thread ID: {self._trace_thread_id}",
                severity="error",
                timeout=10,
            )
            return
        logger.info(
            "Opening thread from trace file: thread_id=%s uuid=%s",
            self._trace_thread_id,
            uuid_str,
        )
        from langshark.screens.threads import ThreadBrowserScreen

        self.push_screen(ThreadBrowserScreen(url=self._server_url, thread_id=uuid_str))

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen(screen_name="trace"))


# ══════════════════════════════════════════════════════════════════════════════
# CONNECTED APP (server mode)
# ══════════════════════════════════════════════════════════════════════════════


class ConnectedApp(LangsharkApp):
    """Connect to a LangGraph server and browse threads."""

    CSS = SHARED_CSS
    BINDINGS: ClassVar[list[Binding]] = []

    # Minimum time (seconds) the splash must be visible before transitioning.
    _MIN_SPLASH_TIME = 2.25

    def __init__(
        self,
        url: str = "http://127.0.0.1:2024",
        graph: str | None = None,
        status: str | None = None,
        phoenix_url: str | None = None,
        phoenix_project: str | None = None,
    ) -> None:
        self._url = url
        self._graph = graph
        self._status = status
        self.phoenix_url = phoenix_url
        self.phoenix_project = phoenix_project
        self._splash_pushed_at: float | None = None
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

    def on_mount(self) -> None:
        logger.info(
            "ConnectedApp started: url=%s graph=%s status=%s",
            self._url,
            self._graph,
            self._status,
        )
        self._queue_worker()
        # Show the splash while we attempt to connect
        self.push_screen(SplashScreen())
        self._splash_pushed_at = self._get_time()
        # Defer connection start so the splash renders first
        self.call_after_refresh(self._start_connection)

    def _get_time(self) -> float:
        """Return monotonic time for splash timing."""
        return time.monotonic()

    @work(thread=False, group="connect", exclusive=True)
    async def _start_connection(self) -> None:
        """Attempt to connect to the LangGraph server. On completion,
        pop the splash and proceed to the next screen."""
        try:
            from langgraph_sdk import get_client

            client = get_client(url=self._url)
            await client.assistants.search()
            # Connection succeeded — pop splash and go to thread browser
            self._langgraph_client = client
            logger.info("Connected to langgraph server: %s", self._url)
            self._on_connect_success()
        except Exception as exc:  # noqa: BLE001
            logger.error("Connection failed: %s", exc)
            self._on_connect_failure(exc)

    def _on_connect_success(self) -> None:
        """Pop splash and push thread browser, ensuring minimum splash time."""
        from langshark.screens.threads import ThreadBrowserScreen

        elapsed = self._get_time() - (self._splash_pushed_at or 0)
        remaining = self._MIN_SPLASH_TIME - elapsed

        def _transition() -> None:
            self._pop_splash_if_showing()
            self.push_screen(
                ThreadBrowserScreen(
                    url=self._url, filter_graph=self._graph, filter_status=self._status
                )
            )

        if remaining > 0:
            self.set_timer(remaining, _transition)
        else:
            _transition()

    def _on_connect_failure(self, exc: Exception) -> None:
        """Pop splash (if still showing) and show connection error dialog."""
        self._pop_splash_if_showing()
        self.push_screen(
            ConnectScreen(self._url, initial_error=f"Connection failed: {exc}"),
            callback=self._on_connect_result,
        )

    def _pop_splash_if_showing(self) -> None:
        """Pop the splash only if it is still on top of the screen stack.

        The splash dismisses itself on any keypress, so by the time a
        connection attempt completes it may already be gone; popping
        unconditionally would raise ``ScreenStackError`` (or pop the
        wrong screen).
        """
        if isinstance(self.screen, SplashScreen):
            self.pop_screen()

    def _on_connect_result(self, result: ConnectResult | None) -> None:
        if result is None:
            logger.error("Connection cancelled by user")
            self.notify("Connection cancelled", severity="error")
            self.exit(1)
            return
        self._langgraph_client = result.client
        logger.info(
            "Connected: url=%s client=%s", result.url, type(result.client).__name__
        )
        from langshark.screens.threads import ThreadBrowserScreen

        self.push_screen(
            ThreadBrowserScreen(
                url=self._url, filter_graph=self._graph, filter_status=self._status
            )
        )
