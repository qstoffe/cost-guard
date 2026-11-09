"""Previous-schema SQLite entries rebuild only alias-affected conclusions on access."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal as D
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from development.tests.fixtures.claude_alias import LABEL, snapshot, service, reopen, desktop_service, catalog
from development.tests.fixtures.opencode_v2_service import fixture, source_with_service
from development.tests.fixtures.compact_reports import report_service, Availability
from src.sources.opencode_v2 import OpenCodeV2Source
from src.analysis.cache import _source_key, dependency_signature
from src.analysis.session_cost import reconcile_session_cost, NAMESPACE as COST_NAMESPACE, ALGORITHM as COST_ALGORITHM
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportKind, ReportRequest
from src.reports.ai_stats import build_ai_stats
from src.reports.session_summary import session_summary
from src.reports.shared_evidence import flush

ROOT = Path(__file__).resolve().parents[2]


def previous_payload(value):
    """Remove the new optional semantic marker; poison only derived conclusions.

    The original alias IDs/tokens remain available, just as in the prior schema.
    """
    if isinstance(value, list):
        return [previous_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: previous_payload(item) for key, item in value.items() if key != 'model_identity_semantics'}
    if result.get('provider') == 'claude-agent' and result.get('model') == 'sonnet':
        result['display_name'] = 'Claude Sonnet 4' if 'display_name' in result else result.get('display_name')
        if result['display_name'] is None:
            del result['display_name']
    if isinstance(result.get('model'), list) and result['model'][1] == 'sonnet':
        result['model'][2] = 'Claude Sonnet 4'
        result['costs'] = ['123', '0', '0', '0']
    if 'contributor_models' in result and 'claude-agent/sonnet' in result['contributor_models']:
        result.update(model='Claude Sonnet 4', ccost='123', complete=True, ccost_unavailable=[])
    return result


def seed_previous(original):
    for value in original.source.snapshots.values():
        original._analyze(value.root, detail=True)
        session_summary(original, value.root, value.source_revision)
    original.shared_web_evidence = True
    for value in original.source.snapshots.values():
        original._analyze_snapshot(value)
    flush(original)
    repository = original.cache_repository
    with repository.database.connect(operation='read') as connection:
        entries = connection.execute('SELECT namespace, cache_key FROM cache_entries').fetchall()
    for namespace, key in entries:
        entry = repository.get(namespace, key)
        repository.put(namespace, key, previous_payload(deepcopy(entry.payload)),
            source_revision=entry.source_revision, algorithm_version=entry.algorithm_version)


class ClaudeAliasCacheTests(unittest.TestCase):
    def test_catalog_turnover_revalidates_all_compact_caches_without_reloading_pinned_roots(self):
        for mode in ('analysis', 'summary', 'mix', 'stats', 'matches'):
            with self.subTest(mode=mode):
                original = desktop_service(self)
                raw = tuple(original.source.snapshots.values())
                for value in raw:
                    item = original._analyze(value.root, detail=True)
                    session_summary(original, value.root, value.source_revision)
                    original.shared_web_evidence = True
                    original._analyze_snapshot(item.snapshot)
                    original.shared_web_evidence = False
                flush(original)
                fresh = reopen(original, shared=True)
                fresh.source.model, fresh.source.label, fresh.source.clock = 'claude-sonnet-4', 'Sonnet 4', 31
                loads = fresh.source.load_count
                if mode == 'analysis':
                    affected = fresh._analyze(raw[0].root)
                    pinned = fresh._analyze(raw[1].root)
                    self.assertEqual('Sonnet 4', affected.bundle.trace_entries[0].model.display_name)
                    self.assertFalse(affected.cache_hit)
                    self.assertTrue(pinned.cache_hit)
                elif mode == 'summary':
                    row, _ = session_summary(fresh, raw[0].root, raw[0].source_revision)
                    session_summary(fresh, raw[1].root, raw[1].source_revision)
                    self.assertEqual('Sonnet 4', row.model)
                elif mode == 'mix':
                    report = fresh.build_token_mix_history()
                    self.assertIn('Sonnet 4', [row.model for row in report.model_token_mix])
                elif mode == 'stats':
                    build_ai_stats(fresh, 'all')
                else:
                    report = fresh.build(ReportRequest(ReportKind.COMPARISONS))
                    self.assertIn('Sonnet 4', [run.model_label for group in report.comparisons.groups for run in group.runs])
                # Match previews read visible representatives in addition to cache repair.
                self.assertEqual(loads + (2 if mode == 'matches' else 1), fresh.source.load_count)
                self.assertEqual(raw, tuple(fresh.source.snapshots.values()))

    def test_real_v2_wire_cache_restart_uses_exact_location_catalog_and_preserves_raw_alias(self):
        payload = fixture()
        payload['projects'] = payload['projects'][:1]
        payload['sessions']['/repo'] = payload['sessions']['/repo'][:1]
        payload['messages']['ses_root'] = payload['messages']['ses_root'][:2]
        assistant = payload['messages']['ses_root'][1]
        assistant['info'].update(providerID='claude-agent', modelID='sonnet', variant='default')
        payload['desktop_catalogs'] = {'/repo': [dict(providerID='claude-agent', id='sonnet',
            name='Sonnet 5.5', modelID='claude-sonnet-5-5')]}
        with source_with_service(payload) as (source, server, _registration):
            original = report_service(self, source, availability=Availability(None))
            original.pricing_provider.catalog = catalog()
            first = original.build(ReportRequest(ReportKind.SESSIONS, session_limit=None))
            raw = deepcopy(server.fixture['messages'])
            source.close_reads()
            server.fixture['desktop_catalogs']['/repo'][0].update(name='Sonnet 4.5', modelID='claude-sonnet-4-5')
            fresh = reopen(original)
            fresh.source = OpenCodeV2Source(source.registration_path)
            fresh.selection = replace(fresh.selection, source=fresh.source)
            fresh._acquisition.source = fresh.source
            self.addCleanup(fresh.source.close_reads)

            second = fresh.build(ReportRequest(ReportKind.SESSIONS, session_limit=None))
            warm = reopen(fresh).build(ReportRequest(ReportKind.SESSIONS, session_limit=None))

            self.assertEqual('Sonnet 5.5', first.session_usage[0].model)
            self.assertEqual('Sonnet 4.5', second.session_usage[0].model)
            self.assertEqual(second.session_usage[0].model, warm.session_usage[0].model)
            self.assertEqual(second.session_usage[0].ccost, warm.session_usage[0].ccost)
            self.assertEqual(raw, server.fixture['messages'])
            self.assertEqual('sonnet', fresh._analyzed['ses_root'].bundle.trace_entries[0].model.recorded_model)
            catalogs = [path for path, _ in server.requests if path.startswith('/api/model?')]
            self.assertEqual(2, len(catalogs))
            self.assertTrue(all('location%5Bdirectory%5D=%2Frepo' in path for path in catalogs))

    def test_legacy_derived_cache_rejects_alias_but_keeps_unaffected_entry_and_raw_evidence(self):
        original = service(self)
        seed_previous(original)
        fresh = reopen(original)
        dependencies = fresh._dependencies(fresh._load_catalog())
        values = tuple(original.source.snapshots.values())
        affected, unaffected = values
        key = _source_key(affected.root.provenance, affected.root.session_id)
        before = original.cache_repository.get('derived-analysis', key)
        pinned_key = _source_key(unaffected.root.provenance, unaffected.root.session_id)
        pinned_before = original.cache_repository.get('derived-analysis', pinned_key)
        self.assertIn('Claude Sonnet 4', str(before.payload))
        loads = original.source.load_count

        alias = fresh._analyze(affected.root)
        pinned = fresh._analyze(unaffected.root)

        self.assertFalse(alias.cache_hit)
        self.assertTrue(pinned.cache_hit)
        self.assertEqual(loads + 1, original.source.load_count)
        self.assertEqual(pinned_before, original.cache_repository.get('derived-analysis', pinned_key))
        self.assertEqual(values, tuple(original.source.snapshots.values()))
        self.assertEqual('sonnet', alias.bundle.trace_entries[0].model.model)
        self.assertIsNone(alias.bundle.trace_entries[0].model.display_name)
        self.assertEqual(25050, alias.bundle.prompts[0].total_token_volume)
        reopened = CacheRepository(CacheDatabase(original.cache_repository.database.package_root))
        fresh._derived.repository = reopened
        self.assertIsNotNone(fresh._derived.load(provenance=affected.root.provenance,
            root_session_id=affected.root.session_id, source_revision=affected.source_revision,
            dependencies=dependencies))

    def test_legacy_zero_request_summary_cannot_keep_an_unproven_release_label(self):
        from src.reports.session_summary import NAMESPACE, summary_key
        original = service(self, snapshots=(replace(snapshot(), invocations=()),))
        value = next(iter(original.source.snapshots.values()))
        session_summary(original, value.root, value.source_revision)
        key = summary_key(original, value.root)
        entry = original.cache_repository.get(NAMESPACE, key)
        payload = dict(entry.payload, model='Claude Sonnet 4')
        payload.pop('model_identity_semantics')
        original.cache_repository.put(NAMESPACE, key, payload,
            source_revision=entry.source_revision, algorithm_version=entry.algorithm_version)

        row, _revision = session_summary(reopen(original), value.root, value.source_revision)

        self.assertNotEqual('Claude Sonnet 4', row.model)
        self.assertEqual(D(0), row.ccost)

    def test_each_persisted_projection_rebuilds_only_affected_analysis_then_reuses_warm_cache(self):
        for mode in ('summary', 'mix', 'stats', 'comparisons'):
            with self.subTest(mode=mode):
                original = service(self)
                seed_previous(original)
                fresh = reopen(original, shared=True)
                analyzed = []
                analyze = fresh._analyze_snapshot
                def observed(value):
                    analyzed.append(value.root.session_id)
                    return analyze(value)

                with patch.object(fresh, '_analyze_snapshot', side_effect=observed), \
                        patch.object(fresh._acquisition, 'analyzer', side_effect=observed):
                    if mode == 'summary':
                        result = [session_summary(fresh, value.root, value.source_revision)[0]
                                  for value in original.source.snapshots.values()]
                        self.assertEqual(LABEL, result[0].model)
                        self.assertFalse(result[0].complete)
                    elif mode == 'mix':
                        result = fresh.build_token_mix_history()
                        self.assertEqual({LABEL, 'Claude Sonnet 4.5'}, {row.model for row in result.model_token_mix})
                        self.assertEqual(2, result.token_mix.request_count)
                        self.assertEqual(50100, result.token_mix.known_total_tokens)
                        self.assertEqual(1, result.token_mix.priced_requests)
                    elif mode == 'stats':
                        result = build_ai_stats(fresh, 'all')
                    else:
                        result = fresh.build(ReportRequest(ReportKind.COMPARISONS))
                        runs = result.comparisons.groups[0].runs
                        alias = next(run for run in runs if run.model == 'sonnet')
                        self.assertIsNone(alias.ccost)
                        self.assertFalse(alias.cost_complete)
                flush(fresh)
                self.assertEqual(['root-0000'], analyzed)
                self.assertNotIn('Claude Sonnet 4\'', str(result))
                warm = reopen(original, shared=True)
                warm.cache_repository = CacheRepository(CacheDatabase(original.cache_repository.database.package_root))
                warm._derived.repository = warm.cache_repository
                with patch.object(warm, '_analyze_snapshot', side_effect=AssertionError('warm reanalysis')), \
                        patch.object(warm._acquisition, 'analyzer', side_effect=AssertionError('warm reanalysis')):
                    if mode == 'summary':
                        again = [session_summary(warm, value.root, value.source_revision)[0]
                                 for value in original.source.snapshots.values()]
                    elif mode == 'mix':
                        again = warm.build_token_mix_history()
                    elif mode == 'stats':
                        again = build_ai_stats(warm, 'all')
                    else:
                        again = warm.build(ReportRequest(ReportKind.COMPARISONS))
                self.assertEqual(result, again)

    def test_real_process_restarts_do_not_serve_false_historical_labels_in_cli_web_or_watch(self):
        original = service(self)
        seed_previous(original)
        child = '''
import json, sys, unittest
from src.cache import CacheDatabase, CacheRepository
from src.reports import ReportKind, ReportRequest
from src.reports.ai_stats import build_ai_stats
from src.reports.session_summary import session_summary
from src.reports.watch_capture import capture_rows
from src.reports.shared_evidence import flush
from src.application.projection import project
from development.tests.fixtures.compact_reports import rendered
from development.tests.fixtures.claude_alias import service, reopen, desktop_service
from pathlib import Path
test = unittest.TestCase()
original = desktop_service(test) if len(sys.argv) > 2 else service(test)
original.cache_repository = CacheRepository(CacheDatabase(Path(sys.argv[1])))
current = reopen(original, shared=True)
root = current.source.snapshots['root-0000'].root
row, _ = session_summary(current, root, current.source.get_session_tree_revision(root.session_id))
detail = current.build(ReportRequest(ReportKind.SESSION, session_id=root.session_id))
watch, _ = capture_rows(current, root)
mix = current.build_token_mix_history()
stats = build_ai_stats(current, 'all')
comparisons = current.build(ReportRequest(ReportKind.COMPARISONS))
flush(current)
print(json.dumps(dict(model=row.model, complete=row.complete, watch=watch.rows[0].watch_model,
    cli=rendered(detail), web=project(detail).to_json(), mix=project(mix).to_json(),
    stats=project(stats).to_json(), comparisons=project(comparisons).to_json())))
test.doCleanups()
'''
        for desktop in (False, True):
            for _restart in range(2):
                completed = subprocess.run([sys.executable, '-c', child,
                    str(original.cache_repository.database.package_root), *(['desktop'] if desktop else [])], cwd=ROOT,
                    capture_output=True, text=True, encoding='utf-8', timeout=15)
                self.assertEqual(0, completed.returncode, completed.stderr)
                value = json.loads(completed.stdout)
                expected = 'Sonnet 5.5' if desktop else LABEL
                self.assertEqual(expected, value['model'])
                self.assertEqual(expected, value['watch'])
                self.assertEqual(desktop, value['complete'])
                self.assertIn(expected, value['cli'])
                self.assertIn(expected, str(value['comparisons']))
                self.assertNotIn('Claude Sonnet 4"', completed.stdout)

    def test_session_cost_revalues_only_alias_request_not_pinned_contribution(self):
        original = service(self)
        first, second = original.source.snapshots.values()
        mixed = replace(first, invocations=(*first.invocations, *second.invocations))
        reference = original._load_catalog()
        reconcile_session_cost(original.cache_repository, mixed, reference)
        p = mixed.root.provenance
        key = dependency_signature((p.source_type, p.source_generation, p.source_instance,
            mixed.root.session_id, COST_ALGORITHM, reference.analysis_signature))
        entry = original.cache_repository.get(COST_NAMESPACE, key)
        value = entry.payload
        from src.analysis.causal import trace_entries
        alias = trace_entries(mixed)[0]
        identity = dependency_signature((alias.source_instance, alias.session_id, mixed.invocations[0].invocation_id))
        value['contributions'][identity] = dict(fingerprint=dependency_signature((alias.model,
            alias.tokens, alias.completed_at_ms)), amount='123')
        value.update(known_ccost=str(D('123') + D('6.89')), priced_requests=2)
        original.cache_repository.put(COST_NAMESPACE, key, value, source_revision=entry.source_revision,
            algorithm_version=entry.algorithm_version)

        result = reconcile_session_cost(original.cache_repository, mixed, reference)

        self.assertEqual(1, result.valued_requests)
        self.assertEqual(2, result.total.observed_requests)
        self.assertEqual(1, result.total.priced_requests)
        self.assertEqual(D('6.89'), result.total.known_ccost)
        self.assertFalse(result.total.complete)


if __name__ == '__main__':
    unittest.main()
