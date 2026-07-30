"""Modal screen that displays a Phoenix URL for easy copying."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class PhoenixUrlScreen(ModalScreen[None]):
    """Modal that shows a Phoenix URL with an easy copy button.

    Pressing ``c`` or the Copy button copies the URL to the clipboard.
    Escape or the Close button dismisses the modal.
    """

    CSS = """
    PhoenixUrlScreen {
        align: center middle;
    }
    #phoenix-dialog {
        width: 80;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #phoenix-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #phoenix-url-label {
        margin: 0 0 1 0;
    }
    #phoenix-url-link {
        color: $accent;
        text-style: underline;
        margin: 0 0 1 0;
    }
    #phoenix-hint {
        color: $text-muted;
        margin: 0 0 1 0;
    }
    #phoenix-buttons {
        height: auto;
        margin-top: 1;
        align: left middle;
    }
    #phoenix-buttons > Button {
        margin-right: 1;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("c", "copy_url", "Copy", show=True),
        Binding("escape", "dismiss_modal", "Close", show=True),
    ]

    def __init__(self, url: str, *, is_fallback: bool = False) -> None:
        self._url = url
        self._is_fallback = is_fallback
        super().__init__()

    def compose(self) -> ComposeResult:
        label = "Phoenix Project" if self._is_fallback else "Phoenix Trace"
        with Vertical(id="phoenix-dialog"):
            yield Static(f"[bold]↗  {label} URL[/bold]", id="phoenix-title")
            if self._is_fallback:
                yield Static(
                    "  No trace found for this item — showing project page instead.",
                    id="phoenix-url-label",
                )
            yield Static(f"  {self._url}", id="phoenix-url-link")
            yield Static(
                "  [dim]c[/dim] copy   [dim]Esc[/dim] close",
                id="phoenix-hint",
            )
            with Horizontal(id="phoenix-buttons"):
                yield Button("Copy URL", id="btn-copy", variant="primary")
                yield Button("Close", id="btn-close", variant="default")

    def action_copy_url(self) -> None:
        self.app.copy_to_clipboard(self._url)
        self.notify("Phoenix URL copied to clipboard", timeout=4)

    def action_dismiss_modal(self) -> None:
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-copy":
            self.action_copy_url()
        elif event.button.id == "btn-close":
            self.dismiss()
