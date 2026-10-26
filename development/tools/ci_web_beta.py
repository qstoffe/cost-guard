"""Bounded hosted-only Web Beta evidence. No workstation UI or private artifacts."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "ci-results"


def hosted_only():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise SystemExit("Requires a disposable standard GitHub-hosted runner; not authorized on a workstation.")


def save(name, value):
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / (name + ".json")).write_text(json.dumps(value, indent=2), encoding="utf-8")


def run(command, timeout):
    return subprocess.run(command, cwd=ROOT, timeout=timeout, check=False).returncode


def facts():
    tools = {}
    commands = {"node": ["node", "--version"], "git": ["git", "--version"]}
    if sys.platform == "darwin":
        commands.update(sw_vers=["sw_vers"], zsh=["/bin/zsh", "--version"])
    for key, command in commands.items():
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        tools[key] = result.stdout.strip()[:1024]
    return dict(os=platform.system(), build=platform.version(), release=platform.release(),
                architecture=platform.machine(), python=platform.python_version(), tools=tools,
                image=os.environ.get("ImageOS"), image_version=os.environ.get("ImageVersion"),
                runner_arch=os.environ.get("RUNNER_ARCH"), commit=os.environ.get("GITHUB_SHA"))


def main():
    hosted_only()
    phase = sys.argv[1]
    save("platform", facts())
    if phase == "summary":
        lines = ["## Web Beta — " + platform.system() + " / " + platform.machine()]
        for name in ("regression", "native", "browser"):
            path = RESULTS / (name + ".json")
            value = json.loads(path.read_text()) if path.exists() else dict(outcome="NOT RUN", reason="phase did not finish")
            lines.append(f"- {name}: **{value['outcome']}** — {value.get('reason', 'see bounded JSON artifact')}")
        lines.append("- **NOT VERIFIED**: physical clicks, visual tray/status bar, Finder/Gatekeeper, default browser, accessibility and consumer desktop behavior.")
        report = RESULTS / "full.json"
        if report.exists():
            files = json.loads(report.read_text())["files"]
            totals = {key: sum(row.get(key) or 0 for row in files) for key in ("tests", "failures", "errors", "skipped")}
            lines.append(f"- Full suite: {len(files)} files; {totals}. Named skips in full.json.")
        text = "\n".join(lines) + "\n"
        print(text)
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(text)
        return 0
    started = time.monotonic()
    save(phase, dict(outcome="NOT RUN", reason="phase started but has not completed"))
    try:
        if phase == "regression":
            suite = run([sys.executable, "development/tools/run_tests.py", "--suite", "full",
                         "--json-report", "ci-results/full.json"], 900)
            validator = run([sys.executable, "development/tools/validate_package.py", "--working-tree"], 180)
            value = dict(outcome="FAIL" if suite or validator else "PASS", suite_exit=suite, validator_exit=validator)
        elif phase in {"native", "browser"}:
            target = "ci_native_web.py" if phase == "native" else "ci_browser_web.py"
            code = run([sys.executable, "development/tests/integration/" + target], 180)
            value = json.loads((RESULTS / (phase + ".json")).read_text())
            if code:
                value["outcome"] = "FAIL"
        else:
            raise ValueError("unknown phase")
    except Exception as error:
        # No arbitrary exception text, credentials, bootstrap URLs or machine paths.
        value = dict(outcome="FAIL", reason=type(error).__name__)
    value["seconds"] = round(time.monotonic() - started, 2)
    save(phase, value)
    print(json.dumps(value))
    return int(value["outcome"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
