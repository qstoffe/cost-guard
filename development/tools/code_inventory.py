#!/usr/bin/env python3
"""Read-only AST inventory and navigation; never import application/test code."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CODE_AREAS = ("src", "development/tools", "development/tests", "development/fixtures")


def module_name(path: Path, root: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def import_targets(tree: ast.AST, *, module: str, package: bool = False,
                   include_members: bool = True) -> set[str]:
    """Resolve absolute/relative syntax, including lazy and type-only imports.

    Named imports also yield a candidate submodule (``from x import y`` -> x.y).
    Inventory intersects candidates with real modules; validation checks prefixes.
    This is a static dependency map, not proof of eager runtime import cycles.
    """
    owner = module.split(".") if package else module.split(".")[:-1]
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if node.level > len(owner):
                    continue  # invalid Python relative import; compile/import gate owns it
                base = owner[:len(owner) - node.level + 1]
                if node.module:
                    base.extend(node.module.split("."))
                name = ".".join(base)
            else:
                name = node.module or ""
            if name:
                targets.add(name)
                if include_members:
                    targets.update(name + "." + alias.name for alias in node.names if alias.name != "*")
    return targets


def routine_metrics(tree: ast.AST) -> list[dict]:
    """Qualified function bodies; nested routines are measured separately.

    Statements and explicit if/loop/try/match nodes are structural signals, not
    cyclomatic complexity or quality scores. Docstrings do not consume budget.
    """
    values = []

    def measure(node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return 1, 0  # declaration belongs here; its body has a separate owner
        statements = int(isinstance(node, ast.stmt))
        branches = int(isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match)))
        for child in ast.iter_child_nodes(node):
            child_statements, child_branches = measure(child)
            statements += child_statements
            branches += child_branches
        return statements, branches

    def visit(node, owners=()):
        scope = owners
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = (*owners, node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body[1:] if ast.get_docstring(node) is not None else node.body
            counts = [measure(item) for item in body]
            values.append({"name": ".".join(scope), "line": node.lineno,
                           "statements": sum(x[0] for x in counts), "branches": sum(x[1] for x in counts)})
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree)
    return values


def inspect_module(path: Path, root: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(text, filename=path.relative_to(root).as_posix())
    name = module_name(path, root)
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    longest = max(functions, key=lambda node: node.end_lineno - node.lineno, default=None)
    return {
        "path": path.relative_to(root).as_posix(), "module": name,
        "bytes": len(path.read_bytes()), "lines": len(text.splitlines()),
        "purpose": (ast.get_docstring(tree) or "").split("\n", 1)[0],
        "functions": len(functions),
        "routines": routine_metrics(tree),
        "largest_function": None if longest is None else {
            "name": longest.name, "line": longest.lineno, "lines": longest.end_lineno - longest.lineno + 1,
        },
        "imports": sorted(import_targets(tree, module=name, package=path.name == "__init__.py")),
    }


def inventory(root: Path = ROOT) -> dict:
    modules = [inspect_module(path, root) for area in CODE_AREAS for path in sorted((root / area).rglob("*.py"))
               if "__pycache__" not in path.parts]
    names = {item["module"] for item in modules}
    for item in modules:
        item["imports"] = sorted(set(item["imports"]) & names - {item["module"]})
    by_name = {item["module"]: item for item in modules}
    runtime = [item for item in modules if item["path"].startswith("src/")]
    tests = [item for item in modules if item["path"].startswith("development/tests/test_")]
    direct = Counter(target for item in tests for target in item["imports"] if target.startswith("src."))
    reachable: Counter = Counter()
    for item in tests:
        seen: set[str] = set()
        pending = list(item["imports"])
        while pending:
            target = pending.pop()
            if target in seen:
                continue
            seen.add(target)
            pending.extend(by_name[target]["imports"])
        reachable.update(target for target in seen if target.startswith("src."))
    test_edges = [(item["path"], by_name[target]["path"]) for item in tests
                  for target in item["imports"] if target.startswith("development.tests.test_")]
    layers = {}
    for area in CODE_AREAS:
        values = [item for item in modules if item["path"].startswith(area + "/")]
        layers[area] = {"modules": len(values), "lines": sum(item["lines"] for item in values)}
    return {
        "schema_version": 1, "layers": layers, "modules": modules,
        "test_to_test_imports": test_edges,
        "runtime_without_direct_test_import": [item["path"] for item in runtime if not direct[item["module"]]],
        "runtime_without_static_test_path": [item["path"] for item in runtime if not reachable[item["module"]]],
    }


def markdown(data: dict, *, limit: int = 15) -> str:
    lines = ["# Static code inventory", "",
             "AST-only; no application imports, credentials, network or runtime data. Import paths include lazy/type-only imports; absence of a direct test import is not absence of coverage.", "",
             "## Areas", "", "| Area | Modules | Lines |", "| --- | ---: | ---: |"]
    lines.extend(f"| {area} | {value['modules']} | {value['lines']} |" for area, value in data["layers"].items())
    modules = data["modules"]
    lines.extend(["", "## Largest modules", "", "| Path | Bytes | Lines | Largest function |", "| --- | ---: | ---: | --- |"])
    for item in sorted(modules, key=lambda value: (-value["bytes"], value["path"]))[:limit]:
        function = item["largest_function"]
        label = f"{function['name']} ({function['lines']} lines)" if function else "—"
        lines.append(f"| {item['path']} | {item['bytes']} | {item['lines']} | {label} |")
    lines.extend(["", "## Layer imports", "", "| From | To | Edges |", "| --- | --- | ---: |"])
    def layer(name: str) -> str:
        parts = name.split(".")
        return ".".join(parts[:2]) if len(parts) > 1 else name
    edges = Counter((layer(item["module"]), layer(target)) for item in modules for target in item["imports"]
                    if layer(item["module"]) != layer(target))
    lines.extend(f"| {a} | {b} | {count} |" for (a, b), count in sorted(edges.items()))
    lines.extend(["", "## Test coupling", "", f"Test-to-test import edges: {len(data['test_to_test_imports'])}."])
    lines.extend(f"- {source} → {target}" for source, target in data["test_to_test_imports"])
    lines.extend(["", "## Runtime without a static test path", "",
                  "Review these entry/launcher-only modules manually; this is navigation evidence, not a coverage measurement."])
    lines.extend(f"- {path}" for path in data["runtime_without_static_test_path"])
    lines.extend(["", "## Module purposes", ""])
    lines.extend(f"- {item['path']}: {item['purpose'] or '(no module docstring)'}" for item in modules)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit the complete machine-readable map.")
    parser.add_argument("--limit", type=int, default=15, help="Largest-module rows in the Markdown view.")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    data = inventory()
    print(json.dumps(data, indent=2) if args.json else markdown(data, limit=max(1, args.limit)), end="\n" if args.json else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
