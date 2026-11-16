"""Controlled warm-root arrival cost against an exact Git baseline.

Backend wall time is real; the client replay clock is explicitly simulated.
Native source -> shared-owner -> real browser latency is a separate probe.
"""
import argparse
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import src.application.session_catalog as current
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from src.reports.models import SessionUsageRow
from src.watch.observers import observe_catalog


def measure(module, size, passive):
    now = 1_000_000_000
    source = SyntheticMonthSource(size, 1, month_start_ms=1000)
    catalog = module.SessionCatalog(clock=lambda: 0, clock_ms=lambda: now)
    catalog.observe(observe_catalog(source, include_archived_revisions=True))
    for number, (key, root) in enumerate(catalog.roots.items()):
        catalog.rows[key] = SessionUsageRow(key, root.title, "Known", False, Decimal(1), 1,
            duration_ms=1000, context_tokens=100, last_activity_ms=catalog.activity[key])
        catalog.valid[key] = catalog.revisions[key], 0
        catalog.activity_valid[key] = catalog.revisions[key]
    first = catalog.page(period="all")
    pinned = catalog.page(token=first["token"], period="all", offset=25, epoch=first["epoch"]) if size > 25 else None
    snapshot = make_root_snapshot(size, 1, month_start_ms=now - size * 60_000 - 1000)
    source.snapshots[snapshot.root.session_id] = snapshot
    catalog.observe(observe_catalog(source, include_archived_revisions=True))
    times, cpu = [], time.process_time()
    for _ in range(10):
        start = time.perf_counter()
        page = catalog.page(token=first["token"], period="all", **({"passive": True} if passive else {}))
        times.append((time.perf_counter() - start) * 1000)
    if pinned:
        following = catalog.page(token=first["token"], period="all", offset=25, epoch=first["epoch"])
        assert following["view"]["session_usage"] == pinned["view"]["session_usage"]
    assert page["pending_sort"] and page["view"]["session_usage"][0]["session_id"] == snapshot.root.session_id
    assert source.load_count == 0 and catalog.metrics["attempts"] == 0
    assert source.catalog_count == 2
    return dict(roots=size, arm="current" if passive else "baseline",
        page_median_ms=round(statistics.median(times), 3), page_max_ms=round(max(times), 3),
        ten_pages_cpu_ms=round((time.process_time() - cpu) * 1000, 3),
        source_catalog_reads=source.catalog_count, history_reads=source.load_count,
        scalar_attempts=catalog.metrics["attempts"], older_page_unchanged=pinned is not None,
        first=first, arrival=page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    baseline = ModuleType("arrivals_baseline")
    baseline.__package__ = "src.application"
    original = subprocess.run(["git", "show", args.baseline + ":src/application/session_catalog.py"],
        cwd=ROOT, check=True, capture_output=True, encoding="utf-8").stdout
    exec(compile(original, "<git-arrivals-baseline>", "exec"), baseline.__dict__)
    results = [measure(module, size, passive) for size in (25, 26, 324, 3217, 5000)
               for module, passive in ((baseline, False), (current, True))]
    original_js = subprocess.run(["git", "show", args.baseline + ":src/web/assets/sessions.js"],
        cwd=ROOT, check=True, capture_output=True, encoding="utf-8").stdout
    replay = subprocess.run(["node", "development/tests/fixtures/sessions_arrivals_replay.cjs"],
        cwd=ROOT, input=json.dumps(dict(baseline=original_js, results=results)),
        capture_output=True, text=True, encoding="utf-8", check=True)
    for result in results:
        result.pop("first")
        result.pop("arrival")
    evidence = dict(baseline=args.baseline, scope="controlled normalized warm roots, no personal source",
        backend=results, client=json.loads(replay.stdout),
        limitations="Replay time is simulated; no inference or empirical workstation-scale native-source latency claim.")
    args.output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
