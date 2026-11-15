"""Synthetic recorded routes prove Web attribution independently of reference prices."""
from dataclasses import replace
import unittest

from development.tests.fixtures.compact_reports import report_service, rendered
from development.tests.fixtures.session_snapshots import history, prov
from src.analysis.causal import trace_entries
from src.application.projection import project
from src.domain import ModelRef
from src.pricing.catalog import PricingCatalog
from src.reports.token_mix_history import history_projection
from src.sources.opencode_v2_normalization import normalize_message_bundle, normalize_invocations


class TokenMixPublisherTests(unittest.TestCase):
    def report(self, selections, *, scope='all'):
        service = report_service(self)
        service.model_availability_source.ids = None
        template = service._load_comparison_catalog().models[0]
        reference = PricingCatalog(tuple(replace(template,
            model=ModelRef('github-copilot', model, label), metadata=metadata)
            for model, label, metadata in [
                ('fixture-openai', 'Catalog OpenAI', {'publisher': 'OpenAI'}),
                ('fixture-anthropic', 'Catalog Anthropic', {'publisher': 'Anthropic'}),
                ('fixture-conflict', 'Catalog Google', {'manufacturer': 'Google'}),
                ('fixture-invalid', 'Conflicting metadata', {'publisher': 'OpenAI', 'manufacturer': 'Google'}),
            ]))
        snapshot = history([(100, 200)], generation='v2')
        messages, invocations = [snapshot.messages[0]], []
        for index, (provider, model) in enumerate(selections):
            message, _ = normalize_message_bundle({
                'info': {'id': f'a{index}', 'sessionID': 'root', 'role': 'assistant',
                    'parentID': 'u0', 'providerID': provider, 'modelID': model,
                    'time': {'created': 110 + index, 'completed': 150 + index},
                    'tokens': {'input': 100, 'output': 10, 'cache': {'read': 0, 'write': 0}},
                    'finish': 'stop'}, 'parts': []}, prov)
            messages.append(message)
            invocations.extend(normalize_invocations(message, prov))
        entries = trace_entries(replace(snapshot, messages=tuple(messages), invocations=tuple(invocations)))
        self.assertEqual(selections, [(entry.model.provider, entry.model.model) for entry in entries])
        report = history_projection(service, reference, entries, {entry: ('root', 'u0') for entry in entries},
                                    lambda *_: None, scope=scope)
        return report, reference, entries

    def test_recorded_first_party_routes_join_catalog_publishers_without_acquiring_prices(self):
        report, reference, entries = self.report([
            ('openai', 'fixture-unlisted-model'), ('openai', 'fixture-openai'),
            ('claude-agent', 'sonnet'), ('github-copilot', 'fixture-anthropic'),
            ('openai', 'fixture-conflict'), ('openai', 'fixture-invalid'),
            *[(route, f'fixture-unknown-{route}') for route in
              ('github-copilot', 'openai-compatible', 'openrouter', 'azure', 'custom')],
        ])

        rows = {row.web_model: row for row in report.model_token_mix}
        publishers = {row.publisher: row for row in report.publisher_token_mix}
        self.assertEqual('OpenAI', rows['fixture-unlisted-model'].publisher)
        self.assertEqual('Anthropic', rows['sonnet'].publisher)
        self.assertEqual('Google', rows['Catalog Google'].publisher)
        self.assertEqual('—', rows['Conflicting metadata'].publisher)
        self.assertTrue(all(rows[f'fixture-unknown-{route}'].publisher == '—' for route in
                            ('github-copilot', 'openai-compatible', 'openrouter', 'azure', 'custom')))
        self.assertEqual(11, len(rows))
        self.assertEqual({'OpenAI': (1, 2), 'Anthropic': (1, 2), 'Google': (1, 1),
                          'Unknown / unverified': (1, 6)},
                         {name: (row.prompts, row.calls) for name, row in publishers.items()})
        self.assertEqual(rows['Catalog OpenAI'].mix.costs, publishers['OpenAI'].mix.costs)
        self.assertEqual(rows['Catalog Anthropic'].mix.costs, publishers['Anthropic'].mix.costs)
        self.assertEqual((100, 0, 0, 10), rows['fixture-unlisted-model'].observed_totals)
        for index in (0, 2):
            self.assertIsNone(reference.reference_category_valuation(entries[index].model, entries[index].tokens))
            self.assertIsNone(entries[index].model.resolution)
        self.assertFalse(publishers['OpenAI'].mix.cost_complete)
        self.assertFalse(publishers['Anthropic'].mix.cost_complete)
        self.assertEqual('OpenAI', next(row['publisher'] for row in project(report).to_json()['model_token_mix']
                                       if row['model'] == 'fixture-unlisted-model'))

    def test_same_absent_identity_never_takes_last_route_publisher_and_cli_stays_unchanged(self):
        selections = [('openai', 'fixture-unlisted-model'), ('claude-agent', 'fixture-unlisted-model')]
        for order in (selections, list(reversed(selections))):
            with self.subTest(order=order):
                web, _, _ = self.report(order)
                cli, _, _ = self.report(order, scope=None)
                self.assertEqual(1, len(web.model_token_mix))  # Preserve existing model group boundaries.
                self.assertEqual('—', web.model_token_mix[0].publisher)
                self.assertEqual({'OpenAI': 1, 'Anthropic': 1},
                                 {row.publisher: row.calls for row in web.publisher_token_mix})
                self.assertEqual({'Unknown / unverified': 2},
                                 {row.publisher: row.calls for row in cli.publisher_token_mix})
                self.assertNotIn('Anthropic', rendered(cli))
                self.assertEqual(cli.token_mix, web.token_mix)


if __name__ == '__main__':
    unittest.main()
