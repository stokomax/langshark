"""Phoenix deep-link helpers — on-demand trace lookup and URL construction.

Usage from screens::

    from langshark.phoenix import find_trace_for_thread, find_trace_for_run, project_url

All network I/O is async (httpx.AsyncClient) and must be run inside the
existing job queue (``app.submit_job``) so it doesn't block the TUI.

Phoenix redirect URL patterns (v14.2.0+):
    /redirects/projects/{project_name}
    /redirects/traces/{trace_id}
    /redirects/spans/{span_id}
    /redirects/sessions/{session_id}

Project auto-discovery
----------------------
When ``project`` is ``None`` the helpers query ``GET /v1/projects`` and
try each project in order until a matching span is found.  This means
``langshark -c URL --phoenix http://localhost:6006`` works without
``--phoenix-project``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("langshark")


def project_url(phoenix_url: str, project: str | None) -> str:
    """Return the Phoenix project page URL."""
    name = project or "default"
    return f"{phoenix_url.rstrip('/')}/redirects/projects/{name}"


def trace_url(phoenix_url: str, trace_id: str) -> str:
    """Return a direct Phoenix trace URL from an OTel trace ID."""
    return f"{phoenix_url.rstrip('/')}/redirects/traces/{trace_id}"


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _list_project_names(http: Any, base: str) -> list[str]:
    """Return all project names from ``GET /v1/projects``.

    Returns an empty list on any error so callers can fall back gracefully.
    """
    try:
        r = await http.get(f"{base}/v1/projects")
        r.raise_for_status()
        data = r.json()
        return [p["name"] for p in data.get("data", []) if p.get("name")]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Phoenix project list failed: %s", exc)
        return []


async def _find_span_in_project(
    http: Any,
    base: str,
    project: str,
    attr_key: str,
    attr_val: str,
) -> str | None:
    """Query *one* project for a root span matching *attr_key:attr_val*.

    Returns the OTel ``trace_id`` of the first match, or ``None``.
    """
    url = f"{base}/v1/projects/{project}/spans"
    params: dict[str, Any] = {
        "attribute": f"{attr_key}:{attr_val}",
        "parent_id": "null",
        "limit": 1,
    }
    r = await http.get(url, params=params)
    r.raise_for_status()
    data = r.json()
    spans = data.get("data", [])
    if not spans:
        return None
    return spans[0]["context"]["trace_id"]


async def _search_all_projects(
    http: Any,
    base: str,
    configured_project: str | None,
    attr_key: str,
    attr_val: str,
) -> tuple[str | None, str | None]:
    """Search projects for a matching span; return ``(trace_id, project_name)``.

    Search order:
    1. ``configured_project`` (if not None)
    2. All other projects from ``GET /v1/projects``

    Returns ``(None, None)`` when nothing is found.
    """
    tried: set[str] = set()

    # Try configured project first
    if configured_project:
        tried.add(configured_project)
        tid = await _find_span_in_project(
            http, base, configured_project, attr_key, attr_val
        )
        if tid:
            return tid, configured_project

    # Auto-discover remaining projects
    all_names = await _list_project_names(http, base)
    for name in all_names:
        if name in tried:
            continue
        tried.add(name)
        try:
            tid = await _find_span_in_project(http, base, name, attr_key, attr_val)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Skipping project %r: %s", name, exc)
            continue
        if tid:
            return tid, name

    return None, None


# ── Public API ────────────────────────────────────────────────────────────────


async def find_trace_for_thread(
    phoenix_url: str,
    project: str | None,
    thread_id: str,
) -> str | None:
    """Return a Phoenix trace URL for the most recent run of a LangGraph thread.

    Queries Phoenix for root spans whose ``metadata.thread_id`` matches
    *thread_id*.  When *project* is ``None`` (or no matching span is found
    in the configured project), automatically searches all projects.

    Returns the trace redirect URL, or ``None`` if no spans are found.
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not available — cannot query Phoenix")
        return None

    base = phoenix_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            trace_id, _ = await _search_all_projects(
                http, base, project, "metadata.thread_id", thread_id
            )
    except Exception as exc:
        logger.warning("Phoenix span query failed: %s", exc)
        raise  # let callers handle — they show the right notification

    if trace_id is None:
        return None
    return trace_url(phoenix_url, trace_id)


async def find_trace_for_run(
    phoenix_url: str,
    project: str | None,
    run_id: str,
) -> str | None:
    """Return a Phoenix trace URL for a specific LangGraph run_id.

    Each LangGraph checkpoint carries ``metadata.run_id`` which identifies
    the specific invocation that produced it.  When *project* is ``None``
    (or no matching span is found in the configured project), automatically
    searches all projects.

    Returns the trace redirect URL, or ``None`` if no spans are found.
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not available — cannot query Phoenix")
        return None

    base = phoenix_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            trace_id, _ = await _search_all_projects(
                http, base, project, "metadata.run_id", run_id
            )
    except Exception as exc:
        logger.warning("Phoenix span query failed: %s", exc)
        raise

    if trace_id is None:
        return None
    return trace_url(phoenix_url, trace_id)
