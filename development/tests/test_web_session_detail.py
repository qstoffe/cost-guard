"""Complete session paging, report parity and shared live observation contracts."""
from dataclasses import replace
import json
import http.client
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from development.tests.fixtures.report_runtime import FakePricingProvider, FakeSource
from development.tests.fixtures.session_snapshots import make_snapshot, make_uncompacted_snapshot
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.application.projection import project
from src.application.session_detail import SessionDetails
from src.analysis.causal import _root_timeline, prompt_parent_ids
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import EventKind
from src.reports import ReportKind, ReportRequest, ReportService
from src.sources.selection import SourceSelection
from src.web.http import LoopbackServer

ROOT = Path(__file__).resolve().parents[2]


class SessionDetailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        database = CacheDatabase(Path(self.tmp.name))
        database.initialize()
        self.cache = CacheRepository(database)
        self.now = 100_000_000
        self.clock = 0
        self.details = SessionDetails(clock=lambda: self.clock)

    def service(self, source):
        return ReportService(selection=SourceSelection(source, "v1", (), source.probe()),
            pricing_provider=FakePricingProvider(), account_provider=None, cache_repository=self.cache,
            config=dict(load_configuration(ROOT).values, timezone="UTC"), now_ms=self.now)

    def tick(self, service, **kwargs):
        self.clock += 6
        service.set_now_ms(self.now)
        self.details.tick(service, **kwargs)

    def test_scale_all_rows_totals_bounded_pages_and_unchanged_work(self):
        for count in (100, 1000, 10000):
            with self.subTest(count=count):
                source = SyntheticMonthSource(1, count, month_start_ms=1000)
                service = self.service(source)
                self.details = SessionDetails(clock=lambda: self.clock)
                token = self.details.open("root-0000", "live")
                self.tick(service)
                first = self.details.page(token, 0)
                self.assertEqual(first["total"], count)
                self.assertEqual(len(first["result"]["view"]["prompt_blocks"][0]["rows"]), 50)
                for offset in (0, count // 2, count - 50):
                    page = self.details.page(token, offset)
                    block = page["result"]["view"]["prompt_blocks"][0]
                    self.assertEqual(block["rows"][0]["event_id"], f"root-0000-u-{offset:04d}")
                    self.assertEqual(block["total_calls"], count)
                    self.assertLess(len(json.dumps(page)), 200_000)
                loads = source.load_count
                analyses = service.metrics.counts.get("analyzed_prompts", 0)
                for _ in range(10):
                    self.details.tick(service)  # Timer-only ticks must not acquire/revalue.
                self.assertEqual(source.load_count, loads)
                self.tick(service)  # Even a due stable revision reuses analysis.
                self.assertEqual(source.load_count, loads)
                self.assertEqual(service.metrics.counts.get("analyzed_prompts", 0), analyses)
                source.snapshots["root-0000"] = replace(make_root_snapshot(0, count + 1, month_start_ms=1000),
                                                        source_revision="next")
                self.tick(service)
                middle = self.details.page(token, count // 2)
                anchor = middle["result"]["view"]["prompt_blocks"][0]["rows"][0]["id"]
                changed = self.details.page(token, count // 2, first["revision"], anchor)
                self.assertTrue(changed["stale_cursor"])
                self.assertEqual(changed["total"], count + 1)
                self.assertEqual(changed["offset"], count // 2)
                self.assertEqual(self.details.page(token, 2**52)["offset"], count + 1 - 50)

    def test_parity_snapshot_freeze_running_compaction_abort_and_partial_prices(self):
        for index, snapshot in enumerate((make_snapshot(), make_uncompacted_snapshot(running=True))):
            snapshot = replace(snapshot, source_revision=f"parity-{index}")
            with self.subTest(revision=snapshot.source_revision):
                source = FakeSource(snapshot)
                service = self.service(source)
                self.details = SessionDetails(clock=lambda: self.clock)
                live = self.details.open("root", "live")
                self.tick(service)
                page = self.details.page(live, 0)
                canonical = project(self.service(source).build(ReportRequest(ReportKind.SESSION, "root"))).to_json()
                for row in page["result"]["view"]["prompt_blocks"][0]["rows"]:
                    row.pop("id")
                    row.pop("last_observed_at_ms")
                    row.pop("retained")
                self.assertEqual(page["result"]["view"], canonical)
                self.details.freeze(live)
                frozen = self.details.page(live, 0)
                self.now += 10000
                self.tick(service)
                self.assertEqual(self.details.page(live, 0), frozen)
                entering = self.details.open("root", "live")
                self.assertIsNone(self.details.page(entering, 0)["result"])
                self.tick(service)
                self.assertIsNotNone(self.details.page(entering, 0)["result"])

    def test_omission_outage_missing_reconnect_and_multitab_share_analysis(self):
        source = SyntheticMonthSource(1, 100, month_start_ms=1000)
        service = self.service(source)
        a = self.details.open("root-0000", "live")
        b = self.details.open("root-0000", "live")
        self.tick(service)
        self.assertEqual(source.load_count, 1)
        before = self.details.page(a, 0)
        self.assertEqual(self.details.page(b, 0), before)
        snapshot = source.snapshots["root-0000"]
        source.snapshots["root-0000"] = replace(snapshot, events=snapshot.events[50:],
            messages=snapshot.messages[100:], parts=snapshot.parts[50:],
            invocations=snapshot.invocations[50:], source_revision="compacted")
        self.tick(service)
        retained = self.details.page(a, 0)
        self.assertEqual(retained["total"], 100)
        self.assertEqual(retained["state"], "history_retained")
        self.assertEqual(retained["result"]["view"]["prompt_blocks"][0]["total_ccost"],
                         before["result"]["view"]["prompt_blocks"][0]["total_ccost"])
        self.tick(service, unavailable=True)
        outage = self.details.page(a, 0)
        self.assertEqual(outage["state"], "source_unavailable")
        self.assertEqual(outage["total"], 100)
        del source.snapshots["root-0000"]
        self.tick(service)
        self.assertEqual(self.details.page(a, 0)["state"], "session_missing")
        source.snapshots["root-0000"] = replace(snapshot, source_revision="reconnected")
        self.tick(service)
        self.assertEqual(self.details.page(a, 0)["state"], "observed")
        self.assertEqual(self.details.page(a, 0)["total"], 100)

    @unittest.skipUnless(shutil.which("node"), "optional JavaScript test runtime unavailable")
    def test_client_bounded_dom_selection_focus_and_transitions(self):
        source = SyntheticMonthSource(1, 100, month_start_ms=1000)
        service = self.service(source)
        token = self.details.open("root-0000", "live")
        self.tick(service)
        first = self.details.page(token, 0)
        source.snapshots["root-0000"] = replace(make_root_snapshot(0, 101, month_start_ms=1000),
                                                source_revision="appended")
        self.tick(service)
        changed = self.details.page(token, 0)
        latest = self.details.page(token, 2**52)
        result = subprocess.run([shutil.which("node"), "development/tests/integration/web_session.cjs"],
            input=json.dumps(dict(first=first, changed=changed, latest=latest)),
            cwd=ROOT, capture_output=True, text=True, timeout=20, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_authenticated_http_detail_admission_paging_and_freeze(self):
        from src.web.observations import WebObservations

        service = self.service(SyntheticMonthSource(1, 100, month_start_ms=1000))
        lifecycle = SimpleNamespace(root=ROOT, nonce='detail-fixture', observations=WebObservations(),
                                    live=SimpleNamespace(details=self.details), stopping=Event())
        server = LoopbackServer(SimpleNamespace(), lifecycle)
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            cookie, csrf = None, None

            def post(body, *, authorized=True):
                connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
                headers = {"Origin": server.origin, "Content-Type": "application/json"}
                if cookie:
                    headers["Cookie"] = cookie
                if csrf and authorized:
                    headers["X-CG-CSRF"] = csrf
                path = "/api/detail" if cookie else "/api/bootstrap"
                connection.request("POST", path, json.dumps(body), headers)
                response = connection.getresponse()
                data = json.loads(response.read())
                status, session = response.status, response.getheader("Set-Cookie")
                connection.close()
                return status, data, session

            status, auth, session = post({"credential": server.session.bootstrap()})
            self.assertEqual(status, 200)
            cookie, csrf = session.split(";")[0], auth["csrf"]
            self.assertEqual(post({"action": "open", "session_id": "root-0000", "mode": "live"},
                                  authorized=False)[0], 403)
            status, opened, _ = post({"action": "open", "session_id": "root-0000", "mode": "live"})
            self.assertEqual(status, 200)
            token = opened["token"]
            self.tick(service)
            status, page, _ = post({"action": "page", "token": token, "offset": 50})
            self.assertEqual(status, 200)
            self.assertEqual(page["total"], 100)
            self.assertEqual(page["offset"], 50)
            self.assertEqual(post({"action": "freeze", "token": token})[0], 200)
            self.assertEqual(post({"action": "page", "token": token, "offset": True})[0], 400)
            self.assertEqual(post({"action": "page", "token": "expired"})[0], 410)
            self.assertEqual(post({"action": "close", "token": token})[0], 200)
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()

    def test_retained_running_row_never_gains_time_or_terminal_evidence(self):
        source = SyntheticMonthSource(1, 3, month_start_ms=1000, running_roots=1)
        service = self.service(source)
        token = self.details.open("root-0000", "live")
        self.tick(service)
        before = self.details.page(token, 0)["result"]["view"]["prompt_blocks"][0]["rows"][-1]
        self.assertTrue(before["in_progress"])
        snapshot = source.snapshots["root-0000"]
        source.snapshots["root-0000"] = replace(snapshot, messages=snapshot.messages[:-2],
            parts=snapshot.parts[:-1], events=snapshot.events[:-1], invocations=snapshot.invocations[:-1],
            source_revision="running-history-omitted")
        self.now += 10_000
        self.tick(service)
        row = self.details.page(token, 0)["result"]["view"]["prompt_blocks"][0]["rows"][-1]
        self.assertTrue(row["retained"])
        self.assertTrue(row["in_progress"])
        self.assertIsNone(row["completed_at_ms"])
        self.assertEqual(row["duration_ms"], before["duration_ms"])
        self.assertEqual(row["last_observed_at_ms"], before["last_observed_at_ms"])

    def test_unchanged_running_evidence_advances_only_shared_execution_clock(self):
        source = SyntheticMonthSource(1, 100, month_start_ms=1000, running_roots=1)
        service = self.service(source)
        token = self.details.open("root-0000", "live")
        self.tick(service)
        before = self.details.page(token, 2**52)["result"]["view"]["prompt_blocks"][0]
        self.now += 10000
        with patch.object(service, "_analyze_snapshot", side_effect=AssertionError("reanalysis")), \
                patch.object(service, "_prompt_block", side_effect=AssertionError("revaluation")):
            self.tick(service)
        after = self.details.page(token, 2**52)["result"]["view"]["prompt_blocks"][0]
        self.assertEqual(after["total_ccost"], before["total_ccost"])
        self.assertEqual(after["rows"][-1]["duration_ms"], before["rows"][-1]["duration_ms"] + 10000)

    def test_late_child_and_partial_telemetry_remain_shared_report_values(self):
        snapshot = make_uncompacted_snapshot(running=True)
        source = FakeSource(snapshot)
        service = self.service(source)
        token = self.details.open("root", "live")
        self.tick(service)
        before = self.details.page(token, 0)["result"]["view"]["prompt_blocks"][0]
        child = next(item for item in snapshot.invocations if item.session_id == "child")
        child = replace(child, invocation_id="late-child", message_id="late-child-message",
                        created_at_ms=1300, completed_at_ms=1400)
        source.snapshot = replace(snapshot, invocations=(*snapshot.invocations, child), source_revision="late-child")
        self.tick(service)
        after = self.details.page(token, 0)["result"]["view"]["prompt_blocks"][0]
        canonical = project(self.service(source).build(ReportRequest(ReportKind.SESSION, "root"))).to_json()["prompt_blocks"][0]
        self.assertEqual(after["total_ccost"], canonical["total_ccost"])
        self.assertNotEqual(after["total_ccost"], before["total_ccost"])
        self.assertEqual(after["total_calls"], before["total_calls"] + 1)
        # A separate unpriced acquisition stays incomplete instead of priced zero.
        partial = self.service(source)
        partial.pricing_provider.catalog = replace(partial.pricing_provider.catalog, models=())
        self.details = SessionDetails(clock=lambda: self.clock)
        token = self.details.open("root", "live")
        self.tick(partial)
        block = self.details.page(token, 0)["result"]["view"]["prompt_blocks"][0]
        self.assertFalse(block["comparison_cost_complete"])
        self.assertTrue(any(row["unresolved_cost"] for row in block["rows"]))

    def test_index_windows_match_existing_strict_same_timestamp_semantics(self):
        snapshot = make_snapshot()
        sample = snapshot.events[0]
        added = tuple(replace(sample, event_id=f"extra-{index}", created_at_ms=at, kind=kind)
            for index, (at, kind) in enumerate(((1000, EventKind.USER_PROMPT),
                (1200, EventKind.OTHER), (1500, EventKind.BACKGROUND_COMPLETION),
                (2000, EventKind.OTHER), (2400, EventKind.SYNTHETIC_CONTINUATION))))
        snapshot = replace(snapshot, events=(*snapshot.events, *added))
        timeline = _root_timeline(snapshot)
        for event in timeline.visible_events:
            expected = prompt_parent_ids(snapshot, event.event_id, event.created_at_ms,
                subtask=event.kind is EventKind.SUBTASK)
            self.assertEqual(timeline.index.windows[event.event_id], expected)


if __name__ == "__main__":
    unittest.main()
