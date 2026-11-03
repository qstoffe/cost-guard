"""Synthetic finite hourly-cost captures shared by tests and the browser probe."""
from dataclasses import replace
from datetime import datetime

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.report_runtime import FakeSource
from development.tests.fixtures.session_snapshots import DAY, history
from src.analysis.active_hour import HOUR_MS
from src.application import ReportApplication
from src.reports import ReportKind, ReportRequest


def epoch(text):
    return int(datetime.fromisoformat(text).timestamp() * 1000)


def clean_service(owner, snapshot=None, *, now=DAY * 40, zone="UTC"):
    service = report_service(owner, FakeSource(snapshot), now_ms=now, timezone_id=zone)
    service.selection = replace(service.selection, warnings=())
    return service


def hourly_result(owner):
    now = epoch("2026-10-30T12:00:00+00:00")
    snapshot = history(((now - HOUR_MS, now - HOUR_MS // 2), (now - HOUR_MS // 4, now)))
    root = replace(snapshot.root, updated_at_ms=now)
    snapshot = replace(snapshot, root=root, sessions=(root,))
    app = ReportApplication(lambda clock, progress: clean_service(owner, snapshot, now=clock), clock=lambda: now)
    return app.execute(ReportRequest(ReportKind.COST_PER_HOUR)).to_json()
