"""Capture synthetic CLI text, not OS/browser screenshots or live source evidence."""
from dataclasses import replace
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.compact_reports import rendered, report_service
from development.tests.fixtures.warning_projections import warning_prompt, warning_watch_projection
from src.analysis.context import PriceWarningSeverity
from src.presentation import WatchRenderer
from src.reports import ReportKind, ReportRequest


def main():
    owner = unittest.TestCase()
    try:
        service = report_service(owner)
        owner.addCleanup(service.close_accounts)
        reports = []
        for kind in ReportKind:
            request = ReportRequest(kind, session_id="root" if kind is ReportKind.SESSION else None,
                                    date_text="1970-01-01" if kind is ReportKind.DATE else None)
            report = service.build_token_mix_history() if kind is ReportKind.TOKEN_MIX else service.build(request)
            reports.append(report)
        reports.append(service.build(ReportRequest(ReportKind.DATE, date_text="1970-01-01:1970-01-02")))
        frame = replace(warning_watch_projection(warning_prompt(PriceWarningSeverity.NONE)),
                        token_mix=reports[0].token_mix)
        destination = ROOT / "development/tests/fixtures/token-categories"
        destination.mkdir(exist_ok=True)
        for width in (80, 120, 160):
            chunks = [f"Synthetic CLI text at {width} columns; no live source or browser evidence.\n"
                      "Numeric prompt/Watch grids retain their minimum widths (no clipping);\n"
                      "Token Mix cells wrap, and narrow historical tables use labeled rows.\n"]
            for report in reports:
                chunks.extend((f"\n=== {report.kind.value} ===\n", rendered(report, width=width)))
            stream = io.StringIO()
            WatchRenderer({"timezone": "UTC"}, stream=stream, interactive=False,
                          terminal_width=width, started_at_ms=1000).render(frame)
            chunks.extend(("\n=== watch ===\n", stream.getvalue()))
            (destination / f"{width}.txt").write_text("".join(chunks), encoding="utf-8")
    finally:
        owner.doCleanups()


if __name__ == "__main__":
    main()
