"""Shared utility functions for Langshark screens."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

# Regex to strip ANSI escape codes (Rich formatting)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
# Regex to extract content from stringified AIMessageChunk
_CONTENT_RE = re.compile(r"content='([^']*)'")


def strip_ansi(obj: Any) -> Any:
    """Recursively strip ANSI escape codes from all strings."""
    if isinstance(obj, str):
        return _ANSI_RE.sub("", obj)
    if isinstance(obj, dict):
        return {k: strip_ansi(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [strip_ansi(v) for v in obj]
    return obj


def truncate_id(id_str: str, max_len: int = 12) -> str:
    """Shorten a UUID to the first N characters for display."""
    id_str = str(id_str)
    return id_str[:max_len] + "…" if len(id_str) > max_len else id_str


def status_icon(status: str | None) -> str:
    """Return a coloured icon for thread status."""
    icons: dict[str, str] = {
        "idle": "✓",
        "busy": "⟳",
        "interrupted": "⚠",
        "error": "✗",
    }
    return icons.get(status or "", "?")


def to_uuid(value: Any) -> str | None:
    """Convert an int or string to a proper UUID string with dashes, or return None."""
    try:
        if isinstance(value, int):
            return str(uuid.UUID(int=value))
        s = str(value)
        if s.isdigit():
            return str(uuid.UUID(int=int(s)))
        return str(uuid.UUID(s))
    except ValueError, AttributeError:
        return None


def find_thread_id(events: list[dict[str, Any]]) -> str | None:
    """Scan trace events for a ``thread_id`` field."""
    for ev in events:
        tid = ev.get("thread_id")
        if tid:
            return str(tid)
    return None


# ── Tree builder (standalone, reusable across screens) ─────────────────────


def build_detail_tree_inner(
    parent: Any,
    value: Any,
    key: str = "",
    max_depth: int = 8,
    _depth: int = 0,
) -> None:
    """Recursively build a collapsible Tree from a dict/value."""
    if _depth >= max_depth:
        parent.add(f"{key}: … (max depth)")
        return
    label = f"{key}: " if key else ""
    if isinstance(value, dict):
        node = parent.add(
            f"{label}{{{len(value)} keys}}" if _depth > 0 else label or "{}"
        )
        for k, v in value.items():
            build_detail_tree_inner(
                node, v, key=str(k), max_depth=max_depth, _depth=_depth + 1
            )
    elif isinstance(value, list):
        node = parent.add(f"{label}[{len(value)} items]")
        for i, v in enumerate(value):
            build_detail_tree_inner(
                node, v, key=str(i), max_depth=max_depth, _depth=_depth + 1
            )
    elif isinstance(value, str):
        truncated = value[:200] + "…" if len(value) > 200 else value
        parent.add(f"{label}{truncated!r}")
    elif value is None:
        parent.add(f"{label}null")
    else:
        parent.add(f"{label}{value!r}")


# ── Trace event summarisers ────────────────────────────────────────────────


def extract_content(msg: Any) -> str:
    if isinstance(msg, dict):
        return msg.get("content", "") or ""
    if isinstance(msg, str):
        match = _CONTENT_RE.search(msg)
        if match:
            return match.group(1)
        return msg[:120]
    return getattr(msg, "content", "") or ""


def summarise_short(event: dict) -> str:
    typ = event.get("type", "?")
    data = event.get("data", {})
    if typ == "updates":
        if isinstance(data, dict):
            nodes = list(data.keys())
            for node_name in nodes:
                node_data = data[node_name]
                if isinstance(node_data, dict):
                    msgs = node_data.get("messages", [])
                    if msgs:
                        content = extract_content(msgs[0])
                        if content:
                            return f"{node_name}: {content[:120]}"
            return ", ".join(nodes)
        return ""
    elif typ == "messages":
        msg, _ = data if isinstance(data, (list, tuple)) else (data, {})
        content = extract_content(msg)
        return content[:120] if content else str(msg)[:120]
    elif typ == "custom":
        return json.dumps(data, default=str)[:120]
    else:
        return (
            json.dumps(data, default=str)[:120]
            if not isinstance(data, str)
            else data[:120]
        )
