"""Real HTTP/facade/asset integration with a no-browser JavaScript DOM harness.

Node is optional developer tooling, never a product or build dependency.
"""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Event, Thread
import unittest

from development.tests.fixtures.report_runtime import FakeAccountProvider, FakePricingProvider, FakeSource
from development.tests.fixtures.session_snapshots import make_snapshot, make_uncompacted_snapshot
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.pricing_catalog import threshold_catalog
from development.tests.fixtures.accounts import account, NormalizedProvider
from src.application import ReportApplication
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.reports import ReportKind, ReportRequest, ReportService
from src.sources.selection import SourceSelection
from src.web.http import LoopbackServer

ROOT = Path(__file__).resolve().parents[2]


class WebViewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "optional JavaScript test runtime unavailable")
    def test_assets_navigation_snapshot_paging_and_faults_through_real_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = CacheDatabase(Path(tmp))
            database.initialize()
            cache = CacheRepository(database)
            config = dict(load_configuration(ROOT).values, timezone="UTC")
            source = SyntheticMonthSource(55, 151, month_start_ms=1000, running_roots=1)
            now = 10_000_000
            provider = None

            def factory(clock, progress):
                return ReportService(selection=SourceSelection(source, "v1", (), source.probe()),
                    pricing_provider=FakePricingProvider(), account_provider=provider,
                    cache_repository=cache, config=config, now_ms=clock, progress=progress)

            application = ReportApplication(factory, clock=lambda: now)
            examples = []
            for index, snapshot in enumerate((make_snapshot(), make_uncompacted_snapshot(running=True))):
                source = FakeSource(replace(snapshot, source_revision=f"example-{index}"))
                result = application.execute(ReportRequest(ReportKind.SESSION, session_id="root")).to_json()
                self.assertIsNone(result["error"])
                examples.append(result)
            # Preserve the canonical source projection, but use malicious text as actual input.
            snapshot = make_uncompacted_snapshot()
            snapshot = replace(snapshot, source_revision="hostile-aborted",
                root=replace(snapshot.root, title='<img src=x onerror=alert(1)> Å日本語'),
                sessions=tuple(replace(s, title='<img src=x onerror=alert(1)> Å日本語')
                               if s.session_id == "root" else s for s in snapshot.sessions),
                events=tuple(replace(e, text='<script>hostile</script>') if e.event_id == "u_next" else e
                             for e in snapshot.events),
                messages=tuple(replace(m, error_name="MessageAbortedError") if m.message_id == "a_next" else m
                               for m in snapshot.messages))
            source = FakeSource(snapshot)
            examples.append(application.execute(ReportRequest(ReportKind.SESSION, session_id="root")).to_json())
            # Unknown reference prices and a partial source stay visible, not priced zero.
            original_factory = factory

            def partial_factory(clock, progress):
                service = original_factory(clock, progress)
                service.selection = replace(service.selection, warnings=("synthetic partial source",))
                pricing = FakePricingProvider()
                pricing.catalog = replace(pricing.catalog, models=())
                service.pricing_provider = pricing
                service.comparison_pricing_provider = pricing
                return service

            examples.append(ReportApplication(partial_factory, clock=lambda: now).execute(
                ReportRequest(ReportKind.SESSION, session_id="root")).to_json())
            provider = FakeAccountProvider()
            overview = application.execute(ReportRequest()).to_json()
            self.assertIsNone(overview["error"])
            self.assertTrue(overview["view"]["accounts_quotas"]["accounts"])

            def tier_factory(clock, progress):
                service = factory(clock, progress)
                pricing = FakePricingProvider()
                pricing.catalog = threshold_catalog()
                service.pricing_provider = pricing
                service.comparison_pricing_provider = pricing
                return service

            tier_report = ReportApplication(tier_factory, clock=lambda: now).execute(
                ReportRequest(ReportKind.ALL_MODELS)).to_json()
            self.assertIsNone(tier_report["error"])

            def account_factory(clock, progress):
                service = factory(clock, progress)
                service.account_providers = (
                    NormalizedProvider(account("github-copilot", "first", label="First")),
                    NormalizedProvider(replace(account("github-copilot", "second", label="Second"),
                        availability="error", observations={"parser_reason": "unsupported_auth_method"})),
                )
                return service

            account_report = ReportApplication(account_factory, clock=lambda: now).execute(ReportRequest()).to_json()
            self.assertIsNone(account_report["error"])
            self.assertEqual(2, len(account_report["view"]["accounts_quotas"]["accounts"]))
            provider = None
            source = SyntheticMonthSource(55, 1, month_start_ms=1000)
            # Pagination needs 55 roots and one 151-row running detail, not
            # 8,305 prompt analyses behind every UI wait on hosted Intel.
            source.snapshots['root-0000'] = SyntheticMonthSource(
                1, 151, month_start_ms=1000, running_roots=1).snapshots['root-0000']
            # Existing empty session differs from missing catalog entry.
            empty = source.snapshots["root-0001"]
            source.snapshots["root-0001"] = replace(empty, messages=(), parts=(), events=(), invocations=())
            # Analysis cold-start belongs to the report/performance tests. Warm
            # the dependency cache before the VM's fixed 5s UI assertions.
            # Full large-month analysis remains in the performance owner tests.
            for warm in (ReportRequest(), ReportRequest(ReportKind.SESSIONS, session_limit=None),
                         ReportRequest(ReportKind.ALL_MODELS), ReportRequest(ReportKind.TOKEN_MIX)):
                self.assertIsNone(application.execute(warm).error)

            class Jobs:
                def __init__(self):
                    self.results = {}
                    self.work = ThreadPoolExecutor(max_workers=1)
                    self.futures = []

                def readiness(self):
                    return dict(http="ready", source="not_acquired", accounts="not_acquired", analysis="not_requested")

                def submit(self, request):
                    key = f"{len(self.results) + 1:032x}"
                    self.results[key] = dict(id=key, status="running", result=None,
                                            error=None, progress={"phase": "fixture"})
                    self.futures.append(self.work.submit(self.execute, key, request))
                    return key

                def execute(self, key, request):
                    nonlocal now, source
                    now += 1000
                    result = application.execute(request).to_json()
                    if request.session_id == "root-0000" and len(source.snapshots["root-0000"].events) == 151:
                        # New events arrive after capture. Already-published result must stay frozen.
                        source.snapshots["root-0000"] = replace(make_root_snapshot(0, 152, month_start_ms=1000),
                            source_revision="inserted-after-snapshot")
                    self.results[key] = dict(id=key, status="failed" if result["error"] else "complete",
                        result=result, error=None, progress={"phase": "finalizing"})

                def snapshot(self, key):
                    return self.results.get(key)

            jobs = Jobs()
            server = LoopbackServer(jobs)
            stopped = Event()

            def serve():
                while not stopped.is_set():
                    server.handle_request()

            thread = Thread(target=serve)
            thread.start()
            try:
                payload = dict(origin=server.origin, credential=server.session.bootstrap(), examples=examples,
                               overview=overview, tier_report=tier_report, account_report=account_report)
                result = subprocess.run([shutil.which("node"), "development/tests/integration/web_views.cjs"],
                    cwd=ROOT, input=json.dumps(payload), text=True, capture_output=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("web views passed", result.stdout)
                self.assertGreaterEqual(len(jobs.results), 5)
            finally:
                stopped.set()
                thread.join(3)
                server.server_close()
                jobs.work.shutdown(wait=True)
                for future in jobs.futures:
                    future.result()
                self.assertFalse(thread.is_alive())

    def test_missing_and_empty_sessions_have_distinct_application_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = CacheDatabase(Path(tmp))
            database.initialize()
            source = FakeSource(make_snapshot())
            source.snapshot = replace(source.snapshot, messages=(), parts=(), events=(), invocations=())

            def factory(now, progress):
                return ReportService(selection=SourceSelection(source, "v1", (), source.probe()),
                    pricing_provider=FakePricingProvider(), account_provider=None,
                    cache_repository=CacheRepository(database), config=load_configuration(ROOT).values,
                    now_ms=now, progress=progress)

            application = ReportApplication(factory, clock=lambda: 4000)
            missing = application.execute(ReportRequest(ReportKind.SESSION, session_id="missing"))
            empty = application.execute(ReportRequest(ReportKind.SESSION, session_id="root"))
            self.assertEqual("session_not_found", missing.error.code)
            self.assertIsNone(empty.error)
            self.assertEqual([], empty.to_json()["view"]["prompt_blocks"][0]["rows"])


if __name__ == "__main__":
    unittest.main()
