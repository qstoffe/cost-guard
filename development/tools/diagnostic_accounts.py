"""Human-readable quota freshness evidence for the existing Diagnostics bundle."""
from __future__ import annotations


def quota_freshness_summary(data: dict) -> list[str]:
    observation = (data.get("watch_account_refresh") or {}).get("evidence", {}).get("quota_observations", {})
    history = [item for series in observation.get("series", ()) for item in series.get("history", ())]
    if not history:
        return ["Recorded quota freshness: no observations available."]
    successful = sum(item.get("outcome") == "success" for item in history)
    return [f"Recorded quota retrieval: {successful}/{len(history)} successful observations "
            "(latest persisted writer only; upstream freshness is unknown)."]
