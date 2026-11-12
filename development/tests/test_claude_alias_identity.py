"""Moving Claude aliases never acquire a release, publisher or price by fuzzy matching."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from development.tests.fixtures.claude_alias import LABEL, catalog, snapshot, service, reopen, desktop_service
from development.tests.fixtures.compact_reports import rendered
from src.analysis.comparisons import model_timeline_name
from src.application.comparisons import run as export_run
from src.application.projection import project
from src.domain import ModelRef, ModelPricing, TokenUsage
from src.pricing.catalog import PricingCatalog
from src.pricing.publishers import publisher_for
from src.reports import ReportKind, ReportRequest
from src.reports.watch_capture import capture_rows
from src.reports.accounts import accounts_quota_projection
from src.application.session_detail import SessionDetails
from src.analysis.billing import billing_request_fingerprint
from src.analysis.causal import trace_entries
from src.analysis.session_cost import reconcile_session_cost
from src.sources.opencode_v2_model_identity import DesktopModelCatalog
from unittest.mock import Mock


class ClaudeAliasIdentityTests(unittest.TestCase):
    def test_discovered_catalog_shapes_share_prompt_session_watch_detail_cli_and_today_cost(self):
        # Sanitized 2026-11-11 inventory shapes, not a production model allowlist.
        matrix = [('opus', 'opus', 'Opus 5.5'), ('sonnet', 'claude-sonnet-5-5', 'Sonnet 5.5'),
            ('haiku', 'haiku', 'Haiku 5.5'), ('fable', 'fable', 'Fable 5.1')]
        matrix += [(model, model, label) for model, label in (
            ('claude-fable-5-2', 'Fable 5.2'), ('claude-haiku-4-5-20251001', 'Haiku 4.5'),
            ('claude-sonnet-5', 'Sonnet 5'), ('claude-opus-5', 'Opus 5'),
            ('claude-fable-5', 'Fable 5'), ('claude-opus-4-8', 'Opus 4.8'),
            ('claude-opus-4-7', 'Opus 4.7'), ('claude-opus-4-6', 'Opus 4.6'),
            ('claude-sonnet-4-6', 'Sonnet 4.6'))]
        absent = {'claude-opus-4-7', 'claude-opus-4-6'}
        reference = PricingCatalog(tuple(ModelPricing(ModelRef('github-copilot',
            'claude-' + label.lower().replace(' ', '-').replace('.', '-'), 'Claude ' + label),
            'USD', D(2), D('.2'), D(3), D(10), metadata={'publisher': 'Anthropic'})
            for selected, _, label in matrix if selected not in absent), retrieved_at_ms=1, source_revision='fixture')
        for selected, upstream, label in matrix:
            with self.subTest(selection=selected):
                original = desktop_service(self, (snapshot(model=selected),))
                original.source.json = lambda route, **_: dict(location=dict(directory='/synthetic'),
                    data=[dict(id='claude-agent')] if route == '/api/provider' else
                    [dict(providerID='claude-agent', id=selected, modelID=upstream, name=label)])
                original.pricing_provider.catalog = reference
                report = original.build(ReportRequest(ReportKind.SESSION, session_id='root-0000'))
                row = report.prompt_blocks[0].rows[0]
                expected = None if selected in absent else D('6.89')
                self.assertEqual(expected, row.comparison_cost.ccost)
                self.assertEqual(expected is not None, row.comparison_cost.complete)
                watch, _ = capture_rows(reopen(original), original.source.snapshots['root-0000'].root)
                self.assertEqual(expected, watch.rows[0].comparison_cost.ccost)
                sessions = reopen(original).build(ReportRequest(ReportKind.SESSIONS, session_limit=None))
                self.assertEqual(expected is not None, sessions.session_usage[0].complete)
                if expected is not None:
                    self.assertEqual(expected, sessions.session_usage[0].ccost)
                details = SessionDetails()
                token = details.open('root-0000', 'live')
                details.tick(reopen(original))
                exported = details.page(token, 0, begin=True)['result']['view']['prompt_blocks'][0]['rows'][0]
                exported_cost = exported['comparison_cost']
                self.assertEqual(expected, None if exported_cost['ccost'] is None else D(exported_cost['ccost']))
                self.assertEqual(expected is not None, exported_cost['complete'])
                entries = trace_entries(original.source.load_session_snapshot('root-0000'))
                total = accounts_quota_projection((), entries, reference,
                    now_ms=entries[0].completed_at_ms, today_start_ms=0, month_start_ms=0)
                self.assertEqual(expected, total.comparison_today.ccost)
                if expected is not None:
                    self.assertIn(label, rendered(report))
                else:
                    self.assertEqual('model_absent', row.comparison_cost.unavailable[0].reason)
                    self.assertIn('N/A', rendered(report))

    def test_short_catalog_labels_price_all_families_without_guessing_versions_or_rates(self):
        # Current source shape: some modelIDs are aliases, others concrete releases.
        selections = [('opus', 'opus', 'Opus 5.5'), ('haiku', 'haiku', 'Haiku 5.5'),
            ('fable', 'fable', 'Fable 5.1'), ('sonnet', 'claude-sonnet-5-5', 'Sonnet 5.5'),
            ('future-selection', 'future-selection', 'Newfamily 9.2')]
        prices = PricingCatalog(tuple(ModelPricing(ModelRef('github-copilot',
            'claude-' + label.lower().replace(' ', '-').replace('.', '-'), 'Claude ' + label),
            'USD', D(2), D('.2'), D(3), D(10), metadata={'publisher': 'Anthropic'})
            for _, _, label in selections))
        client = Mock(json=lambda route, **_: dict(location=dict(directory='/one'),
            data=[dict(id='claude-agent')] if route == '/api/provider' else
            [dict(providerID='claude-agent', id=selected, modelID=upstream, name=label)
             for selected, upstream, label in selections]))
        resolver = DesktopModelCatalog(lambda: client)
        for selected, _, label in selections:
            with self.subTest(selection=selected):
                model = resolver.resolve(ModelRef('claude-agent', selected), '/one')
                tokens = TokenUsage(input=1000, cache_read=2000, cache_write=3000, output=50)
                self.assertEqual(D('.0119') * 100, prices.reference_valuation(model, tokens))
                self.assertEqual(prices.reference_valuation(model, tokens),
                    sum(prices.reference_category_valuation(model, tokens)))
                self.assertEqual(label, model.display_name)
                self.assertEqual(selected, model.recorded_model)
                self.assertIsNone(prices.estimate(model, tokens))
        unknown = resolver.resolve(ModelRef('claude-agent', 'absent'), '/one')
        self.assertIsNone(prices.reference_valuation(unknown, TokenUsage(input=1000)))
        pinned = ModelRef('claude-agent', 'claude-newfamily-9-2')
        self.assertEqual(pinned, resolver.resolve(pinned, '/one'))

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

        self.assertEqual('Claude Sonnet 5.5', row.watch_model)
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
        self.assertEqual('Claude Sonnet 5.5', after.session_usage[0].model)
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
