"""Entry point for ``langshark`` console script and ``python -m langshark``."""

from __future__ import annotations

import argparse
import logging
import sys

from textual.logging import TextualHandler

from langshark.app import ConnectedApp

logger = logging.getLogger("langshark")


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for langshark."""
    parser = argparse.ArgumentParser(
        prog="langshark",
        description=(
            "Langshark is a TUI for monitoring and diagnosing LangGraph applications.\n"
            "\n"
            "🧵  Browse threads — filter by status or graph\n"
            "🧬  Inspect checkpoints — expand state tree, writes, metadata\n"
            "🔍  Trace execution flow — see where agents stop and why\n"
            "🔥  Phoenix integration — share trace URLs with your team"
        ),
        epilog=(
            "use cases:\n"
            "  Debug a stuck thread (langgraph dev, port 2024)\n"
            "    langshark -c http://127.0.0.1:2024\n"
            "    Hot-reload dev server with in-memory state. No Docker required.\n"
            "\n"
            "  Monitor a standalone LangGraph server (port 8123)\n"
            "    langshark -c http://localhost:8123\n"
            "    Self-hosted deployment with PostgreSQL persistence. Docker required.\n"
            "\n"
            "  Filter to a specific graph\n"
            "    langshark -c URL --graph supervisor --status idle\n"
            "    Focus on one graph's threads; hide idle or busy noise.\n"
            "\n"
            "  Share a trace with your team\n"
            "    langshark -c URL --phoenix http://localhost:6006\n"
            "    Press 'p' on any thread or checkpoint to copy its Phoenix URL.\n"
            "\n"
            "screens:\n"
            "  Thread Browser      List threads; filter by status or graph.\n"
            "  Checkpoint History  Timeline of checkpoints; expand to inspect state.\n"
            "  Server Stats        Live metrics: queue, workers, pools. Auto-refresh.\n"
            "  Phoenix URL         (optional) Press 'p' for a shareable trace URL.\n"
            "\n"
            "note: Langshark works with langgraph dev and self-hosted servers only.\n"
            "      LangGraph Cloud is not supported.\n"
            "\n"
            "textual run (development):\n"
            "  Run Langshark in a dev terminal with live log capture. Textual\n"
            "  console intercepts print/log output for debugging.\n"
            "\n"
            "  textual run langshark\n"
            "  textual run langshark.__main__:app -c URL --graph NAME\n"
            "\n"
            "textual serve (web UI):\n"
            "  Serve Langshark as a web application in your browser."
            "\n"
            "  textual serve langshark\n"
            '  textual serve "langshark.__main__:app -c URL --graph NAME"\n'
            "  Then open http://localhost:8000 in your browser."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--connect",
        nargs="?",
        const="http://127.0.0.1:2024",
        default=None,
        metavar="URL",
        help="Connect to a LangGraph server URL (default: http://127.0.0.1:2024)",
    )
    parser.add_argument(
        "--graph",
        default=None,
        help="Filter threads by graph name (only with --connect)",
    )
    parser.add_argument(
        "--status",
        default=None,
        choices=["idle", "busy", "interrupted", "error"],
        help="Filter threads by status (only with --connect)",
    )
    parser.add_argument(
        "-p",
        "--phoenix",
        default=None,
        metavar="URL",
        help=("Phoenix server URL for trace deep-linking (e.g. http://localhost:6006)"),
    )
    parser.add_argument(
        "--phoenix-project",
        default=None,
        metavar="NAME",
        help="Phoenix project name (auto-detected if omitted)",
    )
    return parser


def _run(args: argparse.Namespace) -> None:
    """Run the app with parsed arguments.

    Shared by ``main()`` (console script / ``python -m langshark``) and by the
    module-level ``app`` below (for ``textual run langshark.__main__:app``).
    """
    if not args.connect:
        print("Usage:", file=sys.stderr)
        print("  langshark --connect http://127.0.0.1:2024", file=sys.stderr)
        sys.exit(1)

    logger.info(
        "Starting server mode: url=%s graph=%s status=%s phoenix=%s",
        args.connect,
        args.graph,
        args.status,
        args.phoenix,
    )
    ConnectedApp(
        url=args.connect,
        graph=args.graph,
        status=args.status,
        phoenix_url=args.phoenix,
        phoenix_project=args.phoenix_project,
    ).run()


def main() -> None:
    """Entry point for the ``langshark`` console script."""
    logging.basicConfig(level=logging.INFO, handlers=[TextualHandler()], force=True)
    logger.info("Starting langshark")
    parser = _build_parser()
    args = parser.parse_args()
    _run(args)


# Expose an app for ``textual run langshark.__main__:app`` — uses
# parse_known_args() so unknown flags from textual are silently ignored.
_parser = _build_parser()
_args, _ = _parser.parse_known_args()
app = ConnectedApp(
    url=_args.connect or "http://127.0.0.1:2024",
    graph=_args.graph,
    status=_args.status,
    phoenix_url=_args.phoenix,
    phoenix_project=_args.phoenix_project,
)


if __name__ == "__main__":
    main()
