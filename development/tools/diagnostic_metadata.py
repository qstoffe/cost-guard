"""Model catalog and release-metadata health section of the Diagnostics bundle.

Read-only: inspects an existing cache only (never creates `cache/`), the
persistent metadata state and failure-period log written by earlier Watch or
report runs, plus an optional live probe. Model names/dates are public data;
no account, session or credential data is included.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, Callable

from src.cache import CacheRepository
from src.pricing.github_copilot import CACHE_KEY, CACHE_NAMESPACE, _catalog_from_payload, _default_fetch_text
from src.pricing.metadata_health import read_state, recent_events
from src.pricing.release_metadata import metadata_health, probe_sources, stage_flags, valid_date

_MAX_MODELS = 96


def _cached_catalog(root: Path, database_factory: Callable[[Path], Any]):
    database = database_factory(root)
    # Inspect only an existing cache; Diagnostics must not create runtime state.
    if not database.paths.database.is_file():
        return None
    database.initialize()
    entry = CacheRepository(database).get(CACHE_NAMESPACE, CACHE_KEY)
    return _catalog_from_payload(entry.payload) if entry else None


def _cache_section(catalog, config: dict) -> dict[str, Any]:
    if catalog is None:
        return {"cache_present": False, "status": "no_cached_catalog"}
    dated = [m for m in catalog.models if valid_date(m.metadata.get("release_date"))]
    return {
        "cache_present": True,
        "cache_age_minutes": max(0, (int(time.time() * 1000) - catalog.retrieved_at_ms) // 60_000),
        "model_count": len(catalog.models),
        "release_dates_known": len(dated),
        "undated_model_count": len(catalog.models) - len(dated),
        "health": metadata_health(len(catalog.models), len(dated)),
        "configured_price_interval_minutes": int(float(config.get("pricingMaxAgeHours", 1)) * 60),
        "watch_price_interval_minutes": 60,
        "watch_availability_interval_minutes": 15,
        "models": [{
            "id": m.model.model, "name": m.model.display_name or m.model.model,
            "release_date": valid_date(m.metadata.get("release_date")) or None,
            "release_date_source": m.metadata.get("release_date_source") if m.metadata.get("release_date") else None,
        } for m in catalog.models[:_MAX_MODELS]],
    }


def _summary(state: dict, cache: dict) -> dict[str, Any]:
    """Machine-readable answer to: which stage of which source failed, and did it heal?"""
    sources = {}
    for name, entry in (state.get("sources") or {}).items():
        last = entry.get("last_result") if isinstance(entry.get("last_result"), dict) else {}
        sources[name] = {
            "last_status": last.get("status"), "last_code": last.get("code"), "last_phase": last.get("phase"),
            "stages": stage_flags(last), "last_success_ms": entry.get("last_success_ms"),
            "last_failure_ms": entry.get("last_failure_ms"), "last_error": entry.get("last_error"),
            "in_failure_period": bool(entry.get("period")), "failure_period": entry.get("period"),
            "last_recovery": entry.get("last_recovery"),
        }
    return {
        "health": state.get("health") or cache.get("health") or "unknown",
        "result_origin": state.get("result_origin"),
        "cache_fallback": state.get("result_origin") == "cache",
        "consecutive_failures": state.get("consecutive_failures"),
        "next_retry_ms": state.get("next_retry_ms"),
        "last_skip": state.get("last_skip"),
        "last_complete_ms": state.get("last_complete_ms"),
        "failing_sources": sorted(n for n, s in sources.items() if s["in_failure_period"]),
        "recovered_sources": sorted(n for n, s in sources.items() if s["last_recovery"]),
        "sources": sources,
    }


def model_metadata_section(root: Path, config: dict, *, network: bool,
                           database_factory: Callable[[Path], Any]) -> dict[str, Any]:
    section: dict[str, Any] = {"schema": 1}
    catalog = None
    try:
        catalog = _cached_catalog(root, database_factory)
        section["cache"] = _cache_section(catalog, config)
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        section["cache"] = {"status": "unavailable", "error_type": type(exc).__name__}
    state = read_state(root)
    section["persistent_state"] = state or {"status": "no_state_recorded"}
    section["failure_events"] = recent_events(root)
    section["summary"] = _summary(state, section["cache"])
    if network:
        section["live_probe"] = probe_sources(catalog.models if catalog else (), _default_fetch_text)
    else:
        section["live_probe"] = {"status": "skipped_no_network"}
    return section
