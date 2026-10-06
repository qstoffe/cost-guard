from __future__ import annotations

import unittest
from dataclasses import replace

from src.domain import IntegrationHealth, NormalizedSession, Provenance, SessionCapabilities
from src.sources.errors import SourceUnavailableError
from src.sources.selection import SourceSelector, inspect_v1_v2_migration_gap


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
            [session("same", 30, "v1"), session("missing", 20, "v1")],
        )
        v2 = StubSource(
            "opencode-v2", IntegrationHealth(True, True, "ok"),
            [session("same", 10, "v2"), session("modern", 40, "v2")],
        )
        gap = inspect_v1_v2_migration_gap(v1, v2)
        self.assertTrue(gap.inspected)
        self.assertEqual(("missing",), gap.missing_in_v2)
        self.assertEqual(("same",), gap.newer_in_v1)
        self.assertIn("will not merge", gap.warning())

    def test_gap_warning_does_not_change_selected_v2_history(self) -> None:
        v1 = StubSource("opencode-v1", IntegrationHealth(True, True, "ok"), [session("legacy", 20, "v1")])
        v2 = StubSource("opencode-v2", IntegrationHealth(True, True, "ok"), [session("modern", 30, "v2")])
        selected = SourceSelector(v1_factory=lambda: v1, v2_factory=lambda: v2).select("auto")
        self.assertIs(v2, selected.source)
        self.assertEqual("v2", selected.selected)
        self.assertTrue(selected.migration_gap.has_gap)
        self.assertEqual(1, len(selected.warnings))


if __name__ == "__main__":
    unittest.main()
