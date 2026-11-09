"""Bounded hosted-only Web evidence. No workstation UI or private artifacts."""
import json
import argparse
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "ci-results"
PLANS = {"common": ("regression", "browser"), "native": ("native-regression", "native")}


def hosted_only():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise SystemExit("Requires a disposable standard GitHub-hosted runner; not authorized on a workstation.")


def save(name, value):
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / (name + ".json")).write_text(json.dumps(value, indent=2), encoding="utf-8")


def run(command, timeout):
    return subprocess.run(command, cwd=ROOT, timeout=timeout, check=False).returncode


def observe_preflight(run, record):
    """Observe the actual bounded child call without changing its contract."""
    def observed(*args, **kwargs):
        started = time.monotonic()
        try:
            result = run(*args, **kwargs)
        except (subprocess.TimeoutExpired, OSError) as error:
            outcome = 'TimeoutExpired' if isinstance(error, subprocess.TimeoutExpired) else 'OSError'
            record(dict(outcome=outcome, seconds=round(time.monotonic() - started, 3)))
            raise
        record(dict(outcome='returned', returncode=result.returncode,
                    seconds=round(time.monotonic() - started, 3)))
        return result
    return observed


def notice(name, value):
    # Structured read-only Checks API evidence as well as downloadable artifacts.
    # This contains allowlisted facts/counts/test names, never raw subprocess logs.
    text = json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    if len(text) > 60000:
        raise ValueError("evidence_notice_too_large")
    print("::notice title=Cost Guard Web " + name + "::" + text.replace("%", "%25"), flush=True)


def facts(scope):
    tools = {}
    commands = {"git": ["git", "--version"]}
    if scope == "common":
        commands["node"] = ["node", "--version"]
    if sys.platform == "darwin":
        commands.update(sw_vers=["sw_vers"], zsh=["/bin/zsh", "--version"])
    for key, command in commands.items():
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        tools[key] = result.stdout.strip()[:1024]
    if sys.platform == "darwin":
        tools["osacompile_sha256"] = hashlib.sha256(Path("/usr/bin/osacompile").read_bytes()).hexdigest()
    return dict(os=platform.system(), build=platform.version(), release=platform.release(),
                architecture=platform.machine(), python=platform.python_version(), tools=tools,
                image=os.environ.get("ImageOS"), image_version=os.environ.get("ImageVersion"),
                runner_arch=os.environ.get("RUNNER_ARCH"), commit=os.environ.get("GITHUB_SHA"))


def summary(scope):
    plan = PLANS[scope]
    notice("platform", facts(scope))
    lines = ["## Cost Guard Web — " + scope + " / " + platform.system() + " / " + platform.machine()]
    success = os.environ.get("CI_JOB_STATUS", "success") == "success"
    for name in plan:
        path = RESULTS / (name + ".json")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or value.get("outcome") not in {"PASS", "FAIL", "BLOCKED", "SKIPPED", "NOT RUN"}:
                raise ValueError("invalid phase evidence")
        except FileNotFoundError:
            value = dict(outcome="NOT RUN", reason="expected phase did not finish")
        except (ValueError, OSError, TypeError):
            value = dict(outcome="FAIL", reason="malformed or unreadable phase evidence")
        success = success and value["outcome"] == "PASS"
        notice(name, value)
        lines.append(f"- {name}: **{value['outcome']}** — {value.get('reason', 'see bounded JSON artifact')}")
    elsewhere = PLANS["native" if scope == "common" else "common"]
    lines.append("- Assigned elsewhere (not executed here): " + ", ".join(elsewhere))
    lines.append("- **NOT VERIFIED**: physical clicks, visual tray/status bar, Finder/Gatekeeper, default-browser page rendering, accessibility and consumer desktop behavior.")
    try:
        suite_ok, description = suite_summary(scope)
        success = success and suite_ok
        lines.append(description)
    except (OSError, ValueError, KeyError, TypeError):
        success = False
        lines.append("- **FAIL**: required suite report missing, incomplete or malformed.")
    lines.append("- Prior job status: " + os.environ.get("CI_JOB_STATUS", "success"))
    text = "\n".join(lines) + "\n"
    print(text)
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
        stream.write(text)
    save("summary", dict(scope=scope, expected=list(plan), outcome="PASS" if success else "FAIL"))
    return int(not success)


def suite_summary(scope):
    sys.path.insert(0, str(ROOT))
    from development.tools import run_tests
    report = RESULTS / ("full.json" if scope == "common" else "native-tests.json")
    files = json.loads(report.read_text(encoding="utf-8"))["files"]
    expected = (run_tests.FULL_ONLY_PATTERNS + run_tests.QUICK_PATTERNS if scope == "common"
                else run_tests.NATIVE_WEB_PATTERNS[sys.platform])
    if [row["file"] for row in files] != list(expected):
        raise ValueError("incomplete selection evidence")
    totals = {key: sum(row.get(key) or 0 for row in files) for key in ("tests", "passed", "failures", "errors", "skipped")}
    complete = all(row["passed"] is not None and row["tests"] and not row["exit_code"] for row in files)
    notice("suite", dict(files=len(files), totals=totals, passed_count_complete=bool(complete),
        failed_files=[row["file"] for row in files if row["exit_code"]]))
    for row in files:
        if row["exit_code"]:
            notice("failure " + row["file"], dict(exit_code=row["exit_code"], diagnostics=row["diagnostics"]))
            for test in row["failed_tests"]:
                notice("failed test", dict(file=row["file"], test=test))
    # Checks annotations can be capped upstream. Preserve actionable failures
    # before the much larger platform-skip inventory, without omitting either.
    for row in files:
        for skip in row["skips"]:
            notice("skip", dict(file=row["file"], **skip))
    return bool(complete), f"- Selected suite: {len(files)} files/case groups; {totals}. Named skips in {report.name}."


def main(argv=None):
    hosted_only()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("regression", "native-regression", "native", "browser", "summary"))
    parser.add_argument("--scope", choices=tuple(PLANS), required=True)
    args = parser.parse_args(argv)
    phase = args.phase
    if phase != "summary" and phase not in PLANS[args.scope]:
        parser.error("phase not assigned to job scope")
    save("platform", facts(args.scope))
    if phase == "summary":
        return summary(args.scope)
    started = time.monotonic()
    save(phase, dict(outcome="NOT RUN", reason="phase started but has not completed"))
    try:
        if phase == "regression":
            # Hosted Windows shell startup is contended by concurrent launcher
            # fixtures. Preserve all tests/deadlines; remove only cross-file load.
            jobs = "1" if sys.platform == "win32" else "4"
            suite = run([sys.executable, "development/tools/run_tests.py", "--suite", "full",
                         "--jobs", jobs, "--json-report", "ci-results/full.json"], 900)
            validation = subprocess.run([sys.executable, "development/tools/validate_package.py", "--working-tree"],
                cwd=ROOT, timeout=180, capture_output=True, text=True, encoding="utf-8")
            print(validation.stdout)
            validator = validation.returncode
            value = dict(outcome="FAIL" if suite or validator else "PASS", suite_exit=suite, validator_exit=validator,
                         validator_failures=[line[:512] for line in validation.stdout.splitlines() if line.startswith("FAIL  ")][:8])
        elif phase == "native-regression":
            code = run([sys.executable, "development/tools/run_tests.py", "--suite", "full",
                        "--profile", "native-web", "--jobs", "1", "--json-report", "ci-results/native-tests.json"], 300)
            value = dict(outcome="FAIL" if code else "PASS", suite_exit=code, profile="native-web")
        elif phase in {"native", "browser"}:
            target = "ci_native_web.py" if phase == "native" else "ci_browser_web.py"
            code = run([sys.executable, "development/tests/integration/" + target], 180)
            value = json.loads((RESULTS / (phase + ".json")).read_text())
            if code and value["outcome"] not in {"BLOCKED", "SKIPPED"}:
                value["outcome"] = "FAIL"
        else:
            raise ValueError("unknown phase")
    except Exception as error:
        # No arbitrary exception text, credentials, bootstrap URLs or machine paths.
        value = dict(outcome="FAIL", reason=type(error).__name__)
    value["seconds"] = round(time.monotonic() - started, 2)
    save(phase, value)
    print(json.dumps(value))
    return int(value["outcome"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
