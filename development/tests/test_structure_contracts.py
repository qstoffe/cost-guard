"""Static navigation and relative/nested architecture enforcement regressions."""
import ast
from pathlib import Path
import re
import tempfile
import unittest

from development.tools.code_inventory import import_targets, inventory, markdown
from development.tools.validate_package import Results, check_architecture_imports


class ImportResolutionTests(unittest.TestCase):
    def test_relative_package_member_lazy_and_type_only_imports_resolve(self):
        tree = ast.parse("from .. import presentation\nfrom .sampling import AnalyzedRoot\n"
                         "def load():\n    from ..sources.opencode_v2 import OpenCodeV2Source\n"
                         "if TYPE_CHECKING:\n    from ..watch import WatchCoordinator\n")

        imports = import_targets(tree, module="src.reports.service")

        self.assertTrue({"src.presentation", "src.reports.sampling", "src.sources.opencode_v2", "src.watch"} <= imports)
        self.assertEqual({"src.domain.models"}, import_targets(ast.parse("from .models import TokenUsage"),
                         module="src.domain", package=True, include_members=False))


class StructureContractTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def module(self, path, body):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")

    def violations(self):
        result = Results()
        check_architecture_imports(self.root, result)
        return result.failures

    def test_nested_relative_report_import_cannot_bypass_policy(self):
        self.module("src/reports/nested/bad.py", "from ...sources.opencode_v2 import OpenCodeV2Source\n")

        errors = self.violations()

        self.assertTrue(any(label == "report architecture" for label, _ in errors))

    def test_from_parent_import_package_is_checked(self):
        self.module("src/domain/bad.py", "from .. import presentation\n")
        self.module("src/presentation/__init__.py", "")

        errors = self.violations()

        self.assertTrue(any(label == "architecture import" for label, _ in errors))

    def test_runtime_and_fixture_dependencies_remain_one_way(self):
        self.module("src/bad.py", "from development.fixtures.session_snapshots import make_snapshot\n")
        self.module("development/fixtures/bad.py", "from ..tests.test_example import data\n")

        errors = self.violations()

        self.assertEqual({"runtime architecture", "fixture architecture"}, {label for label, _ in errors})

    def test_new_v2_sibling_cannot_start_processes_or_read_sqlite(self):
        self.module("src/sources/opencode_v2_extra.py", "import subprocess\nimport sqlite3\n")

        errors = self.violations()

        self.assertTrue(any(label == "V2 source architecture" for label, _ in errors))

    def test_inventory_never_executes_modules_and_detects_transitive_test_routes(self):
        self.module("src/example.py", '"""Example owner."""\nraise AssertionError("must not import")\n')
        self.module("development/fixtures/example.py", "from src import example\n")
        self.module("development/tests/test_example.py", "from development.fixtures import example\n")
        self.module("development/tests/test_other.py", "from .test_example import data\n")

        first = inventory(self.root)
        second = inventory(self.root)

        self.assertEqual(first, second)
        self.assertIn("src/example.py", first["runtime_without_direct_test_import"])
        self.assertNotIn("src/example.py", first["runtime_without_static_test_path"])
        self.assertEqual(1, len(first["test_to_test_imports"]))
        self.assertIn("Example owner.", markdown(first))

    def test_navigation_document_links_resolve(self):
        root = Path(__file__).resolve().parents[2]
        for name in ("CODE_MAP.md", "REFACTORING_REVIEW.md"):
            document = root / "development" / name
            for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                if link.startswith(("https://", "http://", "#")):
                    continue
                target = link.split("#", 1)[0]
                self.assertTrue((document.parent / target).is_file(), f"{name}: {target}")

    def test_code_map_implementation_and_test_table_paths_exist(self):
        root = Path(__file__).resolve().parents[2]
        text = (root / "development/CODE_MAP.md").read_text(encoding="utf-8")
        routes = text.split("## Ownership and test routes", 1)[1].split("## Shared synthetic fixtures", 1)[0]
        lines = routes.splitlines()
        for line in lines:
            if not line.startswith("| ") or "`" not in line:
                continue
            cells = line.split("|")
            owner = root
            for value in re.findall(r"`([^`]+)`", cells[2]):
                target = root / value if "/" in value else owner / value
                matches = list(target.parent.glob(target.name)) if "*" in value else [target]
                self.assertTrue(matches and all(path.exists() for path in matches), value)
                owner = target.parent
            for name in re.findall(r"`(test_[^`]+\.py)`", cells[3]):
                self.assertTrue((root / "development/tests" / name).is_file(), name)
