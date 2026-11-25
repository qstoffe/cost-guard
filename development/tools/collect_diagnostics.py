#!/usr/bin/env python3
"""Collect local Cost Guard Web support evidence without starting Web or OpenCode."""
from __future__ import annotations

import sys

if __name__ == "__main__":
    # Cover normal imports and startup with the independent fault boundary.
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
        sys.stderr.write(f"COST GUARD FAILED\nUnhandled {type(exc).__name__}\n"
                         "Crash report could not be written: runtime boundary unavailable\n")
        code = 1
    raise SystemExit(code)

import argparse
import json
import platform
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from development.tools.diagnostic_connectivity import connectivity_summary  # noqa: E402
from development.tools.diagnostic_accounts import quota_freshness_summary  # noqa: E402
from development.tools.diagnostic_logs import create_bundle  # noqa: E402
from development.tools.diagnostic_screen import render_result  # noqa: E402
from development.tools.diagnostic_section import load_section  # noqa: E402
from src.log_paths import log_root  # noqa: E402
from src.runtime_errors import recoverable  # noqa: E402
from src.version import DISPLAY_VERSION, mode_heading  # noqa: E402


def _diagnostic_header() -> str:
    return mode_heading("Diagnostics")


def collect() -> dict:
    dependencies = "development.tools.diagnostic_web_dependencies"
    data = {
        "schema_version": 3,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cost_guard": {"version": DISPLAY_VERSION, "product": "Web"},
        "environment": {"python_version": platform.python_version(),
                        "python_implementation": platform.python_implementation(),
                        "system": platform.system(), "release": platform.release(),
                        "os_version": platform.version(), "machine": platform.machine()},
    }
    data["web"] = load_section("development.tools.diagnostic_web", "web_evidence", ROOT, phase="web_record_and_listener")
    config_result = load_section(dependencies, "config_evidence", ROOT, phase="configuration_read")
    config, data["config"] = config_result if isinstance(config_result, tuple) else (None, config_result)
    data["cache"] = load_section(dependencies, "cache_evidence", ROOT, phase="web_caches")
    data["watch_source_recovery_events"] = load_section("src.sources.connectivity_events", "recent_events",
                                                       phase="recorded_source_recovery")
    data["watch_account_refresh"] = load_section("src.cache.account_refresh_state", "read_refresh_state", ROOT,
                                                phase="recorded_quota")
    data["providers"] = load_section(dependencies, "provider_evidence", ROOT, config, phase="local_provider_state")
    data["sources"] = {generation: load_section(dependencies, "local_source", generation, phase="current_source_probe")
                       for generation in ("v1", "v2")}
    return data


def _text_summary(data: dict) -> str:
    environment = data["environment"]
    web = data.get("web", {})
    snapshot = web.get("snapshot") or {}
    lifecycle = web.get("latest_lifecycle") or {}
    host = web.get("host_probe") or {}
    runtime = web.get("runtime_errors") or {}
    providers = data.get("providers") or {}
    enabled = providers.get("configured_integrations") or {}
    pricing = providers.get("pricing_cache") or {}
    lines = [
        f"Cost Guard Web Diagnostics {data['cost_guard']['version']}",
        f"Generated: {data['generated_at_utc']}",
        f"Python: {environment['python_version']} ({environment.get('python_implementation', 'unknown')})",
        f"OS: {environment.get('system')} {environment.get('release')} {environment.get('os_version')} ({environment.get('machine')})",
        "",
        f"Browser → Cost Guard host: loopback HTTP = {host.get('status', 'unknown')} (no browser/session or identity check)",
        f"Recorded Web snapshot: {web.get('status', 'not_observed')}; build={snapshot.get('product_version', 'unknown')}; "
        f"state={snapshot.get('state', 'unknown')}; age={web.get('age_seconds', 'unknown')}s; stale={web.get('stale', 'unknown')}",
        f"Recorded lifecycle: {lifecycle.get('code', web.get('lifecycle_status', 'unknown'))} at {lifecycle.get('observed_at', 'unknown')} UTC epoch seconds",
        f"Recorded Web API failures: {snapshot.get('api_failures', 'unknown')}; reasons: {snapshot.get('api_reasons', 'unknown')}",
        f"Private Web runtime: errors={runtime.get('errors', {}).get('status', 'unknown')}; crashes={runtime.get('crashes', {}).get('status', 'unknown')}",
        "",
        f"Cost Guard host → OpenCode (recorded): {snapshot.get('source_status', 'unknown')}; "
        f"failure={snapshot.get('source_error') or 'not recorded'}; "
        f"last source observation={snapshot.get('source_observed_at_ms') or 'unknown'} UTC epoch ms",
        f"Configuration (current read): {data.get('config', {}).get('status', 'unknown')}; "
        f"requested source={data.get('config', {}).get('open_code_source', 'unknown')}",
        "OpenCode probes (current, independent of the Web host):",
        *connectivity_summary(data),
        "",
        "Web caches (read-only): " + (", ".join(f"{key}={value['status']}" for key, value in data.get("cache", {}).items()
                                              if isinstance(value, dict) and "status" in value) or "unavailable"),
        f"Cached pricing: {pricing.get('status', 'unknown')}; models={pricing.get('model_count', 'unknown')}; "
        f"dated={pricing.get('release_dates_known', 'unknown')}",
        "Enabled quota integrations: " + (", ".join(key for key, value in enabled.items() if value) or
                                           ("none" if enabled else "unknown")),
        *quota_freshness_summary(data),
        "No Web/source startup, full report, external quota request or developer test was run.",
        "Privacy: no prompt text, session titles, credentials, raw logs or source payloads are attached.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=log_root(ROOT) / "diagnostics")
    for unused_flag in ("--no-network", "--skip-validation"):
        parser.add_argument(unused_flag, action="store_true", help=argparse.SUPPRESS)
    try:
        args = parser.parse_args(argv)
    except SystemExit as usage:
        return int(usage.code or 0)
    bundle = args.output_dir / "cost-guard-diagnostics.zip"
    print(_diagnostic_header(), flush=True)
    print("Collecting local Web support evidence...", flush=True)
    data = collect()
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    try:
        create_bundle(bundle, root=ROOT, json_bytes=json_bytes, text_bytes=_text_summary(data).encode("utf-8"),
                      include_logs=False)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        recoverable(exc, "diagnostics-bundle-publish")
        render_result(error=exc)
        return 1
    render_result(path=bundle.resolve(), email=_support_email())
    return 0


def _support_email() -> str:
    defaults = load_section("src.config", "read_jsonc", ROOT / "config/default-config.jsonc", phase="support_contact")
    return str(defaults.get("diagnostics", {}).get("supportEmail", "")) if isinstance(defaults.get("diagnostics"), dict) else ""
