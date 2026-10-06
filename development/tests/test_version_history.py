"""History structure is bounded at every heading depth, not only H2."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from development.tools.validate_package import Results, check_history_bounds

ROOT = Path(__file__).resolve().parents[2]


def history(major=78, minor=19):
    entries = "\n".join(f"## v{major}.{number} — 2026-09-30\n\n- Net behavior.\n"
                        for number in range(minor, max(-1, minor - 5), -1))
    return (f"# Cost Guard version history\n\n{entries}\n## Earlier v{major} history\n\n"
            "- Earlier releases added source support. v78.14 and RC3 were intermediate steps.\n\n"
            "## Earlier versions (v1-v77)\n\n- Earlier architectures.\n")


class HistoryStructureTests(unittest.TestCase):
    def validate(self, text, *, version="78.19"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "development").mkdir()
            (root / "src").mkdir()
            (root / "development/file-budgets.json").write_text(
                (ROOT / "development/file-budgets.json").read_text(encoding="utf-8"), encoding="utf-8")
            (root / "src/version.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
            (root / "VERSION_HISTORY.md").write_text(text, encoding="utf-8")
            results = Results()
            check_history_bounds(root, results)
            return results

    def test_cleaned_repository_history_passes(self):
        results = Results()
        check_history_bounds(ROOT, results)
        self.assertEqual([], results.failures)

    def test_valid_summaries_allow_version_and_rc_mentions_in_prose(self):
        self.assertEqual([], self.validate(history()).failures)
        self.assertEqual([], self.validate(history(92, 9), version="92.9").failures)

    def test_new_major_baseline_keeps_only_bounded_previous_generation_summary(self):
        text = ("# Cost Guard version history\n\n## v80.0 — 2026-10-06\n\n"
                "- Clean public baseline.\n\n## Earlier versions (v1-v78)\n\n"
                "- v78.0 established the Python baseline; v77.0 remains the reference.\n")
        self.assertEqual([], self.validate(text, version="80.0").failures)
        expanded = text.replace("## Earlier versions", "## v78.43\n\n- Old detail.\n\n## Earlier versions")
        self.assertTrue(self.validate(expanded, version="80.0").failures)

    def test_expanded_releases_cannot_hide_beneath_summary_at_any_heading_depth(self):
        for level in range(1, 7):
            bad = history().replace("## Earlier versions", f"{'#' * level} v78.14\n\n- Old detail.\n\n## Earlier versions")
            with self.subTest(level=level):
                self.assertTrue(self.validate(bad).failures)

    def test_requested_old_version_and_rc_sequence_fixture_is_rejected(self):
        bad = history().replace("## Earlier versions", "### v78.14\n### v78.13\n"
                                "### RC3 stabilization\n### RC4 stabilization\n### RC5 stabilization\n\n## Earlier versions")
        self.assertTrue(self.validate(bad).failures)

    def test_rc_and_implementation_attempt_headings_are_rejected(self):
        for title in ("RC3", "rc-4 stabilization", "Release candidate 5", "Implementation attempt 6", "RC10 stabilization"):
            for level in (2, 3, 6):
                bad = history().replace("## Earlier versions", f"{'#' * level} {title}\n\n- Attempt.\n\n## Earlier versions")
                with self.subTest(title=title, level=level):
                    self.assertTrue(self.validate(bad).failures)

    def test_latest_five_are_numeric_ordered_unique_and_not_replaced_by_older_entries(self):
        cases = (
            history().replace("## v78.18", "## v78.19"),
            history().replace("## v78.15", "## v78.9"),
            history().replace("## v78.18", "### v78.18"),
            history().replace("## v78.19", "## v78.19.1"),
            history().replace("## Earlier v78 history", "## v78.14\n\n- Extra release.\n\n## Earlier v78 history"),
        )
        for bad in cases:
            with self.subTest(text=bad):
                self.assertTrue(self.validate(bad).failures)

    def test_missing_or_wrongly_placed_summaries_are_rejected(self):
        cases = (
            history().replace("## Earlier v78 history", "## Notes"),
            history().replace("## Earlier versions (v1-v77)", "### Earlier versions (v1-v77)"),
            history().replace("## v78.17", "## Earlier v78 history\n\n- Summary.\n\n## v78.17"),
            history().replace("## Earlier v78 history", "## Earlier v77 history"),
        )
        for bad in cases:
            with self.subTest(text=bad):
                self.assertTrue(self.validate(bad).failures)

    def test_release_bullets_and_summary_size_are_bounded(self):
        budgets = json.loads((ROOT / "development/file-budgets.json").read_text(encoding="utf-8"))
        spec = budgets["limits"]["versionHistory"]
        too_many = "\n".join("- Detail." for _ in range(spec["majorMaxBullets"] + 1))
        for bad in (history().replace("- Net behavior.", too_many, 1),
                    history().replace("- Earlier architectures.", too_many),
                    history().replace("- Earlier architectures.", "Long prose. " * 1000)):
            with self.subTest(text=bad[:100]):
                self.assertTrue(self.validate(bad).failures)


if __name__ == "__main__":
    unittest.main()
