"""Deterministic large-month fixture for performance/cache verification."""
from __future__ import annotations

from decimal import Decimal
from dataclasses import replace
from src.domain.acquisition import AcquisitionMetrics

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

    def __init__(self, roots: int, prompts_per_root: int, *, month_start_ms: int,
                 children_per_root: int = 0, today_roots: int = 0, running_roots: int = 0,
                 now_ms: int | None = None) -> None:
        self.snapshots = {
            snapshot.root.session_id: snapshot
            for snapshot in (make_root_snapshot(index, prompts_per_root, month_start_ms=month_start_ms) for index in range(roots))
        }
        self.load_count = 0
        self.revision_count = 0
        self.batch_count = 0
        self.catalog_count = 0
        self.metrics = AcquisitionMetrics(generation="synthetic")
        if today_roots and now_ms is None:
            raise ValueError("today_roots requires now_ms")
        for index, (root_id, snapshot) in enumerate(tuple(self.snapshots.items())):
            if index >= roots - today_roots:
                start = int(now_ms) - 3_600_000 - index * 60_000 + (index - roots + today_roots) * 1000
                snapshot = make_root_snapshot(index, prompts_per_root, month_start_ms=start)
            if children_per_root:
                children = [make_root_snapshot(10_000_000 + index * children_per_root + child, prompts_per_root,
                            month_start_ms=snapshot.root.created_at_ms + (child + 1) * 10 - (10_000_000 + index * children_per_root + child) * 60_000)
                            for child in range(children_per_root)]
                snapshot = replace(snapshot,
                    sessions=(*snapshot.sessions, *(replace(item.root, parent_session_id=root_id) for item in children)),
                    messages=(*snapshot.messages, *(message for item in children for message in item.messages)),
                    parts=(*snapshot.parts, *(part for item in children for part in item.parts)),
                    events=(*snapshot.events, *(event for item in children for event in item.events)),
                    invocations=(*snapshot.invocations, *(request for item in children for request in item.invocations)))
            if index < running_roots:
                latest = next(item for item in reversed(snapshot.messages)
                              if item.session_id == root_id and item.role is MessageRole.ASSISTANT)
                snapshot = replace(snapshot, root=replace(snapshot.root, active=True),
                    messages=tuple(replace(item, completed_at_ms=None, finish_reason=None)
                                   if item.message_id == latest.message_id else item for item in snapshot.messages),
                    invocations=tuple(replace(item, completed_at_ms=None, finish_reason=None)
                                      if item.message_id == latest.message_id else item for item in snapshot.invocations))
                snapshot = replace(snapshot, sessions=(snapshot.root, *snapshot.sessions[1:]))
            self.snapshots[root_id] = snapshot

    def probe(self):
        return IntegrationHealth(True, True, "synthetic")

    def list_sessions(self, since_ms=None):
        self.catalog_count += 1
        self.metrics.add("full_catalog_fetches")
        values = tuple(session for snapshot in self.snapshots.values()
                       for session in (snapshot.root, *(item for item in snapshot.sessions if item.session_id != snapshot.root.session_id)))
        if since_ms is None:
            return values
        return tuple(item for item in values if item.updated_at_ms >= since_ms)

    def get_session_tree_revision(self, session_id):
        self.revision_count += 1
        self.metrics.add("revision_checks")
        return self.snapshots[session_id].source_revision

    def get_session_tree_revisions(self, session_ids):
        self.batch_count += 1
        self.metrics.add("revision_checks", len(session_ids))
        return {session_id: self.snapshots[session_id].source_revision for session_id in session_ids}

    def load_session_snapshot(self, session_id):
        self.load_count += 1
        self.metrics.add("hydrated_roots")
        return self.snapshots[session_id]

    def watch_candidate_session_ids(self):
        return frozenset(snapshot.root.session_id for snapshot in self.snapshots.values() if snapshot.root.active is True)
