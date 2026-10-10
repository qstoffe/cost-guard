"""Headless, privacy-safe Watch startup/render evidence and terminal facts for Diagnostics.

Runs the real Watch composition once against the selected source without
account requests or Watch observation logging, then renders the resulting
dashboard to memory at fixed widths. Only counts, timings and geometry leave
this module: never titles, prompts, model names, paths or payloads.
"""
from __future__ import annotations

from dataclasses import replace
import io
import os
import re
import shutil
import sys
import time
from typing import Any, Mapping

from src.pricing.github_copilot import GitHubCopilotPricingProvider
from src.presentation import WatchRenderer
from src.reports import ReportService
from src.watch import WatchCoordinator

WIDTHS = (80, 120, 160)
_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def terminal_facts() -> dict[str, Any]:
    """Facts that decide Watch glyphs, colors and geometry in this console."""
    size = shutil.get_terminal_size(fallback=(0, 0))
    stream = sys.stdout
    return {
        "stdout_encoding": getattr(stream, "encoding", None),
        "stdout_is_tty": bool(getattr(stream, "isatty", lambda: False)()),
        "columns": size.columns, "lines": size.lines,
        "term": os.environ.get("TERM"),
        "colorterm_present": bool(os.environ.get("COLORTERM")),
        "windows_terminal": bool(os.environ.get("WT_SESSION")),
    }


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _render_geometry(renderer_config: Mapping[str, Any], projection: Any, width: int) -> dict[str, Any]:
    stream = io.StringIO()
    started = time.perf_counter()
    WatchRenderer(renderer_config, stream=stream, interactive=True, terminal_width=width).render(projection)
    elapsed = _ms(started)
    lines = [_ANSI.sub("", line).replace("\r", "") for line in stream.getvalue().split("\n")]
    # Fixed table geometry is contractual; only free-flowing lines must fit.
    flowing = [line for line in lines if line and not line.startswith("|")]
    return {
        "render_ms": elapsed, "lines": len(lines),
        "table_width": max((len(line) for line in lines if line.startswith("|")), default=0),
        "max_flowing_width": max((len(line) for line in flowing), default=0),
        "flowing_overflow_lines": sum(len(line) > width for line in flowing),
    }


def watch_evidence(selection: Any, config: Mapping[str, Any], repository: Any, *, quota: Any = None,
                   pricing_provider: Any = None) -> dict[str, Any]:
    """``quota`` reuses already-observed account projections to exercise quota layout."""
    pricing = pricing_provider or GitHubCopilotPricingProvider(
        cache=repository, max_age_hours=float(config.get("pricingMaxAgeHours", 1)), defer_metadata_refresh=True,
    )
    service = ReportService(
        selection=selection, pricing_provider=pricing, account_provider=None, account_providers=(),
        model_availability_source=None, cache_repository=repository, config=config,
        now_ms=int(time.time() * 1000),
    )
    watch = WatchCoordinator(selection=selection, report_service=service, config=config, record_observations=False)
    try:
        started = time.perf_counter()
        initial = watch.initialize()
        initialize_ms = _ms(started)
        started = time.perf_counter()
        polled = watch.poll_once()
        poll_ms = _ms(started)
        started = time.perf_counter()
        status = watch.status_projection(seconds_until_check=5)
        status_ms = _ms(started)
    finally:
        watch.close()
    projection = polled.projection if quota is None else replace(polled.projection, quota=quota)
    metadata = getattr(selection.source, "diagnostic_metadata", None)
    transport = (metadata() or {}).get("transport") if callable(metadata) else None
    return {
        "initialize_ms": initialize_ms, "poll_ms": poll_ms, "status_projection_ms": status_ms,
        "roots": len(initial.changed_roots), "hydrated_roots": len(initial.hydrated_roots),
        "startup_quiet_roots": watch.startup_quiet_roots, "rows": len(projection.rows),
        "running_rows": projection.active_count, "status_active": bool(status.status_active),
        "session_warnings": len(projection.session_warnings or {}),
        "rendered_accounts": len(quota.accounts) if quota is not None else 0,
        "renders": {str(width): _render_geometry(config, projection, width) for width in WIDTHS},
        "selected_source_transport": dict(transport) if isinstance(transport, Mapping) else None,
    }
