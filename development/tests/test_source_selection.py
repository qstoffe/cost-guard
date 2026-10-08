from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from development.fixtures.synthetic_month import SyntheticMonthSource
from development.tests.test_analysis_core import make_snapshot
from development.tests.test_compact_reports import NOW, START, Availability, rendered
from development.tests.test_step7_reports_cli import FakePricingProvider
from development.tests.test_step8_watch import MutableSource, make_service as make_watch_service
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import IntegrationHealth, NormalizedSession, Provenance, SessionCapabilities
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.migration_notice import migration_gap_notes
from src.sources.errors import SourceUnavailableError
from src.sources.selection import (
    MISSING_IN_V2, NEWER_IN_V1, MigrationGapDiagnostic, MigrationGapSession, SourceSelection, SourceSelector,
    inspect_v1_v2_migration_gap,
)
from src.watch import WatchCoordinator

ROOT = Path(__file__).resolve().parents[2]


CAPS = SessionCapabilities()


def session(session_id: str, updated: int, generation: str) -> NormalizedSession:
    return NormalizedSession(
        session_id=session_id,
        title=session_id,
        created_at_ms=1,
        updated_at_ms=updated,
        provenance=Provenance("opencode", generation, source_session_id=session_id),
        capabilities=CAPS,
    )


class StubSource:
    def __init__(self, source_id: str, health: IntegrationHealth, sessions=()):
        self.source_id = source_id
        self.capabilities = CAPS
        self._health = health
        self._sessions = tuple(sessions)

    def probe(self):
        return self._health

    def list_sessions(self, since_ms=None):
        values = self._sessions
        if since_ms is not None:
            values = tuple(item for item in values if item.updated_at_ms >= since_ms)
        return values

    def get_session_tree_revision(self, session_id):
        return "stub"

    def load_session_snapshot(self, session_id):
        raise AssertionError("source selection must not hydrate sessions")


class SourceSelectionTests(unittest.TestCase):
    def test_auto_prefers_healthy_v2_and_never_merges_sources(self) -> None:
        v1 = StubSource("opencode-v1", IntegrationHealth(True, True, "ok"), [session("a", 10, "v1")])
        v2 = StubSource("opencode-v2", IntegrationHealth(True, True, "ok"), [session("a", 10, "v2")])
        selected = SourceSelector(v1_factory=lambda: v1, v2_factory=lambda: v2).select("auto")
        self.assertEqual("v2", selected.selected)
        self.assertIs(v2, selected.source)
        self.assertEqual((), selected.warnings)

    def test_auto_falls_back_to_v1_with_visible_warning_when_v2_is_detected_but_unhealthy(self) -> None:
        v1 = StubSource("opencode-v1", IntegrationHealth(True, True, "v1 ok"))
        v2 = StubSource("opencode-v2", IntegrationHealth(True, False, "service stale"))
        selected = SourceSelector(v1_factory=lambda: v1, v2_factory=lambda: v2).select("auto")
        self.assertEqual("v1", selected.selected)
        self.assertTrue(any("V2 was detected" in warning for warning in selected.warnings))

    def test_auto_uses_v1_silently_when_v2_is_absent(self) -> None:
        v1 = StubSource("opencode-v1", IntegrationHealth(True, True, "v1 ok"))
        v2 = StubSource("opencode-v2", IntegrationHealth(False, False, "missing"))
        selected = SourceSelector(v1_factory=lambda: v1, v2_factory=lambda: v2).select("auto")
        self.assertEqual("v1", selected.selected)
        self.assertEqual((), selected.warnings)

    def test_forced_source_never_falls_back(self) -> None:
        v1 = StubSource("opencode-v1", IntegrationHealth(True, True, "v1 ok"))
        v2 = StubSource("opencode-v2", IntegrationHealth(False, False, "missing"))
        selector = SourceSelector(v1_factory=lambda: v1, v2_factory=lambda: v2)
        with self.assertRaises(SourceUnavailableError):
            selector.select("v2")
        self.assertEqual("v1", selector.select("v1").selected)

    def test_no_healthy_source_is_actionable(self) -> None:
        v1 = StubSource("opencode-v1", IntegrationHealth(False, False, "v1 missing"))
        v2 = StubSource("opencode-v2", IntegrationHealth(False, False, "v2 missing"))
        with self.assertRaisesRegex(SourceUnavailableError, "No supported healthy OpenCode source"):
            SourceSelector(v1_factory=lambda: v1, v2_factory=lambda: v2).select("auto")

    def test_metadata_gap_detects_missing_and_newer_v1_sessions(self) -> None:
        v1 = StubSource(
            "opencode-v1", IntegrationHealth(True, True, "ok"),
            [session("same", 30, "v1"), session("missing", 20, "v1"),
             replace(session("child", 25, "v1"), parent_session_id="missing")],
        )
        v2 = StubSource(
            "opencode-v2", IntegrationHealth(True, True, "ok"),
            [session("same", 10, "v2"), session("modern", 40, "v2")],
        )
        gap = inspect_v1_v2_migration_gap(v1, v2)
        self.assertTrue(gap.inspected)
        self.assertEqual(("child", "missing"), gap.missing_in_v2)
        self.assertEqual(("same",), gap.newer_in_v1)
        windows = {item.session_id: item for item in gap.sessions}
        self.assertEqual(("missing", MISSING_IN_V2, 1, 25), (windows["child"].root_session_id, windows["child"].kind,
                                                             windows["child"].first_ms, windows["child"].last_ms))
        # Only V1 activity after the V2 copy's last update can be unrepresented.
        self.assertEqual(("same", NEWER_IN_V1, 10, 30), (windows["same"].root_session_id, windows["same"].kind,
                                                         windows["same"].first_ms, windows["same"].last_ms))

    def test_gap_is_evidence_not_a_source_warning_and_keeps_selected_v2_history(self) -> None:
        v1 = StubSource("opencode-v1", IntegrationHealth(True, True, "ok"), [session("legacy", 20, "v1")])
        v2 = StubSource("opencode-v2", IntegrationHealth(True, True, "ok"), [session("modern", 30, "v2")])
        selected = SourceSelector(v1_factory=lambda: v1, v2_factory=lambda: v2).select("auto")
        self.assertIs(v2, selected.source)
        self.assertEqual("v2", selected.selected)
        self.assertTrue(selected.migration_gap.has_gap)
        self.assertEqual((), selected.warnings)


def gap_at(*windows: tuple[str, str, int, int], kind: str = MISSING_IN_V2) -> MigrationGapDiagnostic:
    """Diagnostic with (session, root, first_ms, last_ms) V1 activity windows."""
    sessions = tuple(MigrationGapSession(sid, root, kind, first, last) for sid, root, first, last in windows)
    ids = tuple(item.session_id for item in sessions)
    return MigrationGapDiagnostic(True, ids if kind == MISSING_IN_V2 else (),
                                  ids if kind == NEWER_IN_V1 else (), "complete", sessions)


class MigrationGapScopeTests(unittest.TestCase):
    """Report relevance of migration gaps; Watch/Diagnostics consume them differently."""

    DAY = 86_400_000
    CUTOFF = START + 7 * 60_000  # oldest prompt in the bounded synthetic 100-prompt sample

    def service(self, source, gap):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db = CacheDatabase(Path(tmp.name)); db.initialize()
        config = dict(load_configuration(ROOT).values)
        config["timezone"] = "UTC"
        return ReportService(
            selection=SourceSelection(source, "v2", ("Source-wide warning",), source.probe(), gap),
            pricing_provider=FakePricingProvider(), account_provider=None, cache_repository=CacheRepository(db),
            config=config, now_ms=NOW, model_availability_source=Availability(),
        )

    @staticmethod
    def gap_notes(report) -> list[str]:
        return [note for note in report.notes if "OpenCode V1" in note]

    def test_notes_are_counted_per_scope(self) -> None:
        gap = replace(gap_at(("a", "a", 10, 20), ("b", "root", 100, 200)), newer_in_v1=("c",))
        self.assertIn("2 missing from V2, 1 newer than their V2 copy", migration_gap_notes(gap)[0])
        self.assertIn("(1 missing from V2)", migration_gap_notes(gap, start_ms=150)[0])
        self.assertEqual((), migration_gap_notes(gap, start_ms=201))
        self.assertEqual((), migration_gap_notes(gap, start_ms=21, end_ms=100))
        self.assertTrue(migration_gap_notes(gap, start_ms=0, end_ms=11))
        self.assertTrue(migration_gap_notes(gap, root_id="root"))
        self.assertEqual((), migration_gap_notes(gap, root_id="other"))
        self.assertEqual((), migration_gap_notes(MigrationGapDiagnostic(True)))
        self.assertEqual((), migration_gap_notes(None))

    def test_normal_report_note_follows_the_bounded_sample_cutoff(self) -> None:
        source = SyntheticMonthSource(12, 20, month_start_ms=START)
        relevant = self.service(source, gap_at(("legacy", "legacy", START - self.DAY, self.CUTOFF)))
        report = relevant.build(ReportRequest())
        self.assertEqual(100, report.model_comparison_sample_size)
        self.assertEqual(1, len(self.gap_notes(report)))
        self.assertEqual(("Source-wide warning",), report.source_warnings)
        text = rendered(report)
        self.assertIn("* OpenCode V1 has session(s) relevant to this report", text)
        self.assertNotIn("WARNING: OpenCode V1", text)
        for kind in (MISSING_IN_V2, NEWER_IN_V1):
            older = self.service(source, gap_at(("legacy", "legacy", START - self.DAY, self.CUTOFF - 1), kind=kind))
            self.assertEqual([], self.gap_notes(older.build(ReportRequest())), kind)
            self.assertEqual([], self.gap_notes(older.build(ReportRequest(ReportKind.ALL_MODELS))), kind)

    def test_short_sample_spans_all_history_so_any_gap_is_relevant(self) -> None:
        service = self.service(SyntheticMonthSource(2, 20, month_start_ms=START), gap_at(("old", "old", 1, 2)))
        self.assertEqual(1, len(self.gap_notes(service.build(ReportRequest()))))

    def test_date_report_note_requires_overlap_with_the_requested_period(self) -> None:
        source = SyntheticMonthSource(12, 20, month_start_ms=START)
        day = START - (START % self.DAY)  # 2026-09-30 UTC
        inside = self.service(source, gap_at(("legacy", "legacy", day + 1_000, day + 2_000)))
        self.assertEqual(1, len(self.gap_notes(inside.build(ReportRequest(ReportKind.DATE, date_text="2026-09-30")))))
        before = self.service(source, gap_at(("legacy", "legacy", day - 2 * self.DAY, day - 1)))
        self.assertEqual([], self.gap_notes(before.build(ReportRequest(ReportKind.DATE, date_text="2026-09-30"))))
        ranged = before.build(ReportRequest(ReportKind.DATE, date_text="2026-09-28:2026-09-30"))
        self.assertEqual(1, len(self.gap_notes(ranged)))

    def test_session_report_ignores_unrelated_v1_sessions(self) -> None:
        source = SyntheticMonthSource(2, 5, month_start_ms=START)
        unrelated = self.service(source, gap_at(("legacy", "legacy", START, NOW)))
        self.assertEqual([], self.gap_notes(unrelated.build(ReportRequest(ReportKind.SESSION, session_id="root-0001"))))
        related = self.service(source, gap_at(("legacy-child", "root-0001", START, START + 1)))
        self.assertEqual(1, len(self.gap_notes(related.build(ReportRequest(ReportKind.SESSION, session_id="root-0001")))))

    def test_all_history_views_keep_any_gap(self) -> None:
        service = self.service(SyntheticMonthSource(2, 5, month_start_ms=START), gap_at(("old", "old", 1, 2)))
        self.assertEqual(1, len(self.gap_notes(service.build_token_mix_history())))
        self.assertEqual(1, len(self.gap_notes(service.build(ReportRequest(ReportKind.SESSIONS)))))
        limited = service.build(ReportRequest(ReportKind.SESSIONS, session_limit=1))
        self.assertEqual([], self.gap_notes(limited))

    def test_watch_never_projects_migration_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=False))
            config, selection, service, _db = make_watch_service(td, source)
            gapped = replace(selection, migration_gap=gap_at(("legacy", "root", 0, 10**15)))
            service.selection = gapped
            projection = WatchCoordinator(selection=gapped, report_service=service, config=config,
                                          clock_ms=lambda: 2200).initialize().projection
        self.assertEqual((), projection.source_warnings)

    def test_diagnostics_keep_full_gap_counts_regardless_of_report_scope(self) -> None:
        from development.tools import collect_diagnostics as diag

        healthy = SimpleNamespace(available=True, healthy=True, detail="ok")
        source = SimpleNamespace(probe=lambda: healthy, diagnostic_metadata=lambda: {},
                                 database_path="db", registration_path="service.json")
        gap = replace(gap_at(("a", "a", 1, 2), ("b", "b", 1, 2)), newer_in_v1=("c",))
        selected = SimpleNamespace(selected="v2", warnings=(), selected_health=healthy, migration_gap=gap)
        with mock.patch.object(diag, "OpenCodeV1Source", return_value=source), \
             mock.patch.object(diag, "OpenCodeV2Source", return_value=source), \
             mock.patch.object(diag, "_safe_source_stats", return_value={"probe": {"healthy": True}}), \
             mock.patch.object(diag, "SourceSelector") as selector, \
             tempfile.TemporaryDirectory() as root, \
             mock.patch.object(diag, "CacheDatabase", lambda _root: CacheDatabase(Path(root))):
            selector.return_value.select.return_value = selected
            result = diag.collect(network=False, snapshots=0)
            self.assertFalse((Path(root) / "cache").exists())  # read-only freshness probe
        self.assertEqual({"cache_present": False, "status": "no_cached_catalog"}, result["model_freshness"])
        self.assertEqual({"inspected": True, "missing_in_v2": 2, "newer_in_v1": 1, "detail": "complete"},
                         result["selection"]["migration_gap"])


if __name__ == "__main__":
    unittest.main()
