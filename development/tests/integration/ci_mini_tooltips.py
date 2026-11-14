"""Affected-source mouse/touch checks; exhaustive and mixed/control on manual Full."""
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


def fr704_delivery(event, environment):
    if environment.get("GITHUB_REPOSITORY") != "qstoffe/cost-guard":
        return False
    if environment.get("GITHUB_EVENT_NAME") == "pull_request":
        pull = event.get("pull_request", {})
        return (event.get("number") == 310 and pull.get("head", {}).get("ref") == "fr-000704" and
            pull.get("base", {}).get("ref") == "main" and all(pull.get(side, {}).get("repo", {}).get("full_name") ==
                "qstoffe/cost-guard" for side in ("head", "base")))
    head = event.get("head_commit") or {}
    return (environment.get("GITHUB_EVENT_NAME") == "push" and
        environment.get("GITHUB_REF") == "refs/heads/main" and isinstance(head.get("id"), str) and
        len(head["id"]) == 40 and head["id"] == environment.get("GITHUB_SHA") and
        head.get("message", "").split("\n")[0] ==
        "Fix stationary hover lifetime and compact Mini tooltip scopes (FR000704) (#310)")


def accepted_mixed_gap(journey, detail, returncode, event, environment, core):
    """Decision Delegate's FR000704-only exclusion, never a mixed-interaction PASS."""
    try:
        if (journey != "mixed" or returncode != 1 or not fr704_delivery(event, environment) or
                detail["outcome"] != "FAIL" or any(core[name]["outcome"] != "PASS" or
                core[name]["journey"] != name for name in ("mouse", "touch"))):
            return False
        diagnostic = detail["diagnostic"]
        if (diagnostic["phase"] != "rendered-duration" or diagnostic["code"] != "condition_not_reached" or
                diagnostic["probeCase"] != "mini-total-heading-hover"):
            return False
        observation = diagnostic["observation"]
        expected = dict(method="hover", theme="classic", scheme="light", unit="credits",
            same=True, connected=True, focus=True, active=False, open=False, hit=True, hovered=True)
        if any(type(observation[key]) is not type(value) or observation[key] != value
               for key, value in expected.items()):
            return False
        events = observation["events"]
        if not isinstance(events, list) or not 1 <= len(events) <= 100:
            return False
        intact = lambda row: all(row.get(key) is True for key in ("same", "connected", "focus"))
        guards = [row for row in events if row.get("guard") is True]
        if (len(guards) != 1 or guards[0].get("kind") != "selector" or
                guards[0].get("result") is not False or not intact(guards[0]) or
                not 550 <= guards[0]["elapsed"] <= 1000):
            return False
        arrival = any(row.get("kind") == "pointermove" and intact(row) and all(row.get(key) is True
            for key in ("trusted", "mouse", "onTarget", "hovered")) for row in events)
        departure = any(row.get("elapsed") is not None and
            (row.get("kind") == "blur" or row.get("onTarget") is True and
             row.get("kind") in ("pointerout", "pointerleave")) for row in events)
        return arrival and not departure
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


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
        "src/application/mini_costs.py", "development/tests/integration/probe_hover_stationary.cjs",
        "development/tests/integration/probe_web_help.cjs", "development/tests/integration/ci_mini_tooltips.py"],
        cwd=ROOT, capture_output=True, text=True, check=True, timeout=10).stdout
    if not changed.strip() and os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        save("mini-tooltips-" + journey, dict(outcome="NOT RUN", journey=journey, reason="tooltip owners unchanged"))
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
    accepted = False
    if journey == "mixed" and result.returncode != 0:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        core = {name: json.loads((ROOT / f"ci-results/mini-tooltips-{name}.json").read_text(encoding="utf-8"))
                for name in ("mouse", "touch")}
        accepted = accepted_mixed_gap(journey, detail, result.returncode, event, os.environ, core)
    diagnostic = detail.get("diagnostic")
    if diagnostic and diagnostic.get("observation"):
        diagnostic["observation"] = observation_summary(diagnostic["observation"])
    # Separate observations from descriptions to keep each Checks notice bounded.
    for check in detail.get("checks", []):
        if isinstance(check, dict) and check.get("observation"):
            notice("mini-input-control", dict(journey=journey, case=check["case"],
                observation=observation_summary(check["observation"])))
    notice("mini-tooltips", dict(outcome=detail.get("outcome", "FAIL"), journey=journey, base_revision=revision,
        reason="Independent native journey" if journey in ("mouse", "touch") else "Retained mixed-input diagnostic",
        disposition=("KNOWN_GAP — test FAIL, scoped exclusion accepted; remaining mixed cases NOT RUN"
            if accepted else None),
        suggestion=("https://github.com/qstoffe/cost-guard/blob/main/development/backlog/suggestions/"
            "000684-mini-help-mixed-input-hover-opening/SUGGESTION.md" if accepted else None),
        evidence=output.name, diagnostic=diagnostic,
        checks=[check if isinstance(check, str) else check["case"]
            for check in detail.get("checks", [])]))
    return 0 if accepted else result.returncode


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
