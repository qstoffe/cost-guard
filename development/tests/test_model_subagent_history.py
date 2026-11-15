"""Native synthetic child trees distinguish model usage from whole-prompt cost."""
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch
import unittest

from development.tests.fixtures.compact_reports import Availability, report_service
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.model_subagent_history import SOL, ASTRA, NOW, PRICES, native_tree
from development.tests.fixtures.watch_runtime import MutableSource
from src.analysis import analyze_snapshot
from src.analysis.ai_stats import DAY_MS, StatsObservation, StatsRoot, windows
from src.analysis.valuation import comparison_cost
from src.cache.repository import CacheEntry
from src.reports.ai_stats_responses import encode_responses, decode_activity, decode_responses
from src.reports.token_mix_cache import ALGORITHM, decode, encode, load
from src.reports.token_mix_history import history_prompt_keys


class ModelSubagentHistoryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'optional JavaScript runtime unavailable')
    def test_model_accessors_keep_prepared_identity_efforts_and_units(self):
        script = """
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
vm.runInThisContext(fs.readFileSync('src/web/assets/render.js','utf8'));
const row={label:'GPT-6.1 Sol',model_help:'route/GPT-6.1 Sol\\n\\nBy Effort:\\n• High — 2 CCost',
  display:{model_help:'route/GPT-6.1 Sol\\n\\nBy Effort:\\n• High — 2 CCost'},
  display_units:{usd:{model_help:'route/GPT-6.1 Sol\\n\\nBy Effort:\\n• High — $0.02'}}};
assert.equal(ReportView.aiStatsModelHelp(row),row.display.model_help);
ReportView.setUnit('usd');
assert.equal(ReportView.aiStatsModelHelp(row),row.display_units.usd.model_help);
assert.equal(ReportView.display(row,'model_help'),row.display_units.usd.model_help);
ReportView.setUnit('credits');
assert.equal(ReportView.aiStatsModelHelp(row),row.model_help);
assert.equal(ReportView.aiStatsModelHelp({}), '');
"""
        result = subprocess.run([shutil.which('node'), '-e', script],
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stderr)

    def service(self, snapshot, *, cached=False, available=None):
        service = report_service(self, MutableSource(snapshot), now_ms=NOW,
            availability=Availability(available if available is not None else
                                      ('github-copilot/' + SOL, 'github-copilot/' + ASTRA)))
        service.pricing_provider.catalog = PRICES
        service.cache_token_mix_history = cached
        return service

    def stats(self, snapshot, bundle, scope='today'):
        facts = decode(encode(bundle, PRICES))
        responses = encode_responses(bundle, snapshot, NOW)
        root = StatsRoot(snapshot.root.session_id, 'Synthetic', tuple(e for e, _, _ in facts), (),
            responses=decode_responses(responses, facts), activity=decode_activity(responses, facts))
        row = StatsObservation((root,), PRICES.reference_valuation, now=NOW, zone='UTC').period(
            period=scope, start=dict(windows('UTC', NOW))[scope])
        return {metric.metric: metric for metric in row.metrics}

    def test_same_model_high_root_max_child_is_one_bucket_with_two_efforts(self):
        snapshot = native_tree()
        bundle = analyze_snapshot(snapshot, now_ms=NOW)
        entries = {e.message_id: e for e in bundle.trace_entries}
        child = entries['ca']
        self.assertEqual(('ses_current_child', 'ses_current', 'ses_current', 'cu',
                          'github-copilot', SOL, 'max', 3 * DAY_MS + 3800),
            (child.session_id, child.parent_session_id, child.root_session_id, child.logical_prompt_id,
             child.model.provider, child.model.model, child.variant, child.completed_at_ms))
        self.assertEqual(3, len({e.invocation_id for e in entries.values()}))
        self.assertEqual((1, 3), (len(bundle.prompts), bundle.prompts[0].model_calls))
        self.assertEqual(D(183), comparison_cost(bundle.prompts[0].entries, PRICES.reference_valuation).ccost)
        for cached in (False, True):
            service = self.service(snapshot, cached=cached)
            report = service.build_token_mix_history(scope='today')
            (row,) = report.model_token_mix
            self.assertEqual(('GPT-6.1 Sol', 3, (300_000,) * 4, D(183)),
                             (row.model, row.calls, row.mix.totals, sum(row.mix.costs)))
            self.assertEqual(report, service.build_token_mix_history(scope='today'))
        metrics = self.stats(snapshot, bundle)
        expected = {
            'total-tokens': (1_200_000, (('High', 800_000), ('Max', 400_000))),
            'total-cost': (D(183), (('High', D(122)), ('Max', D(61)))),
            'average-cost': (D(183), (('High', D(122)), ('Max', D(61)))),
            'working-time': (800, (('High', 400), ('Max', 400))),
            'token-rate': (D(375_000), (('High', D(500_000)), ('Max', D(250_000)))),
        }
        for metric, (value, efforts) in expected.items():
            with self.subTest(metric=metric):
                (row,) = metrics[metric].podium
                self.assertEqual(SOL, row.model)
                self.assertEqual(value, row.tokens_per_second if metric == 'token-rate' else row.value)
                self.assertEqual(efforts, row.by_effort)

    def test_different_model_child_keeps_own_categories_cost_timing_and_effort(self):
        snapshot = native_tree(ASTRA)
        bundle = analyze_snapshot(snapshot, now_ms=NOW)
        self.assertEqual(D(224), comparison_cost(bundle.prompts[0].entries, PRICES.reference_valuation).ccost)
        for cached in (False, True):
            report = self.service(snapshot, cached=cached).build_token_mix_history(scope='today')
            rows = {row.model: row for row in report.model_token_mix}
            self.assertEqual((2, (200_000,) * 4, (D(20), D(2), D(20), D(80))),
                (rows['GPT-6.1 Sol'].calls, rows['GPT-6.1 Sol'].mix.totals, rows['GPT-6.1 Sol'].mix.costs))
            self.assertEqual((1, (100_000,) * 4, (D(20), D(2), D(20), D(60))),
                (rows['GPT Astra'].calls, rows['GPT Astra'].mix.totals, rows['GPT Astra'].mix.costs))
            self.assertEqual((3, D(224)), (report.token_mix.request_count, sum(report.token_mix.costs)))
        metrics = self.stats(snapshot, bundle)
        for metric, sol, astra in (
            ('total-tokens', 800_000, 400_000), ('total-cost', D(122), D(102)),
            ('average-cost', D(122), D(102)), ('working-time', 400, 400),
            ('token-rate', D(500_000), D(250_000)),
        ):
            with self.subTest(metric=metric):
                rows = {row.model: row for row in metrics[metric].podium}
                for model, expected, effort in ((SOL, sol, 'High'), (ASTRA, astra, 'Max')):
                    row = rows[model]
                    self.assertEqual(expected, row.tokens_per_second if metric == 'token-rate' else row.value)
                    self.assertEqual(((effort, expected),), row.by_effort)

    def test_older_astra_and_today_sol_use_physical_completion_times_cold_and_warm(self):
        snapshot = native_tree(older_astra=True)
        bundle = analyze_snapshot(snapshot, now_ms=NOW)
        for cached in (False, True):
            service = self.service(snapshot, cached=cached)
            for scope, expected in (('today', {'GPT-6.1 Sol': 3}),
                                    ('7-days', {'GPT-6.1 Sol': 3, 'GPT Astra': 1})):
                report = service.build_token_mix_history(scope=scope)
                self.assertEqual(expected, {row.model: row.calls for row in report.model_token_mix})
                self.assertEqual(report, service.build_token_mix_history(scope=scope))
                metrics = self.stats(snapshot, bundle, scope)
                self.assertEqual({SOL} if scope == 'today' else {SOL, ASTRA},
                                 {row.model for row in metrics['total-tokens'].podium})

    def test_executed_child_remains_in_history_when_not_currently_selectable(self):
        service = self.service(native_tree(ASTRA), cached=True, available=('github-copilot/' + SOL,))
        report = service.build_token_mix_history(scope='today')
        self.assertEqual({'GPT-6.1 Sol', 'GPT Astra'}, {row.model for row in report.model_token_mix})
        self.assertEqual((3, D(224)), (report.token_mix.request_count, sum(report.token_mix.costs)))
        self.assertEqual(0, service.model_availability_source.calls, 'historical usage needs no live roster')

    def test_model_prompts_use_child_logical_boundaries_not_root_or_physical_calls(self):
        snapshot = native_tree(multiple=True)
        bundle = analyze_snapshot(snapshot, now_ms=NOW)
        self.assertEqual(1, len(bundle.prompts), 'one real human root prompt remains one')
        self.assertEqual({'cu', 'cu2'}, {e.logical_prompt_id for e in bundle.trace_entries
                                      if e.session_id == 'ses_current_child'})
        for cached in (False, True):
            service = self.service(snapshot, cached=cached)
            report = service.build_token_mix_history(scope='today')
            (row,) = report.model_token_mix
            self.assertEqual((3, 5), (row.prompts, row.calls), 'root + two child prompts, five calls')
            self.assertEqual(3, report.token_mix.sample_size)
            with patch.object(service.source, 'load_session_snapshot',
                              side_effect=AssertionError('warm history hydration')) if cached else patch.object(
                                  service, 'cache_token_mix_history', False):
                self.assertEqual(report, service.build_token_mix_history(scope='today'))

    def test_old_compact_evidence_is_invalidated_and_logical_identity_roundtrips(self):
        bundle = analyze_snapshot(native_tree(), now_ms=NOW)
        facts = encode(bundle, PRICES)
        restored = decode(facts)
        self.assertEqual([(e.session_id, e.logical_prompt_id) for e in bundle.trace_entries],
                         [(e.session_id, e.logical_prompt_id) for e, _, _ in restored])
        old = CacheEntry('web-token-mix-evidence', 'old', facts, 'revision', 'web-token-mix-evidence-2')
        self.assertIsNone(load(old, 'revision'))
        self.assertNotEqual('web-token-mix-evidence-2', ALGORITHM)

    def test_compaction_is_a_call_not_a_prompt_and_unknown_child_does_not_borrow_root(self):
        bundle = analyze_snapshot(make_snapshot(), now_ms=4000)
        keys = history_prompt_keys(bundle)
        self.assertEqual(3, len(set(keys.values())), 'two root prompts plus one recorded child')
        (summary,) = [e for e in bundle.trace_entries if e.summary]
        self.assertNotIn(summary, keys)
        child = next(e for e in bundle.trace_entries if e.session_id == 'child')
        unknown = replace(child, logical_prompt_id=None)
        legacy = replace(bundle,
            trace_entries=tuple(unknown if e == child else replace(e, logical_prompt_id=None)
                                for e in bundle.trace_entries),
            prompts=tuple(replace(p, entries=tuple(unknown if e == child else replace(e, logical_prompt_id=None)
                                                   for e in p.entries)) for p in bundle.prompts))
        fallback = history_prompt_keys(legacy)
        self.assertNotIn(unknown, fallback)
        self.assertEqual({('root', 'u_sub'), ('root', 'u_next')}, set(fallback.values()))
        facts = decode(encode(bundle, PRICES))
        self.assertEqual(5, len(facts))
        self.assertEqual(3, len({prompt for _, prompt, _ in facts if prompt is not None}))
        self.assertEqual(1, sum(e.summary for e, _, _ in facts))


if __name__ == '__main__':
    unittest.main()
