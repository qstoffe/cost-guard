"""Bounded read-only Token Mix baseline; numeric observations, no history text."""
import json
import argparse
import os
from pathlib import Path
import sys
import tempfile
import time
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cold-and-warm', action='store_true')
    args = parser.parse_args()
    temporary = tempfile.TemporaryDirectory(dir=ROOT / 'cache', prefix='token-mix-probe-') if args.cold_and_warm else None
    if temporary:
        os.environ['COST_GUARD_PROBE_CACHE'] = temporary.name
    jobs = ReportJobs(target=isolated_report if temporary else measured_report)
    try:
        for attempt in range(2 if temporary else 1):
            if attempt:
                if 'finished_at' in jobs._jobs[key]:
                    jobs._jobs[key]['finished_at'] -= 61
            key = observe(jobs, attempt)
    finally:
        jobs.close()
        if temporary:
            temporary.cleanup()


def observe(jobs, attempt):
    started = time.monotonic()
    key = jobs.submit(ReportRequest(ReportKind.TOKEN_MIX))
    while time.monotonic() - started < 130:
        jobs.tick()
        value = jobs.snapshot(key)
        if value['status'] not in {'queued', 'running'}:
            result = value.get('result') or {}
            view = result.get('view') or {}
            print(json.dumps(dict(attempt=attempt, seconds=round(time.monotonic() - started, 3),
                status=value['status'], error=value['error'], result_error=result.get('error'),
                model_rows=len(view.get('model_token_mix', [])),
                publisher_rows=len(view.get('publisher_token_mix', [])),
                progress=value.get('progress'))))
            return key
        time.sleep(.05)
    raise RuntimeError('probe_deadline')


if __name__ == '__main__':
    main()
