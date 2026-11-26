"""Foreground-to-rendered-content regressions. Run as a module with Playwright/Chromium."""
from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
from threading import Event
import time
from types import SimpleNamespace
import unittest

from playwright.sync_api import expect, sync_playwright

from development.tests.fixtures.benchmark import page as benchmark_page, row as benchmark_row
from development.tests.fixtures.compact_reports import ROOT, report_service
from development.tests.fixtures.model_views import model_report
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.integration.foreground_period_frames import PeriodFrames
from development.tests.integration.serve_data_dispatch import DispatchJobs
from src.application.detail_archive import DOMAIN, acquired_detail
from src.application.live_projection import project_live
from src.application.projection import project
from src.application.session_catalog import SessionCatalog
from src.application.session_detail import SessionDetails
from src.application.session_epoch_page import sort_value
from src.cache.session_projection import SESSIONS_DOMAIN, SORT_COLUMNS
from src.cache.web_archive import ArchiveFact, WebArchive, source_partition
from src.benchmarks import parse_pages
from src.reports.models import ReportKind, SessionUsageRow
from src.reports.session_summary import encode_summary
from src.reports.watch_capture import capture_rows
from src.watch.models import WatchCard, WatchRow
from src.watch.observers import observe_catalog
from src.web.dispatch import DataDispatcher
from src.web.host import WebHost
from src.web.report_cache_events import ReportCacheEvents


# Suspend delivery, not the SSE connection. Hold one real response *after* the
# server selected its snapshot. Subsequent loopback requests are not delayed.
BROWSER = """(() => {
  window.hold = null;
  const nativeFetch = window.fetch;
  window.fetch = async (...args) => {
    const response = await nativeFetch(...args);
    if (hold && args[0] === hold) {
      hold = null;
      document.documentElement.dataset.readHeld = 'true';
      await new Promise(resolve => { window.releaseRead = resolve; });
    }
    return response;
  };
  window.EventSource = class extends EventSource {
    constructor(...args) {
      super(...args); window.stream = this;
      super.addEventListener('open', () => document.documentElement.dataset.streamOpen = 'true');
    }
    addEventListener(type, fn, options) {
      super.addEventListener(type, e => {
        if (!window.missEvents) fn(e);
      }, options);
    }
  };
  Object.defineProperty(document, 'hidden', {get: () => !!window.fixtureHidden});
})()"""


class ForegroundTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / 'config').mkdir()
        shutil.copyfile(ROOT / 'config/default-config.jsonc', root / 'config/default-config.jsonc')
        self.archive = WebArchive(root)
        self.archive.initialize()
        self.now = time.time_ns() // 1_000_000
        self.seconds = 0
        self.source = SyntheticMonthSource(0, 0, month_start_ms=self.now)
        self.source.source_instance = 'synthetic-month'
        self.source.observation_epoch = None
        self.catalog = SessionCatalog(archive=self.archive, clock_ms=lambda: self.now, timezone_id='UTC')
        self.details = SessionDetails(archive=self.archive, clock=lambda: self.seconds)
        self.partition = source_partition('v1', self.source.source_instance)
        self.details.bind_archive(self.partition, self.partition)
        self.jobs = DispatchJobs()
        self.host = WebHost(root, jobs=self.jobs)
        self.host.report_cache_events = ReportCacheEvents(self.host.events)
        self.host.dispatcher = DataDispatcher(self.jobs, archive=self.archive, notify=self.host.report_cache_events.committed)
        # Publish explicitly. No capture/refresh ticks can rescue a stale view.
        self.host.dispatcher.tick = lambda **kwargs: None
        self.host.benchmark.tick = lambda: None
        self.host.model_snapshots = self.host.dispatcher.models
        self.service = report_service(self, self.source, now_ms=self.now)
        self.host.live = SimpleNamespace(catalog=self.catalog, details=self.details,
            stopping=Event(), start=lambda: None, close=self.catalog.close, observed=Event(),
            driver=SimpleNamespace(error=None, terminal=False, coordinator=SimpleNamespace(report_service=self.service)))
        self.host.live.observed.set()
        self.addCleanup(self.details.close_archive)
        self.host.start()
        self.addCleanup(self.host.close)
        self.host.publish_ready()
        self.publish_watch('Original Watch')
        playwright = sync_playwright().start()
        self.addCleanup(playwright.stop)
        browser = playwright.chromium.launch(headless=True)
        self.addCleanup(browser.close)
        self.page = browser.new_page(viewport={'width': 1400, 'height': 1000})
        self.page.add_init_script(BROWSER)

    def open_view(self, route):
        self.page.goto(self.host.browser_url())
        expect(self.page.locator('html')).to_have_attribute('data-stream-open', 'true')
        self.page.evaluate('route => location.hash = route', route)

    def publish_watch(self, title):
        frame = summary_watch()
        card, *others = frame.active_cards
        frame = replace(frame, active_cards=(replace(card, title=title), *others))
        self.host.events.publish('live', dict(state='running', view=project_live(frame, 'UTC').to_json(),
            source_observed_at_ms=self.now, detail_hints=self.details.archive_hints()))

    def blur(self, *, hidden=False):
        self.page.evaluate("""hidden => {
            window.missEvents = true;
            window.dispatchEvent(new Event('blur'));
            if (hidden) {
                window.fixtureHidden = true;
                document.dispatchEvent(new Event('visibilitychange'));
            }
        }""", hidden)

    def activate(self):
        self.page.evaluate("""() => {
            window.activated = performance.now();
            if (window.fixtureHidden) {
                window.fixtureHidden = false;
                document.dispatchEvent(new Event('visibilitychange'));
            }
            window.dispatchEvent(new Event('focus'));
        }""")

    def within(self, label, limit=2000):
        # Wait for a paint opportunity after the caller checked actual visible
        # values; a conservative upper bound that includes assertion overhead.
        elapsed = self.page.evaluate("""() => new Promise(resolve => requestAnimationFrame(
            () => requestAnimationFrame(() => resolve(Math.ceil(performance.now() - activated)))))""")
        print(f'{label}: {elapsed} ms', flush=True)
        self.assertLessEqual(elapsed, limit, label)

    def hold_passive_read(self, path):
        self.page.evaluate("path => {window.hold = path; window.dispatchEvent(new Event('blur'));}", path)
        self.activate()
        expect(self.page.locator('html')).to_have_attribute('data-read-held', 'true')

    def test_watch_resnapshot_does_not_queue_behind_pre_background_snapshot(self):
        self.open_view('#/watch')
        expect(self.page.get_by_text('Original Watch', exact=True).first).to_be_visible()
        original = self.page.get_by_text('Intermediate Watch', exact=True).first
        updated = self.page.get_by_text('Latest Watch', exact=True).first
        self.blur()
        self.publish_watch('Intermediate Watch')
        self.activate()
        expect(original).to_be_visible(timeout=2000)
        self.within('Watch with missed event')
        self.hold_passive_read('/api/live')
        self.blur(hidden=True)
        self.publish_watch('Latest Watch')
        expect(original).to_be_visible()
        self.assertEqual(1, self.page.evaluate('stream.readyState'), 'SSE must still be open')
        self.activate()
        try:
            expect(updated).to_be_visible(timeout=2000)
            self.within('Watch with earlier snapshot outstanding')
        except AssertionError:
            self.assertTrue(original.is_visible(), 'expected the previous card while blocked')
            self.page.evaluate("releaseRead()")
            expect(updated).to_be_visible(timeout=2000)
            print(f'Watch applied after releasing old snapshot; '
                  f'{self.page.evaluate("Math.ceil(performance.now() - activated)")} ms after activation', flush=True)
            raise
        self.page.evaluate("releaseRead()")
        expect(original).not_to_be_visible()

    def test_catalog_page_two_reconciles_new_member_in_selected_sort(self):
        def publish(index, title):
            key = f'row-{index:03}'
            stamp = self.now - index * 60
            row = SessionUsageRow(key, title, 'Model', False, None, 1, last_activity_ms=stamp)
            fact = ArchiveFact(title, stamp, {'row': encode_summary(row)})
            self.assertTrue(self.archive.publish_session(self.partition, {SESSIONS_DOMAIN: {key: fact}}, key,
                {name: sort_value(row, name) for name in SORT_COLUMNS}, stamp, stamp))

        for i in range(50):
            publish(i, f'Fixture {i:02}')
        self.catalog.archive.update_runtime(state='observed', terminal=False, reset_pending=True, pending={}, live={})
        self.open_view('#/sessions?period=7-days&sort=name&direction=1')
        names = self.page.locator('.session-name')
        expect(names.first).to_have_text('Fixture 00')
        next_page = self.page.get_by_role('button', name='Next', exact=True)
        next_page.evaluate("b => b.addEventListener('click', () => window.activated = performance.now(), {once:true})")
        next_page.click()
        expect(names.first).to_have_text('Fixture 25', timeout=1000)
        self.within('Sessions cached Next', 1000)
        self.blur()
        publish(50, 'Fixture 24a')
        expect(names.first).to_have_text('Fixture 25')
        self.activate()
        expect(names.first).to_have_text('Fixture 24a', timeout=2000)
        expect(names.last).to_have_text('Fixture 48')
        self.within('Sessions page two')
        self.assertIn('period=7-days', self.page.url)
        self.assertEqual(0, self.source.load_count)

        # A blurred (but not hidden) window can *start* a passive read before
        # focus, not just carry one over from before blur.
        self.page.evaluate("""() => {
            window.missEvents = false;
            window.dispatchEvent(new Event('blur'));
            window.hold = '/api/sessions';
        }""")
        self.host.events.publish('sessions_cache', dict(revision=100, periods={'7-days': 100}))
        expect(self.page.locator('html')).to_have_attribute('data-read-held', 'true')
        self.page.evaluate('window.missEvents = true')
        publish(51, 'Fixture 24b')
        self.activate()
        try:
            expect(names.nth(1)).to_have_text('Fixture 24b', timeout=2000)
            self.within('Sessions with passive read started while blurred')
        finally:
            self.page.evaluate('releaseRead()')
            expect(names.nth(1)).to_have_text('Fixture 24b')

    def test_watch_retains_during_transport_loss_and_recovers_without_navigation(self):
        self.open_view('#/watch')
        original = self.page.get_by_text('Original Watch', exact=True).first
        updated = self.page.get_by_text('Recovery Watch', exact=True).first
        expect(original).to_be_visible()
        self.page.context.set_offline(True)
        self.assertTrue(self.page.evaluate("""async () => {
            try { await fetch('/api/live', {cache:'no-store'}); return false; }
            catch (error) { return !navigator.onLine && error instanceof TypeError; }
        }"""))
        self.page.evaluate('window.missEvents = true')
        self.publish_watch('Recovery Watch')
        expect(original).to_be_visible()
        expect(updated).not_to_be_visible()
        self.page.context.set_offline(False)
        expect(updated).to_be_visible()

    def publish_model(self, name):
        view = project(model_report(include_model_catalog=True)).to_json()
        model = next(row for row in view['model_catalog']['rows'] if row['model'] == 'Reference')
        model['model'] = name
        reference = next(row for row in view['model_catalog']['rows'] if row['model'] == 'A')
        reference.update(publisher='Anthropic', model='Claude Opus 5.5')
        result = dict(view=view, source=dict(status='acquired', observed_at_ms=self.now), observed_at_ms=self.now)
        self.host.model_snapshots.publish(dict(result=result, result_id=name, id=name, refresh='scheduled',
            stale=False, error=None, terminal=False, source_identity='fixture', projection_epoch=0), self.now)

    def test_models_recovers_from_missed_commit_without_starting_a_job(self):
        self.publish_model('Original model')
        self.open_view('#/models')
        original = self.page.get_by_text('Original model', exact=True).first
        expect(original).to_be_visible()
        jobs = len(self.jobs.jobs)
        self.blur()
        self.publish_model('Replacement model')
        expect(original).to_be_visible()
        self.activate()
        expect(self.page.get_by_text('Replacement model', exact=True).first).to_be_visible(timeout=2000)
        self.within('Models')
        self.assertEqual(jobs, len(self.jobs.jobs))

    def period_frames(self):
        frames = PeriodFrames(self.host, self.archive, self.now)
        self.addCleanup(frames.close)
        return frames

    def check_period_return(self, kind, original, latest):
        frames = self.period_frames()
        frames.publish_report(kind, 1)
        self.open_view('#/' + kind.value)
        self.page.get_by_role('button', name='7 days', exact=True).click()
        before = self.page.get_by_text(original, exact=True).first
        expect(before).to_be_visible()
        self.blur(hidden=True)
        frames.publish_report(kind, 2)
        expect(before).to_be_visible()
        self.activate()
        expect(self.page.get_by_text(latest, exact=True).first).to_be_visible(timeout=2000)
        self.within(kind.value + ' (7 days)')

    def test_selected_stats_record_updates_on_return(self):
        self.check_period_return(ReportKind.AI_STATS, 'Session 1 in 7-days', 'Session 2 in 7-days')

    def test_selected_token_mix_updates_on_return(self):
        self.check_period_return(ReportKind.TOKEN_MIX, 'Model 0, revision 1', 'Model 0, revision 2')

    def test_account_chart_applies_latest_committed_total_for_selected_period(self):
        frames = self.period_frames()
        frames.publish_chart(1)
        self.open_view('#/accounts')
        self.page.get_by_role('button', name='7 days', exact=True).click()
        total = self.page.locator('.account-timeline-legend-value')
        expect(total).to_have_text('$0.10')
        self.blur(hidden=True)
        frames.publish_chart(2)
        expect(total).to_have_text('$0.10')
        self.activate()
        expect(total).to_have_text('$0.20', timeout=2000)
        expect(total).to_be_visible()
        self.within('Accounts CCost (7 days)')

    def test_benchmark_reconciles_committed_scores_despite_an_older_lookup(self):
        lane = self.host.benchmark
        def publish(score):
            pages = [benchmark_page([benchmark_row(score=score)])]
            snapshot = parse_pages(pages, self.now)
            lane.cache.put(dict(schema=1, fetched_at_ms=self.now, pages=pages))
            lane.snapshot = snapshot
            lane._publish()

        self.publish_model('Benchmark fixture')
        publish(61)
        self.open_view('#/models')
        score = self.page.locator('.benchmark-table tbody tr td:last-child')
        expect(score).to_have_text('61.0%')
        self.hold_passive_read('/api/models/benchmark')
        self.blur(hidden=True)
        publish(72)
        self.activate()
        try:
            expect(score).to_have_text('72.0%', timeout=2000)
            self.within('Benchmark with earlier lookup outstanding')
        finally:
            self.page.evaluate('releaseRead()')
            expect(score).to_have_text('72.0%')

    def test_expired_detail_shows_completed_history_then_full_new_running_row(self):
        key = 'root-0000'
        def snapshot(count, running):
            item = SyntheticMonthSource(1, count, running_roots=int(running),
                month_start_ms=self.now - 60_000).snapshots[key]
            snap = replace(item, complete=True, source_revision=f'{count}-{running}')
            self.source.snapshots[key] = snap
            return snap

        def publish_running(snap, capture):
            prompt = next(row for row in capture.rows if row.in_progress)
            card = WatchCard(key, snap.root.title, prompt.event_id, (WatchRow(key, snap.root.title, prompt),),
                state='observed', observed_at_ms=capture.observed_at_ms)
            frame = replace(summary_watch(), now_ms=capture.observed_at_ms, active_cards=(card,))
            self.host.events.publish('live', dict(state='running', view=project_live(frame, 'UTC').to_json(),
                source_observed_at_ms=capture.observed_at_ms, detail_hints=self.details.archive_hints()))

        first = snapshot(30, True)
        token = self.details.open(key, 'live')
        self.details.tick(self.service)
        self.details.close(token)
        self.open_view('#/watch')
        publish_running(first, capture_rows(self.service, first.root, fresh=first)[0])
        expect(self.page.get_by_text(first.root.title, exact=True).first).to_be_visible()
        with self.page.context.expect_page() as window:
            self.page.locator('#mini-watch-toggle').click()
        mini = window.value
        mini_row = mini.get_by_text(first.root.title, exact=True)
        expect(mini_row).to_be_visible()
        self.page.evaluate("key => location.hash = '#/sessions/' + key", key)
        states = self.page.locator('.session-prompt-state')
        expect(states.filter(has_text='[RUNNING]')).to_have_text('[RUNNING] #30')
        self.blur(hidden=True)
        self.page.evaluate('window.missEvents = false')  # Mini still receives Live; Detail is hidden.
        self.seconds += 1800
        self.assertFalse(self.details.has_leases())
        for count in (31, 32, 33):
            snap = snapshot(count, False)
            self.service.now_ms = self.now + count
            _, captured = capture_rows(self.service, snap.root, fresh=snap)
            fact = acquired_detail(self.service, captured)
            self.assertIsNotNone(fact)
            self.assertTrue(self.archive.publish(self.partition, DOMAIN, {key: fact}))
        snap = snapshot(34, True)
        self.service.now_ms = time.time_ns() // 1_000_000
        capture, _ = capture_rows(self.service, snap.root, fresh=snap)
        card = SimpleNamespace(snapshot=snap, capture=capture, generation=1, verified_generation=1,
            source_status=SimpleNamespace(failed_at=None))
        self.details.observe_source(observe_catalog(self.source), {key: card})
        publish_running(snap, capture)
        mini_row.hover()
        expect(mini.get_by_text('Prompt #34', exact=False).first).to_be_visible()
        expect(states.filter(has_text='[RUNNING]')).to_have_text('[RUNNING] #30')
        loads = self.source.load_count
        self.activate()
        pending = self.page.get_by_text('A prompt is running. Its detail is not available yet.')
        expect(pending).to_be_visible(timeout=2000)
        self.assertEqual([f'#{i}' for i in range(1, 34)], states.all_text_contents())
        self.within('Expired Detail (committed 33, running proof for 34)')
        self.assertEqual(loads, self.source.load_count)
        expect(self.page.get_by_text('Could not update session activity', exact=False)).not_to_be_visible()

        self.details.tick(self.service)
        publish_running(snap, capture)
        expect(states.filter(has_text='[RUNNING]')).to_have_text('[RUNNING] #34')
        expect(states).to_have_count(34)
        expect(pending).not_to_be_visible()


if __name__ == '__main__':
    unittest.main()
