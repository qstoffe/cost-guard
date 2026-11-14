"""Affected-source PR check with a separate bounded real-time PiP budget."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from development.tools.ci_web_beta import hosted_only, notice, save


def probe(state):
    state["stage"] = "checkout-git-identity"
    identity = subprocess.run(["git", "rev-parse", "--show-toplevel"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    if Path(identity).resolve() != ROOT:
        raise ValueError("checkout_identity_mismatch")
    state["stage"] = "affected-source-git-diff"
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD^", "HEAD", "--",
        "src/web/assets/help.js", "src/web/assets/mini.js", "src/application/mini_costs.py"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10).stdout
    if not changed.strip():
        save("mini-tooltips", dict(outcome="NOT RUN", reason="tooltip owners unchanged"))
        return 0
    state["stage"] = "image-browser-binding"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.executable_path  # Full image-provided Chromium.
    output = ROOT / "ci-results/mini-tooltips.json"
    baseline = ROOT / "ci-results/baseline-help.js"
    state["stage"] = "baseline-git-show"
    original = subprocess.run(["git", "show", "HEAD^:src/web/assets/help.js"],
        cwd=ROOT, capture_output=True, check=True, timeout=10).stdout
    state["stage"] = "baseline-write"
    baseline.write_bytes(original)
    env = dict(os.environ, COST_GUARD_TEST_PYTHON=sys.executable,
        COST_GUARD_CI_BROWSER="1", COST_GUARD_BASELINE_HELP=str(baseline))
    state["stage"] = "native-pip-probe"
    result = subprocess.run(["node", "development/tests/integration/probe_web_help.cjs",
        browser, str(output), "--mini-tooltips"], cwd=ROOT, env=env, timeout=960)
    detail = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    notice("mini-tooltips", dict(outcome="PASS" if result.returncode == 0 else "FAIL",
        reason="Actual full-Chromium Document PiP, native input and elapsed-time regression",
        evidence="mini-tooltips.json", diagnostic=detail.get("diagnostic"), checks=detail.get("checks", [])))
    return result.returncode


def main():
    hosted_only()
    state = {"stage": "start"}
    try:
        return probe(state)
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
