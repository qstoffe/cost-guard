"""Read-only accounting parity for one explicitly authorized native root, no UI/inference."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.analysis.session_cost import reconcile_session_cost
from src.analysis.valuation import unique_usage
from src.application.live_projection import project_live
from src.application.projection import block as export_block
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportKind, ReportRequest
from src.reports.prompts import build_prompt_block
from src.reports.sampling import AnalyzedRoot
from src.watch.models import WatchCard, WatchProjection, WatchRow
from src.web.composition import application


def identity(value):
    return value.session_id, value.invocation_id, value.message_id, value.step_part_id


def run(root_id, output):
    started = time.monotonic()
    request = ReportRequest(ReportKind.SESSION, root_id)
    service = application(request)._factory(int(time.time() * 1000), lambda _label: None)
    try:
        # Check metadata before hydration; never follow a supplied child's ancestor.
        root = next(session for session in service.source.list_sessions() if session.session_id == root_id)
        assert root.parent_session_id is None, "probe_requires_explicit_root"
        snapshot = service.source.load_session_snapshot(root_id)
        assert snapshot.complete and snapshot.root.session_id == root_id, "probe_incomplete_or_foreign_root"
        acquired = time.monotonic()
        prices = service._load_comparison_catalog()
        service.now_ms = int(time.time() * 1000)  # Never exclude requests acquired after service creation.
        bundle = service._analyze_snapshot(snapshot)
        requests = {identity(value): value for value in snapshot.invocations}
        assert len(requests) == len(snapshot.invocations), "probe_duplicate_source_identity"
        entries = unique_usage(bundle.trace_entries)
        assert {identity(value) for value in entries} == set(requests), "probe_request_population_mismatch"
        fields = {"input", "cache_read", "cache_write", "output"}
        amounts = {key: (Decimal(0) if fields <= set(value.tokens.known_fields) and not value.tokens.total
            else prices.reference_valuation(value.model, value.tokens)) for key, value in requests.items()}
        total = sum((value for value in amounts.values() if value is not None), Decimal(0))
        main = sum((amounts[key] or Decimal(0) for key in requests if key[0] == root_id), Decimal(0))
        block = build_prompt_block(session_id=root_id, title="", bundle=bundle, snapshot=snapshot,
            catalog=prices, config=service.config, threshold_multiplier=None, snapshot_running_metrics=True)
        item = AnalyzedRoot(snapshot.root, bundle, False, snapshot)
        row = service._session_rows((item,), catalog_models=True)[0]
        assert (block.total_ccost, block.total_calls) == (total, len(requests))
        assert (row.ccost, row.main_ccost, row.subagent_ccost) == (total, main, total - main)
        assigned = Counter(identity(entry) for record in (*bundle.prompts, *bundle.compactions)
            for entry in record.entries)
        assert all(count == 1 for count in assigned.values()) and set(assigned) <= set(requests)
        other = set(requests) - assigned.keys()
        assert block.other_calls == len(other)
        assert block.other_ccost == sum((amounts[key] or Decimal(0) for key in other), Decimal(0))
        assert sum((value.ccost for value in block.rows), block.other_ccost) == total
        with tempfile.TemporaryDirectory(dir=output.parent) as directory:
            database = CacheDatabase(Path(directory)); database.initialize()
            cold = reconcile_session_cost(CacheRepository(database), snapshot, prices)
            warm = reconcile_session_cost(CacheRepository(CacheDatabase(Path(directory))), snapshot, prices)
            assert (cold.total.known_ccost, cold.main_ccost, cold.subagent_ccost) == (total, main, total - main)
            assert (warm.total, warm.source_complete) == (cold.total, cold.source_complete)
            assert warm.valued_requests == 0 and not warm.cache_written
        assert row.complete == (cold.total.complete and cold.source_complete)
        assert block.comparison_cost_complete == row.complete
        exported = export_block(block, details=True).to_json()
        assert Decimal(exported["total_ccost"]) == total
        card = WatchCard(root_id, "", "", tuple(WatchRow(root_id, "", value) for value in block.rows),
            "observed", session_cost=cold, session_cost_state="observed")
        live = project_live(WatchProjection("Watch", "", (), now_ms=service.now_ms,
            active_cards=(card,), history_cards=(card,))).to_json()
        for lane in ("active_cards", "history_cards"):
            cost = live[lane][0]["session_summary"]["cost"]
            assert Decimal(cost["known_ccost"]) == total
            assert (Decimal(cost["main_ccost"]), Decimal(cost["subagent_ccost"])) == (main, total - main)
        parents = {value.session_id: value.parent_session_id for value in snapshot.sessions}
        depth = 0
        for child in parents:
            seen = set()
            while parents.get(child) and child not in seen:
                seen.add(child); child = parents[child]
            depth = max(depth, len(seen))
        result = dict(outcome="PASS", source=service.selection.selected, complete_snapshot=True,
            requests=len(requests), sessions=len(snapshot.sessions), descendant_depth=depth,
            known_ccost=str(total), main_ccost=str(main), subagent_ccost=str(total - main),
            cost_complete=row.complete, coverage_states=dict(Counter(
                agent.state for prompt in bundle.prompts for agent in prompt.agent_coverage)),
            independent_population_and_decimal_parity=True, ownership_reconciles=True,
            sessions_row_and_detail_parity=True, controlled_full_mini_projection_parity=True,
            cold_valuations=cold.valued_requests, warm_valuations=warm.valued_requests,
            acquisition_seconds=round(acquired - started, 3), elapsed_seconds=round(time.monotonic() - started, 3),
            model_calls_started_by_probe=0,
            limitations=["One authorized task root, not the owner's private incident.",
                "Controlled projections, not observed native Earlier publication or rendered interaction.",
                "Live activity and incomplete telemetry are retained, not falsified for cache eligibility."])
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
    finally:
        service.close_accounts()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.session_id, args.output)
