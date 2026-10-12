"""Human-readable connection evidence, separate from validation/bundle results."""
from __future__ import annotations


def connectivity_summary(data: dict) -> list[str]:
    lines = []
    events = data.get("watch_source_recovery_events") or []
    for generation, source in (data.get("sources") or {}).items():
        probe = source.get("probe") or {}
        read_failure = source.get("list_timing", {}).get("source_failure") or next(
            (item.get("snapshot_timing", {}).get("source_failure") for item in source.get("snapshot_sample", [])
             if item.get("snapshot_timing", {}).get("ok") is False), None) or {}
        code = read_failure.get("category") or probe.get("failure_code")
        recovered = any(e.get("source") == generation and e.get("event") == "recovered" for e in events)
        read_failed = bool(read_failure) or source.get("list_timing", {}).get("ok") is False
        if probe.get("healthy") and not read_failed:
            state = "temporarily unavailable but recovered; currently healthy" if recovered else "healthy"
        elif code in {"unsupported_schema", "unsupported_version", "registration_invalid"}:
            state = "incompatible"
        elif code in {"invalid_data", "concurrent_source_change"}:
            state = "unreadable"
        else:
            state = "currently unavailable" if probe else "collection unavailable"
        lines.append(f"{generation.upper()} connectivity: {state}; category={code or 'none'}")
    metadata = (data.get("model_metadata") or {}).get("summary") or {}
    if metadata.get("failing_sources"):
        fallback = "cached fallback" if metadata.get("cache_fallback") else "cache availability recorded separately"
        lines.append(f"External HTTPS metadata acquisition degraded ({fallback}); not proof of a local HTTP failure.")
    lines.append("Validation/test failures are independent of source connectivity and Diagnostics ZIP creation.")
    return lines
