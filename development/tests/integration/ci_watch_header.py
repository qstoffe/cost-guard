"""Hosted synthetic Watch geometry and native Document PiP opening regressions."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from development.tools.ci_web_beta import hosted_only, notice


def header_zooms():
    # Keep the full 576-layout matrix at normal zoom on ordinary delivery.
    # Repeating it at three extra browser zooms is explicit deep verification.
    return ("1", "1.25", "1.5", "2") if os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" else ("1",)


def main():
    hosted_only()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.executable_path
    results = ROOT / "ci-results"
    results.mkdir(exist_ok=True)
    environment = dict(os.environ, COST_GUARD_TEST_PYTHON=sys.executable, COST_GUARD_CI_BROWSER="1")
    for scope in ("opening", "opening-races", "header", "dashboard", "previews"):
        for zoom in (header_zooms() if scope == "header" else ("1",)):
            label = f"watch-{scope}" + (f"-zoom-{zoom}" if zoom != "1" else "")
            output = results / f"{label}.json"
            result = subprocess.run(["node", "development/tests/integration/probe_mini_fit.cjs",
                browser, str(output), "1", zoom, scope + "-only"],
                cwd=ROOT, env=environment, timeout=150, check=False)
            evidence = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
            notice(label, dict(outcome=evidence.get("outcome", "FAIL"), zoom=zoom,
                checks=evidence.get("checks", []), layouts=len(evidence.get("layouts", [])),
                error=evidence.get("error"), phase=evidence.get("phase"),
                diagnostic=evidence.get("diagnostic", dict(returncode=result.returncode)),
                limitations=evidence.get("limitations", [])))
            result.check_returncode()
            if evidence.get("outcome") != "PASS":
                raise SystemExit("Watch evidence did not pass")
    if len(header_zooms()) == 1:
        notice("watch-header-extra-zooms", dict(outcome="NOT RUN", zooms=["1.25", "1.5", "2"],
            reason="Extra browser zoom matrices run on manual Full; ordinary coverage retains 100% zoom."))


if __name__ == "__main__":
    main()
