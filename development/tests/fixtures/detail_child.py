"""Spawned synthetic detail attempts; no real source, provider or model calls."""
import time
import unittest

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application.session_detail import acquire_detail
from src.domain.progress import observe_work, observing_work
from src.watch.detail_capture import WorkMeter, read_payload, write_payload
from src.web.jobs import run_owned_report


def run_owned_fixture(shared, paths):
    run_owned_report(run_fixture, shared, paths)


class DelayedDetailSource(SyntheticMonthSource):
    """Synthetic batched source latency inside the actual history acquisition."""
    def get_session_tree_revision(self, session_id):
        time.sleep(.3)
        return super().get_session_tree_revision(session_id)

    def load_session_snapshot(self, session_id):
        snapshot = super().load_session_snapshot(session_id)
        total = len(snapshot.messages)
        for offset in range(0, total, 100):
            # Each bounded source-shaped message batch is genuinely consumed.
            batch = snapshot.messages[offset:offset + 100]
            time.sleep(.24)
            observe_work('reading', len(batch), completed=offset + len(batch), total=total)
        return snapshot


def run_fixture(shared, paths):
    meter = WorkMeter(shared)
    payload = read_payload(paths[0])
    meter.observe('reading', 1)
    mode = payload['config'].get('detail_test')
    if mode == 'crash':
        raise RuntimeError('synthetic child crash')
    if mode == 'locked':
        shared.get_lock().acquire()
        while True:
            time.sleep(.05)
    if payload['key'] == 'root-0000' and mode in ('blocked', 'identical'):
        while True:
            meter.observe('reading', 0)  # Callback traffic is not useful work.
            time.sleep(.05)
    owner = unittest.TestCase()
    try:
        with observing_work(meter.observe):
            if mode == 'progress':
                for _ in range(25):
                    meter.observe('reading', 1)
                    time.sleep(.1)
            source_type = DelayedDetailSource if mode == 'delayed' else SyntheticMonthSource
            source = source_type(2, payload['config'].get('detail_rows', 3), month_start_ms=1000)
            if 'detail_snapshots' in payload['config']:
                source.snapshots = payload['config']['detail_snapshots']
            service = report_service(owner, source, now_ms=payload['now_ms'])
            outcome = acquire_detail(service, payload['history'], payload['key'])
            outcome['work'] = dict(snapshot_reads=source.load_count)
            write_payload(paths[1], outcome, meter.observe)
    finally:
        owner.doCleanups()
