"""Controlled monotonic lease age; only the disposable synthetic Sessions host."""
from dataclasses import replace
import time

from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application.session_catalog import SessionCatalog
from src.watch.observers import observe_catalog


def configure(runtime, command):
    runtime.scalar_hold = True
    if command.startswith('catalog-idle-source-'):
        count = int(command.removeprefix('catalog-idle-source-'))
        runtime.service.source.snapshots = {
            key: replace(snapshot, complete=True)
            for key, snapshot in SyntheticMonthSource(count, 1, month_start_ms=1000).snapshots.items()
        }
        runtime.catalog = SessionCatalog(clock_ms=lambda: runtime.service.now_ms,
            clock=lambda: time.monotonic() + runtime.catalog_clock_offset,
            timezone_id=runtime.service.timezone_id)
        runtime.catalog.observe(observe_catalog(runtime.service.source, include_archived_revisions=True))
    elif command == 'catalog-idle-advance-240':
        runtime.catalog_clock_offset += 240
    elif command == 'catalog-idle-advance-301':
        runtime.catalog_clock_offset += 301
    elif command != 'catalog-idle-observe':
        raise ValueError('unknown_idle_command')
    return dict(ok=True, roots=len(runtime.catalog.roots), history_reads=runtime.service.source.load_count,
        metrics=dict(runtime.catalog.metrics), leases=len(runtime.catalog.lease_pages.leases))
