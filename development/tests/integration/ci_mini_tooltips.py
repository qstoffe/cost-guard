"""Affected-source PR check with a separate bounded real-time PiP budget."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
# Hosted diagnostics confirmed container/checkout ownership differs. Trust only
# this exact disposable checkout for these read-only commands, never globally.
GIT = ["git", "-c", f"safe.directory={ROOT}"]
sys.path.insert(0, str(ROOT))
from development.tools.ci_web_beta import hosted_only, notice, save


def observation_summary(value):
    result = {key: item for key, item in value.items() if key != "events"}
    events = value.get("events", [])
    result["event_count"] = len(events)
    result["guards"] = [event for event in events if event.get("guard")][-4:]
    result["arrivals"] = [event for event in events if event.get("onTarget") and
        event.get("mouse") and event["kind"] in ("pointerenter", "pointermove")][-4:]
    result["departures_after_arrival"] = [event for event in events if
        event.get("elapsed") is not None and
        ((event.get("onTarget") and event["kind"] in ("pointerleave", "pointerout")) or
         event["kind"] == "blur")][-4:]
    return result


def probe(state, journey):
    state["stage"] = "checkout-git-identity"
    identity = subprocess.run([*GIT, "rev-parse", "--show-toplevel"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    if Path(identity).resolve() != ROOT:
        raise ValueError("checkout_identity_mismatch")
    state["stage"] = "affected-source-git-diff"
    changed = subprocess.run([*GIT, "diff", "--name-only", "HEAD^", "HEAD", "--",
        "src/web/assets/help.js", "src/web/assets/mini.js", "src/web/assets/watch.js",
        "src/application/mini_costs.py"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10).stdout
    if not changed.strip():
        save("mini-tooltips", dict(outcome="NOT RUN", reason="tooltip owners unchanged"))
        return 0
    state["stage"] = "image-browser-binding"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.executable_path  # Full image-provided Chromium.
    baseline = ROOT / "ci-results/baseline-help.js"
    revision = subprocess.run([*GIT, "rev-parse", "HEAD^"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    state["stage"] = "baseline-git-show"
    original = subprocess.run([*GIT, "show", "HEAD^:src/web/assets/help.js"],
        cwd=ROOT, capture_output=True, check=True, timeout=10).stdout
    state["stage"] = "baseline-write"
    baseline.write_bytes(original)
    env = dict(os.environ, COST_GUARD_TEST_PYTHON=sys.executable,
        COST_GUARD_CI_BROWSER="1", COST_GUARD_BASELINE_HELP=str(baseline),
        COST_GUARD_BASELINE_REVISION=revision)
    output = ROOT / f"ci-results/mini-tooltips-{journey}.json"
    state["stage"] = "native-pip-" + journey
    result = subprocess.run(["node", "development/tests/integration/probe_web_help.cjs",
        browser, str(output), "--mini-tooltips", journey], cwd=ROOT, env=env,
        timeout=960 if journey == "mouse" else 180)
    detail = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    diagnostic = detail.get("diagnostic")
    if diagnostic and diagnostic.get("observation"):
        diagnostic["observation"] = observation_summary(diagnostic["observation"])
    # Separate observations from descriptions to keep each Checks notice bounded.
    for check in detail.get("checks", []):
        if isinstance(check, dict) and check.get("observation"):
            notice("mini-input-control", dict(journey=journey, case=check["case"],
                observation=observation_summary(check["observation"])))
    notice("mini-tooltips", dict(outcome=detail.get("outcome", "FAIL"), journey=journey,
        reason="Independent native journey" if journey in ("mouse", "touch") else "Retained mixed-input diagnostic",
        evidence=output.name, diagnostic=diagnostic,
        checks=[check if isinstance(check, str) else check["case"]
            for check in detail.get("checks", [])]))
    return result.returncode


def main():
    hosted_only()
    state = {"stage": "start"}
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in ("mouse", "touch", "mixed", "control"):
            raise ValueError("explicit_native_journey_required")
        return probe(state, sys.argv[1])
    except Exception as error:
        # Only these owned local Git/browser-fixture processes run here. Expose
        # bounded stage failures through Checks without requiring raw CI logs.
        detail = dict(outcome="FAIL", stage=state["stage"], exception=type(error).__name__,
            reason="local_probe_setup_failed")
        if isinstance(error, subprocess.CalledProcessError):
            stderr = error.stderr or ""
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            detail.update(returncode=error.returncode, reason=(
                "git_dubious_ownership" if "dubious ownership" in stderr.lower() else
                "git_revision_unavailable" if "unknown revision" in stderr.lower() or
                    "ambiguous argument" in stderr.lower() else "git_command_failed"))
        elif isinstance(error, subprocess.TimeoutExpired):
            detail.update(timeout=error.timeout, reason="owned_process_timeout")
        elif isinstance(error, FileNotFoundError):
            detail["reason"] = "required_runtime_or_file_missing"
        save("mini-tooltips", detail)
        notice("mini-tooltips", detail)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
