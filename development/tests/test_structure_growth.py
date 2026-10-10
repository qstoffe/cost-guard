"""Growth gates cannot silently re-baseline oversized functions or test coupling."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest

from development.tools.code_inventory import routine_metrics
from development.tools.structure_guard import structural_errors


def policy():
    return {"schemaVersion": 1, "limits": {"functionStatements": 3, "functionBranches": 1},
            "routineExceptions": {}, "legacyTestImports": {}}


def data(body="def small():\n    return 1\n", *, edges=()):
    return {"modules": [{"path": "src/example.py", "purpose": "Synthetic owner", "routines": routine_metrics(ast.parse(body))}],
            "test_to_test_imports": list(edges)}


class StructuralGrowthTests(unittest.TestCase):
    def errors(self, state, limits=None):
        return structural_errors(Path("."), data=state, policy=limits or policy())

    def test_simple_new_routine_needs_no_exception(self):
        self.assertEqual([], self.errors(data()))

    def test_new_oversized_routine_is_rejected(self):
        errors = self.errors(data("def large():\n    a=1\n    b=2\n    c=3\n    return a+b+c\n"))
        self.assertTrue(any("routine growth" in item and "large" in item for item in errors))

    def test_existing_exception_cannot_grow_in_either_dimension(self):
        limits = policy()
        limits["routineExceptions"]["src/example.py::large"] = {"statements": 4, "branches": 2, "reason": "Legacy owner"}
        state = data("def large():\n    if True:\n        a=1\n    if False:\n        a=2\n")
        self.assertEqual([], self.errors(state, limits))
        grown = data("def large():\n    if True:\n        a=1\n    if False:\n        a=2\n    if True:\n        a=3\n")
        self.assertTrue(any("routine growth" in item for item in self.errors(grown, limits)))

    def test_resolved_or_deleted_routine_debt_must_be_retired(self):
        limits = policy()
        limits["routineExceptions"]["src/example.py::small"] = {"statements": 4, "branches": 2, "reason": "Legacy owner"}
        self.assertTrue(any("retire resolved" in item for item in self.errors(data(), limits)))
        self.assertTrue(any("stale routine" in item for item in self.errors(data(""), limits)))

    def test_docstrings_and_nested_function_bodies_are_not_parent_growth(self):
        values = routine_metrics(ast.parse('def outer():\n    """Notes."""\n    def inner():\n        if True:\n            return 1\n    return inner()\n'))
        self.assertEqual(["outer", "outer.inner"], [item["name"] for item in values])
        self.assertEqual((2, 0), (values[0]["statements"], values[0]["branches"]))
        self.assertEqual((2, 1), (values[1]["statements"], values[1]["branches"]))

    def test_class_method_names_do_not_collide(self):
        values = routine_metrics(ast.parse("class A:\n    def run(self): pass\nclass B:\n    def run(self): pass\n"))
        self.assertEqual(["A.run", "B.run"], [item["name"] for item in values])

    def test_new_test_import_is_rejected_without_an_automatic_count_allowance(self):
        state = data(edges=(("development/tests/test_a.py", "development/tests/test_b.py"),))
        self.assertTrue(any("new test-to-test import" in item for item in self.errors(state)))

    def test_legacy_edge_is_exact_and_removal_requires_retiring_it(self):
        limits = policy()
        limits["legacyTestImports"]["test_a.py"] = {"reason": "Native fixture extraction pending", "targets": ["test_b.py"]}
        state = data(edges=(("development/tests/test_a.py", "development/tests/test_b.py"),))
        self.assertEqual([], self.errors(state, limits))
        self.assertTrue(any("retire resolved test import" in item for item in self.errors(data(), limits)))
        replacement = data(edges=(("development/tests/test_a.py", "development/tests/test_c.py"),))
        self.assertTrue(any("new test-to-test import" in item for item in self.errors(replacement, limits)))

    def test_nested_test_path_does_not_alias_an_allowed_basename(self):
        limits = policy()
        limits["legacyTestImports"]["test_a.py"] = {"reason": "Legacy fixture", "targets": ["test_b.py"]}
        state = data(edges=(("development/tests/nested/test_a.py", "development/tests/test_b.py"),))
        self.assertTrue(any("new test-to-test import: nested/test_a.py" in item for item in self.errors(state, limits)))

    def test_bad_policy_and_unexplained_or_duplicate_debt_fail_closed(self):
        self.assertTrue(structural_errors(Path("."), data=data(), policy={}))
        limits = policy()
        limits["legacyTestImports"]["test_a.py"] = {"reason": "", "targets": ["test_b.py"]}
        self.assertTrue(any("invalid legacy" in item for item in self.errors(data(), limits)))
        limits["legacyTestImports"]["test_a.py"] = {"reason": "Legacy fixture", "targets": ["test_b.py", "test_b.py"]}
        self.assertTrue(any("duplicate legacy" in item for item in self.errors(data(), limits)))
        limits = policy()
        limits["routineExceptions"]["src/example.py::small"] = {"statements": True, "branches": 2, "reason": ""}
        self.assertTrue(any("invalid routine" in item for item in self.errors(data(), limits)))

    def test_repository_policy_and_inputs_are_not_mutated(self):
        root = Path(__file__).resolve().parents[2]
        path = root / "development/structure-policy.json"
        before = path.read_bytes()
        self.assertEqual([], structural_errors(root))
        self.assertEqual(before, path.read_bytes())
        limits, state = policy(), data()
        original = deepcopy((limits, state))
        self.errors(state, limits)
        self.assertEqual(original, (limits, state))

    def test_runtime_and_fixture_modules_need_an_explicit_responsibility(self):
        state = data()
        state["modules"][0]["purpose"] = ""
        self.assertTrue(any("declare its responsibility" in item for item in self.errors(state)))

    def test_repository_default_budgets_remain_the_deliberate_contract(self):
        import json
        root = Path(__file__).resolve().parents[2]
        limits = json.loads((root / "development/structure-policy.json").read_text())["limits"]
        self.assertEqual({"functionStatements": 55, "functionBranches": 15}, limits)
