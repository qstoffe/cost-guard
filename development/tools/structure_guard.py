"""Deterministic anti-growth gate; explicit bounded legacy debt, never auto-baselines."""
from __future__ import annotations

import json
from pathlib import Path

if __package__:
    from development.tools.code_inventory import inventory
else:
    from code_inventory import inventory


def structural_errors(root: Path, *, data: dict | None = None, policy: dict | None = None) -> list[str]:
    """Reject new oversized routines/test coupling and stale debt declarations."""
    if policy is None:
        try:
            policy = json.loads((root / "development/structure-policy.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ["structure-policy.json is missing or invalid"]
    if not isinstance(policy, dict) or policy.get("schemaVersion") != 1:
        return ["structure policy schema must be version 1"]
    limits = policy.get("limits")
    exceptions = policy.get("routineExceptions")
    imports = policy.get("legacyTestImports")
    if not isinstance(limits, dict) or not isinstance(exceptions, dict) or not isinstance(imports, dict):
        return ["structure policy requires limits, routineExceptions and legacyTestImports objects"]
    maximum = limits.get("functionStatements")
    branches = limits.get("functionBranches")
    if (type(maximum) is not int or maximum < 1 or type(branches) is not int or branches < 1):
        return ["structure limits must be positive integers"]
    if data is None:
        try:
            data = inventory(root)
        except (OSError, SyntaxError, UnicodeError) as error:
            return [f"cannot inspect structural inputs: {type(error).__name__}"]
    routines = {item["path"] + "::" + routine["name"]: routine
                for item in data["modules"] if item["path"].startswith("src/") for routine in item["routines"]}
    errors = []
    for item in data["modules"]:
        if item["path"].startswith(("src/", "development/fixtures/")) and not item.get("purpose"):
            errors.append(f"module must declare its responsibility: {item['path']}")
    for name, routine in sorted(routines.items()):
        allowed = exceptions.get(name)
        cap, branch_cap = maximum, branches
        if allowed is not None:
            if (not isinstance(allowed, dict) or not isinstance(allowed.get("reason"), str)
                    or not allowed["reason"].strip()
                    or type(allowed.get("statements")) is not int or type(allowed.get("branches")) is not int
                    or allowed["statements"] < 0 or allowed["branches"] < 0):
                errors.append(f"invalid routine exception: {name}")
                continue
            cap, branch_cap = allowed["statements"], allowed["branches"]
            if routine["statements"] <= maximum and routine["branches"] <= branches:
                errors.append(f"retire resolved routine exception: {name}")
        if routine["statements"] > cap or routine["branches"] > branch_cap:
            errors.append(f"routine growth: {name} statements={routine['statements']}/{cap} branches={routine['branches']}/{branch_cap}")
    errors.extend(f"stale routine exception: {name}" for name in sorted(set(exceptions) - routines.keys()))
    actual = {(a.removeprefix("development/tests/"), b.removeprefix("development/tests/"))
              for a, b in data["test_to_test_imports"]}
    allowed_edges = set()
    for source, entry in sorted(imports.items()):
        if (not Path(source).name.startswith("test_") or source.startswith("/") or ".." in Path(source).parts or "\\" in source
                or not isinstance(entry, dict) or not isinstance(entry.get("reason"), str) or not entry["reason"].strip()
                or not isinstance(entry.get("targets"), list) or not entry["targets"]
                or any(not isinstance(x, str) or not Path(x).name.startswith("test_") or x.startswith("/")
                       or ".." in Path(x).parts or "\\" in x for x in entry["targets"])):
            errors.append(f"invalid legacy test import declaration: {source}")
            continue
        for target in entry["targets"]:
            edge = (source, target)
            if edge in allowed_edges:
                errors.append(f"duplicate legacy test import: {source} -> {target}")
            allowed_edges.add(edge)
    errors.extend(f"new test-to-test import: {a} -> {b}; use a responsibility-owned fixture" for a, b in sorted(actual - allowed_edges))
    errors.extend(f"retire resolved test import: {a} -> {b}" for a, b in sorted(allowed_edges - actual))
    return errors
