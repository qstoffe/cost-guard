#!/usr/bin/env python3
"""Run Cost Guard tests as bounded per-file suites.

`quick` is the default for constrained/hosted AI environments. Each test file is
an isolated subprocess with a hard timeout, and quick files run concurrently to
keep hosted wall-clock time low. `full` adds package mutation, release-builder
and benchmark checks and is intended for Diagnostics or unrestricted local use.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from fnmatch import fnmatchcase
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "development/tests"

QUICK_PATTERNS: tuple[str, ...] = (
    "test_foundation_quick.py",
    "test_config.py",
    "test_domain.py",
    "test_cache.py",
    "test_opencode_v1.py",
    "test_opencode_v2.py",
    "test_opencode_aborts.py",
    "test_opencode_terminal.py",
    "test_source_selection.py",
    "test_analysis_core.py",
    "test_step6_context_comparisons.py",
    "test_effort_presentation.py",
    "test_context_warning_presentation.py",
    "test_step6_pricing_accounts.py",
    "test_step7_reports_cli.py",
    "test_step8_watch.py",
    "test_watch_grouping.py",
    "test_watch_rendering.py",
    "test_watch_tool_activity.py",
    "test_watch_source_recovery.py",
    "test_zero_data_robustness.py",
    "test_token_mix.py",
    "test_token_mix_economics.py",
    "test_v783_regressions.py",
    "test_v784_regressions.py",
    "test_v786_regressions.py",
    "test_v788_regressions.py",
    "test_v7810_regressions.py",
    "test_v7811_regressions.py",
    "test_v7814_regressions.py",
    "test_accounts_ccost.py",
    "test_simple_http_engine.py",
    "test_http_account_providers.py",
    "test_ccost_migration.py",
    "test_quota_presentation.py",
    "test_report_polish.py",
    "test_model_pricing_presentation.py",
    "test_report_definitions.py",
    "test_session_move.py",
    "test_compact_reports.py",
    "test_model_availability.py",
    "test_pricing_identities.py",
    "test_claude_code_accounts.py",
    "test_claude_transport.py",
    "test_version_history.py",
)
FULL_ONLY_PATTERNS: tuple[str, ...] = (
    "test_step9_parity_performance.py",
    "test_step10_release_hardening.py",
    "test_rc2_public_diagnostics.py",
    "test_foundation.py",
)
# Intentional omissions require an exact relative module path and a reason.
# None currently: every test_*.py module belongs to Quick or Full-only.
EXCLUDED_TEST_MODULES: dict[str, str] = {}
PROFILES: dict[str, tuple[str, ...]] = {
    "foundation": ("test_foundation_quick.py",),
    "sources": ("test_opencode_v1.py", "test_opencode_v2.py", "test_opencode_aborts.py", "test_opencode_terminal.py", "test_source_selection.py", "test_v7814_regressions.py"),
    "analysis": ("test_analysis_core.py", "test_step6_context_comparisons.py", "test_effort_presentation.py", "test_step6_pricing_accounts.py"),
    "runtime": ("test_step7_reports_cli.py", "test_step8_watch.py", "test_watch_grouping.py", "test_watch_rendering.py", "test_watch_tool_activity.py", "test_watch_source_recovery.py", "test_token_mix.py", "test_token_mix_economics.py", "test_report_definitions.py", "test_session_move.py", "test_opencode_aborts.py", "test_opencode_terminal.py", "test_v786_regressions.py", "test_v788_regressions.py", "test_v7810_regressions.py", "test_v7811_regressions.py", "test_v7814_regressions.py"),
    "release": FULL_ONLY_PATTERNS,
}


def suite_membership_errors(tests: Path = TESTS) -> list[str]:
    """Reject orphaned modules and stale/ambiguous suite declarations."""
    modules = {path.relative_to(tests).as_posix() for path in tests.rglob("test_*.py")}
    patterns = QUICK_PATTERNS + FULL_ONLY_PATTERNS
    errors = []
    for pattern in patterns:
        if not any(fnmatchcase(Path(module).name, pattern) for module in modules):
            errors.append(f"suite pattern matches no test module: {pattern}")
    for module in sorted(modules):
        matches = sum(fnmatchcase(Path(module).name, pattern) for pattern in patterns)
        excluded = module in EXCLUDED_TEST_MODULES
        if matches == 0 and not excluded:
            errors.append(f"unassigned test module: {module}")
        elif matches > 1 or (matches and excluded):
            errors.append(f"test module has overlapping suite/exclusion assignments: {module}")
    for module, reason in EXCLUDED_TEST_MODULES.items():
        if module not in modules or not reason.strip():
            errors.append(f"stale or undocumented test exclusion: {module}")
    return errors


def _run_pattern(pattern: str, *, timeout: float, verbosity: int) -> tuple[str, int, float, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    flag = "-v" if verbosity >= 2 else "-q"
    command = [
        sys.executable, "-m", "unittest", "discover",
        "-s", str(TESTS), "-p", pattern, "-t", str(ROOT), flag,
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command, cwd=ROOT, env=env, timeout=timeout,
            capture_output=True, text=True,
        )
        output = (proc.stdout + proc.stderr).strip()
        return pattern, proc.returncode, time.monotonic() - started, output
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return pattern, 124, elapsed, (stdout + stderr + f"\nTIMEOUT after {timeout:g}s").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("quick", "full"), default="quick")
    parser.add_argument("--profile", choices=tuple(PROFILES), help="Run one bounded profile instead of a suite.")
    parser.add_argument("--pattern", help="Run exactly one unittest discovery pattern.")
    parser.add_argument("--file-timeout", type=float, help="Hard timeout per test file/process.")
    parser.add_argument("--jobs", type=int, help="Concurrent test files (quick default 4; full default 1).")
    parser.add_argument("--verbosity", type=int, default=2)
    args = parser.parse_args(argv)

    errors = suite_membership_errors()
    if errors:
        for error in errors:
            print(f"TEST PLAN ERROR: {error}", file=sys.stderr)
        return 2

    if args.pattern:
        patterns = (args.pattern,)
    elif args.profile:
        patterns = PROFILES[args.profile]
    elif args.suite == "full":
        patterns = QUICK_PATTERNS + FULL_ONLY_PATTERNS
    else:
        patterns = QUICK_PATTERNS

    timeout = args.file_timeout if args.file_timeout is not None else (25.0 if args.suite == "quick" else 90.0)
    default_jobs = 4 if args.suite == "quick" and not args.profile and not args.pattern else 1
    jobs = max(1, min(len(patterns), args.jobs or default_jobs))
    started = time.monotonic()
    results: dict[str, tuple[int, float, str]] = {}
    suite_label = args.pattern or args.profile or args.suite
    print(
        f"TEST PLAN suite={suite_label} files={len(patterns)} jobs={jobs} file_timeout={timeout:g}s",
        flush=True,
    )

    def record(result: tuple[str, int, float, str]) -> None:
        pattern, code, elapsed, output = result
        results[pattern] = (code, elapsed, output)
        state = "PASS" if code == 0 else ("TIMEOUT" if code == 124 else "FAIL")
        print(f"[{state:7}] {pattern} ({elapsed:.2f}s)", flush=True)
        if code != 0 and output:
            print(output, flush=True)

    if jobs == 1:
        for index, pattern in enumerate(patterns, start=1):
            print(f"[START  ] {pattern} ({index}/{len(patterns)})", flush=True)
            record(_run_pattern(pattern, timeout=timeout, verbosity=args.verbosity))
    else:
        with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="cg-test") as pool:
            futures = [pool.submit(_run_pattern, pattern, timeout=timeout, verbosity=args.verbosity) for pattern in patterns]
            for future in as_completed(futures):
                record(future.result())

    failures = [pattern for pattern in patterns if results[pattern][0] != 0]
    elapsed = time.monotonic() - started
    print(f"TEST SUMMARY suite={suite_label} failures={len(failures)} files={len(patterns)} jobs={jobs} elapsed={elapsed:.1f}s")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
