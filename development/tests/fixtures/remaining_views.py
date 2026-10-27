"""Frozen CLI/Web acceptance cases; synthetic data and no external acquisition."""
from dataclasses import replace

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.account_views import account_report
from development.tests.fixtures.model_views import model_report
from development.tests.fixtures.synthetic_month import SyntheticMonthSource
from src.application.projection import project
from src.reports import ReportKind, ReportRequest

NOW = 1_793_052_000_000
ZONE = "Europe/Stockholm"


def remaining_reports(test):
    source = SyntheticMonthSource(1, 120, month_start_ms=NOW - 120_000,
        running_roots=1, now_ms=NOW)
    service = report_service(test, source, now_ms=NOW, timezone_id=ZONE)
    test.addCleanup(service.close_accounts)
    session = service.build(ReportRequest(ReportKind.SESSION, session_id="root-0000"))
    dated = service.build(ReportRequest(ReportKind.DATE, date_text="2026-10-26:2026-10-27"))
    mix = service.build_token_mix_history()
    normal = replace(model_report(), accounts_quotas=account_report().accounts_quotas)
    return {"normal": normal, "all-models": model_report(all_models=True), "session": session,
        "date": dated, "token-mix": mix, "sessions": service.build(ReportRequest(ReportKind.SESSIONS))}


def result(report):
    return dict(observed_at_ms=NOW, scope=dict(timezone_id=ZONE, date_text="2026-10-26:2026-10-27",
        start_ms=1_792_965_600_000, end_ms=1_793_138_400_000),
        source=dict(status="acquired", atomicity="per_root_snapshot"), view=project(report, ZONE).to_json())


def detail_page(full, offset=0, state="available"):
    import copy
    page = copy.deepcopy(full)
    block = page["view"]["prompt_blocks"][0]
    total = len(block["rows"])
    offset = min(offset, max(0, total - 50))
    for row in block["rows"]:
        row.update(id=row["event_id"], retained=False, last_observed_at_ms=NOW)
    block["rows"] = block["rows"][offset:offset + 50]
    return dict(result=page, total=total, offset=offset, revision="synthetic-revision", state=state)
