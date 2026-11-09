"""Moving Claude aliases never acquire a release, publisher or price by fuzzy matching."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from development.tests.fixtures.claude_alias import LABEL, catalog, snapshot, service, reopen, desktop_service
from development.tests.fixtures.compact_reports import rendered
from src.analysis.comparisons import model_timeline_name
from src.application.comparisons import run as export_run
from src.application.projection import project
from src.domain import ModelRef
from src.pricing.publishers import publisher_for
from src.reports import ReportKind, ReportRequest
from src.reports.watch_capture import capture_rows
from src.analysis.billing import billing_request_fingerprint
from src.analysis.causal import trace_entries
from src.analysis.session_cost import reconcile_session_cost
from src.sources.opencode_v2_model_identity import DesktopModelCatalog
from unittest.mock import Mock


class ClaudeAliasIdentityTests(unittest.TestCase):
    def test_exact_location_provider_and_catalog_label_do_not_leak_across_requests(self):
        def response(route, *, query, **_kwargs):
            directory = query['location[directory]']
            models = [dict(providerID='claude-agent', id='sonnet', name='Sonnet 4', modelID='claude-sonnet-4'),
                      dict(providerID='claude-agent', id='sonnet', name='Sonnet 5.5', modelID='claude-sonnet-5-5'),
                      dict(providerID='claude-agent', id='sonnet', name='Deprecated', status='deprecated')]
            return dict(location=dict(directory=directory), data=[dict(id='claude-agent')]
                if route == '/api/provider' else models if directory == '/one' else [])
        client = Mock(json=Mock(side_effect=response))
        resolver = DesktopModelCatalog(lambda: client)

        first = resolver.resolve(ModelRef('claude-agent', 'sonnet'), '/one')
        missing = resolver.resolve(ModelRef('claude-agent', 'sonnet'), '/two')
        other = resolver.resolve(ModelRef('custom', 'sonnet'), '/one')
        pinned = resolver.resolve(ModelRef('claude-agent', 'claude-sonnet-4'), '/one')

        self.assertEqual(('claude-sonnet-5-5', 'Sonnet 5.5'), (first.model, first.display_name))
        self.assertEqual('sonnet', missing.model)
        self.assertEqual(ModelRef('custom', 'sonnet'), other)
        self.assertEqual(ModelRef('claude-agent', 'claude-sonnet-4'), pinned)
        self.assertEqual(4, client.json.call_count)

    def test_catalog_name_without_supported_price_never_uses_fuzzy_reference_rate(self):
        original = desktop_service(self, (snapshot(),))
        original.source.model, original.source.label = 'sonnet', 'Sonnet custom version'
        request = original.source.load_session_snapshot('root-0000').invocations[0]
        reference = catalog()

        self.assertEqual('Sonnet custom version', request.model.display_name)
        self.assertIsNone(reference.reference_valuation(request.model, request.tokens))
        self.assertIsNone(reference.reference_category_valuation(request.model, request.tokens))
        self.assertIsNone(reference.reference_usage(request.model, request.tokens))
        self.assertIsNone(reference.reference_input_context(request.model, input_tokens=1000,
            cache_read_tokens=2000, cache_write_tokens=22000, request_input_tokens=25000))

    def test_desktop_fallback_prices_real_usage_preserving_alias_effort_and_estimate_provenance(self):
        original = desktop_service(self, (snapshot(),))
        report = original.build(ReportRequest(ReportKind.SESSION, session_id='root-0000'))
        row = report.prompt_blocks[0].rows[0]
        request = original._analyzed['root-0000'].snapshot.invocations[0]

        self.assertEqual('Sonnet 5.5', row.watch_model)
        self.assertEqual('Default', row.watch_effort)
        self.assertEqual(D('6.89'), row.ccost)
        self.assertEqual('sonnet', request.model.recorded_model)
        self.assertEqual('claude-agent', request.model.provider)
        self.assertEqual('desktop-catalog-estimate', request.model.resolution.kind)
        self.assertIsNone(catalog().estimate(request.model, request.tokens))
        self.assertIn('Sonnet 5.5', rendered(report))
        self.assertIn('historic executed version unconfirmed', str(project(report, prompt_details=True).to_json()))
        watch, _ = capture_rows(reopen(original), original.source.snapshots['root-0000'].root)
        self.assertEqual(row.watch_model, watch.rows[0].watch_model)
        self.assertEqual(row.ccost, watch.rows[0].ccost)

    def test_catalog_turnover_changes_inferred_only_and_keeps_clone_fingerprint(self):
        original = desktop_service(self, (snapshot(), snapshot(1, 'claude-sonnet-4')))
        first = original.source.load_session_snapshot('root-0000')
        pinned = original.source.load_session_snapshot('root-0001')
        reference = replace(catalog(), models=tuple(replace(model, per_million_input=D(4))
            if model.model.model == 'claude-sonnet-4-5' else model for model in catalog().models))
        first = replace(first, invocations=(*first.invocations, *pinned.invocations))
        old = reconcile_session_cost(original.cache_repository, first, reference)
        original.source.model, original.source.label, original.source.clock = 'claude-sonnet-4-5', 'Sonnet 4.5', 31
        second = original.source.load_session_snapshot('root-0000')
        second = replace(second, invocations=(*second.invocations, *pinned.invocations))
        new = reconcile_session_cost(original.cache_repository, second, reference)

        self.assertEqual('claude-sonnet-5-5', first.invocations[0].model.model)
        self.assertEqual('claude-sonnet-4-5', second.invocations[0].model.model)
        self.assertEqual(pinned, original.source.load_session_snapshot('root-0001'))
        self.assertEqual(billing_request_fingerprint(trace_entries(first)[0]),
                         billing_request_fingerprint(trace_entries(second)[0]))
        self.assertEqual(1, new.valued_requests)
        self.assertEqual(2, new.checked_requests)
        self.assertEqual(old.total.known_ccost + D('.2'), new.total.known_ccost)

    def test_missing_exact_catalog_match_recovers_without_changing_raw_history(self):
        original = desktop_service(self, (snapshot(),))
        original.source.model = None
        before = original.build(ReportRequest(ReportKind.SESSIONS, session_limit=None))
        original.source.model, original.source.clock = 'claude-sonnet-5-5', 31
        after = reopen(original).build(ReportRequest(ReportKind.SESSIONS, session_limit=None))

        self.assertEqual(LABEL, before.session_usage[0].model)
        self.assertFalse(before.session_usage[0].complete)
        self.assertEqual('Sonnet 5.5', after.session_usage[0].model)
        self.assertEqual(D('6.89'), after.session_usage[0].ccost)
        self.assertEqual('sonnet', original.source.snapshots['root-0000'].invocations[0].model.model)

    def test_alias_only_availability_does_not_hide_resolved_history(self):
        original = desktop_service(self, (snapshot(),))
        original.model_availability_source.ids = ('claude-agent/sonnet',)

        result = reopen(original, shared=True).build_token_mix_history()

        self.assertEqual(['Sonnet 5.5'], [row.model for row in result.model_token_mix])
        self.assertEqual(1, result.token_mix.priced_requests)
        self.assertEqual(2, original.source.catalog_reads)

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
