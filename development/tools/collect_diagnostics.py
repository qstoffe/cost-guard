#!/usr/bin/env python3
"""Collect a privacy-conscious Cost Guard environment diagnostic bundle.

The bundle intentionally omits prompt text, session titles, auth tokens and raw
OpenCode payloads. It is designed to be safe to hand back to a maintainer when
debugging source discovery, provider health, cache behaviour and report wiring.
"""
from __future__ import annotations

import sys

if __name__ == "__main__":
    # Guard ALL normal imports/initialization, including the diagnostic tooling.
    try:
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root))
        from src.runtime_errors import RuntimeErrors
        def start():
            import runpy
            return runpy.run_path(__file__, run_name="cost_guard_diagnostics")["main"]()
        code = RuntimeErrors(root, mode="Diagnostics").run(start, preserve_hooks=True)
    except KeyboardInterrupt:
        code = 130
    except BaseException as exc:
        try:
            sys.stderr.write(f"COST GUARD FAILED\nUnhandled {type(exc).__name__}\n"
                             "Crash report could not be written: runtime boundary unavailable\n")
        except BaseException:
            pass
        code = 1
    raise SystemExit(code)

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import time
import traceback
import zipfile
from collections import Counter
from decimal import Decimal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.accounts.github_copilot import GitHubCopilotAccountProvider  # noqa: E402
from src.accounts.diagnostics import sanitized_account_observation  # noqa: E402
from src.bootstrap import _account_providers, _model_availability_source, _select_source  # noqa: E402
from src.cache import CacheDatabase, CacheRepository  # noqa: E402
from src.config import load_configuration  # noqa: E402
from src.pricing.github_copilot import GitHubCopilotPricingProvider  # noqa: E402
from src.presentation import StartupProgress  # noqa: E402
from src.reports import ReportKind, ReportRequest, ReportService  # noqa: E402
from src.sources.opencode_v1 import OpenCodeV1Source  # noqa: E402
from src.sources.discovery import default_opencode_data_dir  # noqa: E402
from src.sources.opencode_v2 import OpenCodeV2Source  # noqa: E402
from src.sources.selection import SourceSelector  # noqa: E402
from src.version import DISPLAY_VERSION, PRODUCT_NAME, RELEASE_DATE, mode_heading  # noqa: E402
from src.runtime_errors import recoverable, recovered  # noqa: E402
from src.sources.errors import SourceError  # noqa: E402
from src.config import ConfigError  # noqa: E402




def _diagnostic_header() -> str:
    return mode_heading("Diagnostics")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _home_redacted(path: Path | str | None) -> str | None:
    if path is None:
        return None
    text = str(path)
    try:
        home = str(Path.home())
        if os.path.normcase(text).startswith(os.path.normcase(home)):
            return "~" + text[len(home):]
    except (OSError, RuntimeError):
        return "<unavailable>"
    return text


def _hash_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:12]


def _health(value: Any) -> dict[str, Any]:
    return {
        "available": bool(getattr(value, "available", False)),
        "healthy": bool(getattr(value, "healthy", False)),
        "detail": str(getattr(value, "detail", "")),
    }


def _timed(call: Callable[[], Any]) -> tuple[Any | None, dict[str, Any]]:
    start = time.perf_counter()
    try:
        value = call()
        return value, {"ok": True, "elapsed_ms": round((time.perf_counter() - start) * 1000, 2)}
    except Exception as exc:
        # Each diagnostic section is explicitly isolated: failed acquisition
        # becomes an honest error record, never fabricated application truth.
        expected = isinstance(exc, (SourceError, ConfigError, OSError, ValueError))
        if not expected:
            recoverable(exc, "diagnostics-section")
        return None, {
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
            "error_type": type(exc).__name__,
            "error": "Operational collection failure" if expected else "ERROR: Diagnostic section failed internally",
        }


def _session_stats(source: Any, *, snapshots: int) -> dict[str, Any]:
    health, probe_timing = _timed(source.probe)
    result: dict[str, Any] = {"probe": _health(health) if health is not None else None, "probe_timing": probe_timing}
    if health is None or not getattr(health, "healthy", False):
        return result
    sessions, list_timing = _timed(source.list_sessions)
    result["list_timing"] = list_timing
    if sessions is None:
        return result
    values = list(sessions)
    result["session_count"] = len(values)
    result["root_count"] = sum(1 for item in values if not item.parent_session_id)
    result["child_count"] = sum(1 for item in values if item.parent_session_id)
    result["archived_count"] = sum(1 for item in values if item.archived_at_ms)
    if values:
        result["oldest_created_ms"] = min(item.created_at_ms for item in values)
        result["newest_updated_ms"] = max(item.updated_at_ms for item in values)
    roots = [item for item in values if not item.parent_session_id][: max(0, snapshots)]
    sample: list[dict[str, Any]] = []
    for root in roots:
        snap, timing = _timed(lambda root=root: source.load_session_snapshot(root.session_id))
        entry: dict[str, Any] = {"session_hash": _hash_id(root.session_id), "snapshot_timing": timing}
        if snap is not None:
            providers = Counter()
            models = Counter()
            token_total = 0
            reported_cost_observations = 0
            positive_reported_cost_observations = 0
            reported_cost_total = Decimal("0")
            for invocation in snap.invocations:
                providers[invocation.model.provider] += 1
                models[invocation.model.model] += 1
                token_total += invocation.tokens.total
                cost = getattr(invocation, "cost", None)
                if cost is not None:
                    reported_cost_observations += 1
                    reported_cost_total += cost.amount
                    positive_reported_cost_observations += int(cost.amount > 0)
            entry.update({
                "tree_sessions": len(snap.sessions),
                "messages": len(snap.messages),
                "events": len(snap.events),
                "invocations": len(snap.invocations),
                "token_total": token_total,
                "reported_cost_observations": reported_cost_observations,
                "positive_reported_cost_observations": positive_reported_cost_observations,
                "reported_cost_total": str(reported_cost_total),
                "providers": dict(providers),
                "models": dict(models),
                "running_invocations": sum(1 for invocation in snap.invocations if invocation.completed_at_ms is None),
            })
        sample.append(entry)
    result["snapshot_sample"] = sample
    return result


def _projection_summary(projection: Any) -> dict[str, Any]:
    summary = {
        "local_usage_provider_scope": "all-canonical-providers",
        "model_comparison_rows": len(projection.model_comparison),
        "session_usage_rows": len(projection.session_usage),
        "prompt_blocks": len(projection.prompt_blocks),
        "prompt_rows": sum(len(block.rows) for block in projection.prompt_blocks),
        "warnings": [*projection.source_warnings, *projection.notes],
        "recent_model_notice": projection.recent_model_notice,
        "pricing": dict(projection.pricing_diagnostics),
        "token_mix": {"sample_prompts": projection.token_mix.sample_size,
                      "totals": projection.token_mix.totals, "percentages": projection.token_mix.percentages},
    }
    quota = projection.accounts_quotas
    if quota is not None:
        summary["accounts_quotas"] = {
            "accounts": [sanitized_account_observation(item.account) for item in quota.accounts],
        }
    return summary


def _safe_source_stats(source: Any, *, snapshots: int) -> dict[str, Any]:
    value, timing = _timed(lambda: _session_stats(source, snapshots=snapshots))
    if value is not None:
        return value
    return {"collection_error": timing}


def _report_summary(selection: Any, config: dict[str, Any], *, network: bool) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    database = CacheDatabase(ROOT)
    database.initialize()
    repository = CacheRepository(database)
    pricing = GitHubCopilotPricingProvider(
        cache=repository,
        max_age_hours=float(config.get("pricingMaxAgeHours", 6)),
    )
    providers = _account_providers(config, selection.selected) if network else ()
    service = ReportService(
        selection=selection,
        pricing_provider=pricing,
        account_provider=None,
        account_providers=providers,
        model_availability_source=_model_availability_source(selection) if network else None,
        cache_repository=repository,
        config=config,
        now_ms=_now_ms(),
    )
    projection, timing = _timed(lambda: service.build(ReportRequest(ReportKind.NORMAL)))
    if projection is None:
        return None, timing
    return _projection_summary(projection), timing



def _safe_process_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def _validation_command(script: Path, *args: str, timeout: int) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, str(script), *args], cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=timeout,
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "output_tail": output[-8000:],
        }
    except subprocess.TimeoutExpired as exc:
        output = ((_safe_process_text(exc.stdout)) + "\n" + _safe_process_text(exc.stderr)).strip()
        return {
            "ok": False, "timed_out": True,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "output_tail": output[-8000:],
        }


def _validation_test_suite(progress: StartupProgress, *, timeout: int = 900) -> dict[str, Any]:
    """Stream full-suite file completion so diagnostics progress reflects real work."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.perf_counter()
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "development/tools/run_tests.py"), "--suite", "full"],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    lines: list[str] = []
    total = 16
    completed = 0
    plan_re = re.compile(r"TEST PLAN .*files=(\d+)")
    result_re = re.compile(r"^\[(?:PASS|FAIL|TIMEOUT)\s*\]\s+(\S+)")
    start_re = re.compile(r"^\[START\s*\]\s+(\S+)")
    deadline = time.monotonic() + timeout
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))
            plan = plan_re.search(line)
            if plan:
                total = max(1, int(plan.group(1)))
            started_match = start_re.match(line)
            if started_match:
                percent = 8 + int(50 * min(completed + 0.5, total) / total)
                progress.update(f"Full tests {completed}/{total}: running {started_match.group(1)}", percent)
            match = result_re.match(line)
            if match:
                completed += 1
                percent = 8 + int(50 * min(completed, total) / total)
                progress.update(f"Full tests {completed}/{total}: {match.group(1)}", percent)
            if time.monotonic() > deadline:
                proc.kill()
                raise subprocess.TimeoutExpired(proc.args, timeout)
        code = proc.wait(timeout=max(1, deadline - time.monotonic()))
        output = "\n".join(lines)
        return {
            "ok": code == 0, "exit_code": code,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "output_tail": output[-8000:],
        }
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        output = "\n".join(lines)
        return {
            "ok": False, "timed_out": True,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "output_tail": output[-8000:],
        }


def _macos_compatibility_checks() -> dict[str, Any]:
    """Execute isolated cross-platform simulations, never invoking a real Mac CLI."""
    command = _validation_command(
        ROOT / "development/tools/macos_compatibility.py", timeout=30,
    )
    tail = command.pop("output_tail", "")
    try:
        result = json.loads(tail)
        if not isinstance(result, dict) or not isinstance(result.get("cases"), list):
            raise ValueError("invalid compatibility result")
        allowed = {"mode", "native_macos_execution", "cases", "passed", "failed", "skipped", "ok"}
        result = {key: value for key, value in result.items() if key in allowed}
        clean_cases = []
        for case in result["cases"]:
            if isinstance(case, dict):
                clean_cases.append({
                    "id": str(case.get("id", ""))[:100],
                    "status": str(case.get("status", "ERROR"))[:16],
                    **({"error_type": str(case["error_type"])[:80]} if case.get("error_type") else {}),
                })
        result["cases"] = clean_cases
        result["ok"] = bool(result.get("ok")) and bool(command["ok"])
        return {**result, "elapsed_ms": command["elapsed_ms"]}
    except (ValueError, TypeError, KeyError):
        return {
            "mode": "simulated-macos-behavior",
            "native_macos_execution": False,
            "ok": False,
            "cases": [],
            "error_type": "CompatibilityRunnerFailure",
            "timed_out": bool(command.get("timed_out")),
            "exit_code": command.get("exit_code"),
        }


def run_full_validation(progress: StartupProgress) -> dict[str, Any]:
    """Run the unrestricted/local validation tier without preventing diagnostics output."""
    progress.update("Running full deterministic test suite", 8)
    tests = _validation_test_suite(progress, timeout=900)
    progress.update("Validating package architecture and inventory", 62)
    package = _validation_command(
        ROOT / "development/tools/validate_package.py", "--working-tree", timeout=180,
    )
    return {
        "tier": "full-local",
        "tests": tests,
        "package_validator": package,
        "ok": bool(tests.get("ok") and package.get("ok")),
    }

def _text_summary(data: dict[str, Any]) -> str:
    validation = data.get("validation") or {}
    validation_ok = validation.get("ok")
    validation_text = "SKIPPED" if validation_ok is None else str(bool(validation_ok))
    compatibility = data.get("macos_compatibility") or {}
    tests_ok = (validation.get("tests") or {}).get("ok")
    validator_ok = (validation.get("package_validator") or {}).get("ok")
    tests_text = "SKIPPED" if tests_ok is None else str(bool(tests_ok))
    validator_text = "SKIPPED" if validator_ok is None else str(bool(validator_ok))
    lines = [
        f"Cost Guard diagnostics {data['cost_guard']['version']}",
        f"Generated: {data['generated_at_utc']}",
        f"Python: {data['environment']['python_version']}",
        f"Platform: {data['environment']['platform']}",
        "",
        f"macOS compatibility (simulated): {compatibility.get('ok', False)}",
        f"  PASS={compatibility.get('passed', 0)} FAIL={compatibility.get('failed', 0)} SKIP={compatibility.get('skipped', 0)}",
        "  This is not a native macOS execution.",
        "",
        f"Full validation: {validation_text}",
        f"  Tests: {tests_text}",
        f"  Package validator: {validator_text}",
        "",
        f"Configured source: {data.get('config', {}).get('open_code_source')}",
        f"Selected source: {(data.get('selection') or {}).get('selected')}",
    ]
    startup = data.get("service_start_test")
    if startup is not None:
        lines.append(f"V2 startup test: {startup['outcome']} (before: {startup['v2_healthy_before']}, after: {startup['v2_healthy_after']})")
    for key in ("v1", "v2"):
        item = data.get("sources", {}).get(key, {})
        probe = item.get("probe") or {}
        lines.append(
            f"{key.upper()}: available={probe.get('available')} healthy={probe.get('healthy')} "
            f"sessions={item.get('session_count', 'N/A')} roots={item.get('root_count', 'N/A')} detail={probe.get('detail', '')}"
        )
    report = data.get("report") or {}
    lines.extend([
        "",
        f"Report diagnostic ok: {data.get('report_timing', {}).get('ok')}",
        f"Session rows: {report.get('session_usage_rows', 'N/A')}",
        f"Prompt rows: {report.get('prompt_rows', 'N/A')}",
        f"Model comparison rows: {report.get('model_comparison_rows', 'N/A')}",
        "",
        "Privacy: prompt text, session titles, auth tokens, raw auth files and raw OpenCode payloads are intentionally excluded.",
    ])
    return "\n".join(lines) + "\n"


def collect(*, network: bool, snapshots: int, test_service_start: bool = False) -> dict[str, Any]:
    loaded = load_configuration(ROOT)
    cfg = dict(loaded.values)
    v1 = OpenCodeV1Source()
    v2 = OpenCodeV2Source()
    data: dict[str, Any] = {
        "schema_version": 2,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cost_guard": {"version": DISPLAY_VERSION},
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "system": platform.system(),
        },
        "config": {
            "default_config": "config/default-config.jsonc",
            "user_config": "config/user-config.jsonc",
            "user_config_present": loaded.user_config_present,
            "open_code_source": loaded.open_code_source,
            "timezone": cfg.get("timezone"),
            "workday_calendar": cfg.get("workdayCalendar"),
            "pricing_max_age_hours": cfg.get("pricingMaxAgeHours"),
            "running_prompt_warning_ccost": cfg.get("runningPromptWarningCCost"),
            "copilot_quota_enabled": bool((cfg.get("copilotQuota") or {}).get("enabled", True)) if isinstance(cfg.get("copilotQuota"), dict) else True,
        },
        "paths": {
            "v1_database": _home_redacted(v1.database_path),
            "v2_service_registration": _home_redacted(v2.registration_path),
            "cache_database": "cache/" + CacheDatabase(ROOT).paths.database.name,
        },
        "sources": {},
        "network_enabled": network,
        "reference_valuation_unit": "CCost (Copilot AI-credit-equivalent; not billed money or deducted credits)",
    }
    data["sources"]["v1"] = _safe_source_stats(v1, snapshots=snapshots)
    data["sources"]["v2"] = _safe_source_stats(v2, snapshots=snapshots)
    try:
        data["sources"]["v2"]["wire_observation"] = dict(v2.diagnostic_metadata())
    except Exception as exc:
        if not isinstance(exc, (SourceError, OSError)):
            recoverable(exc, "diagnostics-wire-observation")
        data["sources"]["v2"]["wire_observation"] = {
            "error_type": type(exc).__name__, "error": "ERROR: Wire observation unavailable"
        }
    selection, selection_timing = _timed(lambda: SourceSelector().select(loaded.open_code_source))
    data["selection_timing"] = selection_timing
    # Inventory even when no network/account is available, without raw records,
    # labels, locators or secret material. Normalized request evidence is in report.
    data["account_provider_inventory"] = []
    for provider in _account_providers(cfg, selection.selected if selection else "v1"):
        inventory = getattr(provider, "diagnostic_inventory", None)
        if not callable(inventory):
            continue
        value, status = _timed(inventory)
        if status.get("ok") and value is not None:
            data["account_provider_inventory"].append(value)
        else:
            data["account_provider_inventory"].append({
                "provider_type": type(provider).__name__,
                "error_type": status.get("error_type"),
                "error": "ERROR: Provider inventory unavailable",
            })
    if test_service_start:
        before = bool((data["sources"]["v2"].get("probe") or {}).get("healthy"))
        if selection is None:
            # Exercise exactly the real startup path; never stop an existing
            # service, spawn a desktop window or include CLI output in the ZIP.
            selection, startup_timing = _timed(lambda: _select_source(loaded.open_code_source))
            outcome = "started" if selection is not None else "failed"
        else:
            startup_timing = {"ok": True, "skipped": "source already selectable"}
            outcome = "already_running" if before else "other_source_available"
        after_health, _ = _timed(v2.probe)
        data["service_start_test"] = {
            "outcome": outcome,
            "v2_healthy_before": before,
            "v2_healthy_after": bool(getattr(after_health, "healthy", False)),
            "selected": None if selection is None else selection.selected,
            "elapsed_ms": startup_timing.get("elapsed_ms"),
            "error_type": startup_timing.get("error_type"),
        }
    if selection is not None:
        data["selection"] = {
            "selected": selection.selected,
            "warnings": list(selection.warnings),
            "health": _health(selection.selected_health),
            "migration_gap": None if selection.migration_gap is None else {
                "inspected": selection.migration_gap.inspected,
                "missing_in_v2": len(selection.migration_gap.missing_in_v2),
                "newer_in_v1": len(selection.migration_gap.newer_in_v1),
                "detail": selection.migration_gap.detail,
            },
        }
        if network:
            report_result, outer_timing = _timed(lambda: _report_summary(selection, cfg, network=True))
            if report_result is None:
                data["report"] = None
                data["report_timing"] = outer_timing
            else:
                report, report_timing = report_result
                data["report"] = report
                data["report_timing"] = {**report_timing, "section_elapsed_ms": outer_timing.get("elapsed_ms")}
        else:
            data["report"] = None
            data["report_timing"] = {"ok": False, "skipped": "--no-network disables report build because pricing may require network"}
    else:
        data["selection"] = None
        data["report"] = None
        data["report_timing"] = {"ok": False, "error": "source selection failed"}

    quota_cfg = cfg.get("copilotQuota") if isinstance(cfg.get("copilotQuota"), dict) else {}
    try:
        account = GitHubCopilotAccountProvider(
            enabled=bool(quota_cfg.get("enabled", True)),
            auth_json_path=quota_cfg.get("authJsonPath"),
            credential_db_path=(default_opencode_data_dir() / "opencode.db") if (data.get("selection") or {}).get("selected") == "v2" else None,
        )
        health, timing = _timed(account.probe)
        data["github_copilot_account"] = {"probe": _health(health) if health is not None else None, "probe_timing": timing}
        if network and health is not None and getattr(health, "healthy", False):
            quotas, quota_timing = _timed(account.get_account_snapshots)
            data["github_copilot_account"]["quota_timing"] = quota_timing
            if quotas is not None:
                data["github_copilot_account"]["accounts"] = [sanitized_account_observation(item) for item in quotas]
    except Exception as exc:
        if not isinstance(exc, (OSError, ValueError)):
            recoverable(exc, "diagnostics-account-observation")
        data["github_copilot_account"] = {
            "probe": None,
            "probe_timing": {"ok": False, "error_type": type(exc).__name__, "error": "ERROR: Account observation unavailable"},
        }
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-network", action="store_true", help="Skip live GitHub pricing/quota requests.")
    parser.add_argument("--snapshots", type=int, default=3, help="Latest root snapshots to inspect per healthy source (default 3).")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "diagnostics")
    parser.add_argument(
        "--test-service-start", action="store_true",
        help="Test the real source startup path if no source is selectable; never stop OpenCode.",
    )
    parser.add_argument(
        "--skip-validation", action="store_true",
        help="Emergency/recursive mode: collect diagnostics without the full local test + package validation tier.",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as usage:
        return int(usage.code or 0)  # Only argparse's deliberate help/usage exit.
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle = output_dir / f"cost-guard-diagnostics-{stamp}.zip"
    print(_diagnostic_header())
    progress = StartupProgress(mode="normal")
    validation: dict[str, Any] | None = None
    try:
        progress.update("Inspecting local OpenCode sources", 12)
        try:
            data = collect(network=not args.no_network, snapshots=max(0, min(args.snapshots, 10)), test_service_start=args.test_service_start)
        except Exception as exc:
            recoverable(exc, "diagnostics-collection")
            data = {
                "schema_version": 2,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "cost_guard": {"version": DISPLAY_VERSION},
                "environment": {
                    "python_version": platform.python_version(),
                    "platform": platform.platform(),
                    "machine": platform.machine(),
                    "system": platform.system(),
                },
                "collection_error": {
                    "error_type": type(exc).__name__,
                    "error": "ERROR: Diagnostic collection unavailable",
                },
            }
        progress.update("Checking simulated macOS compatibility", 20)
        data["macos_compatibility"] = _macos_compatibility_checks()
        if not args.skip_validation:
            try:
                validation = run_full_validation(progress)
            except Exception as exc:
                recoverable(exc, "diagnostics-validation")
                validation = {
                    "tier": "full-local", "ok": False,
                    "error_type": type(exc).__name__,
                    "error": "ERROR: Local validation unavailable",
                }
        if validation is not None:
            data["validation"] = validation
        else:
            data["validation"] = {"tier": "skipped", "ok": None}
        progress.update("Writing diagnostic bundle", 96)
    finally:
        progress.stop()
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
    text_bytes = _text_summary(data).encode("utf-8") if "cost_guard" in data else (json.dumps(data, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("diagnostics.json", json_bytes)
        archive.writestr("summary.txt", text_bytes)
    progress.stop()
    print(f"Diagnostic bundle created: {bundle}")
    print("Prompt text, session titles, auth tokens and raw OpenCode payloads are not included.")
    return 0
