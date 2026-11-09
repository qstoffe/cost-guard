"""Read-only real-installation finite AI Stats timings; numeric evidence only."""
import json
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
from decimal import Decimal
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.integration.historical_report_observations import measured_report
from src.reports import ReportKind, ReportRequest
from src.web.jobs import ReportJobs


def isolated_report(sender, request):
    from src.cache import CacheDatabase
    with patch('src.web.composition.CacheDatabase', lambda _root: CacheDatabase(Path(os.environ['COST_GUARD_PROBE_CACHE']))):
        measured_report(sender, request)


def check_rates(result):
    checks = []
    for row in (result.get('view') or {}).get('ai_stats', []):
        hourly, cost, working = row['metrics'][:3]
        rates = hourly['rates']
        total, duration = Decimal(cost['value']), Decimal(working['value'])
        active = total * 3_600_000 / duration if duration else Decimal(0)
        assert Decimal(rates['total']) == total
        assert Decimal(rates['active_rate']) == active
        assert Decimal(rates['robot_day']) == active * 8
        assert Decimal(rates['robot_period']) == active * 8 * rates['workdays']
        assert Decimal(rates['calendar_rate']) == (total / rates['calendar_hours'] if rates['calendar_hours'] else 0)
        assert (Decimal(rates['workday_rate']) if rates['workday_rate'] is not None else None) == (
            total / rates['workday_hours'] if rates['workday_hours'] else None)
        for unit in ('credits', 'usd'):
            for key in ('calendar_rate', 'workday_rate', 'robot_day', 'rate_help'):
                assert isinstance(hourly.get('display_units', {}).get(unit, {}).get(key, hourly['display'].get(key)), str)
        checks.append(row['period'])
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cold-and-warm', action='store_true')
    parser.add_argument('--budget-seconds', type=float, default=600,
                        help='Bounded probe budget per logical attempt; child watchdogs remain unchanged')
    args = parser.parse_args()
    if not 1 <= args.budget_seconds <= 1800:
        parser.error('budget-seconds must be between 1 and 1800')
    temporary = tempfile.TemporaryDirectory(dir=os.environ['OPENCODE_TOOLKIT_SESSION_SCRATCH'], prefix='ai-stats-cache-') if args.cold_and_warm else None
    if temporary:
        os.environ['COST_GUARD_PROBE_CACHE'] = temporary.name
    jobs = ReportJobs(target=isolated_report if temporary else measured_report)
    try:
        for scope in ('30-days', 'all'):
            for attempt in range(2):
                request = ReportRequest(ReportKind.AI_STATS, stats_scope=scope)
                if attempt:
                    jobs._jobs[key]['finished_at'] = 0
                started = time.monotonic()
                key = jobs.submit(request)
                while time.monotonic() - started < args.budget_seconds:
                    jobs.tick()
                    job = jobs.snapshot(key)
                    if job['status'] not in ('queued', 'running'):
                        result = job.get('result') or {}
                        states = {row['period']: [dict(metric=metric['metric'], status=metric['status'],
                            reasons=metric.get('reasons', []), value_present=metric['value'] is not None)
                            for metric in row['metrics']] for row in (result.get('view') or {}).get('ai_stats', [])}
                        print(json.dumps(dict(scope=scope, attempt=attempt, status=job['status'],
                            seconds=round(time.monotonic() - started, 3), error=job['error'],
                             result_error=result.get('error'), periods=len((result.get('view') or {}).get('ai_stats', [])),
                             rate_checks=check_rates(result),
                             progress=job.get('progress'), work=job.get('work'), metric_states=states)), flush=True)
                        break
                    time.sleep(.05)
                else:
                    raise RuntimeError('probe_deadline')
    finally:
        jobs.close()
        if temporary:
            temporary.cleanup()


if __name__ == '__main__':
    main()
