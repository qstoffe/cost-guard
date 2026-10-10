from __future__ import annotations

import re
import unittest
from pathlib import Path

from src.version import DISPLAY_VERSION, RELEASE_DATE

ROOT = Path(__file__).resolve().parents[2]


class DistributionDocumentationTests(unittest.TestCase):
    def test_root_readme_documents_public_baseline_and_retains_proof_limits(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(DISPLAY_VERSION, text)
        self.assertIn("v80.0 is the Python 3.11+ public baseline", text)
        self.assertIn("Claude quotas remain experimental", text)
        self.assertIn("need separate live evidence", text)
        self.assertIn("## Setup and usage", text)
        self.assertIn("## Current version", text)
        self.assertNotIn("## Release status", text)
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

    def test_current_main_is_the_only_recommended_download(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        quick_start = text.split("## Quick start", 1)[1].split("## Core concepts", 1)[0]
        self.assertIn("current `main`", quick_start)
        self.assertIn("latest supported Cost Guard code", quick_start)
        self.assertIn("main → Code → Download ZIP", quick_start)
        self.assertIn("git clone --branch main https://github.com/qstoffe/cost-guard.git", quick_start)
        self.assertIn("git pull --ff-only", quick_start)
        self.assertNotIn("releases/latest", text)
        self.assertNotIn("extracted package", text)
        self.assertIn("Packaged GitHub Releases are currently paused", text)
        self.assertIn("they do not imply a Git tag, release ZIP or GitHub Release", text)
        self.assertIn("version numbers never trigger it automatically", text)

    def test_source_zip_launchers_and_macos_remedy_are_documented(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("extraction tools may not preserve it", text)
        self.assertIn("chmod +x macos/*.command development/macos/*.command", text)
        self.assertNotIn("Files ship executable", text)
        self.assertIn("Windows source ZIPs use the same `.cmd` launchers", text)
        self.assertIn("from the extracted repository root", text)
        self.assertIn("Get-ChildItem -Recurse | Unblock-File", text)

    def test_all_maintainer_routes_package_by_environment(self) -> None:
        """Hosted/web AI never builds a ZIP; every completed local version does, Full-verified."""
        for name in ("AGENTS.md", "development/MAINTAINER.md", "development/README.md", "README.md"):
            with self.subTest(path=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn("Hosted/web AI", text)
                self.assertRegex(text, r"never builds? (a|an|one|the) (ZIP|archive)|never builds one")
                self.assertIn("build_release.py --full-verification", text)
        for name in ("AGENTS.md", "development/MAINTAINER.md", "development/README.md"):
            with self.subTest(path=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn("every completed", text.lower())
                self.assertIn("working tree", text)
                self.assertIn("never commit/push automatically" if name.endswith("MAINTAINER.md") else "commit or push automatically", text)
                self.assertIn("v80.0 tag", text)
        guide = (ROOT / "development/FR_GUIDE.md").read_text(encoding="utf-8")
        self.assertIn("Brainstorming never builds a ZIP", guide)
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        hosted, local = agents.split("**Hosted/web AI**", 1)[1].split("**Local workstation", 1)
        self.assertNotIn("build_release.py", hosted)
        self.assertIn("--suite full", local)
        self.assertIn("build_release.py --full-verification", local)
        self.assertIn("treat the environment as hosted", agents)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        development_commands = readme.split("## Development", 1)[1].split("```text", 1)[1].split("```", 1)[0]
        self.assertNotIn("build_release.py", development_commands)

    def test_git_delivery_policy_is_generic_and_consistent(self) -> None:
        """Explicitly authorized Git delivery is tool-neutral; isolated clones skip the ZIP unless packaging is requested."""
        for name in ("AGENTS.md", "development/MAINTAINER.md", "development/README.md"):
            with self.subTest(path=name):
                text = (ROOT / name).read_text(encoding="utf-8")
                self.assertNotRegex(text, re.compile(r"/repo-|repo-command|toolkit", re.IGNORECASE))
                self.assertIn("authorized Git delivery", text)
                self.assertIn("isolated", text)
                self.assertRegex(text, r"current task or a development workflow (they|the user) started")
        maintainer = (ROOT / "development/MAINTAINER.md").read_text(encoding="utf-8")
        section = maintainer.split("## Authorized Git delivery", 1)[1].split("\n## ", 1)[0]
        self.assertIn("need no further confirmation", section)
        self.assertIn("ordinary working tree is neither edited", section)
        self.assertIn("no local release ZIP unless packaging is explicitly requested", section)
        self.assertIn("keeps the ZIP requirement", section)
        self.assertIn("Never force-merge, bypass branch protection", section)
        self.assertIn("protection of this file", section)

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
