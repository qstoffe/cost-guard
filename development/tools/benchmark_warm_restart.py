"""Compare separate, gracefully stopped HTTP hosts over deterministic history."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if os.environ.get('COST_GUARD_RESTART_SOURCE'):
    ROOT = Path(os.environ['COST_GUARD_RESTART_SOURCE'])
sys.path.insert(0, str(ROOT))

from development.tests.integration import ci_account_timeline as chart
from development.tests.fixtures.watch_runtime import make_service
from src.application import ReportApplication
from src.reports import ReportKind
from src.web.jobs import ReportJobs, run_report


class History(chart.ChartSource):
    def __init__(self, accounts):
        super().__init__(accounts)
        self.clock_offset_ms = int(os.environ['COST_GUARD_RESTART_CLOCK_OFFSET'])
        for index in range(25, int(os.environ['COST_GUARD_RESTART_ROOTS'])):
            offset = index % 4 * chart.DAY_MS + index * 1000
            self.replace_usage(index, chart.NOV_1 + offset, 1000, accounts[index % 3].ref)
        self.first_read.set()
        self.continue_history.set()


def stats_worker(sender, request):
    from src.web import composition
    if request.kind is not ReportKind.AI_STATS:
        sender.send(('error', 'fixture_scope'))
        sender.close()
        return
    source = History((chart.subscription('github-copilot'), chart.subscription('github-copilot', identity='second'),
                      chart.subscription()))
    root = Path(os.environ['COST_GUARD_RESTART_ROOT'])
    service = None

    def application(actual, **options):
        def factory(now, progress):
            nonlocal service
            service = make_service(str(root), source, now_ms=now)[2]
            service.progress = progress
            service.allow_partial_history = service.shared_web_evidence = True
            service.stats_slice_roots, service.stats_batch_size = actual.slice_roots, actual.batch_size
            service.stats_scan, service.history_resuming = actual.scan, actual.resuming
            return service
        return ReportApplication(factory, clock=lambda: chart.NOV_5 + source.clock_offset_ms, models_only=True)

    started = time.perf_counter()
    with patch.object(composition, 'application', application):
        run_report(sender, request)
    metrics = service.metrics.snapshot() if service is not None else {}
    with (root / 'stats-counts.jsonl').open('a', encoding='utf-8') as log:
        log.write(json.dumps(dict(seconds=time.perf_counter() - started, hydrated=source.load_count,
                                  catalogs=source.catalog_count, revision_roots=source.metrics.counts.get('revision_checks', 0),
                                  hits=metrics.get('counts', {}).get('ai_stats_warm_projection_hits', 0),
                                  cache_read_ms=metrics.get('milliseconds', {}).get('ai_stats_cache_read', 0),
                                  project_ms=metrics.get('milliseconds', {}).get('ai_stats_projection', 0))) + '\n')


def journey(root, executable, mode):
    from playwright.sync_api import sync_playwright

    # Each invocation owns a new process, browser context, Live coordinator and
    # report scheduler. Only the fixture installation/cache survives between runs.
    (root / 'config' / 'default-config.jsonc').unlink(missing_ok=True)
    config = root / 'config'
    if config.exists():
        config.rmdir()
    counts = root / 'stats-counts.jsonl'
    counts.unlink(missing_ok=True)
    os.environ['COST_GUARD_RESTART_ROOT'] = str(root)
    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=True, executable_path=executable) as browser:
            with patch.object(chart, 'DispatchJobs', lambda: ReportJobs(target=stats_worker)):
                with chart.chart_fixture(browser, root, History) as (page, host, coordinator, source, *rest):
                    page.goto(host.browser_url())
                    page.wait_for_function('() => liveValue?.view?.accounts?.accounts?.length')
                    start = time.perf_counter()
                    paint = "() => new Promise(done => requestAnimationFrame(() => requestAnimationFrame(done)))"
                    if mode == 'accounts':
                        page.get_by_role('link', name='Accounts', exact=True).click()
                        page.get_by_role('button', name='30 days', exact=True).click()
                        page.wait_for_function('''() => current.accountTimeline?.view?.period === '30-days'
                            && current.accountTimeline.plot.querySelector('.account-timeline-bar:not([data-bucket="29"])')''',
                            timeout=180_000)
                        page.evaluate(paint)
                        first = time.perf_counter()
                        page.wait_for_function('''() => current.accountTimeline?.view?.period === '30-days'
                            && !current.accountTimeline.view.initial_pending_buckets.length
                            && !current.accountTimeline.view.pending_buckets.length
                            && current.accountTimeline.view.series.some(row => row.points.some(point => +point?.amount > 0))''',
                            timeout=180_000)
                    else:
                        page.get_by_role('link', name='AI Stats', exact=True).click()
                        page.wait_for_function('''() => current.statsResults?.has(current.period)
                            && [...document.querySelectorAll('.ai-stat-value')].some(node =>
                                node.textContent.trim() && !node.textContent.includes('Loading'))''', timeout=180_000)
                        page.evaluate(paint)
                        first = time.perf_counter()
                        page.wait_for_function('''() => current.statsResults?.size === 5''', timeout=180_000)
                    page.evaluate(paint)
                    end = time.perf_counter()
                    account_counts = dict(hydrated=sum(source.timeline_reads.values()), catalogs=source.catalog_count,
                                          revision_roots=source.metrics.counts.get('revision_checks', 0))
                    assert host.failure is None and not rest[2], 'Host or page error'
    report_counts = [json.loads(line) for line in counts.read_text().splitlines()] if counts.exists() else []
    files = sorted((root / 'cache').glob('cost-guard-cache-*.sqlite3'))
    return dict(mode=mode, pid=os.getpid(), first_seconds=round(first - start, 3), ready_seconds=round(end - start, 3),
                account=account_counts, stats=report_counts,
                cache={file.name: file.stat().st_size for file in files})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', required=True)
    parser.add_argument('--roots', type=int, default=1000)
    parser.add_argument('--scratch', required=True, type=Path)
    parser.add_argument('--previous-source', type=Path)
    parser.add_argument('--mode', choices=('accounts', 'stats'))
    parser.add_argument('--child', action='store_true')
    args = parser.parse_args()
    os.environ['COST_GUARD_RESTART_ROOTS'] = str(args.roots)
    if args.child:
        print(json.dumps(journey(args.scratch, args.browser, args.mode)), flush=True)
        return
    for mode in (args.mode,) if args.mode else ('accounts', 'stats'):
        with TemporaryDirectory(prefix=f'warm-restart-{mode}-', dir=args.scratch) as directory:
            for index, launch in enumerate(('initial', 'restart')):
                source = args.previous_source if launch == 'initial' and args.previous_source else ROOT
                output = subprocess.check_output([sys.executable, __file__, '--child', '--mode', mode,
                    '--roots', str(args.roots), '--browser', args.browser, '--scratch', directory],
                    env=dict(os.environ, COST_GUARD_RESTART_SOURCE=str(source), PYTHONDONTWRITEBYTECODE='1',
                             COST_GUARD_RESTART_CLOCK_OFFSET=str(index * 300_000)), text=True)
                print(json.dumps(dict(launch=launch, roots=args.roots, **json.loads(output))), flush=True)


if __name__ == '__main__':
    main()
