"""Server statistics screen — runtime metrics and configuration limits."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static

logger = logging.getLogger("langshark")

# Auto-refresh interval in seconds.
_REFRESH_INTERVAL = 5.0


def _ascii_bar(value: float, maximum: float, width: int = 20) -> str:
    """Return a fixed-width ASCII progress bar, e.g. '▓▓▓▓░░░░░░░░'."""
    if maximum <= 0:
        return "░" * width
    filled = min(width, round(value / maximum * width))
    return "▓" * filled + "░" * (width - filled)


class ServerStatsScreen(Screen[None]):
    """Push-to-stack screen showing LangGraph server runtime statistics.

    Data is fetched from two endpoints:

    * ``GET /info``           — server version and feature flags
    * ``GET /metrics?format=json`` — structured JSON with queue, worker,
      and pool metrics

    The real ``/metrics?format=json`` schema (LangGraph ≥ 0.1)::

        {
          "postgres": {"pool_max": int, "pool_size": int, "pool_available": int,
                       "requests_queued": int, "requests_errors": int},
          "redis":    {"idle_connections": int, "in_use_connections": int,
                       "max_connections": int},
          "queue":    {"n_pending": int, "n_running": int,
                       "pending_runs_wait_time_max_secs": float | null,
                       "pending_runs_wait_time_med_secs": float | null,
                       "pending_unblocked_runs_wait_time_max_secs": float | null},
          "workers":  {"max": int, "active": int, "available": int},
          "api":      {"http_requests_total": [...]}
        }

    The screen auto-refreshes every :data:`_REFRESH_INTERVAL` seconds.
    Press ``a`` to pause/resume auto-refresh.
    """

    CSS = """
    ServerStatsScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
    }
    #stats-header-bar {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    #stats-body {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }
    .stats-section {
        height: auto;
        margin-bottom: 1;
        border: solid $primary;
        padding: 0 1;
    }
    .section-title {
        color: $accent;
        text-style: bold;
        padding: 0 0 0 0;
    }
    #warning-bar {
        height: 1;
        background: $error;
        color: $text;
        padding: 0 1;
        display: none;
    }
    #warning-bar.-visible {
        display: block;
    }
    #status-bar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("r", "refresh_now", "Refresh", show=True),
        Binding("a", "toggle_auto", "Auto-refresh", show=True),
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("q", "app.quit", "Quit", show=True, priority=True),
    ]

    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")
        self._info: dict[str, Any] = {}
        self._metrics: dict[str, Any] = {}
        self._auto_refresh: bool = True
        self._countdown: float = _REFRESH_INTERVAL
        self._refresh_timer = None
        self._countdown_timer = None
        self._fetching: bool = False
        super().__init__()

    # ── Textual lifecycle ────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(f"Server Stats — {self._url}", id="stats-header-bar")
        yield Static("", id="warning-bar")
        with Vertical(id="stats-body"):
            # Server info section
            with Vertical(classes="stats-section"):
                yield Static("SERVER INFO", classes="section-title")
                yield Static("Loading…", id="info-content")
            # Queue / workers section
            with Vertical(classes="stats-section"):
                yield Static("QUEUE & WORKERS", classes="section-title")
                yield Static("Loading…", id="queue-content")
            # Resource pools section
            with Vertical(classes="stats-section"):
                yield Static("RESOURCE POOLS", classes="section-title")
                yield Static("Loading…", id="pools-content")
            # Langshark SDK request backlog
            with Vertical(classes="stats-section"):
                yield Static("LANGSHARK SDK REQUESTS", classes="section-title")
                yield Static("", id="internal-content")
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._fetch_data()
        self._refresh_timer = self.set_interval(
            _REFRESH_INTERVAL, self._on_refresh_tick
        )
        self._countdown_timer = self.set_interval(1.0, self._on_countdown_tick)

    # ── Timers ───────────────────────────────────────────────────────────────

    def _on_refresh_tick(self) -> None:
        if self._auto_refresh:
            self._countdown = _REFRESH_INTERVAL
            self._fetch_data()

    def _on_countdown_tick(self) -> None:
        if self._auto_refresh and not self._fetching:
            self._countdown = max(0.0, self._countdown - 1.0)
        self._update_status_bar()

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_refresh_now(self) -> None:
        self._countdown = _REFRESH_INTERVAL
        self._fetch_data()

    def action_toggle_auto(self) -> None:
        self._auto_refresh = not self._auto_refresh
        self._update_status_bar()
        state = "ON" if self._auto_refresh else "OFF"
        self.notify(f"Auto-refresh {state}")

    # ── Data fetching ────────────────────────────────────────────────────────

    def _fetch_data(self) -> None:
        if self._fetching:
            return
        self._fetching = True
        self._update_status_bar()

        async def _call_info(_client: Any) -> Any:
            import httpx  # transitive dep of langgraph-sdk

            async with httpx.AsyncClient() as http:
                resp = await http.get(f"{self._url}/info", timeout=5.0)
                return resp.json()

        def _on_info(result: Any) -> None:
            self._info = result if isinstance(result, dict) else {}
            self._render_info()
            self._render_internal()
            self._fetching = False
            self._update_status_bar()

        def _on_info_error(exc: Exception) -> None:
            # Detect langgraph dev (no /info endpoint) and show a friendly
            # message instead of a raw connection error.
            self._info = {"_dev_mode": True}
            self._render_info()
            self._render_internal()
            self._fetching = False
            self._update_status_bar()
            logger.info("langgraph dev detected (no /info endpoint): %s", exc)

        async def _call_metrics(_client: Any) -> Any:
            import httpx

            async with httpx.AsyncClient() as http:
                resp = await http.get(f"{self._url}/metrics?format=json", timeout=5.0)
                if resp.status_code == 404:
                    return {"_unavailable": True}
                resp.raise_for_status()
                return resp.json()

        def _on_metrics(result: Any) -> None:
            self._metrics = result if isinstance(result, dict) else {}
            self._render_queue()
            self._render_pools()
            self._render_warning()

        def _on_metrics_error(exc: Exception) -> None:
            self._metrics = {"_error": str(exc)}
            self._render_queue()
            self._render_pools()

        self.app.submit_job(
            call=_call_info, on_result=_on_info, on_error=_on_info_error
        )
        # Only fetch metrics if /info succeeded — langgraph dev has neither.
        if not self._info.get("_dev_mode"):
            self.app.submit_job(
                call=_call_metrics, on_result=_on_metrics, on_error=_on_metrics_error
            )

    # ── Render helpers ───────────────────────────────────────────────────────

    def _render_info(self) -> None:
        w = self.query_one("#info-content", Static)
        if self._info.get("_dev_mode"):
            w.update(
                "[yellow]⚠  langgraph dev detected[/yellow]\n"
                "\n"
                "Server Stats requires a standalone LangGraph server (port 8123).\n"
                "langgraph dev does not expose /info or /metrics endpoints."
            )
            return
        if "_error" in self._info:
            w.update(f"[red]Error fetching /info: {self._info['_error']}[/red]")
            return
        if not self._info:
            w.update("No data yet.")
            return

        version = self._info.get("version", "—")
        lg_ver = self._info.get("langgraph_py_version", "—")
        flags = self._info.get("flags", {})
        flag_str = ", ".join(f"{k}={v}" for k, v in flags.items()) if flags else "none"
        meta = self._info.get("metadata", {})
        meta_str = ""
        if meta:
            meta_str = "\n" + "\n".join(f"  {k}: {v}" for k, v in meta.items())

        lines = [
            f"version             {version}",
            f"langgraph_py        {lg_ver}",
            f"feature flags       {flag_str}",
        ]
        if meta_str:
            lines.append(f"metadata{meta_str}")
        w.update("\n".join(lines))

    def _render_queue(self) -> None:
        w = self.query_one("#queue-content", Static)

        if self._info.get("_dev_mode"):
            w.update("(not available on langgraph dev)")
            return
        if self._metrics.get("_unavailable"):
            w.update(
                "[yellow]/metrics endpoint unavailable (disable_meta=true?)[/yellow]"
            )
            return
        if "_error" in self._metrics:
            w.update(f"[red]Error fetching /metrics: {self._metrics['_error']}[/red]")
            return
        if not self._metrics:
            w.update("No data yet.")
            return

        # Real schema: top-level "workers" and "queue" objects.
        workers = self._metrics.get("workers", {})
        queue = self._metrics.get("queue", {})

        w_max = workers.get("max")
        w_active = workers.get("active")
        w_avail = workers.get("available")
        pending = queue.get("n_pending")
        running = queue.get("n_running")
        wait_med = queue.get("pending_runs_wait_time_med_secs")
        wait_max = queue.get("pending_runs_wait_time_max_secs")

        def _fmt(v: Any, label: str) -> str:
            return f"{label:<20} {v if v is not None else '—'}"

        lines = []

        # Worker saturation bar
        if w_max is not None and w_active is not None and w_max > 0:
            bar = _ascii_bar(w_active, w_max)
            saturation_pct = round(w_active / w_max * 100)
            colour = (
                "red"
                if saturation_pct >= 90
                else "yellow"
                if saturation_pct >= 70
                else "green"
            )
            lines.append(
                f"workers             [{colour}]{bar}[/{colour}]"
                f"  {w_active}/{w_max} ({saturation_pct}%)"
            )
        else:
            lines.append(_fmt(w_active, "workers active"))

        lines.append(_fmt(w_avail, "workers available"))

        # Pending / running runs
        # yellow = backlog forming (pending > 0, workers still available)
        # red    = fully saturated (pending > 0, no workers left)
        # green  = no backlog
        pending_colour = (
            "red"
            if (pending or 0) > 0 and (w_avail is not None and w_avail == 0)
            else "yellow"
            if (pending or 0) > 0
            else "green"
        )
        lines.append(
            f"{'pending runs':<20} [{pending_colour}]{pending if pending is not None else '—'}[/{pending_colour}]"
        )
        lines.append(_fmt(running, "running runs"))

        # Queue wait time (median / max — colour-coded by severity)
        # green < 30s, yellow 30–120s, red > 120s
        if wait_med is not None:
            wait_colour = (
                "red" if wait_med > 120 else "yellow" if wait_med > 30 else "green"
            )
            lines.append(
                f"{'queue wait (med)':<20} [{wait_colour}]{wait_med:.1f} s[/{wait_colour}]"
            )
        if wait_max is not None:
            wait_max_colour = (
                "red" if wait_max > 120 else "yellow" if wait_max > 30 else "green"
            )
            lines.append(
                f"{'queue wait (max)':<20} [{wait_max_colour}]{wait_max:.1f} s[/{wait_max_colour}]"
            )

        w.update("\n".join(lines))

    def _render_pools(self) -> None:
        w = self.query_one("#pools-content", Static)

        if self._info.get("_dev_mode"):
            w.update("(not available on langgraph dev)")
            return
        if self._metrics.get("_unavailable") or "_error" in self._metrics:
            w.update("(metrics unavailable)")
            return
        if not self._metrics:
            w.update("No data yet.")
            return

        # Real schema: top-level "postgres" and "redis" objects.
        pg = self._metrics.get("postgres", {})
        rd = self._metrics.get("redis", {})

        pg_max = pg.get("pool_max")
        pg_size = pg.get("pool_size")
        pg_avail = pg.get("pool_available")
        pg_queued = pg.get("requests_queued")

        # Redis exposes connections differently: idle + in_use = total used
        rd_max = rd.get("max_connections")
        rd_in_use = rd.get("in_use_connections")
        rd_idle = rd.get("idle_connections")

        lines = []

        def _pool_line(
            label: str,
            used: float | None,
            maximum: float | None,
            avail: float | None,
            extra: str = "",
        ) -> str:
            if maximum is None or used is None:
                return f"{label:<10} —"
            bar = _ascii_bar(used, maximum)
            pct = round(used / maximum * 100) if maximum else 0
            colour = "red" if pct >= 90 else "yellow" if pct >= 70 else "green"
            avail_str = f"  ({avail} idle)" if avail is not None else ""
            extra_str = f"  {extra}" if extra else ""
            return (
                f"{label:<10} [{colour}]{bar}[/{colour}]"
                f"  {used}/{maximum}{avail_str}{extra_str}"
            )

        pg_extra = f"[yellow]{pg_queued} queued[/yellow]" if pg_queued else ""
        lines.append(_pool_line("Postgres", pg_size, pg_max, pg_avail, pg_extra))
        lines.append(_pool_line("Redis   ", rd_in_use, rd_max, rd_idle))

        w.update("\n".join(lines))

    def _render_internal(self) -> None:
        """Show Langshark's own asyncio job-queue depth."""
        w = self.query_one("#internal-content", Static)
        qsize = self.app._task_queue.qsize()
        colour = "red" if qsize > 5 else "yellow" if qsize > 0 else "green"
        w.update(
            f"{'SDK job backlog':<20} [{colour}]{qsize}[/{colour}]"
            f"  (jobs waiting in Langshark's async queue)"
        )

    def _render_warning(self) -> None:
        """Show a top-of-screen banner if the server is saturated."""
        bar = self.query_one("#warning-bar", Static)
        queue = self._metrics.get("queue", {})
        workers = self._metrics.get("workers", {})
        pending = queue.get("n_pending", 0) or 0
        w_avail = workers.get("available")
        if pending > 0 and w_avail is not None and w_avail == 0:
            bar.update(
                f"⚠  QUEUE SATURATED — {pending} run(s) pending, 0 workers available"
            )
            bar.add_class("-visible")
        else:
            bar.remove_class("-visible")

    def _update_status_bar(self) -> None:
        bar = self.query_one("#status-bar", Static)
        if self._fetching:
            bar.update("Fetching…")
        elif self._auto_refresh:
            bar.update(
                f"Auto-refresh ON — next in {int(self._countdown)}s  |  [r] refresh now  [a] pause"
            )
        else:
            bar.update("Auto-refresh PAUSED  |  [r] refresh now  [a] resume")
