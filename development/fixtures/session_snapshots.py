"""Canonical synthetic session/message fixtures; no dependency on test modules."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from src.domain import (
    CostKind, CostObservation, EventKind, ModelInvocation, ModelRef, NormalizedEvent,
    NormalizedMessage, NormalizedPart, NormalizedSession, Provenance, SessionCapabilities,
    SessionSnapshot, TokenUsage, MessageRole,
)

CAP = SessionCapabilities(native_cost=True, child_sessions=True, compaction_events=True)
MODEL = ModelRef("github-copilot", "gpt-test")


def prov(session: str, event: str | None = None, gen: str = "v1") -> Provenance:
    return Provenance("opencode", gen, f"instance-{gen}", session, event)


def part(pid: str, mid: str, sid: str, kind: str, data: dict, t: int) -> NormalizedPart:
    return NormalizedPart(pid, mid, sid, kind, t, t, prov(sid, pid), data)


def message(mid: str, sid: str, role: MessageRole, created: int, *, parent: str | None = None,
            parts: tuple[NormalizedPart, ...] = (), completed: int | None = None,
            model: ModelRef | None = None, summary: bool = False, finish: str | None = None,
            error: str | None = None) -> NormalizedMessage:
    return NormalizedMessage(mid, sid, role, created, prov(sid, mid), parts, completed, parent,
                             model, None, None, summary, finish, error)


def make_snapshot(*, generation: str = "v1", running: bool = False) -> SessionSnapshot:
    root = NormalizedSession("root", "Root", 900, 5000, prov("root", gen=generation), CAP)
    child = NormalizedSession("child", "Child", 1100, 1800, prov("child", gen=generation), CAP, "root")

    p_sub = part("p_sub", "u_sub", "root", "subtask", {"description": "inspect"}, 1000)
    tool = part("p_tool", "a_sub", "root", "tool", {
        "tool": "task",
        "state": {"time": {"start": 1150, "end": 1450}, "metadata": {"sessionId": "child"}},
    }, 1150)
    syn = part("p_syn", "u_syn", "root", "text", {
        "synthetic": True, "text": "Summarize the task tool output above and continue with your task."
    }, 1460)
    p_next = part("p_next", "u_next", "root", "text", {"text": "next", "synthetic": False}, 2000)
    p_comp = part("p_comp", "u_comp", "root", "compaction", {"auto": True}, 3000)
    child_user = part("p_child", "cu", "child", "text", {"text": "child work", "synthetic": False}, 1200)

    msgs = (
        message("u_sub", "root", MessageRole.USER, 1000, parts=(p_sub,)),
        message("a_sub", "root", MessageRole.ASSISTANT, 1100, parent="u_sub", parts=(tool,), completed=1500, model=MODEL, finish="tool-calls"),
        message("cu", "child", MessageRole.USER, 1200, parts=(child_user,)),
        message("ca", "child", MessageRole.ASSISTANT, 1230, parent="cu", completed=1400, model=MODEL, finish="stop"),
        message("u_syn", "root", MessageRole.USER, 1460, parts=(syn,)),
        message("a_syn", "root", MessageRole.ASSISTANT, 1500, parent="u_syn", completed=1700, model=MODEL, finish="stop"),
        message("u_next", "root", MessageRole.USER, 2000, parts=(p_next,)),
        message("a_next", "root", MessageRole.ASSISTANT, 2100, parent="u_next", completed=None if running else 2300, model=MODEL, finish=None if running else "stop"),
        message("u_comp", "root", MessageRole.USER, 3000, parts=(p_comp,)),
        message("a_comp", "root", MessageRole.ASSISTANT, 3100, parent="u_comp", completed=3300, model=MODEL, summary=True, finish="stop"),
    )
    events = (
        NormalizedEvent("u_sub", "root", EventKind.SUBTASK, 1000, prov("root", "u_sub", generation), "inspect", metadata={"provider_id":"github-copilot","model_id":"gpt-test"}),
        NormalizedEvent("cu", "child", EventKind.USER_PROMPT, 1200, prov("child", "cu", generation), "child work"),
        NormalizedEvent("u_syn", "root", EventKind.SYNTHETIC_CONTINUATION, 1460, prov("root", "u_syn", generation)),
        NormalizedEvent("u_next", "root", EventKind.USER_PROMPT, 2000, prov("root", "u_next", generation), "next", metadata={"provider_id":"github-copilot","model_id":"gpt-test"}),
        NormalizedEvent("u_comp", "root", EventKind.COMPACTION, 3000, prov("root", "u_comp", generation), metadata={"auto":"true"}),
    )
    inv = (
        ModelInvocation("i_wrapper", "root", 1100, MODEL, TokenUsage(), prov("root", "i_wrapper", generation), completed_at_ms=1500, cost=CostObservation(Decimal("0"), "USD", CostKind.PROVIDER_REPORTED), initiating_event_id="u_sub", message_id="a_sub"),
        ModelInvocation("i_child", "child", 1230, MODEL, TokenUsage(input=20, output=5), prov("child", "i_child", generation), completed_at_ms=1400, cost=CostObservation(Decimal("0.20"), "USD", CostKind.PROVIDER_REPORTED), initiating_event_id="cu", message_id="ca"),
        ModelInvocation("i_syn", "root", 1500, MODEL, TokenUsage(input=10, output=3), prov("root", "i_syn", generation), completed_at_ms=1700, cost=CostObservation(Decimal("0.10"), "USD", CostKind.PROVIDER_REPORTED), initiating_event_id="u_syn", message_id="a_syn"),
        ModelInvocation("i_next", "root", 2100, MODEL, TokenUsage(input=30, output=4), prov("root", "i_next", generation), completed_at_ms=None if running else 2300, cost=CostObservation(Decimal("0.30"), "USD", CostKind.PROVIDER_REPORTED), initiating_event_id="u_next", message_id="a_next"),
        ModelInvocation("i_comp", "root", 3100, MODEL, TokenUsage(input=40, cache_read=3, cache_write=2, output=4, reasoning=1), prov("root", "i_comp", generation), completed_at_ms=3300, cost=CostObservation(Decimal("0.40"), "USD", CostKind.PROVIDER_REPORTED), initiating_event_id="u_comp", message_id="a_comp", summary=True, finish_reason="stop"),
    )
    return SessionSnapshot(root, (root, child), msgs, tuple(p for m in msgs for p in m.parts), events, inv, f"{generation}-rev-1")


def make_native_v2_compaction_snapshot() -> SessionSnapshot:
    """Current V2 compaction is one durable message, not trigger + assistant summary."""
    snapshot = make_snapshot(generation="v2")
    compact_part = part("p_comp", "u_comp", "root", "compaction", {"auto": True, "summary": "x", "recent": None}, 1800)
    native_compaction = message("u_comp", "root", MessageRole.USER, 1800, parts=(compact_part,), completed=1800)
    messages = tuple(native_compaction if item.message_id == "u_comp" else item
                     for item in snapshot.messages if item.message_id != "a_comp")
    events = tuple(replace(item, created_at_ms=1800, metadata={**dict(item.metadata), "auto": "true"})
                   if item.event_id == "u_comp" else item for item in snapshot.events)
    invocations = tuple(item for item in snapshot.invocations if item.invocation_id != "i_comp")
    return replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts),
                   events=events, invocations=invocations, source_revision="v2-native-compaction")
