"""Bounded read-only dispatcher/Live probe; numeric evidence, no UI or inference."""
import argparse
from functools import partial
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.integration.historical_report_observations import measured_report, peak_memory
from development.tests.integration.dispatch_probe_resources import Resources
from src.reports import ReportKind, ReportRequest
from src.web.composition import dispatch_dependencies, live_acquisition
from src.web.dispatch import DataDispatcher
from src.web.host import WebHost
from src.web.jobs import ReportJobs


class ForegroundOnlyDispatcher(DataDispatcher):
    """Probe control only; same foreground workers, no speculative warm set."""
    def tick(self, **kwargs):
        self.next_background = float('inf')
        super().tick(**kwargs)
        self.warm_allowed = False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--budget-seconds', type=int, default=600)
    parser.add_argument('--foreground-only', action='store_true')
    parser.add_argument('--idle-seconds', type=int, default=20)
    parser.add_argument('--initial', choices=('models', 'watch', 'ai-stats'), default='models')
    parser.add_argument('--switch-under-load', action='store_true')
    parser.add_argument('--startup-only', action='store_true')
    parser.add_argument('--sample-window', type=int, choices=(1, 2, 4, 8), help='Opt-in finite-child sampling experiment')
    parser.add_argument('--card-timeline', type=Path, help='Optional numeric owned-card diagnostic output; adds observer overhead')
    parser.add_argument('--owner-profile', type=Path, help='Opt-in coarse wall/thread-CPU and short owner function profile')
    parser.add_argument('--owner-functions', choices=('on', 'off'), default='on', help='Disable function profiling for coarse-only comparisons')
    parser.add_argument('--extend-history-observation', action='store_true',
        help='Same 90s observation may continue in advancing 30s slices, at most 300s total; not a product timeout')
    args = parser.parse_args()
    if not 30 <= args.budget_seconds <= 1200:
        parser.error('budget must be 30..1200 seconds')
    if not 0 <= args.idle_seconds <= 120:
        parser.error('idle must be 0..120 seconds')
    if args.extend_history_observation and (not args.owner_profile or args.budget_seconds != 90 or
            args.initial != 'watch' or args.foreground_only or args.startup_only):
        parser.error('extension requires owner-profile, normal warming, initial watch and a 90s observation')
    jobs = ReportJobs(target=partial(measured_report, sample_window=args.sample_window))
    host = WebHost(ROOT, jobs=jobs, live_factory=live_acquisition)
    host.dispatcher = (ForegroundOnlyDispatcher if args.foreground_only else DataDispatcher)(jobs)
    host.dependencies = dispatch_dependencies(ROOT)
    timeline = None
    owner_profile = None
    if args.card_timeline:
        from development.tests.fixtures.card_service_timeline import CardServiceTimeline
        timeline = CardServiceTimeline()
    if args.owner_profile:
        from development.tests.fixtures.owner_cost_timeline import OwnerCostTimeline
        owner_profile = OwnerCostTimeline(ROOT, functions=args.owner_functions == 'on')
    if timeline is not None or owner_profile is not None:
        original_factory = host.live.factory

        def observed_factory():
            driver = original_factory()
            if timeline is not None:
                timeline.attach(driver.coordinator.cards)
            if owner_profile is not None:
                owner_profile.attach(host.live, driver)
            return driver

        host.live.factory = observed_factory
    started = time.monotonic()
    cpu = time.process_time()
    end = started + args.budget_seconds
    observation_limit = started + (300 if args.extend_history_observation else args.budget_seconds)
    checkpoint_checked = 0
    facts = []
    resources = Resources()
    ready_at = set()
    publications = []
    history = {}
    publish = host.live.publish

    def measured_publish(kind, value):
        if kind == 'live':
            if not publications:
                facts.append(dict(event='first_live', seconds=round(time.monotonic() - started, 3),
                                  finite_jobs_before_live=len(jobs._jobs)))
            publications.append(time.monotonic())
            if timeline is not None or owner_profile is not None:
                def field(record, name, default=None):
                    if isinstance(record, dict):
                        return record.get(name, default)
                    return next((item for key, item in getattr(record, 'fields', ()) if key == name), default)

                view = field(value, 'view')
                history.update(state=field(view, 'history_state'), checked=field(view, 'history_checked'),
                    total=field(view, 'history_total'), visible_cards=len(field(view, 'history_cards', ())))
                if history['state'] == 'observed' and not any(fact['event'] == 'history_observed' for fact in facts):
                    facts.append(dict(event='history_observed', seconds=round(time.monotonic() - started, 3),
                        checked=history['checked'], total=history['total'], visible_cards=history['visible_cards']))
        return publish(kind, value)

    host.live.publish = measured_publish
    idle = None
    host.start()
    try:
        while host.live.driver is None and time.monotonic() < end and not host.failure:
            time.sleep(.05)
        if host.live.driver is None:
            raise RuntimeError('live_source_not_ready')
        first = ReportRequest(ReportKind.AI_STATS) if args.initial == 'ai-stats' else ReportRequest()
        section = args.initial
        selected = None if section == 'watch' else first
        host.dispatcher.interest('probe', section, True, selected)
        renewed = time.monotonic()
        switched = False
        returned = False
        background_before = {}
        while time.monotonic() < end and not host.failure:
            resources.sample(jobs)
            with host.dispatcher.lock:
                states = {request.kind.value + ':' + request.stats_scope: dict(
                    running=bool(entry['job']), ready=bool(entry['result']), error=entry['error'],
                    omitted_roots=(entry['result'] or {}).get('source', {}).get('omitted_roots', 0))
                    for request, entry in host.dispatcher.entries.items()}
                models = host.dispatcher.entries[first]
                for name, state in states.items():
                    if state['ready'] and name not in ready_at:
                        ready_at.add(name)
                        facts.append(dict(event='ready', kind=name, seconds=round(time.monotonic() - started, 3)))
                if args.startup_only and publications and (args.initial == 'watch' or models['result']):
                    facts.append(dict(event='startup_complete', section=args.initial))
                    break
                background = [key for key, job in jobs._jobs.items() if job['request'].kind is ReportKind.AI_STATS
                              and job['status'] in {'queued', 'running'} and job['progress']
                              and job['progress'].get('completed', 0) > 0]
                if (models['result'] and not switched and args.initial == 'models'
                        and (not args.switch_under_load or background)):
                    section, selected = 'token-mix', ReportRequest(ReportKind.TOKEN_MIX)
                    host.dispatcher.interest('probe', section, True, selected)
                    switched = time.monotonic()
                    background_before = {key: dict(jobs._jobs[key]['progress']) for key in background}
                    facts.append(dict(event='priority_switch', seconds=round(switched - started, 3),
                                      incomplete_background=len(background)))
                if switched and not any(fact['event'] == 'foreground_progress' for fact in facts):
                    entry = host.dispatcher.entries.get(selected)
                    snapshot = jobs.snapshot(entry['job']) if entry and entry['job'] else None
                    if snapshot and snapshot['progress'].get('phase') not in ('queued', 'running'):
                        facts.append(dict(event='foreground_progress', delay_seconds=round(time.monotonic() - switched, 3),
                            incomplete_background=sum(job['request'].kind is ReportKind.AI_STATS and
                                 job['status'] in {'queued', 'running'} for job in jobs._jobs.values())))
                if switched and not returned and not args.foreground_only and background_before:
                    target = host.dispatcher.entries.get(selected)
                    if target and target['result']:
                        section, selected = 'ai-stats', ReportRequest(ReportKind.AI_STATS)
                        host.dispatcher.interest('probe', section, True, selected)
                        returned = True
                        facts.append(dict(event='return_to_background',
                            same_logical_jobs=all(key in jobs._jobs for key in background_before),
                            progress_retained={key: jobs._jobs[key]['progress'] for key in background_before}))
                if idle is None and time.monotonic() - renewed >= 30:
                    host.dispatcher.interest('probe', section, True, selected)
                    renewed = time.monotonic()
                relevant = [entry for request, entry in host.dispatcher.entries.items()
                    if not args.foreground_only or request.kind in (
                        (ReportKind.NORMAL, ReportKind.TOKEN_MIX) if args.initial == 'models' else
                        (ReportKind.AI_STATS,) if args.initial == 'ai-stats' else ())]
                history_pending = owner_profile is not None and history.get('state') != 'observed'
                if publications and not history_pending and all(entry['result'] or entry['terminal'] for entry in relevant):
                    if idle is None:
                        idle = dict(start=time.monotonic(), cpu=time.process_time(), jobs=len(jobs._jobs))
                        host.dispatcher.interest('probe', 'watch', False)
                    if time.monotonic() - idle['start'] >= args.idle_seconds:
                        idle = dict(seconds=round(time.monotonic() - idle['start'], 3),
                            cpu_seconds=round(time.process_time() - idle['cpu'], 3),
                            new_jobs=len(jobs._jobs) - idle['jobs'])
                        break
            if (args.extend_history_observation and time.monotonic() >= end - .2 and end < observation_limit
                    and history.get('state') == 'loading' and (history.get('checked') or 0) > checkpoint_checked):
                checkpoint_checked = history['checked']
                end = min(observation_limit, end + 30)
                facts.append(dict(event='observation_extended', checked=checkpoint_checked,
                    observation_end_seconds=round(end - started, 3)))
            time.sleep(.1)
        else:
            states['probe'] = dict(error='budget_exhausted')
        gaps = [b-a for a,b in zip(publications, publications[1:])]
        print(json.dumps(dict(foreground_only=args.foreground_only, initial=args.initial, sample_window=args.sample_window,
            states=states, idle=idle,
            live_publications=len(publications), live_max_gap_seconds=round(max(gaps, default=0), 3),
            elapsed_seconds=round(time.monotonic() - started, 3),
            host_cpu_seconds=round(time.process_time() - cpu, 3), host_peak_memory=peak_memory(),
            resources=resources.summary(), facts=facts,
            host_failure=type(host.failure).__name__ if host.failure else None,
            live_state=host.live.driver.source_state if host.live.driver else None,
            history=history if timeline is not None or owner_profile is not None else None)), flush=True)
    finally:
        host.close()
        if timeline is not None:
            args.card_timeline.write_text(json.dumps(timeline.summary(), indent=2), encoding='utf-8')
        if owner_profile is not None:
            owner_profile.close()
            args.owner_profile.write_text(json.dumps(owner_profile.summary(), indent=2), encoding='utf-8')
        print(json.dumps(dict(cleanup='closed', serving_thread_alive=host.thread.is_alive(),
                              live_thread_alive=host.live.thread.is_alive(), owned_parked=len(jobs._parked))), flush=True)


if __name__ == '__main__':
    main()
