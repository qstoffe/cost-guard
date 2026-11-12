"""Read-only real-installation finite AI Stats timings; numeric evidence only."""
import json
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
from statistics import median
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
    from src.reports.ai_stats_responses import response_bounds, response_duration, _explicit_tool_start
    inventory = dict(sampled=0, plausible_responses=0, positive_output=0, tool_responses=0,
                     tool_clipped=0, missing_streamed=0, outside_streamed=0,
                     streamed_before_tool=0, streamed_equal_tool=0, streamed_after_tool=0,
                     rejected_tool_starts=0, streamed_before_tool_end=0, streamed_after_tool_end=0,
                     min_ms=None, max_ms=None)
    deltas = dict(tool_from_created=[], streamed_from_tool=[], completed_from_streamed=[])

    def observed(bundle, reference, snapshot, config, **kwargs):
        # Inspect only already-acquired messages, retain counts, never text/IDs/times.
        messages = {(m.session_id, m.message_id): m for m in snapshot.messages}
        for request in snapshot.invocations:
            if inventory['sampled'] >= 32:
                break
            message = messages.get((request.session_id, request.message_id))
            bounds = response_bounds(request, message)
            if bounds is None or request.tokens.output + request.tokens.reasoning <= 0:
                continue
            inventory['sampled'] += 1
            left, right, _independent = bounds
            duration = response_duration(request, message)
            inventory['positive_output'] += request.tokens.output + request.tokens.reasoning > 0
            if duration:
                inventory['plausible_responses'] += 1
                inventory['min_ms'] = min(inventory['min_ms'] or duration, duration)
                inventory['max_ms'] = max(inventory['max_ms'] or duration, duration)
            all_tools = [(at, p) for p in message.parts if type(at := _explicit_tool_start(p)) is int] if message else []
            tools = [(at, p) for at, p in all_tools if left < at <= right]
            inventory['rejected_tool_starts'] += len(all_tools) - len(tools)
            if tools:
                at, part = min(tools, key=lambda pair: pair[0])
                inventory['tool_responses'] += 1
                streamed = message.metadata.get('streamed_at_ms')
                stream_end = type(streamed) is int and left < streamed <= right
                inventory['tool_clipped'] += not _independent and not stream_end and duration == at - left
                if type(streamed) is not int:
                    inventory['missing_streamed'] += 1
                elif not left <= streamed <= right:
                    inventory['outside_streamed'] += 1
                else:
                    inventory['streamed_before_tool'] += streamed < at
                    inventory['streamed_equal_tool'] += streamed == at
                    inventory['streamed_after_tool'] += streamed > at
                    deltas['tool_from_created'].append(at - left)
                    deltas['streamed_from_tool'].append(streamed - at)
                    deltas['completed_from_streamed'].append(right - streamed)
                    native = part.data.get('observed_time', {})
                    end = native.get('completed', native.get('end'))
                    if type(end) is int:
                        inventory['streamed_before_tool_end'] += streamed <= end
                        inventory['streamed_after_tool_end'] += streamed > end
        return payload(bundle, reference, snapshot, config, **kwargs)

    with patch('src.web.composition.CacheDatabase', lambda _root: CacheDatabase(Path(os.environ['COST_GUARD_PROBE_CACHE']))), \
            patch('src.reports.ai_stats.payload', observed):
        measured_report(sender, request)
    print(json.dumps(dict(timing_inventory=inventory,
        timing_deltas={key: dict(count=len(values), min=min(values), median=median(values), max=max(values))
                       for key, values in deltas.items() if values},
        qualification='approximate response round trip: independent step pair, stream end, then native-tool/completion fallback; not decoding speed')), flush=True)


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
        assert 'rates' not in traffic
        assert 'display_units' not in tokens and 'display_units' not in traffic
        assert len(traffic['podium']) <= 3
        previous = None
        for racer in traffic['podium']:
            expected = Decimal(racer['output_tokens']) * 1000 / racer['duration_ms']
            assert Decimal(racer['tokens_per_second']) == expected and 1 <= racer['sampled_calls'] <= 32
            assert previous is None or previous >= expected
            previous = expected
        for card in row['metrics']:
            assert 'Unavailable' not in json.dumps(card['display']) and 'N/A' not in json.dumps(card['display'])
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
                               podium_counts={row['period']: [r['sampled_calls'] for m in row['metrics']
                                   if m['metric'] == 'token-rate' for r in m['podium']] for row in result['view']['ai_stats']},
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
