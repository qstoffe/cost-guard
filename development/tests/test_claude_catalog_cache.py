"""Snapshot/live turnover rebuilds only alias-dependent conclusions, including restarts."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from development.tests.fixtures.claude_alias import catalog, desktop_service, reopen
from development.tests.fixtures.compact_reports import Availability, report_service
from development.tests.fixtures.opencode_v2_service import fixture, source_with_service
from src.analysis.cache import _source_key
from src.cache import CacheDatabase, CacheRepository
from src.domain import ModelRef
from src.reports import ReportKind, ReportRequest
from src.reports.ai_stats import build_ai_stats
from src.reports.session_summary import session_summary
from src.reports.shared_evidence import flush
from src.sources.claude_agent_catalog import SNAPSHOT_PATH
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.opencode_v2_model_identity import DesktopModelCatalog

ROOT = Path(__file__).resolve().parents[2]


class ClaudeCatalogCacheTests(unittest.TestCase):
    def test_absent_snapshot_recovers_after_30_seconds_then_source_recreation_reuses_persisted_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            original = desktop_service(self)
            original.source.model = None
            original.source.identities.snapshot_path = path
            request = ReportRequest(ReportKind.SESSIONS, session_limit=None)
            raw = deepcopy(original.source.snapshots)

            before = original.build(request)
            path.write_bytes(SNAPSHOT_PATH.read_bytes())
            cached = reopen(original).build(request)
            original.source.clock = 31
            recovered = reopen(original).build(request)
            original.source.identities = DesktopModelCatalog(lambda: original.source,
                clock=lambda: original.source.clock, snapshot_path=path)
            fresh = reopen(original)
            fresh.cache_repository = CacheRepository(CacheDatabase(original.cache_repository.database.package_root))
            fresh._derived.repository = fresh.cache_repository
            loads = original.source.load_count
            restarted = fresh.build(request)
            warm = reopen(fresh).build(request)

            self.assertEqual('Claude Sonnet (version unverified)',
                next(row.model for row in before.session_usage if row.session_id == 'root-0000'))
            facts = lambda report: tuple((row.session_id, row.model, row.ccost, row.complete)
                for row in report.session_usage)
            self.assertEqual(facts(before), facts(cached))
            self.assertEqual('Claude Sonnet 5.5',
                next(row.model for row in recovered.session_usage if row.session_id == 'root-0000'))
            self.assertEqual(facts(recovered), facts(restarted))
            self.assertEqual(facts(restarted), facts(warm))
            self.assertEqual(loads, original.source.load_count)
            self.assertEqual(raw, original.source.snapshots)

    def test_snapshot_to_live_turnover_revalidates_compact_caches_but_not_pinned_history(self):
        for mode in ('analysis', 'summary', 'mix', 'stats', 'matches'):
            with self.subTest(mode=mode):
                original = desktop_service(self)
                original.source.model = None
                raw = tuple(original.source.snapshots.values())
                for value in raw:
                    item = original._analyze(value.root, detail=True)
                    session_summary(original, value.root, value.source_revision)
                    original.shared_web_evidence = True
                    original._analyze_snapshot(item.snapshot)
                    original.shared_web_evidence = False
                flush(original)
                pinned_key = _source_key(raw[1].root.provenance, raw[1].root.session_id)
                pinned_before = original.cache_repository.get('derived-analysis', pinned_key)
                fresh = reopen(original, shared=True)
                fresh.source.model, fresh.source.label, fresh.source.clock = 'claude-sonnet-4-5', 'Sonnet 4.5', 31
                loads = fresh.source.load_count

                if mode == 'analysis':
                    affected = fresh._analyze(raw[0].root)
                    pinned = fresh._analyze(raw[1].root)
                    self.assertEqual('Sonnet 4.5', affected.bundle.trace_entries[0].model.display_name)
                    self.assertEqual('desktop-catalog-estimate', affected.bundle.trace_entries[0].model.resolution.kind)
                    self.assertFalse(affected.cache_hit)
                    self.assertTrue(pinned.cache_hit)
                elif mode == 'summary':
                    row, _ = session_summary(fresh, raw[0].root, raw[0].source_revision)
                    session_summary(fresh, raw[1].root, raw[1].source_revision)
                    self.assertEqual('Claude Sonnet 4.5', row.model)
                elif mode == 'mix':
                    result = fresh.build_token_mix_history()
                    self.assertNotIn('Sonnet 5.5', [row.model for row in result.model_token_mix])
                    self.assertIn('Claude Sonnet 4.5', [row.model for row in result.model_token_mix])
                elif mode == 'stats':
                    build_ai_stats(fresh, 'all')
                else:
                    result = fresh.build(ReportRequest(ReportKind.COMPARISONS))
                    self.assertIn('Claude Sonnet 4.5',
                        [run.model_label for group in result.comparisons.groups for run in group.runs])

                self.assertEqual(loads + (2 if mode == 'matches' else 1), fresh.source.load_count)
                self.assertEqual(pinned_before, original.cache_repository.get('derived-analysis', pinned_key))
                self.assertEqual(raw, tuple(original.source.snapshots.values()))

    def test_snapshot_refresh_and_identical_live_label_change_only_dependent_signatures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            value = json.loads(SNAPSHOT_PATH.read_bytes())
            path.write_text(json.dumps(value), encoding='utf-8')
            original = desktop_service(self)
            source = original.source
            source.model = None
            source.identities.snapshot_path = path
            alias = source.identities.resolve(ModelRef('claude-agent', 'sonnet'), '/synthetic')
            pinned = source.identities.resolve(ModelRef('claude-agent', 'claude-sonnet-5'), '/synthetic')
            other = source.identities.resolve(ModelRef('other', 'sonnet'), '/synthetic')
            value['models'][1].update(name='Sonnet 4.5', modelID='claude-sonnet-4-5')
            path.write_text(json.dumps(value), encoding='utf-8')
            source.clock = 29
            self.assertTrue(source.identities.current((alias, pinned, other)))
            source.clock = 30

            self.assertFalse(source.identities.current((alias,)))
            self.assertTrue(source.identities.current((pinned, other)))
            refreshed = source.identities.resolve(ModelRef('claude-agent', 'sonnet'), '/synthetic')
            self.assertEqual('Sonnet 4.5', refreshed.display_name)
            self.assertEqual('bundled-catalog-estimate', refreshed.resolution.kind)
            source.model, source.label, source.clock = 'claude-sonnet-4-5', 'Sonnet 4.5', 60
            self.assertFalse(source.identities.current((refreshed,)))
            live = source.identities.resolve(ModelRef('claude-agent', 'sonnet'), '/synthetic')
            self.assertEqual(refreshed.display_name, live.display_name)
            self.assertNotEqual(refreshed.resolution.signature, live.resolution.signature)
            self.assertEqual('desktop-catalog-estimate', live.resolution.kind)
            self.assertTrue(source.identities.current((pinned, other)))

    def test_real_v2_http_404_cache_and_cold_source_restart_recover_to_live_without_history_edits(self):
        payload = fixture()
        payload['projects'] = payload['projects'][:1]
        payload['sessions']['/repo'] = payload['sessions']['/repo'][:1]
        payload['messages']['ses_root'] = payload['messages']['ses_root'][:2]
        payload['messages']['ses_root'][1]['info'].update(providerID='claude-agent', modelID='sonnet', variant='default')
        payload['desktop_catalog_status'] = {'/api/provider': 404, '/api/model': 404}
        payload['desktop_catalogs'] = {'/repo': [dict(providerID='claude-agent', id='sonnet',
            name='Sonnet 4.5', modelID='claude-sonnet-4-5')]}
        with source_with_service(payload) as (source, server, _registration):
            original = report_service(self, source, availability=Availability(None))
            original.pricing_provider.catalog = catalog()
            request = ReportRequest(ReportKind.SESSIONS, session_limit=None)
            raw = deepcopy(server.fixture['messages'])

            fallback = original.build(request)
            warm = reopen(original).build(request)
            source.close_reads()
            fresh = reopen(original)
            fresh.source = OpenCodeV2Source(source.registration_path)
            fresh.selection = replace(fresh.selection, source=fresh.source)
            fresh._acquisition.source = fresh.source
            self.addCleanup(fresh.source.close_reads)
            restarted = fresh.build(request)
            fresh.source.close_reads()
            server.fixture['desktop_catalog_status'] = {}
            recovered = reopen(fresh)
            recovered.source = OpenCodeV2Source(source.registration_path)
            recovered.selection = replace(recovered.selection, source=recovered.source)
            recovered._acquisition.source = recovered.source
            self.addCleanup(recovered.source.close_reads)
            live = recovered.build(request)

            self.assertEqual('Claude Sonnet 5.5', fallback.session_usage[0].model)
            self.assertEqual(fallback.session_usage[0].model, warm.session_usage[0].model)
            self.assertEqual(fallback.session_usage[0].model, restarted.session_usage[0].model)
            self.assertEqual('Claude Sonnet 4.5', live.session_usage[0].model)
            self.assertEqual(raw, server.fixture['messages'])
            catalogs = [path for path, _ in server.requests if path.startswith(('/api/provider?', '/api/model?'))]
            self.assertTrue(catalogs)
            self.assertTrue(all('location%5Bdirectory%5D=%2Frepo' in path for path in catalogs))

    def test_packaged_runtime_asset_works_offline_from_unrelated_cwd_in_two_cold_processes(self):
        child = '''
import json, sys
sys.path.insert(0, sys.argv[1])
from src.domain import ModelRef
from src.sources.errors import http_failure
from src.sources.opencode_v2_model_identity import DesktopModelCatalog
class Offline:
    def json(self, *args, **kwargs):
        raise http_failure(404, phase="model_identity")
resolver = DesktopModelCatalog(Offline)
print(json.dumps([(m.display_name, m.recorded_model, m.resolution.kind)
    for m in [resolver.resolve(ModelRef("claude-agent", alias), "/deleted")
              for alias in ("sonnet", "opus", "haiku", "fable")]]))
'''
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / 'installed'
            shutil.copytree(ROOT / 'src', package / 'src', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            for _restart in range(2):
                result = subprocess.run([sys.executable, '-c', child, str(package)], cwd=directory,
                    capture_output=True, text=True, encoding='utf-8', timeout=15)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual([
                    ['Sonnet 5.5', 'sonnet', 'bundled-catalog-estimate'],
                    ['Opus 5.5', 'opus', 'bundled-catalog-estimate'],
                    ['Haiku 5.5', 'haiku', 'bundled-catalog-estimate'],
                    ['Fable 5.1', 'fable', 'bundled-catalog-estimate']], json.loads(result.stdout))


if __name__ == '__main__':
    unittest.main()
