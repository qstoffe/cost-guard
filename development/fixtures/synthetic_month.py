"""Deterministic large-month fixture for performance/cache verification."""
from __future__ import annotations

from decimal import Decimal

from src.domain import (
    CostKind, CostObservation, EventKind, IntegrationHealth, MessageRole, ModelInvocation,
    ModelRef, NormalizedEvent, NormalizedMessage, NormalizedPart, NormalizedSession,
    Provenance, SessionCapabilities, SessionSnapshot, TokenUsage,
)

CAP = SessionCapabilities(native_cost=True, child_sessions=True, compaction_events=True)
MODEL = ModelRef("github-copilot", "gpt-test", "GPT Test")


def _prov(session_id: str, event_id: str | None = None) -> Provenance:
    return Provenance("opencode", "v1", "synthetic-month", session_id, event_id)


def make_root_snapshot(root_index: int, prompts_per_root: int, *, month_start_ms: int) -> SessionSnapshot:
    sid = f"root-{root_index:04d}"
    base = month_start_ms + root_index * 60_000
    root = NormalizedSession(sid, f"Synthetic {root_index:04d}", base, base + prompts_per_root * 1_000 + 500, _prov(sid), CAP)
    messages = []
    parts = []
    events = []
    invocations = []
    for prompt_index in range(prompts_per_root):
        at = base + prompt_index * 1_000
        uid = f"{sid}-u-{prompt_index:04d}"
        aid = f"{sid}-a-{prompt_index:04d}"
        pid = f"{sid}-p-{prompt_index:04d}"
        part = NormalizedPart(pid, uid, sid, "text", at, at, _prov(sid, pid), {"text": f"prompt {root_index}-{prompt_index}", "synthetic": False})
        parts.append(part)
        messages.append(NormalizedMessage(uid, sid, MessageRole.USER, at, _prov(sid, uid), (part,)))
        messages.append(NormalizedMessage(
            aid, sid, MessageRole.ASSISTANT, at + 100, _prov(sid, aid), (), at + 300, uid,
            MODEL, None, None, False, "stop", None,
        ))
        events.append(NormalizedEvent(uid, sid, EventKind.USER_PROMPT, at, _prov(sid, uid), f"prompt {root_index}-{prompt_index}", metadata={"provider_id":"github-copilot","model_id":"gpt-test"}))
        invocations.append(ModelInvocation(
            f"{sid}-i-{prompt_index:04d}", sid, at + 100, MODEL,
            TokenUsage(input=100 + prompt_index, cache_read=20, output=10), _prov(sid, aid),
            completed_at_ms=at + 300,
            cost=CostObservation(Decimal("0.01"), "USD", CostKind.PROVIDER_REPORTED),
            initiating_event_id=uid, provider_request_id=f"req-{sid}-{prompt_index}", message_id=aid,
            finish_reason="stop",
        ))
    return SessionSnapshot(root, (root,), tuple(messages), tuple(parts), tuple(events), tuple(invocations), f"synthetic-rev-{root_index}")


class SyntheticMonthSource:
    source_id = "synthetic-v1"
    capabilities = CAP

    def __init__(self, roots: int, prompts_per_root: int, *, month_start_ms: int) -> None:
        self.snapshots = {
            snapshot.root.session_id: snapshot
            for snapshot in (make_root_snapshot(index, prompts_per_root, month_start_ms=month_start_ms) for index in range(roots))
        }
        self.load_count = 0
        self.revision_count = 0
        self.batch_count = 0

    def probe(self):
        return IntegrationHealth(True, True, "synthetic")

    def list_sessions(self, since_ms=None):
        values = tuple(snapshot.root for snapshot in self.snapshots.values())
        if since_ms is None:
            return values
        return tuple(item for item in values if item.updated_at_ms >= since_ms)

    def get_session_tree_revision(self, session_id):
        self.revision_count += 1
        return self.snapshots[session_id].source_revision

    def get_session_tree_revisions(self, session_ids):
        self.batch_count += 1
        return {session_id: self.snapshots[session_id].source_revision for session_id in session_ids}

    def load_session_snapshot(self, session_id):
        self.load_count += 1
        return self.snapshots[session_id]
