from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfoNotFoundError

from src.analysis.billing import actual_entry_cost, aggregate_trace_usage, billing_request_fingerprint
from src.analysis.cache import AnalysisDependencies, DerivedAnalysisCache, analyze_with_cache
from src.analysis.causal import build_prompt_records
from src.analysis.context import build_context_timeline
from src.analysis.compaction import completed_compactions
from src.analysis.core import analyze_snapshot, snapshot_is_stable
from src.analysis.models import TraceEntry
from src.analysis.timezones import local_date_range, local_report_range, resolve_timezone, utc_month_start_ms, workday_stats, TimezoneUnavailableError
from src.cache import CacheDatabase, CacheRepository
from src.pricing.catalog import PricingCatalog
from src.domain import (
    CostDisposition, CostKind, CostObservation, SessionSnapshot, TokenUsage,
)

from development.fixtures.session_snapshots import (
    CAP, MODEL, part, make_snapshot, make_native_v2_compaction_snapshot,
)


class BillingTests(unittest.TestCase):
    def test_stored_cost_zero_usage_and_estimated_fallback_are_distinct(self) -> None:
        base = TraceEntry("s", "p", "m", None, 1000, 0, MODEL, None, TokenUsage(input=100), Decimal("1.25"))
        self.assertEqual(Decimal("1.25"), actual_entry_cost(base, lambda *_: Decimal("9")).dollars)
        zero = replace(base, tokens=TokenUsage(), reported_cost=Decimal("0"))
        self.assertTrue(actual_entry_cost(zero).zero_usage)
        missing = replace(base, reported_cost=Decimal("0"))
        self.assertTrue(actual_entry_cost(missing).unresolved)
        estimated = actual_entry_cost(missing, lambda *_: Decimal("0.07"))
        self.assertTrue(estimated.estimated)
        self.assertEqual(Decimal("0.07"), estimated.dollars)
        included = replace(missing, cost_disposition=CostDisposition.INCLUDED_SUBSCRIPTION)
        self.assertEqual(Decimal("0"), actual_entry_cost(included, lambda *_: Decimal("9")).dollars)
        self.assertFalse(actual_entry_cost(included).fallback)

    def test_fingerprint_ignores_row_ids_and_deduplicates_only_cross_session(self) -> None:
        one = TraceEntry("a", "p1", "m1", "x", 1000, 0, MODEL, None, TokenUsage(input=10, output=2), Decimal("0.5"))
        clone = replace(one, session_id="b", parent_event_id="p2", message_id="m2", step_part_id="y", sort_order=4)
        self.assertEqual(billing_request_fingerprint(one), billing_request_fingerprint(clone))
        usage = aggregate_trace_usage((one, clone), since_ms=0, tracked_provider="github-copilot")
        self.assertEqual(1, usage.requests)
        self.assertEqual(1, usage.deduplicated_clone_requests)
        self.assertEqual(Decimal("0.5"), usage.dollars)
        same_session = aggregate_trace_usage((one, replace(clone, session_id="a")), since_ms=0, tracked_provider="github-copilot")
        self.assertEqual(2, same_session.requests)


class CausalAnalysisTests(unittest.TestCase):
    def test_subtask_synthetic_continuation_and_child_work_match_v77_shape(self) -> None:
        records = build_prompt_records(make_snapshot(), now_ms=4000)
        sub = next(record for record in records if record.prompt_id == "u_sub")
        self.assertEqual(3, sub.model_calls)
        self.assertEqual(Decimal("0.10"), sub.main_cost)
        self.assertEqual(Decimal("0.20"), sub.subagent_cost)
        self.assertEqual(Decimal("0.30"), sub.cost)
        self.assertTrue(sub.has_cost_breakdown)
        self.assertEqual(["a_sub", "a_syn", "ca"], [entry.message_id for entry in sub.entries])
        self.assertEqual(20, sub.input_context_tokens, "subtask should use first meaningful causal request")

    def test_completed_compaction_is_separate_billed_event(self) -> None:
        events = completed_compactions(make_snapshot())
        self.assertEqual(1, len(events))
        item = events[0]
        self.assertTrue(item.automatic)
        self.assertEqual(Decimal("0.40"), item.cost)
        self.assertEqual(45, item.input_context_tokens)
        self.assertEqual(50, item.input_tokens + item.cache_read_tokens + item.cache_write_tokens + item.output_tokens)

    def test_native_v2_compaction_is_visible_boundary_and_owns_context_shrink(self) -> None:
        snapshot = make_native_v2_compaction_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        self.assertEqual(1, len(bundle.compactions))
        compact = bundle.compactions[0]
        self.assertEqual("u_comp", compact.user_message_id)
        self.assertEqual("u_comp", compact.summary_message_id)
        self.assertEqual(0, compact.model_calls)
        timeline = build_context_timeline(snapshot, bundle, PricingCatalog(()))
        compact_state = next(item for item in timeline if item.event_kind == "compaction")
        next_state = next(item for item in timeline if item.event_id == "u_next")
        self.assertIsNotNone(compact_state.delta_tokens)
        self.assertLess(compact_state.delta_tokens, 0, "context shrink belongs on /compact")
        self.assertIsNotNone(next_state.delta_tokens)
        self.assertGreater(next_state.delta_tokens, 0, "following prompt must not inherit the compaction shrink")

    def test_equivalent_v1_v2_provenance_has_same_analysis_semantics(self) -> None:
        one = analyze_snapshot(make_snapshot(generation="v1"), now_ms=4000)
        two = analyze_snapshot(make_snapshot(generation="v2"), now_ms=4000)
        from dataclasses import asdict
        def semantic(value):
            if isinstance(value, dict):
                return {key: semantic(child) for key, child in value.items() if key not in {"source_instance", "source_revision"}}
            if isinstance(value, (list, tuple)):
                return tuple(semantic(child) for child in value)
            return value
        self.assertEqual(semantic(asdict(one)), semantic(asdict(two)))


    def test_zero_usage_completed_root_request_with_final_response_is_not_abort(self) -> None:
        snapshot = make_snapshot()
        # Replace the ordinary next request with a terminal zero-token/cost request.
        inv = tuple(
            replace(item, tokens=TokenUsage(), cost=CostObservation(Decimal("0"), "USD", CostKind.PROVIDER_REPORTED))
            if item.invocation_id == "i_next" else item
            for item in snapshot.invocations
        )
        modified = replace(snapshot, invocations=inv)
        record = next(item for item in build_prompt_records(modified, now_ms=4000) if item.prompt_id == "u_next")
        self.assertFalse(record.aborted)
        self.assertFalse(record.in_progress)
        self.assertEqual(Decimal("0"), record.cost)

    def test_running_snapshot_is_never_cacheable(self) -> None:
        bundle = analyze_snapshot(make_snapshot(running=True), now_ms=2200)
        self.assertFalse(bundle.cacheable)
        self.assertTrue(any(record.in_progress for record in bundle.prompts))
        self.assertFalse(snapshot_is_stable(make_snapshot(running=True)))

    def test_authoritative_active_session_and_running_tool_keep_prompt_live(self) -> None:
        snapshot = make_snapshot(running=False)
        running_tool = part("live-tool", "a_next", "root", "tool", {
            "name": "shell", "state": {"status": "running", "input": {"command": "long"}},
        }, 2400)
        messages = tuple(
            replace(item, parts=item.parts + (running_tool,)) if item.message_id == "a_next" else item
            for item in snapshot.messages
        )
        root = replace(snapshot.root, active=True, updated_at_ms=9000)
        snapshot = replace(
            snapshot, root=root, sessions=(root, snapshot.sessions[1]), messages=messages,
            parts=tuple(value for message_value in messages for value in message_value.parts),
        )
        record = next(item for item in build_prompt_records(snapshot, now_ms=10_000) if item.prompt_id == "u_next")
        self.assertTrue(record.in_progress)
        self.assertEqual(8_000, record.duration_ms)

        completed_tool = replace(
            running_tool, updated_at_ms=9_000,
            data={"name": "shell", "state": {"status": "completed", "input": {"command": "long"}}},
        )
        completed_messages = tuple(
            replace(item, parts=(completed_tool,)) if item.message_id == "a_next" else item
            for item in messages
        )
        inactive_root = replace(root, active=False)
        completed_snapshot = replace(
            snapshot, root=inactive_root, sessions=(inactive_root, snapshot.sessions[1]),
            messages=completed_messages,
            parts=tuple(value for message_value in completed_messages for value in message_value.parts),
        )
        completed = next(item for item in build_prompt_records(completed_snapshot, now_ms=20_000) if item.prompt_id == "u_next")
        self.assertFalse(completed.in_progress)
        self.assertEqual(7_000, completed.duration_ms)

    def test_native_v2_compaction_prefers_exact_usage_for_incoming_and_summary_context(self) -> None:
        snapshot = make_native_v2_compaction_snapshot()
        compaction_message = next(item for item in snapshot.messages if item.message_id == "u_comp")
        compact_part = replace(compaction_message.parts[0], data={
            "status": "completed", "summary": "short", "recent": "x" * 37_600,
            "tokens": {"input": 200_000, "output": 1_800, "reasoning": 0, "cache": {"read": 38_200, "write": 0}},
        })
        messages = tuple(
            replace(item, parts=(compact_part,)) if item.message_id == "u_comp" else item
            for item in snapshot.messages
        )
        snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts))
        bundle = analyze_snapshot(snapshot, now_ms=4000)
        record = bundle.compactions[0]
        self.assertEqual(238_200, record.input_context_tokens)
        self.assertEqual(11_200, record.result_context_tokens)


class FakeSource:
    source_id = "fake"
    capabilities = CAP

    def __init__(self, snapshot: SessionSnapshot):
        self.snapshot = snapshot
        self.load_count = 0
        self.revision_count = 0

    def probe(self): raise NotImplementedError
    def list_sessions(self, since_ms=None): return self.snapshot.sessions
    def get_session_tree_revision(self, session_id):
        self.revision_count += 1
        return self.snapshot.source_revision
    def load_session_snapshot(self, session_id):
        self.load_count += 1
        return self.snapshot


class DerivedCacheTests(unittest.TestCase):
    def test_pre_abort_fix_algorithm_cache_is_rebuilt_without_source_revision_change(self) -> None:
        snapshot = make_snapshot()
        old_snapshot = replace(snapshot, messages=tuple(
            replace(m, error_name="dict") if m.message_id == "a_next" else m
            for m in snapshot.messages))
        fixed_snapshot = replace(snapshot, messages=tuple(
            replace(m, error_name="AbortedError") if m.message_id == "a_next" else m
            for m in snapshot.messages))
        source = FakeSource(old_snapshot)
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize()
            cache = DerivedAnalysisCache(CacheRepository(db))
            old = analyze_with_cache(source, snapshot.root, cache,
                                     AnalysisDependencies("cfg", "price", "v78-analysis-3"),
                                     lambda snap: analyze_snapshot(snap, now_ms=4000))
            self.assertTrue(next(p for p in old.bundle.prompts if p.prompt_id == "u_next").watch_error)
            source.snapshot = fixed_snapshot
            fixed = analyze_with_cache(source, snapshot.root, cache, AnalysisDependencies("cfg", "price"),
                                       lambda snap: analyze_snapshot(snap, now_ms=4000))
            self.assertFalse(fixed.cache_hit)
            self.assertEqual(2, source.load_count)
            prompt = next(p for p in fixed.bundle.prompts if p.prompt_id == "u_next")
            self.assertTrue(prompt.aborted)
            self.assertFalse(prompt.watch_error)

    def test_cache_hit_miss_dependency_invalidation_and_delete_rebuild(self) -> None:
        snapshot = make_snapshot()
        source = FakeSource(snapshot)
        deps = AnalysisDependencies("cfg-a", "price-a")
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize()
            cache = DerivedAnalysisCache(CacheRepository(db))
            first = analyze_with_cache(source, snapshot.root, cache, deps, lambda snap: analyze_snapshot(snap, now_ms=4000))
            self.assertFalse(first.cache_hit); self.assertEqual(1, source.load_count)
            second = analyze_with_cache(source, snapshot.root, cache, deps, lambda snap: analyze_snapshot(snap, now_ms=4000))
            self.assertTrue(second.cache_hit); self.assertEqual(1, source.load_count)
            self.assertEqual(first.bundle, second.bundle)
            changed_deps = AnalysisDependencies("cfg-b", "price-a")
            third = analyze_with_cache(source, snapshot.root, cache, changed_deps, lambda snap: analyze_snapshot(snap, now_ms=4000))
            self.assertFalse(third.cache_hit); self.assertEqual(2, source.load_count)
            db.paths.database.unlink()
            rebuilt = CacheDatabase(Path(td)); rebuilt.initialize()
            fourth = analyze_with_cache(source, snapshot.root, DerivedAnalysisCache(CacheRepository(rebuilt)), deps, lambda snap: analyze_snapshot(snap, now_ms=4000))
            self.assertFalse(fourth.cache_hit)
            self.assertEqual(first.bundle, fourth.bundle)


    def test_source_revision_change_invalidates_reuse(self) -> None:
        snapshot = make_snapshot()
        source = FakeSource(snapshot)
        deps = AnalysisDependencies("cfg", "price")
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize()
            cache = DerivedAnalysisCache(CacheRepository(db))
            analyze_with_cache(source, snapshot.root, cache, deps, lambda snap: analyze_snapshot(snap, now_ms=4000))
            source.snapshot = replace(snapshot, source_revision="v1-rev-2")
            second = analyze_with_cache(source, snapshot.root, cache, deps, lambda snap: analyze_snapshot(snap, now_ms=4000))
            self.assertFalse(second.cache_hit)
            self.assertEqual(2, source.load_count)

    def test_malformed_cached_json_is_a_miss_not_a_crash(self) -> None:
        snapshot = make_snapshot()
        source = FakeSource(snapshot)
        deps = AnalysisDependencies("cfg", "price")
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize()
            repo = CacheRepository(db)
            cache = DerivedAnalysisCache(repo)
            analyze_with_cache(source, snapshot.root, cache, deps, lambda snap: analyze_snapshot(snap, now_ms=4000))
            with db.connect() as connection:
                connection.execute("UPDATE cache_entries SET payload_json='not-json' WHERE namespace='derived-analysis'")
            second = analyze_with_cache(source, snapshot.root, cache, deps, lambda snap: analyze_snapshot(snap, now_ms=4000))
            self.assertFalse(second.cache_hit)
            self.assertEqual(2, source.load_count)

    def test_running_bundle_is_not_persisted(self) -> None:
        snapshot = make_snapshot(running=True)
        source = FakeSource(snapshot)
        with tempfile.TemporaryDirectory() as td:
            db = CacheDatabase(Path(td)); db.initialize()
            cache = DerivedAnalysisCache(CacheRepository(db))
            deps = AnalysisDependencies("cfg", "price")
            analyze_with_cache(source, snapshot.root, cache, deps, lambda snap: analyze_snapshot(snap, now_ms=2200))
            analyze_with_cache(source, snapshot.root, cache, deps, lambda snap: analyze_snapshot(snap, now_ms=2200))
            self.assertEqual(2, source.load_count)


class TimezoneTests(unittest.TestCase):
    def test_stockholm_day_boundaries_cover_dst_23_and_25_hour_days(self) -> None:
        spring = local_date_range("2026-03-29", "Europe/Stockholm")
        autumn = local_date_range("2026-10-25", "Europe/Stockholm")
        self.assertEqual(23 * 3600 * 1000, spring.end_ms - spring.start_ms)
        self.assertEqual(25 * 3600 * 1000, autumn.end_ms - autumn.start_ms)
        range_value = local_report_range("2026-03-28:2026-03-29", "Europe/Stockholm")
        self.assertEqual(47 * 3600 * 1000, range_value.end_ms - range_value.start_ms)

    def test_stockholm_fallback_works_when_host_has_no_iana_database(self) -> None:
        with mock.patch("src.analysis.timezones.ZoneInfo", side_effect=ZoneInfoNotFoundError("missing")):
            tz = resolve_timezone("Europe/Stockholm")
            self.assertIsNotNone(tz)
            value = local_date_range("2026-03-29", "Europe/Stockholm")
            self.assertEqual(23 * 3600 * 1000, value.end_ms - value.start_ms)


    def test_non_default_zone_fails_actionably_when_host_has_no_iana_database(self) -> None:
        with mock.patch("src.analysis.timezones.ZoneInfo", side_effect=ZoneInfoNotFoundError("missing")):
            with self.assertRaises(TimezoneUnavailableError):
                resolve_timezone("America/New_York")

    def test_swedish_workday_stats_match_calendar_rules(self) -> None:
        # 2026-06-05 12:00 UTC: Friday before National Day (Saturday).
        now = 1780660800000
        stats = workday_stats("Europe/Stockholm", "SE", now_ms=now)
        self.assertTrue(stats.today_is_workday)
        self.assertGreater(stats.total, 0)
        self.assertGreaterEqual(stats.remaining_including_today, 1)

    def test_utc_month_start_matches_v77_utc_billing_boundary(self) -> None:
        # 2026-09-27T00:00Z
        now = 1790467200000
        self.assertEqual(1788220800000, utc_month_start_ms(now_ms=now))


if __name__ == "__main__":
    unittest.main()
