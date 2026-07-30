"""Modal confirmation screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class ConfirmScreen(ModalScreen[bool]):
    """Modal screen asking for confirmation."""

    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-dialog {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #confirm-dialog > Static {
        margin: 0 0 1 0;
    }
    """

    def __init__(self, message: str) -> None:
        self._message = message
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self._message)
            yield Static("")
            yield Static(
                "Press [bold]Enter[/bold] to confirm, [bold]Escape[/bold] to cancel"
            )

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.dismiss(True)
        elif event.key == "escape":
            self.dismiss(False)
