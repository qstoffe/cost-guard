"""Canonical synthetic price/usage snapshots for real CCost-help browser interactions."""
from dataclasses import replace
import time

from src.analysis import analyze_snapshot
from src.analysis.daily_usage import DailyUsage
from src.analysis.session_cost import SessionCost
from src.analysis.token_mix import priced_token_mix
from src.analysis.valuation import comparison_cost
from src.application.live_projection import project_live
from src.application.projection import project
from src.domain import ModelRef, TokenUsage
from src.reports.models import ReportKind, ReportProjection, SessionUsageRow
from src.reports.prompt_rows import PromptRowProjector
from src.reports.prompts import build_prompt_block
from src.watch.models import WatchRow
from .pricing_catalog import catalog
from .session_snapshots import make_uncompacted_snapshot


def unavailable_frames(frame):
    result = {}
    now = int(time.time() * 1000)
    for mode in ("absent", "identity", "rate", "usage", "catalog", "mixed", "known", "zero", "pending", "prompt-only", "session-only"):
        prices = replace(catalog(), retrieved_at_ms=now, source_revision="synthetic-acquired-list",
                         reference_stale=mode == "catalog")
        if mode == "rate":
            model = prices.models[0]
            prices = replace(prices, models=(replace(model, tiers=(replace(model.tiers[0], per_million_output=None),)),))
        source = make_uncompacted_snapshot()
        requests = []
        for item in source.invocations:
            name = "sonnet" if mode == "identity" else "gpt-test" if mode in {"known", "rate", "session-only"} or mode == "mixed" and item.session_id == "root" or mode == "prompt-only" and item.invocation_id == "i_next" else "claude-sonnet-4"
            tokens = TokenUsage() if mode == "zero" else TokenUsage(input=100, known_fields=("input",)) if mode == "usage" else item.tokens
            requests.append(replace(item, model=ModelRef("github-copilot", name), tokens=tokens))
        snapshot = replace(source, invocations=tuple(requests))
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        record = next(item for item in bundle.prompts if item.prompt_id == "u_sub")
        row = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=prices,
            config={}, snapshot_running_metrics=True).prompt(record)
        total = comparison_cost(bundle.trace_entries, prices.reference_valuation, diagnose=prices.reference_issue)
        base = frame.active_cards[0]
        card = replace(base, rows=(WatchRow(base.session_id, base.title, row),), focal_id=row.event_id,
            session_id=base.session_id + ("-pending" if mode == "pending" else ""),
            session_cost=None if mode in {"pending", "session-only"} else SessionCost(total, True, True),
            session_cost_state="loading" if mode == "pending" else "unavailable" if mode == "session-only" else "observed")
        mix = priced_token_mix(((entry.model, entry.tokens) for entry in bundle.trace_entries), prices.reference_category_valuation)
        value = replace(frame, now_ms=now, active_cards=(card,), history_cards=(replace(card, focal_id=""),),
            history_state="observed", daily_usage=DailyUsage(frame.daily_usage.day_start_ms, now, total, mix, 2, True))
        result[mode] = project_live(value).to_json()
        summary = SessionUsageRow(base.session_id, "Synthetic unavailable session", "Claude Sonnet 4", False,
            total.known_ccost, 2, total.complete, ccost_unavailable=total.unavailable)
        result[mode]["probe_sessions"] = project(ReportProjection(ReportKind.SESSIONS, "Sessions", "Synthetic", (),
            session_usage=(summary,))).to_json()["session_usage"]
        for item in result[mode]["probe_sessions"]:
            item.update(indexed=True, has_summary=True, metric_state="ready")
        block = build_prompt_block(session_id=snapshot.root.session_id, title="Synthetic unavailable session",
            bundle=bundle, snapshot=snapshot, catalog=prices, config={})
        detail = project(ReportProjection(ReportKind.SESSION, "Session", "Synthetic", (),
            prompt_blocks=(block,)), prompt_details=True).to_json()
        for prompt in detail["prompt_blocks"][0]["rows"]:
            prompt["id"] = prompt["event_id"]
        result[mode]["probe_detail"] = detail
    return result
