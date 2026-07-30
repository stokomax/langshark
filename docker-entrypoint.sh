#!/bin/sh
set -e

# If first arg is "web", shift and launch textual serve instead of langshark.
# textual serve spawns the app via asyncio.create_subprocess_shell(), so the
# command must be a valid shell string, not a Python module path like
# langshark.__main__:app.  We use the "langshark" console script (on PATH)
# instead of "python -m langshark" for simplicity and consistency with the
# TUI entrypoint.
if [ "$1" = "web" ]; then
    shift
    # The remaining args may arrive as a single quoted string, e.g.
    # "langshark.__main__:app -c URL".  Re-split on spaces so we can
    # inspect and strip the module path if present.
    set -- $1
    # Strip module path if present (e.g. langshark.__main__:app) — users may
    # pass this from habit with textual run/serve, but it is not a valid
    # shell command.
    if [ "${1#*:}" != "$1" ]; then
        shift
    fi
    # Strip bare "langshark" token if present — users may include it from
    # habit, but we add it ourselves below.
    if [ "$1" = "langshark" ]; then
        shift
    fi
    # --host 0.0.0.0  bind to all interfaces (required for Docker -p mapping)
    # --url  PUBLIC_URL  advertised address embedded in the served HTML —
    #        the page builds its websocket URL from this, and 0.0.0.0 is
    #        not routable from a browser.  Defaults to localhost:8000 to
    #        match the documented "-p 8000:8000" mapping; override with
    #        -e PUBLIC_URL=... when mapping a different host port or when
    #        serving to other machines on the LAN.
    #
    # "; kill -INT 1"  textual serve runs as PID 1 (via exec above) and is a
    #        persistent server — when the user quits the app with "q", only
    #        the spawned app subprocess exits and the container would keep
    #        running.  The spawned subshell continues to this kill command
    #        when the app exits, sending SIGINT to textual serve, which
    #        treats it like Ctrl+C and shuts down gracefully so the
    #        --rm container disappears.  If the browser tab closes instead,
    #        AppService kills the app subprocess (and its subshell) before
    #        the kill runs, so the server stays up for reconnects.
    # Build the shell command string so $* is expanded here, then passed
    # as a single argument to textual serve (which spawns it via
    # create_subprocess_shell).
    # Wrapping in sh -c ensures the ; is parsed as a command separator
    # rather than being passed as a literal argument to langshark.
    cmd="sh -c 'langshark $*; kill -INT 1'"
    exec textual serve --host 0.0.0.0 \
        --url "${PUBLIC_URL:-http://localhost:8000}" "$cmd"
fi

# Default: launch the native TUI.
exec langshark "$@"
