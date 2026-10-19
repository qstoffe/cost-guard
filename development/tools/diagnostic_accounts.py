"""Human-readable quota freshness evidence for the existing Diagnostics bundle."""
from __future__ import annotations


def quota_freshness_summary(data: dict) -> list[str]:
    watch = (data.get("watch_account_refresh") or {}).get("evidence", {}).get("quota_observations", {})
    report = (data.get("report") or {}).get("account_acquisition", {}).get("quota_observations", {})
    lines = ["Quota freshness: retrieval success is not proof of upstream currency; upstream freshness is unknown.",
             "Watch history is run-local, latest persisted writer only; independent report observations are separate."]
    for title, evidence in (("Watch", watch), ("Independent report", report)):
        lines.append(f"{title} quota history: run={evidence.get('run_id', 'unavailable')}; "
                     f"ages at captured_at_ms={evidence.get('captured_at_ms')}")
        for series in evidence.get("series", ()):
            history = series.get("history", ())
            successful = sum(item.get("outcome") == "success" for item in history)
            lines.append(
                f"  {series.get('provider_id')} series {series.get('series_id')} window {series.get('window_id')} "
                f"({series.get('duration_seconds')}s): {successful}/{len(history)} successful observations; "
                f"last retrieval={series.get('last_successful_retrieval_ms')}ms UTC; "
                f"last change={series.get('last_value_change_ms')}ms UTC; "
                f"change age={series.get('value_change_age_seconds')}s; "
                f"observed unchanged={series.get('observed_unchanged_seconds')}s; "
                f"last Watch publication={series.get('last_watch_publication_ms')}ms UTC")
    return lines
