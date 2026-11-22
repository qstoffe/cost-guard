"""Synthetic per-route/request evidence, projected through real report owners."""
from dataclasses import replace

from development.tests.fixtures.claude_alias import snapshot, service, catalog
from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot
from src.analysis import analyze_snapshot
from src.application.display import with_display
from src.application.projection import prompt, project
from src.domain import ModelRef
from src.reports import ReportKind, ReportRequest
from src.reports.prompt_rows import PromptRowProjector
from src.sources.opencode_v2_effort import observation


def capture(test):
    saved = []
    for index in range(5):
        model = ModelRef("anthropic", "claude-sonnet-5-5")
        if index == 1:
            model = replace(model, effort_default=observation("/synthetic", model.model, {},
                {"modelID": model.model, "package": "@opencode/ai/providers/anthropic", "settings": {"effort": "low"}}))
        if index == 3:
            model = ModelRef("unknown", "unpriced-model")
        value = snapshot(index, model.model, model.provider)
        variant = "high" if index in (2, 4) else "default"
        value = replace(value,
            events=tuple(replace(e, metadata={**e.metadata, "model_id": model.model, "provider_id": model.provider,
                "variant": "high" if index == 4 else "default"}) for e in value.events),
            messages=tuple(replace(m, model=model, variant=variant) if m.role.value == "assistant" else m
                           for m in value.messages),
            invocations=tuple(replace(i, model=model, variant=variant) for i in value.invocations))
        saved.append(value)
    reports = service(test, snapshots=saved)
    views = {kind.value: project(reports.build(ReportRequest(kind,
        **({"session_id": "root-0000"} if kind is ReportKind.SESSION else {}))), prompt_details=True).to_json()
        for kind in (ReportKind.SESSIONS, ReportKind.SESSION, ReportKind.COMPARISONS, ReportKind.AI_STATS)}
    rows = []
    for value in saved:
        bundle = analyze_snapshot(value, tracked_provider=None)
        row = PromptRowProjector(snapshot=value, bundle=bundle, catalog=catalog(), config={}).prompt(bundle.prompts[0])
        rows.append(with_display(prompt(row, details=True)).to_json())
    mixed = make_uncompacted_snapshot()
    models = {sid: ModelRef("anthropic", name) for sid, name in
        (("root", "claude-sonnet-5-5"), ("child", "claude-opus-5-5"))}
    mixed = replace(mixed,
        events=tuple(replace(e, metadata={**e.metadata, "provider_id": "anthropic",
            "model_id": models[e.session_id].model, "variant": "default"}) for e in mixed.events),
        invocations=tuple(replace(i, model=models[i.session_id], variant="default") for i in mixed.invocations))
    bundle = analyze_snapshot(mixed, tracked_provider=None)
    record = next(p for p in bundle.prompts if p.prompt_id == "u_sub")
    row = PromptRowProjector(snapshot=mixed, bundle=bundle, catalog=catalog(), config={}).prompt(record)
    return dict(browser_rows=rows, synthetic_views=views,
                mixed_prompt=with_display(prompt(row, details=True)).to_json())
