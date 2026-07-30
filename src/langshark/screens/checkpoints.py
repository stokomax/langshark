"""Checkpoint history screen — browse checkpoint timeline for a thread."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Label, Tree

from langshark.helpers import build_detail_tree_inner, strip_ansi, truncate_id
from langshark.screens.help import HelpScreen

logger = logging.getLogger("langshark")


class CheckpointHistoryScreen(Screen[None]):
    """Screen showing checkpoint history for a thread."""

    CSS = """
    CheckpointHistoryScreen {
        layout: vertical;
    }
    #history-table {
        height: 1fr;
    }
    #checkpoint-detail {
        height: 1fr;
        border: solid $primary;
        display: none;
        overflow-y: auto;
    }
    #checkpoint-detail.-visible {
        display: block;
    }
    #checkpoint-tree {
        height: 100%;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j", "cursor_down", "Down", show=True),
        Binding("k", "cursor_up", "Up", show=True),
        Binding("ctrl+d", "page_down", "Page Dn", show=True),
        Binding("ctrl+u", "page_up", "Page Up", show=True),
        Binding("escape", "back", "Back", show=True, priority=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("c", "copy", "Copy", show=True),
        Binding("p", "open_in_phoenix", "Phoenix URL", show=True),
        Binding("P", "copy_phoenix_url", "Copy Phoenix URL", show=True),
        Binding("question_mark", "show_help", "Help", show=True),
        Binding("q", "app.quit", "Quit", show=True, priority=True),
    ]

    def __init__(self, server_url: str, thread_id: str) -> None:
        self._server_url = server_url
        self._history: list[dict[str, Any]] = []
        self._expanded_index: int | None = None
        self._langgraph_thread_id = thread_id
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(
            Label(f"Checkpoints — {self._langgraph_thread_id}"), id="header-bar"
        )
        yield DataTable(id="history-table")
        with Vertical(id="checkpoint-detail"):
            yield Tree("Checkpoint", id="checkpoint-tree")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.cursor_type = "row"
        table.focus()
        self._load_history()

    def _load_history(self) -> None:
        thread_id = self._langgraph_thread_id
        logger.info("Submitting get_history job: thread_id=%s", thread_id)

        def _call(client: Any) -> Awaitable[Any]:
            return client.threads.get_history(thread_id=thread_id, limit=200)

        def _on_result(history: list[dict[str, Any]]) -> None:
            self._history = history
            self._populate_table()
            logger.info(
                "Loaded %d checkpoints for thread_id=%s", len(history), thread_id
            )
            self.notify(f"Loaded {len(self._history)} checkpoints")

        def _on_error(exc: Exception) -> None:
            logger.error("get_history failed: thread_id=%s error=%s", thread_id, exc)
            self.notify(
                f"Failed to load history for {thread_id}: {exc}",
                severity="error",
                timeout=10,
            )

        self.app.submit_job(call=_call, on_result=_on_result, on_error=_on_error)

    def _populate_table(self) -> None:
        table = self.query_one("#history-table", DataTable)
        table.clear()
        table.cursor_type = "row"
        table.add_columns("Step", "Source", "Writes", "Checkpoint ID", "Timestamp")
        for cp in self._history:
            meta = cp.get("metadata", {})
            step = meta.get("step", "?")
            source = meta.get("source", "?")
            writes = meta.get("writes", {})
            writes_summary = ", ".join(writes.keys()) if writes else "—"
            raw_cp_id = cp.get("checkpoint_id", "") or cp.get("config", {}).get(
                "configurable", {}
            ).get("checkpoint_id", "")
            cp_id = str(raw_cp_id) if raw_cp_id else ""
            ts = str(cp.get("created_at", ""))[:19]
            table.add_row(
                str(step), source, writes_summary, truncate_id(str(cp_id), 16), ts
            )

    def _update_detail(self) -> None:
        table = self.query_one("#history-table", DataTable)
        cursor = table.cursor_row
        if cursor is None or cursor >= len(self._history):
            return
        tree = self.query_one("#checkpoint-tree", Tree)
        tree.clear()
        tree.root.expand()
        cp = self._history[cursor]
        meta = cp.get("metadata", {})
        step = meta.get("step", "?")
        tree.root.label = f"Checkpoint (Step: {step})"
        clean = strip_ansi(cp)
        build_detail_tree_inner(tree.root, clean, key="", max_depth=10)

    def action_toggle_detail(self) -> None:
        panel = self.query_one("#checkpoint-detail", Vertical)
        table = self.query_one("#history-table", DataTable)
        cursor = table.cursor_row
        if cursor is None or cursor >= len(self._history):
            return
        if self._expanded_index == cursor:
            panel.display = False
            self._expanded_index = None
        else:
            self._update_detail()
            panel.display = True
            self._expanded_index = cursor

    def action_close_detail(self) -> None:
        panel = self.query_one("#checkpoint-detail", Vertical)
        panel.display = False
        self._expanded_index = None
        self.query_one("#history-table", DataTable).focus()

    def action_back(self) -> None:
        panel = self.query_one("#checkpoint-detail", Vertical)
        if panel.display:
            self.action_close_detail()
        else:
            self.app.pop_screen()

    def action_refresh(self) -> None:
        logger.info(
            "Refreshing checkpoint history: thread_id=%s", self._langgraph_thread_id
        )
        self._load_history()

    def action_copy(self) -> None:
        table = self.query_one("#history-table", DataTable)
        cursor = table.cursor_row
        if cursor is None or cursor >= len(self._history):
            return
        cp = self._history[cursor]
        clean = strip_ansi(cp)
        formatted = json.dumps(clean, indent=2, default=str)
        self.app.copy_to_clipboard(formatted)
        self.notify("Checkpoint copied to clipboard")

    def action_cursor_down(self) -> None:
        self.query_one("#history-table", DataTable).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#history-table", DataTable).action_cursor_up()

    def action_page_down(self) -> None:
        table = self.query_one("#history-table", DataTable)
        for _ in range(20):
            table.action_cursor_down()

    def action_page_up(self) -> None:
        table = self.query_one("#history-table", DataTable)
        for _ in range(20):
            table.action_cursor_up()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_toggle_detail()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if self._expanded_index is not None:
            self._update_detail()

    # ── Phoenix deep-link actions ────────────────────────────────────────────

    def _get_cursor_run_id(self) -> str | None:
        """Return the ``run_id`` from the currently-highlighted checkpoint, or None."""
        table = self.query_one("#history-table", DataTable)
        cursor = table.cursor_row
        if cursor is None or cursor >= len(self._history):
            return None
        cp = self._history[cursor]
        return cp.get("metadata", {}).get("run_id")

    def _get_phoenix_url_for_current_checkpoint(
        self, on_url: callable, *, copy_mode: bool = False
    ) -> None:
        """Resolve a Phoenix URL for the selected checkpoint's run, then call *on_url(url)*.

        Falls back through:
        - No --phoenix flag → inform user, point to --help
        - No checkpoint selected → inform user
        - No run_id on checkpoint → fall back to thread-level query
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

        run_id = self._get_cursor_run_id()
        thread_id = self._langgraph_thread_id
        self.notify("Looking up trace in Phoenix…", timeout=3)

        from langshark.phoenix import find_trace_for_run, find_trace_for_thread
        from langshark.phoenix import project_url as phoenix_project_url

        async def _lookup(_client: Any) -> str:
            # Prefer run_id lookup (exact checkpoint), fall back to thread_id
            if run_id:
                url = await find_trace_for_run(phoenix_url, phoenix_project, run_id)
                if url:
                    return url
            url = await find_trace_for_thread(phoenix_url, phoenix_project, thread_id)
            if url:
                return url
            return phoenix_project_url(phoenix_url, phoenix_project)

        def _on_result(url: str) -> None:
            is_fallback = url == phoenix_project_url(phoenix_url, phoenix_project)
            if is_fallback:
                self.notify(
                    "No trace found for this checkpoint — opening Phoenix project instead",
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
        """Show the Phoenix URL modal for the selected checkpoint (press 'o')."""
        from langshark.screens.phoenix_url import PhoenixUrlScreen

        def _show(url: str, *, is_fallback: bool = False) -> None:
            self.app.push_screen(PhoenixUrlScreen(url, is_fallback=is_fallback))

        self._get_phoenix_url_for_current_checkpoint(_show)

    def action_copy_phoenix_url(self) -> None:
        """Copy the selected checkpoint's Phoenix trace URL to clipboard (press 'O')."""

        def _copy(url: str, *, is_fallback: bool = False) -> None:
            self.app.copy_to_clipboard(url)
            msg = (
                "Phoenix project URL copied"
                if is_fallback
                else "Phoenix trace URL copied to clipboard"
            )
            self.notify(msg, timeout=5)

        self._get_phoenix_url_for_current_checkpoint(_copy, copy_mode=True)

    def action_show_help(self) -> None:
        self.app.push_screen(HelpScreen(screen_name="checkpoints"))
