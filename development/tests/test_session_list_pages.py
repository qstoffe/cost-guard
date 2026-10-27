"""Bounded Web pages use CLI root order and reject catalog drift, never offset silently."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from development.tests.fixtures.report_runtime import FakePricingProvider
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.reports import ReportKind, ReportRequest, ReportService
from src.sources.selection import SourceSelection
from src.web.jobs import parse_report

ROOT = Path(__file__).resolve().parents[2]


class SessionListPagesTests(unittest.TestCase):
    def test_pages_match_cli_order_totals_fields_and_hydrate_only_selected_roots(self):
        for count in (0, 1, 100, 1001):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as tmp:
                source = SyntheticMonthSource(count, 1, month_start_ms=1000, running_roots=1)
                database = CacheDatabase(Path(tmp))
                database.initialize()
                services = []

                def factory(now, progress):
                    service = ReportService(selection=SourceSelection(source, 'v1', (), source.probe()),
                        pricing_provider=FakePricingProvider(), account_provider=None,
                        cache_repository=CacheRepository(database), config=load_configuration(ROOT).values,
                        now_ms=now, progress=progress)
                    services.append(service)
                    return service

                app = ReportApplication(factory, clock=lambda: 10_000_000)
                first = app.execute(parse_report(dict(kind='sessions', session_page_size=50))).to_json()
                self.assertIsNone(first['error'])
                page = first['view']['session_page']
                self.assertEqual(count, page['total'])
                self.assertLessEqual(len(services[-1]._analyzed), 50)
                self.assertEqual([], first['view']['request_identities'])
                # Independent CLI ordering rule: activity descending, root id descending.
                expected = sorted(source.snapshots.values(), key=lambda s: (s.root.updated_at_ms, s.root.session_id), reverse=True)
                self.assertEqual([s.root.session_id for s in expected[:50]],
                                 [r['session_id'] for r in first['view']['session_usage']])
                if count >= 100:
                    second = app.execute(parse_report(dict(kind='sessions', session_page_size=50,
                        session_offset=50, session_catalog_revision=page['catalog_revision']))).to_json()
                    self.assertIsNone(second['error'])
                    self.assertLessEqual(len(services[-1]._analyzed), 50)
                    self.assertEqual([s.root.session_id for s in expected[50:100]],
                                     [r['session_id'] for r in second['view']['session_usage']])
                    cli = app.execute(ReportRequest(ReportKind.SESSIONS, session_limit=100)).to_json()
                    self.assertEqual(cli['view']['session_usage'], first['view']['session_usage'] + second['view']['session_usage'])

    def test_catalog_changes_archives_partial_and_out_of_bounds_are_honest(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = SyntheticMonthSource(100, 1, month_start_ms=1000)
            database = CacheDatabase(Path(tmp))
            database.initialize()
            snapshot = source.snapshots['root-0000']
            archived = replace(snapshot.root, archived_at_ms=2000)
            source.snapshots['root-0000'] = replace(snapshot, root=archived,
                sessions=tuple(archived if s.session_id == archived.session_id else s for s in snapshot.sessions))

            def factory(now, progress):
                return ReportService(selection=SourceSelection(source, 'v1', ('partial fixture',), source.probe()),
                    pricing_provider=FakePricingProvider(), account_provider=None,
                    cache_repository=CacheRepository(database), config=load_configuration(ROOT).values,
                    now_ms=now, progress=progress)

            app = ReportApplication(factory, clock=lambda: 10_000_000)
            first = app.execute(parse_report(dict(kind='sessions', session_page_size=50))).to_json()
            self.assertEqual('partial', first['source']['status'])
            revision = first['view']['session_page']['catalog_revision']
            request = dict(kind='sessions', session_page_size=50, session_offset=50, session_catalog_revision=revision)
            second = app.execute(parse_report(request)).to_json()
            self.assertTrue(next(r for r in second['view']['session_usage'] if r['session_id'] == 'root-0000')['archived'])
            beyond = app.execute(parse_report(dict(request, session_offset=100))).to_json()
            self.assertEqual('report_unavailable', beyond['error']['code'])
            del source.snapshots['root-0000']
            changed = app.execute(parse_report(request)).to_json()
            self.assertEqual('session_catalog_changed', changed['error']['code'])
            self.assertIsNone(changed['view'])
            source.snapshots['root-0000'] = replace(snapshot, root=archived,
                sessions=tuple(archived if s.session_id == archived.session_id else s for s in snapshot.sessions))
            source.snapshots['root-0100'] = SyntheticMonthSource(101, 1, month_start_ms=1000).snapshots['root-0100']
            added = app.execute(parse_report(request)).to_json()
            self.assertEqual('session_catalog_changed', added['error']['code'])
            del source.snapshots['root-0100']
            original = source.snapshots['root-0000']
            moved = replace(original.root, provenance=replace(original.root.provenance, source_instance='different-source'))
            source.snapshots['root-0000'] = replace(original, root=moved)
            source_changed = app.execute(parse_report(request)).to_json()
            self.assertEqual('session_catalog_changed', source_changed['error']['code'])

    def test_request_bounds_and_cursor_validation(self):
        for value in (dict(session_page_size=True), dict(session_page_size=101), dict(session_offset=-1),
                      dict(session_offset=50), dict(session_catalog_revision='bad'), dict(session_offset=True)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_report(dict(kind='sessions', **value))
        with self.assertRaises(ValueError):
            parse_report(dict(kind='normal', session_page_size=50))


if __name__ == '__main__':
    unittest.main()
