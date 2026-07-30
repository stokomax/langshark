"""Langshark — TUI viewer for JSONL debug trace files and LangGraph server threads.

Usage:
    langshark <path-to-trace.jsonl>
    langshark --connect http://127.0.0.1:2024
    langshark -c http://127.0.0.1:2024 --graph supervisor --status idle
    textual run langshark.__main__:app -c http://localhost:8123
"""

from __future__ import annotations

import importlib.metadata

# NOTE: __version__ must be defined *before* `from langshark.app import
# ConnectedApp` below — app.py imports langshark.splash, which reads
# __version__ from this partially-initialized package during that import.
try:
    __version__ = importlib.metadata.version("langshark")
except importlib.metadata.PackageNotFoundError:  # not installed
    __version__ = "0.0.0+unknown"

from langshark.app import ConnectedApp

# Expose a default ``app`` for ``textual run langshark``.  This must be an
# actual assignment (not a lazy ``__getattr__``) because the ``langshark.app``
# submodule import above would shadow it.  For custom flags with ``textual
# run``, use::
#
#     textual run langshark.__main__:app -c http://localhost:8123
#
# which parses ``sys.argv`` with ``argparse.parse_known_args()`` (tolerant of
# unknown flags from ``textual run`` itself).
app = ConnectedApp()
