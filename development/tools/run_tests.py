#!/usr/bin/env python3
"""Run Cost Guard tests as bounded per-file suites.

`quick` is the default for constrained/hosted AI environments. Each test file is
an isolated subprocess with a hard timeout, and files run concurrently to keep
wall-clock time low. `full` adds package mutation and
benchmark checks and is intended for Diagnostics or unrestricted local use; its
slowest (full-only) files start first so they overlap the many quick files.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "development/tests"

QUICK_PATTERNS: tuple[str, ...] = (
    "test_macos_web.py",
    "test_macos_app.py",
    "test_windows_web.py",
    "test_web_lifecycle.py",
    "test_web_runtime.py",
    "test_application_reports.py",
    "test_history_loading.py",
    "test_source_history_loading.py",
    "test_foundation_quick.py",
    "test_config.py",
    "test_domain.py",
    "test_session_tree.py",
    "test_report_sampling.py",
    "test_report_duration.py",
    "test_session_snapshot.py",
    "test_v2_normalization.py",
    "test_watch_account_refresh.py",
    "test_prompt_projection.py",
    "test_cache.py",
    "test_opencode_v1.py",
    "test_opencode_v2.py",
    "test_connectivity_reliability.py",
    "test_watch_startup_recovery.py",
    "test_opencode_aborts.py",
    "test_watch_stop_reasons.py",
    "test_live_stop_reasons.py",
    "test_opencode_terminal.py",
    "test_source_selection.py",
    "test_analysis_core.py",
    "test_step6_context_comparisons.py",
    "test_context_history_projection.py",
    "test_windows_launcher.py",
    "test_launcher_feedback.py",
    "test_startup_progress.py",
    "test_watch_screen.py",
    "test_effort_presentation.py",
    "test_context_warning_presentation.py",
    "test_step6_pricing_accounts.py",
    "test_step7_reports_cli.py",
    "test_step8_watch.py",
    "test_watch_grouping.py",
    "test_watch_session_groups.py",
    "test_watch_session_retention.py",
    "test_watch_terminal_recency.py",
    "test_watch_idle_accounts.py",
    "test_watch_subtotals.py",
    "test_watch_today_ccost.py",
    "test_watch_rendering.py",
    "test_watch_tool_activity.py",
    "test_watch_skills.py",
    "test_watch_activity_lifecycle.py",
    "test_watch_source_recovery.py",
    "test_watch_observation_diagnostics.py",
    "test_v2_synthetic_attribution.py",
    "test_v2_tool_continuations.py",
    "test_threshold_multiplier.py",
    "test_watch_lifecycle.py",
    "test_runtime_errors.py",
    "test_zero_data_robustness.py",
    "test_token_mix.py",
    "test_token_mix_economics.py",
    "test_priced_token_mix.py",
    "test_v783_regressions.py",
    "test_v784_regressions.py",
    "test_v786_regressions.py",
    "test_v788_regressions.py",
    "test_v7810_regressions.py",
    "test_v7811_regressions.py",
    "test_v7814_regressions.py",
    "test_accounts_ccost.py",
    "test_account_period_ccost.py",
    "test_copilot_unaccounted_usage.py",
    "test_account_ordering.py",
    "test_simple_http_engine.py",
    "test_http_account_providers.py",
    "test_ccost_migration.py",
    "test_quota_presentation.py",
    "test_account_status_layout.py",
    "test_report_polish.py",
    "test_model_pricing_presentation.py",
    "test_model_comparison_tiers.py",
    "test_model_supersession.py",
    "test_account_acquisition.py",
    "test_openai_account_switch.py",
    "test_account_freshness.py",
    "test_quota_observations.py",
    "test_report_definitions.py",
    "test_session_move.py",
    "test_compact_reports.py",
    "test_model_availability.py",
    "test_watch_model_discovery.py",
    "test_release_metadata_recovery.py",
    "test_pricing_watch_startup.py",
    "test_diagnostic_logs.py",
    "test_diagnostics_ux.py",
    "test_pricing_identities.py",
    "test_claude_code_accounts.py",
    "test_claude_transport.py",
)
FULL_ONLY_PATTERNS: tuple[str, ...] = (
    # Slowest first: Full starts these before the quick files.
    "test_foundation.py",
    "test_rc2_public_diagnostics.py",
    "test_step9_parity_performance.py",
)
PROFILES: dict[str, tuple[str, ...]] = {
    "startup": ("test_launcher_feedback.py", "test_windows_launcher.py", "test_startup_progress.py", "test_watch_screen.py", "test_watch_rendering.py", "test_watch_startup_recovery.py"),
    "sources": ("test_opencode_v1.py", "test_opencode_v2.py", "test_v2_normalization.py", "test_v2_tool_continuations.py", "test_opencode_aborts.py", "test_opencode_terminal.py", "test_source_selection.py", "test_v7814_regressions.py"),
    "analysis": ("test_analysis_core.py", "test_step6_context_comparisons.py", "test_effort_presentation.py", "test_step6_pricing_accounts.py"),
    "runtime": ("test_step7_reports_cli.py", "test_step8_watch.py", "test_watch_grouping.py", "test_watch_session_retention.py", "test_watch_idle_accounts.py", "test_watch_subtotals.py", "test_watch_today_ccost.py", "test_watch_rendering.py", "test_watch_tool_activity.py", "test_watch_skills.py", "test_watch_activity_lifecycle.py", "test_watch_source_recovery.py", "test_watch_lifecycle.py", "test_token_mix.py", "test_token_mix_economics.py", "test_priced_token_mix.py", "test_report_definitions.py", "test_session_move.py", "test_opencode_aborts.py", "test_opencode_terminal.py", "test_v786_regressions.py", "test_v788_regressions.py", "test_v7810_regressions.py", "test_v7811_regressions.py", "test_v7814_regressions.py"),
}


def _run_pattern(pattern: str, *, timeout: float, verbosity: int) -> tuple[str, int, float, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["COST_GUARD_TEST_MODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"  # child output is decoded as UTF-8 regardless of console code page
    flag = "-v" if verbosity >= 2 else "-q"
    command = [
        sys.executable, "-m", "unittest", "discover",
        "-s", str(TESTS), "-p", pattern, "-t", str(ROOT), flag,
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command, cwd=ROOT, env=env, timeout=timeout,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
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
    parser.add_argument("--jobs", type=int, help="Concurrent test files (suite default 4; profile/pattern 1).")
    parser.add_argument("--verbosity", type=int, default=2)
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # failure text may contain non-console characters
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    if args.pattern:
        patterns = (args.pattern,)
    elif args.profile:
        patterns = PROFILES[args.profile]
    elif args.suite == "full":
        patterns = FULL_ONLY_PATTERNS + QUICK_PATTERNS
    else:
        patterns = QUICK_PATTERNS

    # Full files may nest validator/builder subprocesses while other files run.
    timeout = args.file_timeout if args.file_timeout is not None else (25.0 if args.suite == "quick" else 240.0)
    default_jobs = 4 if not args.profile and not args.pattern else 1
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
