"""Thread browser screen — lists threads with a detail panel."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Label, Static, Tree

from langshark.helpers import (
    build_detail_tree_inner,
    status_icon,
    strip_ansi,
    truncate_id,
)
from langshark.screens.confirm import ConfirmScreen
from langshark.screens.help import HelpScreen
from langshark.splash import SplashScreen

logger = logging.getLogger("langshark")


class ThreadBrowserScreen(Screen[None]):
    """Screen that lists threads with a detail panel in the lower half."""

    CSS = """
    ThreadBrowserScreen {
        layout: vertical;
    }
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
    #thread-detail-panel {
        height: 40%;
        border: solid $primary;
        display: none;
        overflow-y: auto;
    }
    #thread-detail-panel.-visible {
        display: block;
    }
    #thread-meta-box {
        height: auto;
        max-height: 6;
        border-bottom: solid $primary;
        padding: 0 1;
    }
    #state-content {
        height: 1fr;
    }
    DataTable > .datatable--header {
        display: none;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j", "cursor_down", "Down", show=True),
        Binding("k", "cursor_up", "Up", show=True),
        Binding("ctrl+d", "page_down", "Page Dn", show=True),
        Binding("ctrl+u", "page_up", "Page Up", show=True),
        Binding("slash", "focus_filter", "Filter", show=True),
        Binding("escape", "close_detail", "Close detail", show=False),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("h", "history", "History", show=True),
        Binding("c", "copy", "Copy", show=True),
        Binding("d", "delete_thread", "Delete", show=True),
        Binding("s", "show_stats", "Stats", show=True),
        Binding("p", "open_in_phoenix", "Phoenix URL", show=True),
        Binding("P", "copy_phoenix_url", "Copy Phoenix URL", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
        Binding("q", "app.quit", "Quit", show=True, priority=True),
    ]

    def __init__(
        self,
        url: str,
        thread_id: str | None = None,
        filter_graph: str | None = None,
        filter_status: str | None = None,
    ) -> None:
        self._url = url
        self._initial_thread_id = thread_id
        self._filter_graph = filter_graph
        self._filter_status_init = filter_status
        self._threads: list[dict[str, Any]] = []
        self._loading: bool = False
        self._thread_meta: dict[str, Any] | None = None
        self._thread_state: dict[str, Any] | None = None
        self._selected_thread_id: str | None = None
        self._detail_open: bool = False
        logger.info(
            "ThreadBrowserScreen.__init__ url=%s graph=%s status=%s",
            url,
            filter_graph,
            filter_status,
        )
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(Label(f"Threads — server: {self._url}"), id="header-bar")
        yield Input(
            placeholder="Filter by status (idle/busy/interrupted/error) or clear for all",
            id="filter-input",
        )
        yield DataTable(id="event-table")
        with Vertical(id="thread-detail-panel"):
            yield Static(id="thread-meta-box")
            yield Tree("State", id="state-content")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#event-table", DataTable)
        table.cursor_type = "row"
        table.focus()
        self._load_threads()
        if self._initial_thread_id:
            self._selected_thread_id = self._initial_thread_id

    def _load_threads(self, status_filter: str | None = None) -> None:
        self._loading = True

        def _call(client: Any) -> Awaitable[Any]:
            kwargs: dict[str, Any] = {"limit": 100}
            if status_filter:
                kwargs["status"] = status_filter
            elif self._filter_status_init:
                kwargs["status"] = self._filter_status_init
            if self._filter_graph:
                kwargs["metadata"] = {"graph_id": self._filter_graph}
            logger.info("Loading threads: kwargs=%s", kwargs)
            return client.threads.search(**kwargs)

        def _on_result(raw_threads: list[dict[str, Any]]) -> None:
            self._loading = False
            self._threads = []
            for t in raw_threads:
                raw_id = t.get("thread_id")
                tid = str(raw_id) if raw_id is not None else ""
                t["_uuid"] = tid
                self._threads.append(t)
            self._populate_table()
            logger.info("Loaded %d threads", len(self._threads))
            self.notify(f"Loaded {len(self._threads)} threads")

        def _on_error(exc: Exception) -> None:
            self._loading = False
            logger.error("Failed to load threads: %s", exc)
            self.notify(f"Failed to load threads: {exc}", severity="error", timeout=10)

        self.app.submit_job(call=_call, on_result=_on_result, on_error=_on_error)

    def _populate_table(self) -> None:
        table = self.query_one("#event-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Status", "Thread ID", "Graph", "Created", "Updated")
        for t in self._threads:
            status = t.get("status", "?")
            icon = status_icon(status)
            graph = t.get("metadata", {}).get("graph_id", "—")
            created = t.get("created_at", "")[:19]
            updated = t.get("updated_at", "")[:19]
            table.add_row(
                f"{icon} {status}", truncate_id(t["_uuid"]), graph, created, updated
            )

    def _load_selected_thread(self, thread_id: str) -> None:
        self._selected_thread_id = thread_id
        self._thread_meta = None
        self._thread_state = None

        panel = self.query_one("#thread-detail-panel", Vertical)
        self.query_one("#thread-meta-box", Static).update("Loading...")
        tree = self.query_one("#state-content", Tree)
        tree.clear()
        tree.root.expand()
        tree.root.label = "Loading thread data..."
        panel.display = True
        self._detail_open = True

        def call_state(client: Any) -> Awaitable[Any]:
            return client.threads.get_state(thread_id)

        def on_state(state: dict[str, Any]) -> None:
            self._thread_state = state

            def call_meta(client: Any) -> Awaitable[Any]:
                return client.threads.get(thread_id)

            def on_meta(meta: dict[str, Any]) -> None:
                self._thread_meta = meta
                self._update_detail_ui()

            def on_meta_error(exc: Exception) -> None:
                self._update_detail_ui()

            self.app.submit_job(call_meta, on_meta, on_error=on_meta_error)

        def on_state_error(exc: Exception) -> None:
            self.notify(
                f"Failed to load thread {thread_id}: {exc}",
                severity="error",
                timeout=10,
            )

        self.app.submit_job(call_state, on_state, on_error=on_state_error)

    def _update_detail_ui(self) -> None:
        meta_box = self.query_one("#thread-meta-box", Static)
        meta_parts: list[str] = []
        if self._thread_meta:
            meta_parts.append(f"Status: {self._thread_meta.get('status', '?')}")
            meta_parts.append(
                f"Created: {str(self._thread_meta.get('created_at', ''))[:19]}"
            )
            meta_parts.append(
                f"Updated: {str(self._thread_meta.get('updated_at', ''))[:19]}"
            )
            gid = self._thread_meta.get("metadata", {}).get("graph_id", "—")
            meta_parts.append(f"Graph: {gid}")
        if self._thread_state:
            next_nodes = ", ".join(self._thread_state.get("next", ())) or "—"
            meta_parts.append(f"Next: {next_nodes}")
            checkpoint = (
                self._thread_state.get("checkpoint")
                if self._thread_state.get("checkpoint") is not None
                else {}
            )
            checkpoint_id = str(checkpoint.get("checkpoint_id", "—"))
            meta_parts.append(f"Checkpoint: {truncate_id(checkpoint_id, 24)}")
        meta_box.update("  |  ".join(meta_parts))

        tree = self.query_one("#state-content", Tree)
        tree.clear()
        tree.root.expand()
        if self._thread_state:
            values = self._thread_state.get("values", {})
            clean = strip_ansi(values)
            tree.root.label = "State"
            build_detail_tree_inner(tree.root, clean, key="", max_depth=10)
        else:
            tree.root.label = "No state data loaded."

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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_select_thread()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if self._detail_open:
            self.action_select_thread()

    def action_select_thread(self) -> None:
        if self._loading:
            return
        table = self.query_one("#event-table", DataTable)
        cursor = table.cursor_row
        if cursor is None or cursor >= len(self._threads):
            return
        thread = self._threads[cursor]
        tid = thread["_uuid"]
        if tid != self._selected_thread_id or not self._detail_open:
            self._detail_open = True
            self._load_selected_thread(tid)

    def action_focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()

    def action_refresh(self) -> None:
        self._load_threads()

    def action_history(self) -> None:
        if not self._selected_thread_id:
            self.notify("No thread selected", timeout=5)
            return
        logger.info(
            "Opening checkpoint history: thread_id=%s", self._selected_thread_id
        )
        from langshark.screens.checkpoints import CheckpointHistoryScreen

        self.app.push_screen(
            CheckpointHistoryScreen(
                server_url=self._url, thread_id=self._selected_thread_id
            )
        )

    def action_copy(self) -> None:
        if self._thread_state:
            clean = strip_ansi(self._thread_state)
            formatted = json.dumps(clean, indent=2, default=str)
            self.app.copy_to_clipboard(formatted)
            self.notify("Thread state copied to clipboard")

    def action_delete_thread(self) -> None:
        """Delete the selected thread with confirmation."""
        if not self._selected_thread_id:
            self.notify("No thread selected", timeout=5)
            return

        def on_confirm(result: bool | None) -> None:
            if not result:
                return

            def _call(client: Any) -> Awaitable[None]:
                return client.threads.delete(self._selected_thread_id)

            def _on_result(_: None) -> None:
                self._thread_meta = None
                self._thread_state = None
                self._selected_thread_id = None
                self._detail_open = False
                panel = self.query_one("#thread-detail-panel", Vertical)
                panel.display = False
                self.notify("Thread deleted", timeout=5)
                self._load_threads()

            def _on_error(exc: Exception) -> None:
                self.notify(
                    f"Failed to delete thread: {exc}", severity="error", timeout=10
                )

            self.app.submit_job(call=_call, on_result=_on_result, on_error=_on_error)

        tid_display = truncate_id(self._selected_thread_id)
        self.app.push_screen(
            ConfirmScreen(f"Delete thread [bold]{tid_display}[/bold]?"),
            callback=on_confirm,
        )

    def action_close_detail(self) -> None:
        panel = self.query_one("#thread-detail-panel", Vertical)
        if panel.display:
            panel.display = False
            self._detail_open = False
            self.query_one("#event-table", DataTable).focus()
        else:
            # Detail already closed — bump into the splash "wall"
            self.app.push_screen(SplashScreen())

    def action_show_stats(self) -> None:
        from langshark.screens.stats import ServerStatsScreen

        self.app.push_screen(ServerStatsScreen(url=self._url))

    def action_show_help(self) -> None:
        self.app.push_screen(HelpScreen(screen_name="threads"))

    # ── Phoenix deep-link actions ────────────────────────────────────────────

    def _get_phoenix_url_for_current_thread(
        self, on_url: callable, *, copy_mode: bool = False
    ) -> None:
        """Resolve a Phoenix URL for the selected thread, then call *on_url(url)*.

        Handles all fallback tiers with appropriate notifications:
        - No --phoenix flag → inform user, point to --help
        - No thread selected → inform user
        - Phoenix unreachable → warning notification
        - No matching spans → fall back to project page
        - No browser (copy_mode=False) → auto-copy to clipboard
        """
        phoenix_url: str | None = getattr(self.app, "phoenix_url", None)
        phoenix_project: str = getattr(self.app, "phoenix_project", "default")

        if not phoenix_url:
            self.notify(
                "Phoenix not configured — run 'langshark --help' for setup instructions",
                timeout=8,
            )
            return

        if not self._selected_thread_id:
            self.notify("No thread selected", timeout=5)
            return

        thread_id = self._selected_thread_id
        self.notify("Looking up trace in Phoenix…", timeout=3)

        from langshark.phoenix import find_trace_for_thread
        from langshark.phoenix import project_url as phoenix_project_url

        async def _lookup(_client: Any) -> str:
            url = await find_trace_for_thread(phoenix_url, phoenix_project, thread_id)
            if url:
                return url
            # No spans found — fall back to project page
            return phoenix_project_url(phoenix_url, phoenix_project)

        def _on_result(url: str) -> None:
            is_fallback = url == phoenix_project_url(phoenix_url, phoenix_project)
            if is_fallback:
                self.notify(
                    "No trace found for this thread — opening Phoenix project instead",
                    timeout=8,
                )
            on_url(url, is_fallback=is_fallback)

        def _on_error(exc: Exception) -> None:
            self.notify(
                f"Could not reach Phoenix at {phoenix_url}: {exc}",
                severity="warning",
                timeout=10,
            )

        self.app.submit_job(call=_lookup, on_result=_on_result, on_error=_on_error)

    def action_open_in_phoenix(self) -> None:
        """Show the Phoenix URL modal for the selected thread (press 'o')."""
        from langshark.screens.phoenix_url import PhoenixUrlScreen

        def _show(url: str, *, is_fallback: bool = False) -> None:
            self.app.push_screen(PhoenixUrlScreen(url, is_fallback=is_fallback))

        self._get_phoenix_url_for_current_thread(_show)

    def action_copy_phoenix_url(self) -> None:
        """Copy the selected thread's Phoenix trace URL to clipboard (press 'O')."""

        def _copy(url: str, *, is_fallback: bool = False) -> None:
            self.app.copy_to_clipboard(url)
            msg = (
                "Phoenix project URL copied"
                if is_fallback
                else "Phoenix trace URL copied to clipboard"
            )
            self.notify(msg, timeout=5)

        self._get_phoenix_url_for_current_thread(_copy, copy_mode=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.query_one("#filter-input", Input).value = ""
        self._load_threads(status_filter=value if value else None)
