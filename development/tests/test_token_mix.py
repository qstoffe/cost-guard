"""Volume, availability, latest-prompt window and process-lifetime mix regressions."""
from __future__ import annotations

from dataclasses import replace
import io
import tempfile
import unittest
from unittest.mock import patch

from development.fixtures.synthetic_month import SyntheticMonthSource
from development.fixtures.session_snapshots import make_snapshot
from src.reports.sampling import latest_token_prompts
from development.tests import test_compact_reports as compact_fixtures
from development.tests.test_compact_reports import START, rendered
from development.tests.test_quota_presentation import quotas, rolling
from development.fixtures.watch_runtime import MutableSource, make_service
from src.analysis import analyze_snapshot
from src.analysis.cache import AnalysisDependencies, _bundle_from_dict, _bundle_to_dict
from src.analysis.token_mix import token_mix
from src.cli import help_text
from src.domain import TokenUsage, TerminalEvidence, TerminalOutcome
from src.presentation import WatchRenderer
from src.presentation.accounts import capacity_lines
from src.presentation.terminal import AnsiStyler
from src.presentation.token_mix import token_mix_line
from src.reports import ReportKind, ReportProjection, ReportRequest, ReportService
from src.sources.opencode_v1 import _token_usage as v1_usage
from src.sources.opencode_v2_normalization import normalize_token_usage as v2_usage
from src.watch import WatchCoordinator
from src.watch.models import WatchProjection
from src.watch.token_mix import WatchTokenMix


def one_request(*, running=True, usage=None):
    snapshot = make_snapshot(running=running)
    invocation = next(i for i in snapshot.invocations if i.invocation_id == "i_next")
    if usage is not None:
        invocation = replace(invocation, tokens=usage)
    messages = tuple(replace(m, tokens=invocation.tokens) if m.message_id == "a_next" else m
                     for m in snapshot.messages if m.message_id in {"u_next", "a_next"})
    return replace(snapshot, sessions=(snapshot.root,), messages=messages,
                   parts=tuple(p for m in messages for p in m.parts),
                   events=tuple(e for e in snapshot.events if e.event_id == "u_next"),
                   invocations=(invocation,))


def observe(tracker, snapshot):
    tracker.observe(snapshot, analyze_snapshot(snapshot, now_ms=4000))
    return tracker.project()


class TokenMixCalculationTests(unittest.TestCase):
    def test_raw_volume_not_average_of_percentages(self):
        mix = token_mix((TokenUsage(input=1), TokenUsage(cache_read=99)))
        self.assertEqual((1, 99, 0, 0), mix.totals)
        self.assertEqual((1, 99, 0, 0), mix.percentages)

    def test_clean_rounding_sums_to_100_and_is_stable(self):
        for counts, expected in (((1, 1, 1, 0), (34, 33, 33, 0)),
                                 ((1, 1, 1, 1), (25, 25, 25, 25)),
                                 ((99999, 1, 0, 0), (100, 0, 0, 0)),
                                 ((9, 85, 1, 5), (9, 85, 1, 5))):
            mix = token_mix((TokenUsage(*counts),))
            self.assertEqual(expected, mix.percentages)
            self.assertEqual(100, sum(mix.percentages))

    def test_reasoning_is_folded_into_output_once(self):
        self.assertEqual((20, 0, 0, 80), token_mix((TokenUsage(input=2, output=5, reasoning=3),)).percentages)

    def test_known_zero_unknown_and_empty_are_distinct(self):
        known = token_mix((TokenUsage(input=100),))
        self.assertEqual((100, 0, 0, 0), known.percentages)
        unknown = token_mix((TokenUsage(input=100, known_fields=("input", "cache_read", "output")),))
        self.assertEqual((100, 0, None, 0), unknown.totals)
        self.assertEqual((None,) * 4, unknown.percentages, "unknown denominator cannot yield reliable shares")
        self.assertEqual((None,) * 4, token_mix(()).totals)
        self.assertEqual((0,) * 4, token_mix((TokenUsage(),)).totals)
        self.assertEqual((None,) * 4, token_mix((TokenUsage(),)).percentages)

    def test_mixed_incomplete_providers_do_not_hide_unknown_usage(self):
        mix = token_mix((TokenUsage(cache_write=80),
                         TokenUsage(input=20, known_fields=("input", "cache_read", "output"))))
        self.assertIsNone(mix.totals[2])
        self.assertEqual((None,) * 4, mix.percentages)

    def test_v1_v2_normalization_explicit_zero_absent_null_and_malformed(self):
        for normalize in (v1_usage, v2_usage):
            with self.subTest(normalize=normalize):
                complete = normalize({"input": 10, "output": 5, "cache": {"read": 0, "write": 0}}, context="test")
                self.assertEqual({"input", "cache_read", "cache_write", "output"}, set(complete.known_fields))
                for write in (None, "invalid", True, 1.5):
                    usage = normalize({"input": 10, "output": 5, "cache": {"read": 0, "write": write}}, context="test")
                    self.assertNotIn("cache_write", usage.known_fields)
                missing = normalize({"input": 10, "output": 5}, context="test")
                self.assertEqual(("input", "output"), missing.known_fields)
                self.assertEqual((), normalize({}, context="test").known_fields)
                self.assertIsNone(normalize(None, context="test"))

    def test_derived_cache_roundtrip_retains_availability(self):
        usage = TokenUsage(input=8, output=2, known_fields=("input", "output"))
        bundle = analyze_snapshot(one_request(running=False, usage=usage), now_ms=4000)
        restored = _bundle_from_dict(_bundle_to_dict(bundle, AnalysisDependencies("c", "p")))
        self.assertEqual(bundle, restored)
        self.assertEqual((None,) * 4, token_mix(e.tokens for e in restored.prompts[0].entries).percentages)


class WatchTokenMixTests(unittest.TestCase):
    def test_start_empty_exclude_completed_history_even_in_session_scope(self):
        tracker = WatchTokenMix(4000)
        self.assertEqual((None,) * 4, tracker.project().totals)
        self.assertEqual((None,) * 4, observe(tracker, one_request(running=False)).totals)

    def test_already_running_request_is_included_not_old_requests_in_same_prompt(self):
        tracker = WatchTokenMix(2200)
        snapshot = one_request(usage=TokenUsage(input=9, cache_read=85, cache_write=1, output=5))
        historical = replace(snapshot.invocations[0], invocation_id="old", message_id="old",
                             created_at_ms=2050, completed_at_ms=2090, tokens=TokenUsage(input=9999))
        mix = observe(tracker, replace(snapshot, invocations=(historical, *snapshot.invocations)))
        self.assertEqual((9, 85, 1, 5), mix.totals)

    def test_request_completes_between_polls_and_before_first_hydration(self):
        tracker = WatchTokenMix(2200)
        self.assertEqual((30, 0, 0, 4), observe(tracker, one_request(running=False)).totals)

    def test_refresh_is_idempotent_counts_updated_raw_usage_once(self):
        tracker = WatchTokenMix(2200)
        snapshot = one_request()
        first = observe(tracker, snapshot)
        self.assertEqual(first, observe(tracker, snapshot))
        updated = replace(snapshot, invocations=(replace(snapshot.invocations[0], tokens=TokenUsage(input=30, cache_read=50, output=20)),))
        self.assertEqual((30, 50, 0, 20), observe(tracker, updated).totals)
        self.assertEqual((30, 50, 0, 20), observe(tracker, replace(updated, invocations=())).totals)

    def test_completed_disappeared_and_restarted_lifetime(self):
        tracker = WatchTokenMix(2200)
        snapshot = one_request()
        observe(tracker, snapshot)
        final = one_request(running=False, usage=TokenUsage(input=30, output=10))
        expected = observe(tracker, final)
        self.assertEqual(expected, observe(tracker, replace(final, invocations=())))
        self.assertEqual((None,) * 4, observe(WatchTokenMix(4000), final).totals)

    def test_countdown_and_identical_observations_do_not_rescan_run_history(self):
        tracker = WatchTokenMix(2200)
        snapshot = one_request()
        expected = observe(tracker, snapshot)
        with patch("src.watch.token_mix.token_mix", side_effect=AssertionError("unneeded history scan")):
            self.assertEqual(expected, tracker.project())
            self.assertEqual(expected, observe(tracker, snapshot))

    def test_incomplete_refresh_preserves_known_fields_then_resolves_unknown(self):
        tracker = WatchTokenMix(2200)
        snapshot = one_request(usage=TokenUsage(input=10, known_fields=("input",)))
        self.assertEqual((None,) * 4, observe(tracker, snapshot).percentages)
        complete = one_request(usage=TokenUsage(input=10, cache_read=80, cache_write=0, output=10))
        expected = observe(tracker, complete)
        missing = one_request(usage=TokenUsage(known_fields=()))
        self.assertEqual(expected, observe(tracker, missing))

    def test_message_to_steps_replaces_cumulative_fallback_not_adds_it(self):
        tracker = WatchTokenMix(2200)
        snapshot = one_request(usage=TokenUsage(input=10, output=10))
        observe(tracker, snapshot)
        invocation = snapshot.invocations[0]
        steps = (replace(invocation, invocation_id="one", step_part_id="one", tokens=TokenUsage(input=10)),
                 replace(invocation, invocation_id="two", step_part_id="two", tokens=TokenUsage(output=10)))
        expected = observe(tracker, replace(snapshot, invocations=steps))
        self.assertEqual((10, 0, 0, 10), expected.totals)
        self.assertEqual(expected, observe(tracker, snapshot), "do not reinstate cumulative fallback")
        self.assertEqual(expected, observe(tracker, replace(snapshot, invocations=steps[1:])))

    def test_terminal_evidence_before_start_is_not_active(self):
        snapshot = one_request()
        messages = tuple(replace(m, termination=TerminalEvidence(2150, TerminalOutcome.FAILURE))
                         if m.message_id == "a_next" else m for m in snapshot.messages)
        self.assertEqual((None,) * 4, observe(WatchTokenMix(2200), replace(snapshot, messages=messages)).totals)

    def test_coordinator_disappearing_root_status_resync_and_new_run(self):
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(one_request())
            config, selection, service, _ = make_service(td, source)
            clock = [2200]
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            initial = watch.initialize().projection.token_mix
            clock[0] = 2250
            self.assertEqual(initial, watch.poll_once(force_resync=True).projection.token_mix)
            self.assertEqual(initial, watch.status_projection().token_mix)
            source.snapshot = replace(source.snapshot, sessions=(), source_revision="gone")
            self.assertEqual(initial, watch.poll_once().projection.token_mix)
            self.assertFalse(watch.blocks)
            restarted = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            self.assertEqual((None,) * 4, restarted.initialize().projection.token_mix.totals)

    def test_aggregate_is_independent_of_row_cap_and_includes_child_and_compaction(self):
        tracker = WatchTokenMix(1000)
        snapshot = make_snapshot()
        mix = observe(tracker, snapshot)
        self.assertEqual((100, 3, 2, 17), mix.totals)
        self.assertEqual(2, mix.sample_size, "child/tool and compaction calls are not extra user prompts")
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(snapshot)
            config, selection, service, _ = make_service(td, source)
            config["watchDashboardMaxRows"] = 1
            config["watchRecentEventSeconds"] = 0
            projection = WatchCoordinator(selection=selection, report_service=service, config=config,
                                          clock_ms=lambda: 1000).initialize().projection
            self.assertEqual(1, len(projection.rows))
            # Watch additionally prices each request; the volume mix is identical.
            self.assertEqual(mix, replace(projection.token_mix, costs=None, priced_requests=0))
            self.assertIsNotNone(projection.token_mix.costs)


class ReportTokenMixTests(unittest.TestCase):
    def service(self, source):
        # Reuse the established test service factory without inheriting its tests.
        return compact_fixtures.CompactReportTests.service(self, source)

    def test_latest100_window_across_roots_and_months_reuses_bounded_hydration(self):
        source = SyntheticMonthSource(12, 20, month_start_ms=START)
        service = self.service(source)
        report = service.build(ReportRequest())
        prompts = latest_token_prompts(tuple(service._analyzed.values()))
        self.assertEqual(100, report.token_mix.sample_size)
        self.assertEqual({f"root-{n:04d}" for n in range(7, 12)}, {p.session_id for p in prompts})
        self.assertEqual(5, source.load_count)
        expected = token_mix(e.tokens for p in prompts for e in p.entries)
        self.assertEqual(expected.totals, report.token_mix.totals)
        self.assertEqual(expected.percentages, report.token_mix.percentages)

    def test_usage_eligibility_keeps_running_aborted_known_zero_and_partial(self):
        service = self.service(MutableSource(one_request(running=False)))
        service.build(ReportRequest())
        root = next(iter(service._analyzed.values()))
        record = root.bundle.prompts[0]
        missing = replace(record, prompt_id="no-usage", prompt_time_ms=9999, entries=())
        root.bundle = replace(root.bundle, prompts=(missing,
            replace(record, prompt_id="running", in_progress=True),
            replace(record, prompt_id="aborted", aborted=True),
            replace(record, prompt_id="zero", entries=(replace(record.entries[0], tokens=TokenUsage()),)),
            replace(record, prompt_id="partial", entries=(replace(record.entries[0], tokens=TokenUsage(input=10, known_fields=("input",))),)),
        ))
        selected = latest_token_prompts((root,))
        self.assertEqual({"running", "aborted", "zero", "partial"}, {p.prompt_id for p in selected})

    def test_touched_old_root_does_not_hide_newer_usage_and_ignores_wall_clock(self):
        source = SyntheticMonthSource(12, 20, month_start_ms=START)
        old = source.snapshots["root-0000"]
        root = replace(old.root, updated_at_ms=START + 100 * 86_400_000)
        source.snapshots[root.session_id] = replace(old, root=root, sessions=(root,))
        service = self.service(source)
        before = service.build(ReportRequest()).token_mix
        prompts = latest_token_prompts(tuple(service._analyzed.values()))
        self.assertEqual({f"root-{n:04d}" for n in range(7, 12)}, {p.session_id for p in prompts})
        self.assertEqual(6, source.load_count)
        service.set_now_ms(START + 365 * 86_400_000)
        self.assertEqual(before, service.build(ReportRequest()).token_mix)

    def test_empty_fewer_and_deleted_samples_actual_count(self):
        source = SyntheticMonthSource(2, 20, month_start_ms=START)
        service = self.service(source)
        self.assertEqual(40, service.build(ReportRequest()).token_mix.sample_size)
        del source.snapshots["root-0001"]
        self.assertEqual(20, service.build(ReportRequest()).token_mix.sample_size)
        source.snapshots.clear()
        empty = service.build(ReportRequest())
        self.assertEqual(0, empty.token_mix.sample_size)
        self.assertEqual((None,) * 4, empty.token_mix.percentages)

    def test_missing_telemetry_survives_actual_cache_reuse(self):
        source = MutableSource(one_request(running=False, usage=TokenUsage(input=30, output=10, known_fields=("input", "output"))))
        service = self.service(source)
        before = service.build(ReportRequest())
        service.invalidate_roots(("root",))
        after = service.build(ReportRequest())
        self.assertEqual(before.token_mix, after.token_mix)
        self.assertEqual((None,) * 4, after.token_mix.percentages)
        self.assertEqual(1, source.load_count)


class TokenMixPresentationTests(unittest.TestCase):
    def test_compact_row_no_bar_and_labelled_categories(self):
        mix = token_mix((TokenUsage(input=9, cache_read=85, cache_write=1, output=5),))
        expected = "Token Mix % · 12 prompts · Input: 9%   Cache: 85%   Write: 1%   Output: 5%"
        self.assertEqual(expected, token_mix_line("12 prompts", mix))
        self.assertNotIn("█", expected)

    def test_no_observations_differs_from_known_zero_and_unknown_telemetry(self):
        self.assertEqual("Token Mix % · 0 prompts · no token data yet", token_mix_line("0 prompts", token_mix(())))
        self.assertEqual(0, token_mix(()).request_count)
        for usages in ((TokenUsage(),), (TokenUsage(input=5, known_fields=("input",)),)):
            line = token_mix_line("this watch", token_mix(usages))
            self.assertEqual(4, line.count("--"), "observed but undefined shares stay per-category")
            self.assertNotIn("no token data", line)

    def test_watch_heading_replaced_accounts_byte_identical_and_empty_always_shown(self):
        account = rolling()
        quota = quotas(account)
        projection = WatchProjection("Watch", "V2", (), quota=quota, now_ms=quota.now_ms)
        stream = io.StringIO()
        renderer = WatchRenderer({"timezone": "UTC"}, stream=stream, interactive=False, terminal_width=120)
        renderer._render_quota(projection)
        lines = stream.getvalue().splitlines()
        self.assertTrue(lines[0].startswith("Token Mix % · 0 prompts"))
        self.assertEqual("Watch total CCost: 0", lines[1])
        expected = capacity_lines(account, AnsiStyler({}, enabled=False), "UTC", width=120,
                                  watch=True, now_ms=quota.now_ms, account_label_width=len(account.label),
                                  primary_label_width=4)
        self.assertEqual(expected, lines[2:-1])
        self.assertNotIn("Quotas", stream.getvalue())
        stream.seek(0); stream.truncate()
        renderer.render(replace(projection, quota=None))
        self.assertIn("Token Mix % · 0 prompts", stream.getvalue())

    def test_report_mix_is_defined_above_table_and_not_repeated_above_accounts(self):
        mix = token_mix((TokenUsage(input=11, cache_read=82, cache_write=1, output=6),), sample_size=37)
        report = ReportProjection(ReportKind.NORMAL, "Report", "V2", accounts_quotas=quotas(rolling()), token_mix=mix)
        lines = rendered(report).splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith("Token Mix %"))
        self.assertIn("latest 37 prompts with token data", lines[index + 1])
        self.assertLess(index, next(i for i, line in enumerate(lines) if line.startswith("| Publisher")))
        accounts = lines.index("Accounts Overview")
        self.assertEqual("", lines[accounts - 1])
        self.assertTrue(lines[accounts - 2].startswith("|"), "accounts follow the table directly")
        self.assertEqual("OpenAI Plus", lines[accounts + 2])

    def test_initializing_and_help_document_abbreviations(self):
        stream = io.StringIO()
        WatchRenderer({}, stream=stream, interactive=True).render_initializing()
        from src.version import mode_heading
        self.assertIn(mode_heading("Watch") + "\n", stream.getvalue())
        self.assertNotIn("Token Mix %", stream.getvalue())
        self.assertNotIn("Quotas", stream.getvalue())
        for phrase in ("I = uncached input", "C = cache read", "W = cache write", "O = output"):
            self.assertIn(phrase, help_text())


if __name__ == "__main__":
    unittest.main()
