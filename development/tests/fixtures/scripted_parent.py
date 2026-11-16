"""Native V2-shaped local fixture and child attempt, never a live model call."""
from dataclasses import replace
from decimal import Decimal

from .session_snapshots import make_snapshot
from src.domain import EventKind, NormalizedEvent
from src.sources.opencode_v2_normalization import normalize_message_bundle, normalize_invocations
from src.domain import ModelPricing, ModelRef
from src.pricing.catalog import PricingCatalog
from src.sources.opencode_v2_model_identity import DesktopModelCatalog


def catalog():
    return PricingCatalog(tuple(ModelPricing(ModelRef(provider, model, label), "USD",
        Decimal(rate), Decimal(rate), Decimal(rate), Decimal(rate))
        for provider, model, label, rate in (("fixture", "scripted", "Scripted", "0"),
                                           ("claude-agent", "claude-opus-5-5", "Opus 5.5", "5"))),
        retrieved_at_ms=1, source_revision="scripted-qualified-catalog")


class FixtureCatalog:
    def json(self, route, **_kwargs):
        return dict(location={"directory": "/scripted"}, data=[{"id": "claude-agent"}] if route == "/api/provider"
            else [dict(providerID="claude-agent", id="opus", name="Opus 5.5", modelID="claude-opus-5-5")])


def scripted_parent(*, start=2000, child_state="unknown", selection=True, complete=True, finished=False):
    base = make_snapshot(generation="v2")
    root = replace(base.root, title="Scripted parent", created_at_ms=start - 100,
        updated_at_ms=start + 900_000, active=False)
    child = replace(base.sessions[1], created_at_ms=start + 20, updated_at_ms=start + 900_000,
        active=False if child_state == "not-executed" else None)
    provenance = lambda sid, eid=None: replace(root.provenance, source_session_id=sid, source_event_id=eid)
    raw = [
        dict(info=dict(id="u", sessionID="root", role="user", time={"created": start},
            model={"providerID": "fixture", "modelID": "scripted", "variant": "default"}), parts=[]),
        dict(info=dict(id="a", sessionID="root", role="assistant", parentID="u",
            providerID="fixture", modelID="scripted", variant="default",
            time={"created": start + 10, "completed": start + 120_030},
            finish="stop" if finished else "tool-calls", cost=0,
            tokens={"input": 0, "output": 0, "reasoning": 0, "cache": {"read": 0, "write": 0}}),
            parts=[dict(id="tool", messageID="a", sessionID="root", type="tool",
                tool="subagent", callID="call-proof", state=dict(status="error",
                    time={"start": start + 20, "end": start + 120_020},
                    metadata={"sessionID": "child"}, error="Tool deadline exceeded"))]),
        dict(info=dict(id="cu", sessionID="child", role="user", time={"created": start + 20},
            **({"model": dict(providerID="claude-agent", modelID="opus", variant="max")} if selection else {})), parts=[]),
    ]
    if child_state in {"positive", "zero", "failed"}:
        info = dict(id="ca", sessionID="child", parentID="cu", role="assistant",
            time={"created": start + 30, "completed": start + 100},
            providerID="claude-agent", modelID="opus", variant="max", finish="stop")
        if child_state == "failed":
            info["error"] = {"name": "ProviderError"}
        else:
            info.update(cost=0.2 if child_state == "positive" else 0,
                tokens=dict(input=100 if child_state == "positive" else 0, output=0, reasoning=0,
                    cache={"read": 0, "write": 0}))
        raw.append(dict(info=info, parts=[]))
    resolver = DesktopModelCatalog(lambda: FixtureCatalog())
    messages = tuple(replace(message, model=resolver.resolve(message.model, "/scripted"))
        for value in raw for message in (normalize_message_bundle(value, provenance)[0],))
    events = (
        NormalizedEvent("u", "root", EventKind.USER_PROMPT, start, provenance("root", "u"), "Scripted launch",
            metadata=dict(provider_id="fixture", model_id="scripted", variant="default")),
        NormalizedEvent("cu", "child", EventKind.USER_PROMPT, start + 20, provenance("child", "cu"), "Child attempt",
            metadata=dict(provider_id="claude-agent", model_id="opus", variant="max") if selection else {}),
    )
    return replace(base, root=root, sessions=(root, child), messages=messages,
        parts=tuple(part for message in messages for part in message.parts), events=events,
        invocations=tuple(inv for message in messages for inv in normalize_invocations(message, provenance)),
        complete=complete, source_revision=f"scripted-{start}-{child_state}-{selection}-{complete}-{finished}")
