"""Context-aware help screen showing keyboard bindings for the current screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

# ── Binding tables keyed by screen name ────────────────────────────────────

BINDINGS: dict[str, list[tuple[str, str]]] = {
    "threads": [
        ("j / k", "Scroll up / down"),
        ("Ctrl+D / U", "Page down / up"),
        ("Enter", "Select thread / show detail"),
        ("Escape", "Close detail panel"),
        ("/", "Filter by status"),
        ("r", "Refresh thread list"),
        ("h", "View checkpoint history"),
        ("c", "Copy thread state to clipboard"),
        ("d", "Delete selected thread"),
        ("s", "Show server stats"),
        ("p", "Show Phoenix trace URL"),
        ("P", "Copy Phoenix trace URL directly"),
        ("?", "Show this help screen"),
        ("q", "Quit"),
    ],
    "checkpoints": [
        ("j / k", "Scroll up / down"),
        ("Ctrl+D / U", "Page down / up"),
        ("Enter", "Expand / collapse checkpoint detail"),
        ("Escape", "Go back to thread list"),
        ("r", "Refresh checkpoint list"),
        ("c", "Copy checkpoint to clipboard"),
        ("p", "Show Phoenix trace URL"),
        ("P", "Copy Phoenix trace URL directly"),
        ("?", "Show this help screen"),
        ("q", "Quit"),
    ],
}

PHOENIX_HELP: list[str] = [
    "─── Phoenix integration (optional) ────────────────",
    "  'p' shows the Phoenix trace URL for the selected",
    "  thread / checkpoint. Requires:",
    "",
    "  1. Instrument your app:",
    "     pip install openinference-instrumentation-langchain",
    "     from openinference.instrumentation.langchain \\",
    "         import LangChainInstrumentor",
    "     LangChainInstrumentor().instrument()",
    "",
    "  2. Launch langshark with --phoenix flag:",
    "     langshark -c URL --phoenix http://localhost:6006",
    "",
    "  Resources:",
    "     Phoenix:  https://arizeai.github.io/phoenix",
    "     LangGraph guide:",
    "       docs.arize.com/phoenix/integrations/langgraph",
]

# A superset shown when the screen isn't explicitly listed
FALLBACK: list[tuple[str, str]] = [
    ("j / k", "Scroll up / down"),
    ("Ctrl+D / U", "Page down / up"),
    ("Enter", "Select / expand"),
    ("Escape", "Close / go back"),
    ("?", "Show this help"),
    ("q", "Quit"),
]


class HelpScreen(ModalScreen[None]):
    """Modal screen showing keyboard shortcuts for the current context."""

    CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-dialog {
        width: 72;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #help-dialog > Static {
        margin: 0 0 1 0;
    }
    #help-title {
        text-style: bold;
    }
    """

    def __init__(self, screen_name: str = "threads") -> None:
        self._screen_name = screen_name
        super().__init__()

    def compose(self) -> ComposeResult:
        title_map = {
            "threads": "Thread Browser Help",
            "checkpoints": "Checkpoint History Help",
        }
        title = title_map.get(self._screen_name, "Langshark Help")
        bindings = BINDINGS.get(self._screen_name, FALLBACK)
        show_phoenix = self._screen_name in ("threads", "checkpoints")

        with Vertical(id="help-dialog"):
            yield Static(f"[bold]{title}[/bold]", id="help-title")
            yield Static("")
            for key, desc in bindings:
                yield Static(f"  {key:<16} {desc}")
            if show_phoenix:
                yield Static("")
                for line in PHOENIX_HELP:
                    yield Static(f"  {line}" if line else "")
            yield Static("")
            yield Static("  Press any key to close")

    def on_key(self, event) -> None:
        self.dismiss()
