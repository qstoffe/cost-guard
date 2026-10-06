#!/usr/bin/env python3
"""Build and clean-room verify one Cost Guard ZIP. Standard library only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_GATE_ENV = "COST_GUARD_RELEASE_GATE_ACTIVE"


def should_include(path: Path) -> bool:
    rp = path.relative_to(ROOT).as_posix()
    # Only the package-root runtime cache is disposable. `src/cache/` is
    # production source and must ship.
    if any(part in {".git", "__pycache__"} for part in path.parts):
        return False
    if (
        rp == "cache" or rp.startswith("cache/")
        or rp == "diagnostics" or rp.startswith("diagnostics/")
        or rp == "releases" or rp.startswith("releases/")
    ):
        return False
    if rp == "config/user-config.jsonc" or path.suffix == ".pyc":
        return False
    if path.suffix == ".zip":
        return False
    return True


def product_version() -> str:
    namespace: dict[str, object] = {}
    exec((ROOT / "src/version.py").read_text(encoding="utf-8"), namespace)
    version = namespace.get("VERSION")
    if not isinstance(version, str):
        raise RuntimeError("src/version.py VERSION is not a string")
    return f"v{version}"


def gate_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env[_GATE_ENV] = "1"
    return env


def run_script(script: Path, *args: str, cwd: Path, env: dict[str, str]) -> int:
    proc = subprocess.run([sys.executable, str(script), *args], cwd=cwd, env=env)
    return proc.returncode


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*") if path.is_file() and should_include(path))


def verify_archive_bytes(archive_path: Path, files: list[Path], extracted_root: Path) -> None:
    expected_names = {path.relative_to(ROOT).as_posix() for path in files}
    with zipfile.ZipFile(archive_path, "r") as archive:
        actual_names = set(archive.namelist())
        for name in sorted(value for value in actual_names if value.startswith("macos/") and value.endswith(".command")):
            mode = (archive.getinfo(name).external_attr >> 16) & 0o777
            if not (mode & 0o100):
                raise RuntimeError(f"macOS launcher is not executable in archive metadata: {name}")
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise RuntimeError(f"release archive inventory mismatch: missing={missing}, extra={extra}")
    for source in files:
        relative = source.relative_to(ROOT)
        extracted = extracted_root / relative
        if not extracted.is_file() or extracted.read_bytes() != source.read_bytes():
            raise RuntimeError(f"release archive byte mismatch: {relative.as_posix()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--full-verification", action="store_true",
        help="Use the full local/unrestricted test tier instead of the default quick RC gate.",
    )
    parser.add_argument(
        "--quick-already-run", action="store_true",
        help="Constrained-harness mode: skip only the duplicate source Quick run after Quick just passed on this unchanged tree; clean-extract Quick still runs.",
    )
    args = parser.parse_args(argv)

    nested = os.environ.get(_GATE_ENV) == "1"
    env = gate_env()
    test_runner = ROOT / "development/tools/run_tests.py"
    validator = ROOT / "development/tools/validate_package.py"

    # Hosted/constrained AI environments default to the bounded quick tier.
    # Full local verification is intentionally available as an explicit gate and
    # is also run by Diagnostics on unrestricted real machines. Nested builder
    # regression tests skip the outer behavior gate to avoid recursive execution.
    suite = "full" if args.full_verification else "quick"
    if args.full_verification and args.quick_already_run:
        parser.error("--quick-already-run cannot be combined with --full-verification")
    source_tests_gated = not nested and not args.quick_already_run
    if source_tests_gated and run_script(test_runner, "--suite", suite, cwd=ROOT, env=env) != 0:
        print(f"Release build refused: {suite} test suite failed.", file=sys.stderr)
        return 2
    if run_script(validator, "--working-tree", cwd=ROOT, env=env) != 0:
        print("Release build refused: distributable working-tree validation failed.", file=sys.stderr)
        return 3

    version = product_version()
    output = args.output.resolve() if args.output else ROOT / "releases" / f"cost-guard-{version}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)

    files = package_files()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            # Normalize archive permissions instead of inheriting host filesystem
            # modes. This keeps release output portable when built on Windows or
            # rebuilt from a Python-extracted ZIP (which does not restore Unix
            # executable bits). Finder-launchable macOS .command files must be
            # executable in the release archive; ordinary files are 0644.
            mode = 0o100755 if relative.startswith("macos/") and relative.endswith(".command") else 0o100644
            info = zipfile.ZipInfo.from_file(path, arcname=relative)
            info.create_system = 3
            info.external_attr = mode << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )

    try:
        with tempfile.TemporaryDirectory(prefix="cost-guard-release-verify-") as tmp:
            extracted = Path(tmp) / "package"
            extracted.mkdir()
            with zipfile.ZipFile(output, "r") as archive:
                archive.extractall(extracted)
            verify_archive_bytes(output, files, extracted)

            required = {
                "AGENTS.md", "cost-guard.py", "README.md", "VERSION_HISTORY.md", "LICENSE",
                "config/default-config.jsonc", "development/MAINTAINER.md",
                "windows/Cost Guard.cmd", "windows/Cost Guard Watch.cmd", "windows/Cost Guard Diagnostics.cmd",
                "macos/Cost Guard.command", "macos/Cost Guard Watch.command", "macos/Cost Guard Diagnostics.command",
            }
            names = {path.relative_to(extracted).as_posix() for path in extracted.rglob("*") if path.is_file()}
            missing = sorted(required - names)
            forbidden = sorted(
                name for name in names
                if name.startswith("cache/") or name.startswith("diagnostics/")
                or name.startswith("releases/") or name == "config/user-config.jsonc"
            )
            if missing or forbidden:
                raise RuntimeError(f"release inventory invalid: missing={missing}, forbidden={forbidden}")

            # A top-level release build must also prove the extracted bytes can
            # run the exact same deterministic suite and validator. Nested builds
            # from builder regression tests skip this duplicate outer gate.
            if not nested:
                if run_script(extracted / "development/tools/run_tests.py", "--suite", suite, cwd=extracted, env=env) != 0:
                    raise RuntimeError(f"clean-extracted release {suite} test suite failed")
                if run_script(extracted / "development/tools/validate_package.py", cwd=extracted, env=env) != 0:
                    raise RuntimeError("clean-extracted release validation failed")
    except Exception as exc:
        output.unlink(missing_ok=True)
        print(f"Release build refused: {exc}", file=sys.stderr)
        return 4

    print(json.dumps({
        "status": "ok",
        "version": version,
        "output": str(output),
        "files": len(files),
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
        "tests_gated": not nested,
        "source_tests_gated": source_tests_gated,
        "test_suite": suite,
        "clean_extract_verified": True,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
