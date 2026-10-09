"""Privacy-safe aggregation for OpenCode V2 diagnostics metadata."""
from __future__ import annotations

from typing import Any, Mapping


def summarize_v2_diagnostics(state: Mapping[str, Any]) -> dict[str, Any]:
    contracts = state.get("message_contracts", {})
    shapes = state.get("message_shapes", {})
    item_counts = state.get("message_items", {})
    page_counts = state.get("message_pages", {})

    def counts(values: Any) -> dict[str, int]:
        result: dict[str, int] = {}
        if isinstance(values, Mapping):
            for value in values.values():
                key = str(value)
                result[key] = result.get(key, 0) + 1
        return result

    ignored = state.get("message_lifecycle_ignored", {})
    terminal = state.get("message_terminal_evidence", {})
    return {
        "session_contract": state.get("session_contract"),
        "session_pages": state.get("session_pages", 0),
        "raw_sessions": state.get("raw_sessions", 0),
        "last_snapshot_stage": state.get("last_snapshot_stage", "unknown"),
        "snapshot_revision_rechecks": state.get("snapshot_revision_rechecks", 0),
        "message_contract_counts": counts(contracts),
        "message_shape_counts": counts(shapes),
        "message_sessions_sampled": len(item_counts) if isinstance(item_counts, Mapping) else 0,
        "message_items_sampled": sum(int(v) for v in item_counts.values()) if isinstance(item_counts, Mapping) else 0,
        "message_pages_sampled": sum(int(v) for v in page_counts.values()) if isinstance(page_counts, Mapping) else 0,
        "message_type_counts": dict(state.get("message_types", {})),
        "message_route_rejection_counts": counts(state.get("message_route_rejections", {})),
        "message_lifecycle_items_ignored": sum(int(v) for v in ignored.values()) if isinstance(ignored, Mapping) else 0,
        "message_terminal_evidence_normalized": sum(int(v) for v in terminal.values()) if isinstance(terminal, Mapping) else 0,
    }
