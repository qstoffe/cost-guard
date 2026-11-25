"""Synthetic canonical model switches/child ancestry for rendered catalog probes."""
from dataclasses import replace
from .synthetic_month import make_root_snapshot
from src.domain import ModelRef

MODELS_DAY_START = 1_794_528_000_000  # 2026-11-13 00:00 UTC


def models_source(source, *, updated=False):
    values = {}
    for index in range(30):
        snapshot = make_root_snapshot(index, 5 if index == 0 else 2, month_start_ms=MODELS_DAY_START)
        main = f"Model-{index:02}"
        if index == 4:
            main += "-" + "long-model-name-" * 12
        requests = tuple(replace(request, model=ModelRef("main-provider", main if number else "Earlier"),
            variant="high") for number, request in enumerate(snapshot.invocations))
        if index == 0:
            requests = tuple(replace(request, variant=effort) for request, effort in
                             zip(requests, ("high", "high", None, "low", "high"), strict=True))
        sessions = (snapshot.root,)
        if index in (0, 2, 3):
            child = replace(snapshot.root, session_id=f"child-{index}", parent_session_id=snapshot.root.session_id)
            sessions += (child,)
            requests += (replace(requests[-1], session_id=child.session_id, message_id=f"child-response-{index}",
                invocation_id=f"child-call-{index}", completed_at_ms=requests[-1].completed_at_ms + 20,
                model=ModelRef("child-provider", "Child-new" if updated else "Child")),)
        if index == 1:
            requests = tuple(replace(request, model=ModelRef("main-provider", main)) for request in requests)
        if index == 2:
            requests = tuple(replace(request, model=ModelRef("main-provider", main)) for request in requests)
        if index == 3:
            requests = tuple(request for request in requests if request.session_id != snapshot.root.session_id)
        values[snapshot.root.session_id] = replace(snapshot, sessions=sessions, invocations=requests,
            source_revision=f"models-{index}-{updated}", complete=True)
    source.snapshots = values


def model_fixture_prices(base, source):
    models = {request.model.model: request.model for snapshot in source.snapshots.values()
              for request in snapshot.invocations}
    prices = tuple(replace(base.models[0], model=model) for model in models.values())
    return replace(base, models=base.models + prices, source_revision="sessions-model-fixture-prices")
