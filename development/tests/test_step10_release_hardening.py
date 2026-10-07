from __future__ import annotations

import re
import unittest
from pathlib import Path

from src.version import DISPLAY_VERSION, RELEASE_DATE

ROOT = Path(__file__).resolve().parents[2]


class ReleaseDocumentationTests(unittest.TestCase):
    def test_root_readme_documents_public_baseline_and_retains_proof_limits(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(DISPLAY_VERSION, text)
        self.assertIn("v80.0 is the Python 3.11+ public baseline", text)
        self.assertIn("Claude quotas remain experimental", text)
        self.assertIn("need separate live evidence", text)
        self.assertIn("## Setup and usage", text)
        self.assertIn("## Release status", text)
        self.assertNotIn("## Release-candidate status", text)
        self.assertIn("OpenCode V1/V2 source selection", text)
        self.assertIn("under `windows/`", text)
        self.assertIn("`Cost Guard Watch.cmd`", text)
        self.assertIn("under `macos/`", text)
        self.assertIn("`development/macos/`", text)
        self.assertIn("`development/windows/`", text)
        self.assertNotIn("| `Cost Guard Diagnostics", text)
        self.assertNotIn("Iteration 9", text)
        self.assertNotIn("Step 10 performs", text)
        self.assertNotIn("IN DEVELOPMENT", text)

    def test_version_history_marks_public_baseline_and_bounds_older_generations(self) -> None:
        text = (ROOT / "VERSION_HISTORY.md").read_text(encoding="utf-8")
        first = next(line for line in text.splitlines() if line.startswith("## v"))
        self.assertEqual(f"## {DISPLAY_VERSION} — {RELEASE_DATE}", first)
        self.assertIn("## Earlier versions (v1-v78)", text)
        self.assertIn("v78.0 established the Python baseline", text)
        self.assertNotRegex(text, r"(?m)^#{1,6}\s+RC\d+")

    def test_maintainer_release_contract_matches_hardened_builder(self) -> None:
        text = (ROOT / "development/MAINTAINER.md").read_text(encoding="utf-8")
        self.assertIn("clean extraction", text)
        self.assertIn("Quick / constrained AI", text)
        self.assertIn("Full / local unrestricted", text)
        self.assertIn("Before removing a release-candidate label", text)
        self.assertNotIn("v78.0 is the Python-rewrite major currently at release-candidate stage", text)


    def test_maintainer_is_user_governed_and_has_no_legacy_script_reference(self) -> None:
        text = (ROOT / "development/MAINTAINER.md").read_text(encoding="utf-8")
        self.assertIn("`development/MAINTAINER.md` is user-governed", text)
        self.assertIn("ask the user before editing this file", text)
        self.assertNotRegex(text, re.compile(r"powershell", re.IGNORECASE))

    def test_ai_handoff_contract_is_packaged_and_bounded(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        maintainer = (ROOT / "development/MAINTAINER.md").read_text(encoding="utf-8")
        self.assertIn("development/MAINTAINER.md", agents)
        self.assertIn("development/FR_GUIDE.md", agents)
        self.assertIn("releases/cost-guard-vMAJOR.MINOR.zip", agents)
        self.assertIn("external reference", agents.lower())
        self.assertIn("AI/session handoff contract", maintainer)
        self.assertNotIn("each checkpoint ZIP contains", maintainer)


if __name__ == "__main__":
    unittest.main()
