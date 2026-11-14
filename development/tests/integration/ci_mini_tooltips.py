"""Affected-source PR check with a separate bounded real-time PiP budget."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from development.tools.ci_web_beta import hosted_only, notice, save


def main():
    hosted_only()
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD^", "HEAD", "--",
        "src/web/assets/help.js", "src/web/assets/mini.js", "src/application/mini_costs.py"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10).stdout
    if not changed.strip():
        save("mini-tooltips", dict(outcome="NOT RUN", reason="tooltip owners unchanged"))
        return 0
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.executable_path  # Full image-provided Chromium.
    output = ROOT / "ci-results/mini-tooltips.json"
    baseline = ROOT / "ci-results/baseline-help.js"
    original = subprocess.run(["git", "show", "HEAD^:src/web/assets/help.js"],
        cwd=ROOT, capture_output=True, check=True, timeout=10).stdout
    baseline.write_bytes(original)
    env = dict(os.environ, COST_GUARD_TEST_PYTHON=sys.executable,
        COST_GUARD_CI_BROWSER="1", COST_GUARD_BASELINE_HELP=str(baseline))
    result = subprocess.run(["node", "development/tests/integration/probe_web_help.cjs",
        browser, str(output), "--mini-tooltips"], cwd=ROOT, env=env, timeout=960)
    notice("mini-tooltips", dict(outcome="PASS" if result.returncode == 0 else "FAIL",
        reason="Actual full-Chromium Document PiP, native input and elapsed-time regression",
        evidence="mini-tooltips.json"))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
