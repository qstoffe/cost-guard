"""Moving Claude aliases never acquire a release, publisher or price by fuzzy matching."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from development.tests.fixtures.claude_alias import LABEL, catalog, snapshot, service, reopen
from development.tests.fixtures.compact_reports import rendered
from src.analysis.comparisons import model_timeline_name
from src.application.comparisons import run as export_run
from src.application.projection import project
from src.domain import ModelRef
from src.pricing.publishers import publisher_for
from src.reports import ReportKind, ReportRequest
from src.reports.watch_capture import capture_rows


class ClaudeAliasIdentityTests(unittest.TestCase):
    def test_current_v2_alias_shape_does_not_inherit_mutable_selection_or_catalog_order(self):
        original = snapshot()
        self.assertIsNone(original.messages[0].model)
        self.assertEqual(ModelRef('claude-agent', 'sonnet'), original.invocations[0].model)
        self.assertEqual('default', original.invocations[0].variant)
        self.assertEqual(25050, original.invocations[0].tokens.total)
        for reverse in (False, True):
            reference = catalog(reverse=reverse)
            request = original.invocations[0]
            with self.subTest(reverse=reverse):
                self.assertEqual(LABEL + ' (Default)', model_timeline_name(reference, 'sonnet', 'claude-agent', 'default'))
                self.assertIsNone(reference.resolve('sonnet'))
                self.assertIsNone(reference.reference_valuation(request.model, request.tokens))
                self.assertIsNone(reference.estimate(request.model, request.tokens))
                self.assertEqual('identity', reference.reference_issue(request.model, request.tokens).reason)

    def test_alias_release_turnover_uses_each_assistants_own_pinned_identity_only(self):
        values = (snapshot(), snapshot(1, 'claude-sonnet-4'), snapshot(2, 'claude-sonnet-5-5'),
                  snapshot(3, 'claude-sonnet-4-5', 'anthropic'))
        original = service(self, snapshots=values)
        report = original.build(ReportRequest(ReportKind.SESSIONS, session_limit=None))
        rows = {row.session_id: row for row in report.session_usage}
        self.assertEqual(LABEL, rows['root-0000'].model)
        self.assertFalse(rows['root-0000'].complete)
        for index, name in ((1, 'Claude Sonnet 4'), (2, 'Claude Sonnet 5.5'), (3, 'Claude Sonnet 4.5')):
            row = rows[f'root-{index:04d}']
            self.assertEqual(name, row.model)
            # 100 credits/USD: .002 input + .0004 read + .066 write + .0005 output.
            self.assertEqual(D('6.89'), row.ccost)
            self.assertTrue(row.complete)
        original.pricing_provider.catalog = replace(catalog(reverse=True), retrieved_at_ms=999)
        refreshed = reopen(original).build(ReportRequest(ReportKind.SESSIONS, session_limit=None))
        self.assertEqual(report.session_usage, refreshed.session_usage)

    def test_cli_web_detail_and_watch_share_model_effort_and_unpriced_reason(self):
        original = service(self, snapshots=(snapshot(),))
        report = original.build(ReportRequest(ReportKind.SESSION, session_id='root-0000'))
        row = report.prompt_blocks[0].rows[0]
        watch, _item = capture_rows(reopen(original), original.source.snapshots['root-0000'].root)
        self.assertEqual(LABEL, row.watch_model)
        self.assertEqual('Default', row.watch_effort)
        self.assertIn(LABEL, rendered(report))
        self.assertIn(LABEL, str(project(report).to_json()))
        self.assertEqual(LABEL, watch.rows[0].watch_model)
        self.assertEqual('identity', row.comparison_cost.unavailable[0].reason)
        self.assertFalse(row.comparison_cost.complete)
        self.assertEqual('sonnet', row.cost_parts[0].model_id)
        self.assertEqual('claude-agent', row.cost_parts[0].provider_id)
        self.assertEqual(LABEL, row.cost_parts[0].model)

    def test_model_mix_keeps_unknown_alias_backends_separate_without_publisher_guess(self):
        original = service(self, snapshots=(snapshot(), snapshot(1, provider='custom'),
                                           snapshot(2, 'claude-sonnet-5-5')))
        report = reopen(original, shared=True).build_token_mix_history()
        names = {row.model for row in report.model_token_mix}
        self.assertEqual({LABEL, 'sonnet (version unverified)', 'Claude Sonnet 5.5'}, names)
        self.assertEqual(3, report.token_mix.request_count)
        self.assertEqual(1, report.token_mix.priced_requests)
        self.assertEqual({'Anthropic', 'Unknown / unverified'}, {row.publisher for row in report.publisher_token_mix})
        self.assertIsNone(publisher_for(catalog(), 'sonnet'))
        original.model_availability_source.ids = ('claude-agent/sonnet',)
        filtered = reopen(original, shared=True).build_token_mix_history()
        self.assertEqual([LABEL], [row.model for row in filtered.model_token_mix])

    def test_other_moving_selections_and_missing_pinned_rates_are_honest(self):
        reference = catalog()
        for alias in ('opus', 'haiku', 'fable', 'sonnet[1m]', 'claude-sonnet-latest', 'default', 'best', 'opusplan'):
            with self.subTest(alias=alias):
                request = replace(snapshot().invocations[0], model=ModelRef('claude-agent', alias))
                self.assertIn('version unverified', reference.display_name(alias, 'claude-agent'))
                self.assertIsNone(reference.reference_valuation(request.model, request.tokens))
        reference = replace(reference, models=tuple(m for m in reference.models if m.model.model != 'claude-sonnet-4'))
        request = snapshot(model='claude-sonnet-4').invocations[0]
        self.assertIsNone(reference.reference_valuation(request.model, request.tokens))
        self.assertEqual('model_absent', reference.reference_issue(request.model, request.tokens).reason)

    def test_comparisons_exports_unverified_label_separately_from_raw_request_identity(self):
        original = service(self)
        report = original.build(ReportRequest(ReportKind.COMPARISONS))
        alias = next(value for value in report.comparisons.groups[0].runs if value.model == 'sonnet')

        value = export_run(alias).to_json()

        self.assertEqual('sonnet', value['model'])
        self.assertEqual('claude-agent', value['provider'])
        self.assertEqual(LABEL, value['model_label'])
        self.assertEqual('sonnet', value['contributors'][0]['model'])
        self.assertEqual(LABEL, value['contributors'][0]['model_label'])
        self.assertIsNone(value['ccost'])


if __name__ == '__main__':
    unittest.main()
