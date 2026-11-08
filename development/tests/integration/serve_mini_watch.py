"""Private-stdio synthetic host for the bounded headless Mini browser probe.

Uses shipped HTTP/assets/CSP/session/SSE and disposable Settings. No real source,
provider, browser launch or inference. The one-use URL stays inside the probe pipe.
"""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from threading import Timer

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.watch_summary import summary_watch, many_cost_groups, same_model_groups
from development.tests.fixtures.web_reports import finite_report
from development.tests.fixtures.web_help_reports import HelpAuditJobs
from development.tests.fixtures.token_mix_views import TokenMixJobs
from development.tests.fixtures.models_refresh import ModelsRefreshJobs
from development.tests.fixtures.ai_stats_views import AIStatsJobs, evidence_views
from development.tests.fixtures.stats_slices import slice_report
from development.tests.fixtures.matched_inputs import ComparisonsJobs
from development.tests.fixtures.report_loading import LoadingJobs
from src.application.live_projection import project_live
from src.application.display import with_display
from src.application.projection import accounts as project_accounts
from src.analysis.timezones import local_day_start_ms
from src.domain import QuotaComponent
from src.analysis.valuation import ComparisonCost
from src.reports.models import QuotaPeriodProjection
from src.watch.models import WatchRow
from src.watch.running import running_prompts
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path(tmp)
        (root / "config").mkdir(exist_ok=True)
        if not (root / "config/default-config.jsonc").exists():
            shutil.copyfile(ROOT / "config/default-config.jsonc", root / "config/default-config.jsonc")
        jobs = HelpAuditJobs() if sys.argv[2:] == ["--help-audit"] else ReportJobs(target=finite_report)
        if sys.argv[2:] == ['--token-mix']:
            jobs = TokenMixJobs()
        if sys.argv[2:] == ['--ai-stats']:
            jobs = AIStatsJobs()
        if sys.argv[2:] == ['--stats-slices']:
            if sys.platform == 'win32':
                import multiprocessing
                executable = Path(sys.executable).with_name('pythonw.exe')
                if not executable.is_file():
                    raise RuntimeError('fixture_gui_interpreter_unavailable')
                multiprocessing.set_executable(str(executable))
            os.environ.update(COST_GUARD_STATS_FIXTURE=str(root), COST_GUARD_STATS_BROWSER='1')
            jobs = ReportJobs(target=slice_report)
        if sys.argv[2:] == ['--comparisons']:
            jobs = ComparisonsJobs()
        if sys.argv[2:] == ['--report-loading']:
            jobs = LoadingJobs()
        if sys.argv[2:] == ['--models-refresh']:
            (root / 'pricing-mode.txt').write_text('unchanged')
            jobs = ModelsRefreshJobs(root)
        host = WebHost(root, jobs=jobs)
        if sys.argv[2:] == ['--history-demand']:
            from src.web.dispatch import DataDispatcher
            # Real authenticated lease registry, but no source/provider or finite warming owner.
            host.dispatcher = DataDispatcher(jobs)
        timer = Timer(420 if sys.argv[2:] == ['--token-mix'] else 300, host.stop)
        frame = summary_watch()
        now = int(time.time() * 1000)
        frame = replace(frame, now_ms=now, daily_usage=replace(frame.daily_usage,
            day_start_ms=local_day_start_ms('UTC', now_ms=now), observed_at_ms=now))
        # Synthetic quota observations stay current when the probe runs later.
        refreshed = []
        for item in frame.quota.accounts:
            quotas = tuple(replace(q, reset_at_ms=now + 3600000) if q.reset_at_ms else q for q in item.account.quotas)
            periods = tuple(replace(p, quota=q) for p, q in zip(item.quota_periods, quotas))
            refreshed.append(replace(item, account=replace(item.account, quotas=quotas), quota_periods=periods))
        frame = replace(frame, quota=replace(frame.quota, accounts=tuple(refreshed)))
        base = frame.active_cards[0]
        cards = tuple(replace(base, focal_id=str(index), rows=(WatchRow(base.session_id, base.title,
            replace(base.rows[0].prompt, event_id=str(index), prompt_number=22 + index,
                at_ms=frame.now_ms - duration, duration_ms=duration,
                 ccost=Decimal(33) if sys.argv[2:] == ["--help-audit"] else Decimal(cost),
                 cost_parts=base.rows[0].prompt.cost_parts if sys.argv[2:] == ["--help-audit"] else (),
                 unresolved_cost=False, cost_estimated=False)),))
            for index, duration, cost in ((1, 600_000, "1.25"), (2, 1_200_000, "2.75")))
        frame = replace(frame, active_cards=cards, running=running_prompts(cards, "observed"))
        cost_groups = (project_live(many_cost_groups(frame)).to_json()['active_cards'][0]['rows'][0]['prompt']
            if sys.argv[2:] == ["--help-audit"] else None)
        same_model = (project_live(same_model_groups(frame)).to_json()['active_cards'][0]['rows'][0]['prompt']
            if sys.argv[2:] == ["--help-audit"] else None)

        def publish(state="running", value=frame, timezone_name="UTC"):
            current = int(time.time() * 1000)
            value = replace(value, now_ms=current, quota=replace(value.quota, now_ms=current))
            host.events.publish("live", {"state": state, "source_observed_at_ms": value.now_ms,
                "view": project_live(value, timezone_name).to_json(),
                "probe_cost_groups": cost_groups,
                "probe_same_model": same_model,
                "probe_accounts": with_display(project_accounts(value.quota), now_ms=value.now_ms).to_json()})

        try:
            host.start()
            host.publish_ready()
            if sys.argv[2:] != ["--accounts-live"]:
                publish()
            timer.start()
            print(json.dumps({"url": host.browser_url()}), flush=True)
            for line in sys.stdin:
                command = json.loads(line)["command"]
                if command == "stop":
                    host.stop()
                    print('{"ok":true}', flush=True)
                    break
                if command.startswith('loading-') and sys.argv[2:] == ['--report-loading']:
                    action = command.removeprefix('loading-')
                    if action == 'hold':
                        jobs.mode = 'hold'
                        jobs.step = 0
                    elif action == 'complete':
                        jobs.mode = 'complete'
                    elif action == 'step':
                        jobs.step += 1
                    elif action == 'busy':
                        jobs.busy = 2
                    elif action == 'source':
                        from src.web.source_startup import SourceStartup
                        host.source_startup = SourceStartup(root, host.events.publish, host.stopping)
                        host.source_startup.finished.set()
                    elif action == 'ready':
                        host.source_startup._selected(None)
                    elif action == 'failed':
                        jobs.mode = 'failed'
                    else:
                        raise ValueError('unknown_loading_fixture_action')
                    print('{"ok":true}', flush=True)
                    continue
                if command == 'jobs-status' and sys.argv[2:] == ['--ai-stats']:
                    print(json.dumps(jobs.updates()), flush=True)
                    continue
                if command == 'stats-slices-status' and sys.argv[2:] == ['--stats-slices']:
                    loads = root / 'loads.jsonl'
                    print(json.dumps(dict(jobs=len(jobs._jobs), active=jobs._active is not None,
                        work=[dict(kind=job['request'].kind.value, scope=job['request'].stats_scope,
                            status=job['status'], progress=job['progress']) for job in jobs._jobs.values()],
                        loads=[json.loads(line) for line in loads.read_text().splitlines()] if loads.exists() else [])), flush=True)
                    continue
                if command == 'stats-evidence' and sys.argv[2:] == ['--ai-stats']:
                    print(json.dumps(evidence_views()), flush=True)
                    continue
                if command in ('stats-hold-all', 'stats-release-all') and sys.argv[2:] == ['--ai-stats']:
                    jobs.hold_all = command == 'stats-hold-all'
                    jobs.jobs = {key: job for key, job in jobs.jobs.items()
                                 if getattr(job.get('request'), 'stats_scope', '') != 'all'}
                    print('{"ok":true}', flush=True)
                    continue
                if command == "terminal":
                    ended = replace(cards[1], rows=(replace(cards[1].rows[0],
                        prompt=replace(cards[1].rows[0].prompt, in_progress=False, completed_successfully=True)),))
                    current = (cards[0], ended)
                    publish(value=replace(frame, active_cards=current, running=running_prompts(current, "observed")))
                elif command.startswith('models-'):
                    mode = command.removeprefix('models-')
                    assert mode in {'unchanged', 'changed', 'offline', 'invalid', 'status'}
                    if mode == 'status':
                        fetches = root / 'fetches.txt'
                        print(json.dumps({'fetches': len(fetches.read_text().splitlines()) if fetches.exists() else 0}), flush=True)
                        continue
                    (root / 'pricing-mode.txt').write_text(mode)
                elif command == "empty":
                    publish(value=replace(frame, active_cards=(), running=running_prompts((), "observed")))
                elif command == "recovering":
                    publish(state="recovering")
                elif command == "unavailable":
                    publish(value=replace(frame, active_cards=(), cards_state='unavailable',
                        running=running_prompts((), 'unavailable'), daily_state='retrying', quota_stale=True))
                elif command == "running":
                    publish()
                elif command in {"accounts-empty", "accounts-failed-empty"}:
                    publish(value=replace(frame, quota=replace(frame.quota, accounts=()),
                        quota_stale=command == "accounts-failed-empty"))
                elif command == "accounts-stale":
                    stale = tuple(replace(item, account=replace(item.account, availability="stale",
                        observations={"parser_reason": "transport_failure"})) for item in frame.quota.accounts)
                    publish(value=replace(frame, quota=replace(frame.quota, accounts=stale), quota_stale=True))
                elif command == "watch-starting":
                    host.events.publish("live", {"state": "running", "view": None})
                elif command == "watch-retrying":
                    publish(state="retrying")
                elif command.startswith("watch-delay-"):
                    seconds = int(command.removeprefix("watch-delay-"))
                    assert 0 <= seconds <= 300
                    payload = project_live(frame).to_json()
                    payload.update(history_state="loading", accounts=None,
                        daily_state="loading", daily_usage=None)
                    payload["active_cards"] = payload["active_cards"][:1 if seconds < 60 else 2]
                    for card in payload["active_cards"]:
                        row = card["rows"][0]
                        row["prompt"]["calls"] = seconds + 1
                        row["display"]["watch_duration_ms"] = f"{seconds}s"
                    host.events.publish("live", {"state": "running", "view": payload,
                        "source_observed_at_ms": int(time.time() * 1000)})
                elif command in {"quota-idle", "quota-ratio"}:
                    base_account = frame.quota.accounts[0]
                    idle_window = command == 'quota-idle'
                    primary = QuotaComponent('5-hour', 'rolling', remaining_fraction=Decimal(1) if idle_window else Decimal('.9'),
                        duration_seconds=18000, window_active=False if idle_window else None,
                        reset_at_ms=None if idle_window else int(time.time() * 1000) + 3600000, primary=True)
                    secondary = replace(primary, label='Weekly', duration_seconds=604800, primary=False)
                    quotas = (primary, secondary)
                    periods = tuple(QuotaPeriodProjection(q, ComparisonCost(Decimal(0) if idle_window else Decimal(100),
                        0 if idle_window else 1, 0 if idle_window else 1), None) for q in quotas)
                    idle = replace(base_account, account=replace(base_account.account, quotas=quotas,
                        primary_quota_label='5-hour'), quota_periods=periods)
                    publish(value=replace(frame, quota=replace(frame.quota, accounts=(idle,))))
                elif command.startswith('proof-'):
                    state = command.removeprefix('proof-')
                    history = tuple(replace(frame.history_cards[0], session_id=f'proof-{index}',
                        title=f'Latest sample {index}') for index in range(5))
                    publish(value=replace(frame, history_cards=history,
                        history_state='loading' if state == 'switch' else state,
                        history_scope='other-source' if state == 'switch' else 'fixed-source',
                        history_epoch=0 if state in {'loading', 'switch'} else 1,
                        history_total=12, history_checked=12 if state == 'observed' else 4,
                        history_verified_at_ms=None if state in {'loading', 'switch'} else 1000))
                elif command in {'history-times', 'history-dst'}:
                    instants = ((2026, 11, 5, 22, 47), (2026, 11, 5, 23, 8), None) if command == 'history-times' else (
                        (2026, 10, 25, 0, 30), (2026, 10, 25, 1, 30), (2026, 11, 5, 23, 8))
                    history = tuple(replace(frame.history_cards[0], session_id=f'earlier-{index}',
                        title='Earlier long session title ' * 20, rows=(replace(frame.history_cards[0].rows[0],
                            prompt=replace(frame.history_cards[0].rows[0].prompt,
                                completed_at_ms=int(datetime(*instant, tzinfo=timezone.utc).timestamp() * 1000) if instant else None)),))
                        for index, instant in enumerate(instants))
                    publish(value=replace(frame, active_cards=cards[:1], history_cards=history,
                        quota=replace(frame.quota, accounts=frame.quota.accounts[:1])), timezone_name='Europe/Stockholm')
                elif command.startswith('history-'):
                    _, count, prompt_count, *account_count = command.split('-')
                    history = tuple(replace(frame.history_cards[0], session_id=f'earlier-{index}',
                        title='Earlier long session title ' * 20, rows=(replace(frame.history_cards[0].rows[0],
                            prompt=replace(frame.history_cards[0].rows[0].prompt,
                                completed_at_ms=frame.now_ms - 100000 + index)),)) for index in range(int(count)))
                    current = tuple(replace(cards[0], focal_id=str(index), title='Active long title ' * 30,
                        rows=(replace(cards[0].rows[0], prompt=replace(cards[0].rows[0].prompt,
                            event_id=str(index), prompt_number=index + 23)),)) for index in range(int(prompt_count)))
                    quota = replace(frame.quota, accounts=frame.quota.accounts[:int(account_count[0])]) if account_count else frame.quota
                    publish(value=replace(frame, active_cards=current, history_cards=history, quota=quota,
                        running=running_prompts(current, 'observed')))
                elif command.startswith('density-'):
                    _, prompts, accounts, *flags = command.split('-')
                    current = tuple(replace(cards[0], focal_id=str(index),
                        title='Long session title ' * 30 if flags else cards[0].title,
                        rows=(replace(cards[0].rows[0], prompt=replace(cards[0].rows[0].prompt,
                            event_id=str(index), prompt_number=index + 23, at_ms=frame.now_ms - 10000 + index)),))
                        for index in range(int(prompts)))
                    quota = replace(frame.quota, accounts=tuple(replace(item, label=f'Subscription {index + 1}')
                        for index, item in enumerate(frame.quota.accounts[:int(accounts)])))
                    warning = 'warning' in flags
                    publish(state='recovering' if warning else 'running', value=replace(frame,
                        active_cards=current, quota=quota, quota_stale=warning,
                        daily_state='retrying' if warning else frame.daily_state,
                        running=running_prompts(current, 'observed')))
                else:
                    raise ValueError("unsupported_probe_command")
                print('{"ok":true}', flush=True)
        finally:
            timer.cancel()
            host.close()
            if sys.argv[2:] == ['--stats-slices']:
                print(json.dumps(dict(active=jobs._active is not None, hostFailure=host.failure is not None,
                    servingAlive=host.thread.is_alive(),
                    httpWorkersAlive=any(thread.is_alive() for thread in host.server._pool._threads),
                    eventsClosed=host.events.closed)), flush=True)


if __name__ == "__main__":
    main()
