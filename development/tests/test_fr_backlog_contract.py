"""Static FR guide/layout contracts, not a model-workflow execution test."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "development/FR_GUIDE.md"


class FrBacklogContractTests(unittest.TestCase):
    def test_standard_directories_are_tracked_without_example_requests(self):
        for relative in ("development/backlog/todo", "development/backlog/complete"):
            with self.subTest(directory=relative):
                directory = ROOT / relative
                self.assertTrue(directory.is_dir())
                # Future real FRs may replace the placeholder; never require an empty queue.
                self.assertTrue(any(path.is_file() for path in directory.iterdir()))
                self.assertEqual(relative, relative.lower())

    def test_documented_filename_pattern_accepts_shared_names_only(self):
        text = GUIDE.read_text(encoding="utf-8")
        pattern = re.search(r"matching `([^`]+)`", text).group(1)
        for filename in ("0100-improve-session-recovery.md", "0115-fix-usage.md", "0000-first.md"):
            with self.subTest(filename=filename):
                self.assertRegex(filename, pattern)
        for filename in ("100-short.md", "00100-long.md", "0100-Upper.md", "0100-two--gaps.md",
                         "0100-.md", "0100-name.txt", ".gitkeep", "٠١٠٠-non-ascii.md"):
            with self.subTest(filename=filename):
                self.assertNotRegex(filename, pattern)

    def test_verification_matrix_keeps_all_requested_cases_and_outcomes(self):
        text = GUIDE.read_text(encoding="utf-8")
        rows = dict(re.findall(r"^\| (FR-[0-9]{2}) \| (.+) \|$", text, re.MULTILINE))
        self.assertEqual({f"FR-{number:02d}" for number in range(1, 16)}, set(rows))
        for case, outcome in (("FR-01", "`0100`"), ("FR-02", "`0130`, no question"),
                              ("FR-03", "`0180`"), ("FR-04", "`0105`, existing names unchanged"),
                              ("FR-05", "`0090`"), ("FR-06", "Refuse collision"),
                              ("FR-07", "explicit renumbering/placement decision")):
            with self.subTest(case=case):
                self.assertIn(outcome, rows[case].split(" | ", 1)[1])

    def test_requested_fr_is_published_to_main_without_version_bump(self):
        guide = GUIDE.read_text(encoding="utf-8")
        maintainer = (ROOT / "development/MAINTAINER.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for key in ("FR-09", "FR-13", "FR-14", "FR-15"):
            self.assertIn(f"| {key} |", guide)
        self.assertIn("including PR merge", guide)
        self.assertIn("do not leave a safe FR-only PR unmerged", guide)
        self.assertIn("must **not** update `VERSION` or `RELEASE_DATE`", maintainer)
        self.assertIn("FR-only", agents)
        self.assertIn("merging it into `main` by default", agents)

    def test_guide_retains_quality_authorities_and_publication_boundaries(self):
        text = GUIDE.read_text(encoding="utf-8")
        for required in ("## Start with behavior and ownership", "## FR shape", "## AI-to-AI handoff",
                         "10 * (maximum // 10 + 1)", "`todo` **and** `complete`",
                         "Brainstorming alone creates no FR file, branch, commit or PR",
                         "never wrap, reuse an identifier", "Never overwrite an existing file",
                         "do not ask whether last is acceptable", "Never start it automatically",
                         "explicitly stating it remains uncommitted", "Four-digit priorities range",
                         "FR-only and other documentation-only changes do not change", "merge to `main` by default"):
            with self.subTest(contract=required):
                self.assertIn(required, text)
        for target in re.findall(r"\]\((MAINTAINER.md#[^)]+)\)", text):
            document, anchor = target.split("#")
            authority = (GUIDE.parent / document).read_text(encoding="utf-8")
            headings = {heading.lower().replace(" ", "-")
                        for heading in re.findall(r"^## (.+)$", authority, re.MULTILINE)}
            self.assertIn(anchor, headings)
