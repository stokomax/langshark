"""Regression tests for the splash screen animation.

The animation is driven by a ``set_interval`` timer armed in
``NoiseLogo.on_mount``. A previous version named the callback ``_animate``,
which collided with ``Widget``'s instance attribute ``self._animate`` (the
slot for Textual's lazily bound animator): the instance attribute shadowed
the method, ``set_interval`` received ``None``, and the timer silently
posted Timer events instead of advancing frames.
"""

from textual.app import App

from langshark import __version__
from langshark.splash import TAGLINE, TICK_INTERVAL, NoiseLogo, SplashScreen


def test_tagline_includes_project_version() -> None:
    """The splash tagline advertises the installed package version."""
    assert f"v{__version__}" in TAGLINE


class _SplashApp(App[None]):
    def on_mount(self) -> None:
        self.push_screen(SplashScreen())


async def test_animation_timer_advances_fin() -> None:
    """The fin offset advances while the splash is mounted."""
    app = _SplashApp()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        logo = app.screen.query_one(NoiseLogo)
        start = logo._fin_offset
        await pilot.pause(10 * TICK_INTERVAL + 0.1)
        assert logo._fin_offset != start


async def test_animation_updates_frame_content() -> None:
    """The rendered frame changes as the animation ticks."""
    app = _SplashApp()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        logo = app.screen.query_one(NoiseLogo)
        frames = {str(logo.render())}
        for _ in range(4):
            await pilot.pause(0.1)
            frames.add(str(logo.render()))
        assert len(frames) > 1


async def test_timer_callback_is_bound_method() -> None:
    """Guard: the interval timer must have a real callback (not None)."""
    app = _SplashApp()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        logo = app.screen.query_one(NoiseLogo)
        timers = list(logo._timers)
        assert len(timers) == 1
        assert timers[0]._callback is not None
        assert timers[0]._callback.__func__ is NoiseLogo._advance_frame


async def test_splash_dismisses_on_keypress() -> None:
    """Any key dismisses the splash (it's also the about screen)."""
    app = _SplashApp()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        assert isinstance(app.screen, SplashScreen)
        await pilot.press("space")
        await pilot.pause(0.2)
        assert not isinstance(app.screen, SplashScreen)


async def test_logo_is_vertically_centered() -> None:
    """The logo sits in the middle of the page, not pinned to the top."""
    app = _SplashApp()
    async with app.run_test() as pilot:
        await pilot.pause(0.2)
        logo = app.screen.query_one(NoiseLogo)
        expected_y = (app.screen.region.height - logo.region.height) // 2
        assert logo.region.y == expected_y
        assert logo.region.y > 0
