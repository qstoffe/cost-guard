"""Bounded hosted-only Web Beta evidence. No workstation UI or private artifacts."""
import json
import hashlib
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


def notice(name, value):
    # Structured read-only Checks API evidence as well as downloadable artifacts.
    # This contains allowlisted facts/counts/test names, never raw subprocess logs.
    text = json.dumps(value, separators=(",", ":"), ensure_ascii=True)
    if len(text) > 60000:
        raise ValueError("evidence_notice_too_large")
    print("::notice title=Web Beta " + name + "::" + text.replace("%", "%25"), flush=True)


def facts():
    tools = {}
    commands = {"node": ["node", "--version"], "git": ["git", "--version"]}
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


def main():
    hosted_only()
    phase = sys.argv[1]
    save("platform", facts())
    if phase == "summary":
        notice("platform", facts())
        lines = ["## Web Beta — " + platform.system() + " / " + platform.machine()]
        for name in ("regression", "native", "browser"):
            path = RESULTS / (name + ".json")
            value = json.loads(path.read_text()) if path.exists() else dict(outcome="NOT RUN", reason="phase did not finish")
            notice(name, value)
            lines.append(f"- {name}: **{value['outcome']}** — {value.get('reason', 'see bounded JSON artifact')}")
        lines.append("- **NOT VERIFIED**: physical clicks, visual tray/status bar, Finder/Gatekeeper, default browser, accessibility and consumer desktop behavior.")
        report = RESULTS / "full.json"
        if report.exists():
            files = json.loads(report.read_text())["files"]
            totals = {key: sum(row.get(key) or 0 for row in files) for key in ("tests", "failures", "errors", "skipped")}
            notice("suite", dict(files=len(files), totals=totals,
                failed_files=[row["file"] for row in files if row["exit_code"]]))
            for row in files:
                if row["exit_code"]:
                    notice("failure " + row["file"], dict(exit_code=row["exit_code"], diagnostics=row["diagnostics"]))
                    for test in row["failed_tests"]:
                        notice("failed test", dict(file=row["file"], test=test))
                for skip in row["skips"]:
                    notice("skip", dict(file=row["file"], **skip))
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
            validation = subprocess.run([sys.executable, "development/tools/validate_package.py", "--working-tree"],
                cwd=ROOT, timeout=180, capture_output=True, text=True, encoding="utf-8")
            print(validation.stdout)
            validator = validation.returncode
            value = dict(outcome="FAIL" if suite or validator else "PASS", suite_exit=suite, validator_exit=validator,
                         validator_failures=[line[:512] for line in validation.stdout.splitlines() if line.startswith("FAIL  ")][:8])
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
