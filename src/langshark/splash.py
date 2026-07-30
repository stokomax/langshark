"""Langshark splash screen — B3 style: shark fin cutting through animated
scanline/static noise, rendered as a Textual Screen.

Usage in your existing app:

    from langshark.splash import SplashScreen

    class LangsharkApp(App):
        async def on_mount(self) -> None:
            self.push_screen(SplashScreen())
            # do real init work here (connect to LangGraph server, etc.)
            # then call self.pop_screen() when ready, or let the
            # SplashScreen's own timer dismiss it.
"""

import random

from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label

from langshark import __version__

# ── Animated shark fin ─────────────────────────────────────────────────────
FIN_ROWS: list[tuple[int, str]] = [
    (5, "██"),
    (3, "████"),
    (2, "██████"),
    (0, "█████████"),
]

FIN_WIDTH = max(offset + len(glyphs) for offset, glyphs in FIN_ROWS)
FIN_TOP_ROW = 3
WORDMARK = "L A N G S H A R K"
TAGLINE = f"A friendly LangGraph inspector — v{__version__}"
NOISE_WIDTH = 70
NOISE_HEIGHT = 9
NOISE_GLYPHS = ["▓", "▒", "░"]
NOISE_WEIGHTS = [50, 30, 20]
NOISE_COLORS: list[str | Style] = ["dim cyan", "grey23", "dim grey50", "grey15"]
NOISE_CHURN = 0.12
TICK_INTERVAL = 0.05
FIN_SPEED = 1
FIN_STYLE = Style(bold=True, color="#22d3ee")
BORDER_STYLE = Style(color="grey15")
WORDMARK_STYLE = Style(bold=True, color="#22d3ee")
TAGLINE_STYLE = Style(dim=True, italic=True, color="grey58")

# A noise cell is a (glyph, style) pair.
NoiseCell = tuple[str, str | Style]


def _random_noise_cell() -> NoiseCell:
    glyph = random.choices(NOISE_GLYPHS, weights=NOISE_WEIGHTS, k=1)[0]
    style = random.choice(NOISE_COLORS)
    return (glyph, style)


def _build_noise() -> list[list[NoiseCell]]:
    grid: list[list[NoiseCell]] = []
    for row in range(NOISE_HEIGHT):
        cells: list[NoiseCell] = []
        is_border = row == 0 or row == NOISE_HEIGHT - 1
        for _ in range(NOISE_WIDTH):
            if is_border:
                cells.append(("▓", BORDER_STYLE))
            else:
                cells.append(_random_noise_cell())
        grid.append(cells)
    return grid


def _mutate_noise(noise: list[list[NoiseCell]], fraction: float = NOISE_CHURN) -> None:
    interior_cells = NOISE_WIDTH * (NOISE_HEIGHT - 2)
    for _ in range(int(interior_cells * fraction)):
        row = random.randrange(1, NOISE_HEIGHT - 1)
        col = random.randrange(NOISE_WIDTH)
        noise[row][col] = _random_noise_cell()


def _build_frame(fin_offset: int, noise: list[list[NoiseCell]]) -> Text:
    text = Text()
    base = fin_offset - FIN_WIDTH
    for row in range(NOISE_HEIGHT):
        fin_start = fin_end = -1
        fin_row_idx = row - FIN_TOP_ROW
        if 0 <= fin_row_idx < len(FIN_ROWS):
            offset, glyphs = FIN_ROWS[fin_row_idx]
            fin_start = base + offset
            fin_end = fin_start + len(glyphs)
        for col in range(NOISE_WIDTH):
            if fin_start <= col < fin_end:
                text.append("█", style=FIN_STYLE)
            else:
                glyph, style = noise[row][col]
                text.append(glyph, style=style)
        text.append("\n")
    text.append("\n")
    text.append(WORDMARK.center(NOISE_WIDTH) + "\n", style=WORDMARK_STYLE)
    text.append(TAGLINE.center(NOISE_WIDTH), style=TAGLINE_STYLE)
    return text


class NoiseLogo(Label):
    _CYCLE = NOISE_WIDTH + 2 * FIN_WIDTH

    def __init__(self) -> None:
        self._fin_offset = 0
        self._noise = _build_noise()
        super().__init__(_build_frame(0, self._noise))

    def on_mount(self) -> None:
        # NOTE: the callback must not be named ``_animate`` — Widget.__init__
        # sets an instance attribute ``self._animate = None`` (the slot for
        # Textual's lazily bound animator), which shadows any same-named
        # method and would silently pass None as the timer callback.
        self.set_interval(TICK_INTERVAL, self._advance_frame)

    def _advance_frame(self) -> None:
        _mutate_noise(self._noise)
        self._fin_offset = (self._fin_offset + FIN_SPEED) % self._CYCLE
        self.update(_build_frame(self._fin_offset, self._noise))


class SplashScreen(ModalScreen[None]):
    CSS = """
    SplashScreen {
        align: center middle;
    }

    NoiseLogo {
        width: 100%;
        height: 12;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        yield NoiseLogo()

    def on_key(self, event) -> None:
        self.dismiss()


if __name__ == "__main__":

    class _TestApp(App):
        def on_mount(self) -> None:
            self.push_screen(SplashScreen())
            self.set_timer(10, self.exit)

    _TestApp().run()
