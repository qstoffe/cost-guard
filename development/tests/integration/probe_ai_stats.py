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
from src.numbers import ccost_amount
from src.web.jobs import ReportJobs


def isolated_report(sender, request):
    from src.cache import CacheDatabase
    from src.reports.ai_stats import payload
    inventory = dict(sampled=0, created=0, completed=0, streamed=0, qualified_generation_intervals=0)

    def observed(bundle, reference, snapshot, config):
        # Inspect only already-acquired messages, retain counts, never text/IDs/times.
        for message in snapshot.messages:
            if inventory['sampled'] >= 32:
                break
            if message.role.value != 'assistant':
                continue
            inventory['sampled'] += 1
            inventory['created'] += message.created_at_ms > 0
            inventory['completed'] += message.completed_at_ms is not None
            inventory['streamed'] += 'streamed_at_ms' in message.metadata
        return payload(bundle, reference, snapshot, config)

    with patch('src.web.composition.CacheDatabase', lambda _root: CacheDatabase(Path(os.environ['COST_GUARD_PROBE_CACHE']))), \
            patch('src.reports.ai_stats.payload', observed):
        measured_report(sender, request)
    print(json.dumps(dict(timing_inventory=inventory,
        qualification='created/completed/streamed do not establish first/last output-token generation boundaries')), flush=True)


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
            for key in ('calendar_rate', 'workday_rate', 'active_rate', 'rate_help'):
                assert isinstance(hourly.get('display_units', {}).get(unit, {}).get(key, hourly['display'].get(key)), str)
            display = {**hourly['display'], **hourly['display_units'][unit]}
            expected = ccost_amount(min(Decimal('1e12'), active), unit=unit) + (' CCost/h' if unit == 'credits' else '/h')
            assert display['active_rate'] == expected
            assert len(display['rate_help'].split('\n\n')) == 3
            assert display['rate_help'].endswith('(Total CCost ÷ active AI hours)')
        metrics = {m['metric']: m for m in row['metrics']}
        tokens, traffic = metrics['total-tokens'], metrics['token-rate']
        assert len(metrics) == 12 and int(tokens['exact_value']) == tokens['value']
        for field in ('calendar_days', 'workdays', 'calendar_hours', 'workday_hours', 'active_hours'):
            assert traffic['rates'][field] == rates[field]
        assert Decimal(traffic['rates']['total']) == tokens['value']
        assert 'display_units' not in tokens and 'display_units' not in traffic
        if tokens['status'] == 'complete':
            assert Decimal(traffic['rates']['calendar_rate']) == (Decimal(tokens['value']) / rates['calendar_hours'] if rates['calendar_hours'] else 0)
        if not traffic['reasons']:
            assert Decimal(traffic['rates']['active_rate']) == (Decimal(tokens['value']) * 3_600_000 / duration if duration else 0)
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
                        assert job['status'] == 'complete' and not job['error'] and not result.get('error')
                        assert len((result.get('view') or {}).get('ai_stats', [])) == 5
                        states = {row['period']: [dict(metric=metric['metric'], status=metric['status'],
                            reasons=metric.get('reasons', []), value_present=metric['value'] is not None)
                            for metric in row['metrics']] for row in (result.get('view') or {}).get('ai_stats', [])}
                        print(json.dumps(dict(scope=scope, attempt=attempt, status=job['status'],
                            seconds=round(time.monotonic() - started, 3), error=job['error'],
                             result_error=result.get('error'), periods=len((result.get('view') or {}).get('ai_stats', [])),
                              rate_checks=check_rates(result),
                              payload_bytes=len(json.dumps(result, separators=(',', ':')).encode()),
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
