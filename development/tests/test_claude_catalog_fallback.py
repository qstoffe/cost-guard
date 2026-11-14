"""Frozen catalog names are exact offline estimates, never execution attestations."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from development.tests.fixtures.claude_alias import catalog, desktop_service, reopen, snapshot
from development.tests.fixtures.compact_reports import rendered
from development.tests.fixtures.watch_summary import summary_watch
from src.application.live_projection import project_live
from src.application.projection import project
from src.application.session_detail import SessionDetails
from src.domain import ModelRef, TokenUsage
from src.reports import ReportKind, ReportRequest
from src.reports.watch_capture import capture_rows
from src.sources.claude_agent_catalog import SNAPSHOT_PATH, load_snapshot
from src.sources.errors import SourceDataError, http_failure
from src.sources.opencode_v2_model_identity import DesktopModelCatalog
from src.watch.models import WatchCard, WatchRow

ALIASES = (('sonnet', 'Claude Sonnet 5.5'), ('opus', 'Claude Opus 5.5'),
           ('haiku', 'Claude Haiku 5.5'), ('fable', 'Claude Fable 5.1'))


class ClaudeCatalogFallbackTests(unittest.TestCase):
    def test_shipped_sanitized_snapshot_has_exact_reviewed_thirteen_records(self):
        models, metadata = load_snapshot(SNAPSHOT_PATH)
        self.assertEqual(('2026-11-14T19:46:36Z', '2.3.0'), metadata)
        self.assertEqual({
            'opus': ('Opus 5.5', 'opus'), 'sonnet': ('Sonnet 5.5', 'claude-sonnet-5-5'),
            'haiku': ('Haiku 5.5', 'haiku'), 'fable': ('Fable 5.1', 'fable'),
            'claude-fable-5-2': ('Fable 5.2', 'claude-fable-5-2'),
            'claude-haiku-4-5-20251001': ('Haiku 4.5', 'claude-haiku-4-5-20251001'),
            'claude-sonnet-5': ('Sonnet 5', 'claude-sonnet-5'),
            'claude-opus-5': ('Opus 5', 'claude-opus-5'),
            'claude-fable-5': ('Fable 5', 'claude-fable-5'),
            'claude-opus-4-8': ('Opus 4.8', 'claude-opus-4-8'),
            'claude-opus-4-7': ('Opus 4.7', 'claude-opus-4-7'),
            'claude-opus-4-6': ('Opus 4.6', 'claude-opus-4-6'),
            'claude-sonnet-4-6': ('Sonnet 4.6', 'claude-sonnet-4-6')}, models)
        value = json.loads(SNAPSHOT_PATH.read_bytes())
        self.assertEqual(13, len(value['models']))
        self.assertTrue(all(row['status'] == 'active' for row in value['models']))

    def test_four_404_aliases_share_normalized_report_sessions_detail_watch_and_mini_labels(self):
        for alias, expected in ALIASES:
            with self.subTest(alias=alias):
                original = desktop_service(self, (snapshot(model=alias),))
                original.source.json = Mock(side_effect=http_failure(404, phase='model_identity'))
                raw = deepcopy(original.source.snapshots)

                report = original.build(ReportRequest(ReportKind.SESSION, session_id='root-0000'))
                sessions = reopen(original).build(ReportRequest(ReportKind.SESSIONS, session_limit=None))
                watch, _ = capture_rows(reopen(original), raw['root-0000'].root)
                details = SessionDetails()
                token = details.open('root-0000', 'live')
                details.tick(reopen(original))
                detail = details.page(token, 0, begin=True)['result']['view']
                frame = replace(summary_watch(), active_cards=(WatchCard('root-0000', 'Fixture', 'u',
                    (WatchRow('root-0000', 'Fixture', watch.rows[0]),)),), history_cards=())
                mini = project_live(frame).to_json()

                row = report.prompt_blocks[0].rows[0]
                self.assertEqual(expected, row.watch_model)
                self.assertEqual(expected, sessions.session_usage[0].model)
                self.assertEqual(expected, watch.rows[0].watch_model)
                self.assertIn(expected, str(detail))
                self.assertIn(expected, str(mini))
                self.assertIn(expected, rendered(report))
                help_text = str(project(report, prompt_details=True).to_json())
                self.assertIn('catalog-based estimate', help_text)
                self.assertIn('bundled frozen snapshot', help_text)
                self.assertIn('historic executed version unconfirmed', help_text)
                request = original._analyzed['root-0000'].snapshot.invocations[0]
                self.assertEqual(alias, request.model.recorded_model)
                self.assertEqual('bundled-catalog-estimate', request.model.resolution.kind)
                self.assertEqual('2026-11-14T19:46:36Z', request.model.resolution.observed_at)
                self.assertEqual(25050, request.tokens.total)
                self.assertEqual(raw, original.source.snapshots)
                self.assertIsNone(catalog().estimate(request.model, request.tokens))
                self.assertEqual(D('6.89') if alias == 'sonnet' else None, row.comparison_cost.ccost)
                if alias != 'sonnet':
                    self.assertFalse(row.comparison_cost.complete)

    def test_usable_last_live_exact_match_always_wins_over_conflicting_snapshot(self):
        client = Mock(json=Mock(side_effect=lambda route, **_: dict(location=dict(directory='/deleted'),
            data=[dict(id='claude-agent')] if route == '/api/provider' else [
                dict(providerID='claude-agent', id='sonnet', name='Sonnet 4', modelID='claude-sonnet-4'),
                dict(providerID='claude-agent', id='sonnet', name='Sonnet 4.5', modelID='claude-sonnet-4-5'),
                dict(providerID='claude-agent', id='sonnet', name='Retired', status='deprecated')])))
        resolver = DesktopModelCatalog(lambda: client)

        resolved = resolver.resolve(ModelRef('claude-agent', 'sonnet'), '/deleted')

        self.assertEqual(('Sonnet 4.5', 'claude-sonnet-4-5'), (resolved.display_name, resolved.model))
        self.assertEqual('desktop-catalog-estimate', resolved.resolution.kind)
        self.assertIsNone(resolved.resolution.observed_at)
        self.assertEqual(2, client.json.call_count)
        for call in client.json.call_args_list:
            self.assertEqual({'location[directory]': '/deleted'}, call.kwargs['query'])

    def test_missing_alias_provider_invalid_response_and_source_failure_use_exact_fallback(self):
        responses = [
            lambda route, **_: dict(location=dict(directory='/one'), data=[]),
            lambda route, **_: dict(location=dict(directory='/one'),
                data=[dict(id='claude-agent')] if route == '/api/provider' else
                [dict(providerID='other', id='opus', name='Wrong provider', modelID='other-opus')]),
            lambda route, **_: dict(location=dict(directory='/unrelated'),
                data=[dict(id='claude-agent')] if route == '/api/provider' else
                [dict(providerID='claude-agent', id='opus', name='Wrong location', modelID='opus')]),
            lambda *_args, **_kwargs: {'data': 'invalid'},
            Mock(side_effect=SourceDataError('Invalid catalog response')),
        ]
        for response in responses:
            with self.subTest(response=responses.index(response)):
                resolver = DesktopModelCatalog(lambda: Mock(json=response))
                model = resolver.resolve(ModelRef('claude-agent', 'opus'), '/one')
                self.assertEqual('Opus 5.5', model.display_name)
                self.assertEqual('Claude Opus 5.5', model.model)
                self.assertEqual('bundled-catalog-estimate', model.resolution.kind)

    def test_unknown_other_provider_and_pinned_release_never_borrow_snapshot_or_price(self):
        client = Mock(json=Mock(side_effect=http_failure(404, phase='model_identity')))
        resolver = DesktopModelCatalog(lambda: client)
        for provider, selection in [('claude-agent', 'unknown-sonnet'), ('other', 'sonnet'),
                                    ('claude-agent', 'claude-sonnet-5')]:
            with self.subTest(provider=provider, selection=selection):
                model = resolver.resolve(ModelRef(provider, selection), '/deleted')
                self.assertEqual(selection, model.model)
                self.assertIsNone(model.display_name)
                self.assertIsNone(catalog().reference_valuation(model, TokenUsage(input=100)))
                if provider != 'claude-agent' or selection.startswith('claude-'):
                    self.assertIsNone(model.resolution)
                else:
                    self.assertEqual('desktop-catalog-estimate', model.resolution.kind)
        known = resolver.resolve(ModelRef('claude-agent', 'sonnet'), '/deleted')
        self.assertIsNone(catalog().reference_valuation(known, TokenUsage(known_fields=())))
        self.assertEqual('sonnet', known.recorded_model)
        self.assertEqual('claude-sonnet-5-5', known.model)

    def test_missing_malformed_bad_schema_and_invalid_rows_fail_closed_without_crashing_reports(self):
        valid = json.loads(SNAPSHOT_PATH.read_bytes())
        invalid = [None, [], {}, dict(valid, schemaVersion=2), dict(valid, schemaVersion=True),
                   dict(valid, providerID='other'), dict(valid, source='untrusted'),
                   dict(valid, observedAtUtc='not-a-dateZ'), dict(valid, opencodeVersion=''),
                   dict(valid, models='invalid'), dict(valid, models=[{}])]
        for key, value in [('id', ''), ('name', 42), ('modelID', None), ('status', 'unknown')]:
            row = dict(valid['models'][0], **{key: value})
            invalid.append(dict(valid, models=[valid['models'][1], row]))
        payloads = [None, b'{', b'\xff', b' ' * 32769]
        payloads += [json.dumps(value).encode() for value in invalid]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            for index, payload in enumerate(payloads):
                with self.subTest(case=index):
                    if payload is not None:
                        path.write_bytes(payload)
                    original = desktop_service(self, (snapshot(),))
                    original.source.identities.snapshot_path = path
                    original.source.model = None

                    report = original.build(ReportRequest(ReportKind.SESSION, session_id='root-0000'))

                    row = report.prompt_blocks[0].rows[0]
                    self.assertEqual('Claude Sonnet (version unverified)', row.watch_model)
                    self.assertIsNone(row.comparison_cost.ccost)
                    self.assertFalse(row.comparison_cost.complete)
                    self.assertEqual(({}, None), load_snapshot(path))

    def test_snapshot_last_nondeprecated_row_matches_live_semantics_without_inventing_ids(self):
        value = json.loads(SNAPSHOT_PATH.read_bytes())
        value['models'] = [
            dict(id='opaque', name='First 1', modelID='opaque', status='active'),
            dict(id='opaque', name='Last 2', modelID='opaque', status='active'),
            dict(id='opaque', name='Deprecated 3', modelID='opaque', status='deprecated')]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            path.write_text(json.dumps(value), encoding='utf-8')
            resolver = DesktopModelCatalog(lambda: Mock(json=Mock(side_effect=http_failure(404,
                phase='model_identity'))), snapshot_path=path)

            model = resolver.resolve(ModelRef('claude-agent', 'opaque'), '/deleted')

            self.assertEqual('Last 2', model.display_name)
            self.assertEqual('Claude Last 2', model.model)
            self.assertEqual('opaque', model.recorded_model)
            self.assertIsNone(catalog().reference_valuation(model, TokenUsage(input=100)))


if __name__ == '__main__':
    unittest.main()
