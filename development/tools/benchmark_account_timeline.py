"""Time source, publication and browser stages with and without card-history sharing."""
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import current_thread
from time import perf_counter, sleep
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from development.tests.integration.ci_account_timeline import ChartSource, chart_fixture
from development.tests.test_account_timeline import NOV_1
from src.analysis.account_timeline import DAY_MS
from src.watch import account_timeline


def run(browser, root, count, delay, share):
    class Source(ChartSource):
        def __init__(self, accounts):
            super().__init__(accounts)
            for i in range(25, count):
                self.replace_usage(i, NOV_1 + i % 4 * DAY_MS + i * 1000, 1000, accounts[i % 3].ref)
            self.first_read.set()
            self.continue_history.set()

        def load_session_snapshot(self, key):
            if delay and current_thread().name.startswith('cost-guard-account-timeline'):
                sleep(delay)
            return super().load_session_snapshot(key)

    steps, reads, indices = [], [], []

    def measure(call, samples):
        def invoke(*args, **kwargs):
            start = perf_counter()
            result = call(*args, **kwargs)
            samples.append((start, perf_counter(), result if samples is steps else None))
            return result
        return invoke

    ms = lambda seconds: round(seconds * 1000, 1)
    frame = "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
    with chart_fixture(browser, root, Source) as (page, host, coordinator, source, *rest):
        lane = coordinator.account_timeline
        tick = lane.tick

        def isolated(**options):
            return tick(**(options | dict(card_today=None, shared_roots=None)))

        lane.history._load = measure(lane.history._load, reads)
        lane.history.step = measure(lane.history.step, steps)
        if not share:
            lane.tick = isolated
        with patch.object(account_timeline, 'PeriodCCostIndex', measure(account_timeline.PeriodCCostIndex, indices)):
            page.goto(host.browser_url())
            page.wait_for_function("""() => liveValue?.view?.accounts?.accounts?.some(row =>
                +row.ccost_scopes.find(scope => scope.name === 'today')?.cost?.known_ccost > 0)""")
            card = perf_counter()
            page.get_by_role('link', name='Accounts', exact=True).click()
            page.wait_for_function("""() => current.accountTimeline?.view?.series.some(row =>
                +row.points[4]?.amount > 0)""")
            page.evaluate(frame)
            first = perf_counter()
            page.wait_for_function("""() => current.accountTimeline?.view?.series.some(row => +row.points[0]?.amount > 0)
                && !current.accountTimeline.view.pending_buckets.length""", timeout=60_000)
            page.evaluate(frame)
            complete = perf_counter()
            read_count = sum(source.timeline_reads.values())
            through = [(start, end) for start, end, _ in reads if end <= complete]
            emissions = [end for _, end, (views, _, _, _) in steps if views and end <= complete]
            snapshot = dict(roots=count, delay_ms=ms(delay), share=share, card_to_first_paint_ms=ms(first - card),
                card_to_complete_paint_ms=ms(complete - card), reads=read_count,
                read_ms=ms(sum(end - start for start, end in through)),
                index_ms=ms(sum(end - start for start, end, _ in indices if end <= complete)),
                worker_idle_ms=ms(sum(right[0] - left[1] for left, right in zip(through, through[1:]))),
                card_to_last_worker_emission_ms=ms(emissions[-1] - card), worker_emissions=len(emissions))
            start = perf_counter()
            page.get_by_role('button', name='30 days', exact=True).click()
            page.wait_for_function("""() => current.accountTimeline?.view?.period === '30-days'
                && !current.accountTimeline.view.pending_buckets.length""")
            page.evaluate(frame)
            snapshot['warm_30_days_paint_ms'] = ms(perf_counter() - start)
            page.get_by_role('link', name='Watch', exact=True).click()
            start = perf_counter()
            page.get_by_role('link', name='Accounts', exact=True).click()
            page.wait_for_function("""() => current.accountTimeline?.view?.period === '30-days'
                && !current.accountTimeline.view.pending_buckets.length""")
            page.evaluate(frame)
            snapshot['revisit_paint_ms'] = ms(perf_counter() - start)
            snapshot['extra_reads_warm_and_revisit'] = sum(source.timeline_reads.values()) - read_count
        assert host.live.failure is None
        return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    options = parser.parse_args()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=options.browser)
        for count in (25, 217):
            for delay in (0, .11):
                for share in (False, True):
                    with TemporaryDirectory(prefix='benchmark-accounts-', dir=options.scratch) as directory:
                        print(json.dumps(run(browser, Path(directory), count, delay, share)), flush=True)


if __name__ == '__main__':
    main()
