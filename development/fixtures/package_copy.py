"""Disposable package copies and isolated tool subprocesses for validator/builder tests."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_python(
    *args: str, cwd: Path = ROOT, release_nested: bool = False, timeout: float = 60,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if release_nested:
        env["COST_GUARD_RELEASE_GATE_ACTIVE"] = "1"
    return subprocess.run(
        [sys.executable, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
    )


def copy_package(destination: Path) -> Path:
    """Distributable working-tree view: no runtime state, user config, archives or bytecode."""
    root = destination / "package"

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = {name for name in names if name in {".git", "__pycache__"} or name.endswith((".pyc", ".zip"))}
        current = Path(directory).resolve()
        if current == ROOT.resolve():
            ignored.update(name for name in ("cache", "diagnostics", "logs", "releases") if name in names)
        if current == (ROOT / "config").resolve() and "user-config.jsonc" in names:
            ignored.add("user-config.jsonc")
        return ignored

    shutil.copytree(ROOT, root, ignore=ignore)
    return root


def make_package(tmp: str, fixture: str | None = None) -> Path:
    """Config-only package: shipped defaults plus an optional `fixtures/config` user config."""
    package = Path(tmp) / "package"
    package.mkdir()
    (package / "config").mkdir()
    shutil.copy2(ROOT / "config/default-config.jsonc", package / "config/default-config.jsonc")
    if fixture:
        shutil.copy2(ROOT / "development/fixtures/config" / fixture, package / "config/user-config.jsonc")
    return package
