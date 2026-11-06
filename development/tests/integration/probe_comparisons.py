"""Read-only real-installation finite Comparisons cold/warm observations, no payloads."""
import json
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
    with tempfile.TemporaryDirectory(dir=os.environ['OPENCODE_TOOLKIT_SESSION_SCRATCH'], prefix='comparisons-cache-') as cache:
        os.environ['COST_GUARD_PROBE_CACHE'] = cache
        jobs = ReportJobs(target=isolated_report)
        outcomes = []
        try:
            for attempt in range(2):
                if attempt:
                    jobs._jobs[key]['finished_at'] = 0
                start = time.monotonic()
                key = jobs.submit(ReportRequest(ReportKind.COMPARISONS))
                while time.monotonic() - start < 130:
                    jobs.tick()
                    job = jobs.snapshot(key)
                    if job['status'] not in ('queued', 'running'):
                        result = job.get('result') or {}
                        page = (result.get('view') or {}).get('comparisons') or {}
                        summary = dict(attempt=attempt, status=job['status'], seconds=round(time.monotonic() - start, 3),
                            error=job['error'], result_error=result.get('error'), complete=page.get('complete'),
                            scanned=page.get('scanned'), excluded=page.get('excluded'), total_groups=page.get('total'),
                            displayed_groups=len(page.get('groups', [])),
                            displayed_runs=sum(len(group['runs']) for group in page.get('groups', [])), progress=job.get('progress'))
                        outcomes.append(summary)
                        print(json.dumps(summary), flush=True)
                        break
                    time.sleep(.05)
                else:
                    raise RuntimeError('probe_deadline')
        finally:
            jobs.close()
        if any(row['status'] != 'complete' or row['result_error'] for row in outcomes):
            raise SystemExit(1)


if __name__ == '__main__':
    main()
