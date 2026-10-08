#!/usr/bin/env python3
"""Deterministic working-tree and explicit-packaging gate. Python standard library only."""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import shutil
import tempfile
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REQUIRED_FILES = {
    ".gitignore",
    "AGENTS.md",
    "LICENSE",
    "cost-guard.py",
    "README.md",
    "docs/usage-and-cost.md",
    "docs/images/cost-guard-watch.png",
    "docs/images/cost-guard-report.png",
    "docs/images/cost-guard-token-mix.png",
    "VERSION_HISTORY.md",
    "config/default-config.jsonc",
    "src/__init__.py",
    "src/bootstrap.py",
    "src/cli.py",
    "src/version.py",
    "src/config.py",
    "src/domain/capabilities.py",
    "src/domain/models.py",
    "src/domain/status.py",
    "src/sources/base.py",
    "src/sources/discovery.py",
    "src/sources/errors.py",
    "src/sources/opencode_v1.py",
    "src/sources/opencode_v2.py",
    "src/sources/opencode_v2_wire.py",
    "src/sources/opencode_v2_transport.py",
    "src/sources/selection.py",
    "src/accounts/base.py",
    "src/accounts/openai_subscription.py",
    "src/pricing/base.py",
    "src/pricing/catalog.py",
    "src/pricing/github_copilot.py",
    "src/accounts/github_copilot.py",
    "src/reports/models.py",
    "src/reports/service.py",
    "src/presentation/terminal.py",
    "src/presentation/progress.py",
    "src/presentation/report.py",
    "src/windows_launcher.ps1",
    "windows/Cost Guard.cmd",
    "windows/Cost Guard Watch.cmd",
    "macos/Cost Guard.command",
    "macos/Cost Guard Watch.command",
    "development/windows/Cost Guard Diagnostics.cmd",
    "development/macos/Cost Guard Diagnostics.command",
    "src/cache/database.py",
    "src/cache/repository.py",
    "development/README.md",
    "development/MAINTAINER.md",
    "development/ARCHITECTURE.md",
    "development/FR_GUIDE.md",
    "development/file-budgets.json",
    "development/tools/run_tests.py",
    "development/tools/collect_diagnostics.py",
    "development/tools/validate_package.py",
    "development/tools/build_release.py",
    "development/tests/test_opencode_v1.py",
    "development/tests/test_opencode_v2.py",
    "development/tests/test_source_selection.py",
    "development/fixtures/opencode_v1/schema.sql",
    "development/fixtures/opencode_v2/service-fixture.json",
}

# User-facing launcher folders hold only everyday modes; Diagnostics lives under development/.
PUBLIC_LAUNCHERS = {
    "windows": {"Cost Guard.cmd", "Cost Guard Watch.cmd"},
    "macos": {"Cost Guard.command", "Cost Guard Watch.command"},
}

FORBIDDEN_TOP_LEVEL = {"cache", "diagnostics", "logs", ".git", "data"}
FORBIDDEN_NAMES = {"auth.json", ".env", "credentials.json"}
TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonc", ".py", ".cmd", ".command", ".ps1", ".sh", ".toml", ".yaml", ".yml"}


@dataclass
class Results:
    failures: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[tuple[str, str]] = field(default_factory=list)
    passes: list[str] = field(default_factory=list)

    def fail(self, label: str, detail: str) -> None:
        self.failures.append((label, detail))

    def warn(self, label: str, detail: str) -> None:
        self.warnings.append((label, detail))

    def ok(self, label: str) -> None:
        self.passes.append(label)


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def load_json(path: Path, results: Results, label: str) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # deterministic validation surface
        results.fail(label, f"{path.name}: invalid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        results.fail(label, f"{path.name}: top-level JSON must be an object")
        return None
    return data


def iter_package_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in {".git", "__pycache__"} for part in relative.parts):
            continue
        if relative.parts and relative.parts[0] == "releases":
            continue
        if path.suffix == ".pyc":
            continue
        yield path


def file_kind(root: Path, path: Path) -> str:
    rp = rel(root, path)
    if rp == "cost-guard.py":
        return "rootEntrypoint"
    if rp == "README.md":
        return "rootReadme"
    if rp == "VERSION_HISTORY.md":
        return "versionHistory"
    if rp == "config/default-config.jsonc":
        return "defaultConfig"
    if rp == "development/MAINTAINER.md":
        return "maintainer"
    if rp == "development/ARCHITECTURE.md":
        return "architecture"
    if rp.startswith("development/tests/") and path.suffix == ".py":
        return "testModule"
    if path.suffix == ".py":
        return "pythonModule"
    if path.name == "file-budgets.json":
        return "jsonConfig"
    if rp.startswith("development/fixtures/"):
        return "fixture"
    if rp.startswith("development/") and path.suffix in {".md", ".txt"}:
        return "developmentProse"
    if rp.startswith("docs/images/") and path.suffix == ".png":
        # Static documentation images are binary assets, not otherText.
        # Retain the existing universal file cap; no text budget is raised.
        return "universalFile"
    return "otherText"


def check_required_layout(root: Path, results: Results) -> None:
    for rp in sorted(REQUIRED_FILES):
        if not (root / rp).is_file():
            results.fail("required layout", f"missing required file: {rp}")

    for folder, expected in sorted(PUBLIC_LAUNCHERS.items()):
        directory = root / folder
        actual = {path.name for path in directory.iterdir()} if directory.is_dir() else set()
        for name in sorted(actual - expected):
            results.fail("public launchers", f"unexpected entry in user-facing launcher folder: {folder}/{name}")

    for name in sorted(FORBIDDEN_TOP_LEVEL):
        if (root / name).exists():
            results.fail("runtime artifact", f"forbidden packaged top-level path: {name}")

    for path in root.rglob("*"):
        if path.name in FORBIDDEN_NAMES:
            results.fail("secret/runtime artifact", f"forbidden file name: {rel(root, path)}")
        if path.name == "__pycache__" or path.suffix == ".pyc":
            results.fail("generated artifact", f"forbidden generated artifact: {rel(root, path)}")

    gitignore = root / ".gitignore"
    if gitignore.is_file():
        text = gitignore.read_text(encoding="utf-8")
        for required in ("/cache/", "/diagnostics/", "/logs/", "/releases/", "/config/user-config.jsonc"):
            if required not in text:
                results.fail("gitignore contract", f".gitignore must include {required}")
    results.ok("required layout/runtime-artifact rules checked")


def check_lowercase_directories(root: Path, results: Results) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_dir():
            continue
        relative = path.relative_to(root)
        if any(part in {".git", "__pycache__"} for part in relative.parts):
            continue
        for part in relative.parts:
            if part != part.lower():
                results.fail(
                    "lowercase directories",
                    f"package-owned directory names must be lowercase: {relative.as_posix()}",
                )
                break
    results.ok("package-owned directory names are lowercase")


def check_text_encoding(root: Path, results: Results) -> None:
    for path in iter_package_files(root):
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".gitignore":
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            results.fail("UTF-8", f"{rel(root, path)}: {exc}")
    results.ok("text files are UTF-8 readable")


def check_budgets(root: Path, results: Results) -> None:
    budget_path = root / "development/file-budgets.json"
    budgets = load_json(budget_path, results, "file budgets")
    if not budgets:
        return
    limits = budgets.get("limits")
    if not isinstance(limits, dict):
        results.fail("file budgets", "limits object missing")
        return
    universal = limits.get("universalFile", {}).get("hardBytes")
    if not isinstance(universal, int):
        results.fail("file budgets", "universalFile.hardBytes must be an integer")
        return

    for path in iter_package_files(root):
        size = path.stat().st_size
        rp = rel(root, path)
        if size > universal:
            results.fail("universal file cap", f"{rp}: {size} > {universal} bytes")
        kind = file_kind(root, path)
        spec = limits.get(kind)
        if not isinstance(spec, dict):
            results.fail("file budgets", f"missing budget class {kind} for {rp}")
            continue
        hard = spec.get("hardBytes")
        design = spec.get("designBytes")
        if isinstance(hard, int) and size > hard:
            results.fail(f"{kind} hard cap", f"{rp}: {size} > {hard} bytes")
        elif isinstance(design, int) and size > design:
            results.warn(f"{kind} design budget", f"{rp}: {size} > {design} bytes")
    results.ok("machine-enforced file budgets checked")


def compile_python(root: Path, results: Results) -> None:
    python_files = [path for path in iter_package_files(root) if path.suffix == ".py"]
    syntax_311_ok = True
    for path in python_files:
        try:
            source = path.read_text(encoding="utf-8")
            # feature_version constrains syntax to the documented minimum runtime
            # even when release validation itself runs on a newer interpreter.
            ast.parse(source, filename=str(path), feature_version=(3, 11))
            compile(source, str(path), "exec")
        except SyntaxError as exc:
            syntax_311_ok = False
            results.fail("Python 3.11 syntax", f"{rel(root, path)}: {exc}")
        except Exception as exc:
            results.fail("Python compile", f"{rel(root, path)}: {exc}")
    if syntax_311_ok:
        results.ok("Python 3.11 syntax compatibility checked")
    results.ok("Python compile checks executed")

def check_import_smoke(root: Path, results: Results) -> None:
    code = "import src.version, src.cli, src.bootstrap; print(src.version.DISPLAY_VERSION)"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if proc.returncode != 0:
        results.fail("import smoke", (proc.stdout + proc.stderr).strip()[:1500])
    elif not re.fullmatch(r"v\d+\.\d+", proc.stdout.strip()):
        results.fail("import smoke", f"unexpected version output: {proc.stdout.strip()!r}")
    else:
        results.ok("bootstrap import smoke passed")


def parse_version_constant(root: Path, results: Results) -> str | None:
    path = root / "src/version.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        results.fail("version consistency", f"cannot parse src/version.py: {exc}")
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "VERSION":
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
    results.fail("version consistency", "src/version.py must define literal VERSION")
    return None


def check_version_consistency(root: Path, results: Results) -> None:
    version = parse_version_constant(root, results)
    if not version:
        return
    if not re.fullmatch(r"\d+\.\d+", version):
        results.fail("version consistency", f"VERSION must have MAJOR.MINOR only: {version!r}")
        return
    display = f"v{version}"
    readme = (root / "README.md").read_text(encoding="utf-8")
    history = (root / "VERSION_HISTORY.md").read_text(encoding="utf-8")
    if display not in readme:
        results.fail("version consistency", f"README.md does not mention {display}")
    first_heading = next((line for line in history.splitlines() if line.startswith("## v")), "")
    if not first_heading.startswith(f"## {display}"):
        results.fail("version consistency", f"first version-history heading is not {display}: {first_heading!r}")
    results.ok(f"version consistency checked for {display}")


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                # Relative imports are kept symbolic; cross-boundary checks focus on absolute src.* imports.
                modules.add("." * node.level + module)
            else:
                modules.add(module)
    return modules


def check_entrypoint(root: Path, results: Results) -> None:
    path = root / "cost-guard.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception:
        return
    # Only the thin guarded import/status seam is allowed, never business logic.
    definitions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if any(not isinstance(node, ast.FunctionDef) or node.name not in {"run", "start"} for node in definitions):
        results.fail("entry-point architecture", "cost-guard.py may define only run/start failure-boundary functions")
    imports = imported_modules(path)
    disallowed = sorted(m for m in imports if m not in {"src.bootstrap", "src.runtime_errors", "pathlib", "sys"})
    if disallowed:
        results.fail("entry-point architecture", f"cost-guard.py may import only the minimal process boundary/bootstrap, found {disallowed}")
    if any(isinstance(node, ast.ImportFrom) and node.module == "src.bootstrap" for node in tree.body):
        results.fail("entry-point architecture", "bootstrap import must occur inside the guarded application callback")
    runtime = root / "src/runtime_errors.py"
    if runtime.exists():
        disallowed = sorted(m for m in imported_modules(runtime) if m.startswith("src.") or m.startswith(".") and m != ".version")
        if disallowed:
            results.fail("runtime-error architecture", f"minimal reporter imports application layers: {disallowed}")
    results.ok("thin entry-point architecture checked")


def check_architecture_imports(root: Path, results: Results) -> None:
    forbidden_by_area = {
        "domain": ("src.sources", "src.accounts", "src.pricing", "src.analysis", "src.cache", "src.reports", "src.watch", "src.presentation"),
        "sources": ("src.accounts", "src.pricing", "src.analysis", "src.reports", "src.watch", "src.presentation"),
        "accounts": ("src.sources", "src.pricing", "src.analysis", "src.reports", "src.watch", "src.presentation"),
        "pricing": ("src.sources", "src.accounts", "src.analysis", "src.reports", "src.watch", "src.presentation"),
        "cache": ("src.sources", "src.accounts", "src.pricing", "src.analysis", "src.reports", "src.watch", "src.presentation"),
        "analysis": ("src.sources", "src.accounts", "src.reports", "src.watch", "src.presentation"),
        "presentation": ("src.sources", "src.accounts", "src.pricing"),
    }
    for area, prefixes in forbidden_by_area.items():
        base = root / "src" / area
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            try:
                imports = imported_modules(path)
            except Exception:
                continue
            for module in sorted(imports):
                if any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes):
                    results.fail("architecture import", f"{rel(root, path)} imports forbidden concrete layer {module}")

    reports_root = root / "src" / "reports"
    for path in reports_root.glob("*.py") if reports_root.exists() else ():
        for module in imported_modules(path):
            forbidden = (
                module.startswith("src.sources.opencode_"),
                module.startswith("src.accounts.github_"),
                module.startswith("src.pricing.github_"),
                module == "src.presentation" or module.startswith("src.presentation."),
                module == "src.watch" or module.startswith("src.watch."),
            )
            if any(forbidden):
                results.fail("report architecture", f"{rel(root, path)} imports concrete/runtime presentation layer {module}")

    watch_root = root / "src" / "watch"
    for path in watch_root.glob("*.py") if watch_root.exists() else ():
        for module in imported_modules(path):
            forbidden = (
                module.startswith("src.sources.opencode_"),
                module.startswith("src.accounts.github_"),
                module.startswith("src.pricing.github_"),
            )
            if any(forbidden):
                results.fail("watch architecture", f"{rel(root, path)} imports concrete integration {module}")

    v1 = root / "src/sources/opencode_v1.py"
    if v1.is_file():
        try:
            imports = imported_modules(v1)
        except Exception:
            imports = set()
        if any(module == "subprocess" or module.startswith("subprocess.") for module in imports):
            results.fail("V1 source architecture", "OpenCode V1 adapter may not start subprocesses")

    for relative in ("src/sources/opencode_v2.py", "src/sources/opencode_v2_transport.py"):
        path = root / relative
        if not path.is_file():
            continue
        try:
            imports = imported_modules(path)
        except Exception:
            imports = set()
        forbidden = sorted(
            module for module in imports
            if module == "subprocess" or module.startswith("subprocess.")
            or module == "sqlite3" or module.startswith("sqlite3.")
        )
        if forbidden:
            results.fail("V2 source architecture", f"{relative} may not use CLI subprocesses or V2 SQLite: {forbidden}")
    # Analysis may consume provider-neutral pricing contracts/catalog helpers, but
    # it must never import a concrete pricing provider implementation.
    analysis_root = root / "src" / "analysis"
    for path in analysis_root.glob("*.py") if analysis_root.exists() else ():
        for module in imported_modules(path):
            if module.startswith("src.pricing.github_"):
                results.fail("architecture import", f"{rel(root, path)} imports concrete pricing provider {module}")

    results.ok("initial architecture import boundaries checked")


def check_history_bounds(root: Path, results: Results) -> None:
    budgets = load_json(root / "development/file-budgets.json", results, "history budgets")
    if not budgets:
        return
    spec = budgets["limits"]["versionHistory"]
    lines = (root / "VERSION_HISTORY.md").read_text(encoding="utf-8").splitlines()
    version = parse_version_constant(root, results)
    if not version or not re.fullmatch(r"\d+\.\d+", version):
        return
    major, minor = map(int, version.split("."))
    # Structure, not prose: mentions of versions/RCs in summary sentences are legal.
    headings = []
    for index, line in enumerate(lines):
        match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            headings.append((index, len(match[1]), match[2]))
    releases = []
    summaries = []
    in_summary = False
    attempt_pattern = re.compile(r"\b(?:RC[ -]*\d+|release[ -]candidate|implementation[ -]attempt|stabili[sz]ation)\b", re.I)
    for position, (start, level, title) in enumerate(headings):
        release = re.match(r"^v(\d+)\.(\d+)\b", title, re.I)
        summary = title.startswith("Earlier ")
        if attempt_pattern.search(title):
            results.fail("version history", f"implementation/RC entry heading is not permanent product history: {title}")
        if release:
            releases.append((int(release[1]), int(release[2])))
            if level != 2 or in_summary or not re.match(r"^v\d+\.\d+(?:\s|$)", title, re.I):
                results.fail("version history", f"release entries must be MAJOR.MINOR H2 headings before summaries: {title}")
        elif summary:
            in_summary = True
            summaries.append(title)
            if level != 2:
                results.fail("version history", f"summary must be an H2 section: {title}")
        elif in_summary or level == 2:
            results.fail("version history", f"unexpected history section; older detail belongs in a flat summary: {title}")
        if release or summary:
            # H2 section boundaries include subordinate headings so bullet limits cannot be bypassed.
            end = next((index for index, depth, _ in headings[position + 1:] if depth <= 2), len(lines))
            body = lines[start + 1:end]
            bullets = [line for line in body if re.match(r"^\s*[-*+]\s+", line)]
            if len(bullets) > spec["majorMaxBullets"]:
                results.fail("version history", f"{title} has {len(bullets)} bullets > {spec['majorMaxBullets']}")
            if summary and len("\n".join(body).encode("utf-8")) > spec["summaryMaxBytes"]:
                results.fail("version history", f"{title} exceeds the bounded summary size ({spec['summaryMaxBytes']} bytes)")
    expected = [(major, number) for number in range(minor, max(-1, minor - spec["maxExplicitMajors"]), -1)]
    if releases != expected:
        results.fail("version history", f"expanded entries must be the latest {len(expected)} releases in numeric descending order: {expected}; got {releases}")
    expected_summaries = [f"Earlier v{major} history"] if expected[-1][1] > 0 else []
    if (
        summaries[:len(expected_summaries)] != expected_summaries
        or len(summaries) != len(expected_summaries) + 1
        or not re.fullmatch(r"Earlier versions(?: \([^)]+\))?", summaries[-1] if summaries else "")
    ):
        results.fail("version history", "older history must end with bounded generation/earlier-version summaries")
    results.ok("version-history release structure and bounded summaries checked")


def validate(root: Path) -> Results:
    results = Results()
    check_required_layout(root, results)
    check_lowercase_directories(root, results)
    check_text_encoding(root, results)
    check_public_hygiene(root, results)
    check_budgets(root, results)
    compile_python(root, results)
    check_import_smoke(root, results)
    check_version_consistency(root, results)
    check_entrypoint(root, results)
    check_architecture_imports(root, results)
    check_history_bounds(root, results)
    return results


def print_results(results: Results, as_json: bool) -> None:
    if as_json:
        print(json.dumps({
            "status": "ok" if not results.failures else "error",
            "passes": results.passes,
            "warnings": [{"label": l, "detail": d} for l, d in results.warnings],
            "failures": [{"label": l, "detail": d} for l, d in results.failures],
        }, ensure_ascii=False, indent=2))
        return
    for label in results.passes:
        print(f"PASS  {label}")
    for label, detail in results.warnings:
        print(f"WARN  {label}: {detail}")
    for label, detail in results.failures:
        print(f"FAIL  {label}: {detail}")
    print(f"SUMMARY failures={len(results.failures)} warnings={len(results.warnings)} passes={len(results.passes)}")



def check_public_hygiene(root: Path, results: Results) -> None:
    """Enforce generic public-repository hygiene without named organizations."""
    license_path = root / "LICENSE"
    if license_path.is_file():
        text = license_path.read_text(encoding="utf-8")
        if "Zero-Clause BSD" not in text or "Permission to use, copy, modify" not in text:
            results.fail("open-source license", "LICENSE must contain the approved 0BSD grant")

    # These are generic organization-bound defaults/claims, not a blacklist of
    # any real employer or customer. The invariant is intentionally portable.
    forbidden_phrases = (
        "internal " + "use only",
        "company " + "confidential",
        "employee" + "-only",
        "employees " + "only",
    )
    for path in iter_package_files(root):
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".gitignore", "LICENSE"}:
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        for phrase in forbidden_phrases:
            if phrase in text:
                results.fail(
                    "public repository hygiene",
                    f"organization-bound public text found in {rel(root, path)}: {phrase!r}",
                )

    config_path = root / "config/default-config.jsonc"
    if config_path.is_file():
        config_text = config_path.read_text(encoding="utf-8").lower()
        organization_bound_keys = (
            "organizationname", "organisationname", "companyname", "employername",
            "tenantid", "corporatedomain", "internaldomain",
        )
        for key in organization_bound_keys:
            if re.search(rf'["\']{re.escape(key)}["\']\s*:', config_text):
                results.fail(
                    "public repository hygiene",
                    f"default config contains organization-bound key: {key}",
                )

    results.ok("generic open-source/public-repository hygiene checked")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="validate an alternate distributable tree root")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--working-tree", action="store_true",
        help="Validate the distributable view of a working tree while ignoring runtime cache/diagnostics/logs/releases/user config/bytecode.",
    )
    args = parser.parse_args(argv)
    root = (args.root.resolve() if args.root else Path(__file__).resolve().parents[2])
    if not root.is_dir():
        print(f"ERROR package root does not exist: {root}", file=sys.stderr)
        return 2
    if args.working_tree:
        def ignore(directory: str, names: list[str]) -> set[str]:
            current = Path(directory).resolve()
            ignored = {name for name in names if name in {".git", "__pycache__"} or name.endswith((".pyc", ".zip"))}
            if current == root:
                ignored.update(name for name in ("cache", "diagnostics", "logs", "releases") if name in names)
            if current == (root / "config").resolve() and "user-config.jsonc" in names:
                ignored.add("user-config.jsonc")
            return ignored
        with tempfile.TemporaryDirectory(prefix="cost-guard-validation-view-") as tmp:
            view = Path(tmp) / "package"
            shutil.copytree(root, view, ignore=ignore)
            results = validate(view)
    else:
        results = validate(root)
    print_results(results, args.json)
    return 1 if results.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
