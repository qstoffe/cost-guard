"""CI evidence accounting and fail-closed workstation UI boundary; no UI invocation."""
import contextlib
import argparse
import io
import json
from pathlib import Path
import re
import shlex
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from development.tools import ci_web_beta, run_tests


class CiEvidenceTests(unittest.TestCase):
    def test_workflow_assigns_shared_work_once_without_native_browser_tools(self):
        workflow = (ci_web_beta.ROOT / ".github/workflows/web-beta.yml").read_text()
        equivalent = workflow.replace('common:', 'shared-checks:').replace('native:', 'platform-checks:')
        equivalent = equivalent.replace('[windows-2025, macos-15, macos-15-intel]',
                                        '[macos-15-intel, windows-2025, macos-15]')
        equivalent = re.sub(r'(ci_web_beta.py) (\S+) --scope (\S+)', r'\1 --scope=\3 \2', equivalent)
        equivalent = re.sub(r'(?m)^( +)', lambda match: match[0] * 2, equivalent)
        for text in (workflow, equivalent):
            self.assert_workflow_topology(text)
        for broken in (workflow.replace('native-regression --scope native', 'regression --scope common'),
                       workflow.replace('cancel-in-progress: true', 'cancel-in-progress: false'),
                       workflow.replace('os: [windows-2025, macos-15, macos-15-intel]', 'os: [windows-2025]')):
            with self.assertRaises(AssertionError):
                self.assert_workflow_topology(broken)

    def assert_workflow_topology(self, workflow):
        # A narrow static topology guard is useful here. Ignore indentation width,
        # matrix order, flag spelling/order, step names and job-local identifiers.
        jobs = workflow.split('jobs:', 1)[1]
        indent = min(len(line) - len(line.lstrip()) for line in jobs.splitlines()
                     if line.strip() and not line.lstrip().startswith('#'))
        blocks = re.split(r'(?m)^ {' + str(indent) + r'}[\w-]+:\s*$', jobs)[1:]
        self.assertEqual(2, len(blocks))
        common = next(block for block in blocks if re.search(r'runs-on:\s*[\'\"]?ubuntu-', block))
        native = next(block for block in blocks if re.search(r'matrix\s*:', block))
        commands = []
        for block, scope in ((common, 'common'), (native, 'native')):
            for line in block.splitlines():
                if 'run:' not in line or 'ci_web_beta.py' not in line:
                    continue
                tokens = shlex.split(line.split('run:', 1)[1].strip().strip('\'\"'))
                parser = argparse.ArgumentParser()
                parser.add_argument('phase')
                parser.add_argument('--scope')
                command = parser.parse_args(tokens[tokens.index('development/tools/ci_web_beta.py') + 1:])
                self.assertEqual(scope, command.scope)
                commands.append((scope, command.phase))
            self.assertRegex(block, r'CI_JOB_STATUS:\s*[\'\"]?\$\{\{\s*job\.status\s*\}\}')
        self.assertCountEqual([('common', phase) for phase in ('regression', 'browser', 'summary')] +
                              [('native', phase) for phase in ('native-regression', 'native', 'summary')], commands)
        for forbidden in ('setup-node', 'playwright', 'validate_package', '--suite full'):
            self.assertNotIn(forbidden, native)
        self.assertLessEqual(int(re.search(r'max-parallel:\s*(\d+)', native)[1]), 2)
        self.assertEqual({'windows-2025', 'macos-15', 'macos-15-intel'},
                         set(re.findall(r'windows-\d+|macos-[\d]+(?:-intel)?', native)))
        self.assertRegex(common, r'playwright\s+install\s+--with-deps\s+chromium')
        self.assertRegex(workflow, r'cancel-in-progress:\s*true\b')

    def test_native_facts_never_discover_node(self):
        with patch.object(ci_web_beta.subprocess, "run", return_value=SimpleNamespace(stdout="version")) as run, \
                patch("sys.platform", "win32"):
            result = ci_web_beta.facts("native")
        self.assertNotIn("node", result["tools"])
        self.assertEqual([["git", "--version"]], [call.args[0] for call in run.call_args_list])

    def test_native_profile_is_focused_and_named_cases_execute_directly(self):
        windows = run_tests.NATIVE_WEB_PATTERNS["win32"]
        self.assertEqual(("test_windows_web.py", "test_windows_web_activity.py"), windows[:2])
        self.assertEqual(("test_windows_clipboard.py", "test_web_browser_links.py"), windows[2:4])
        self.assertEqual(14, len(windows))
        self.assertEqual(3, len(run_tests.NATIVE_WEB_PATTERNS["darwin"]))
        self.assertNotIn("test_web_lifecycle.py", windows)
        selector = "test_web_lifecycle.LifecycleTests.test_windows_held_lifetime_file_cannot_be_deleted_or_replaced"
        self.assertIn(selector, windows)
        with patch.object(run_tests.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")) as run:
            run_tests._run_pattern(selector, timeout=240, verbosity=2)
        self.assertEqual([run_tests.sys.executable, "-m", "unittest", "development.tests." + selector, "-v"], run.call_args.args[0])

    def test_native_phase_runs_profile_without_validator(self):
        with patch.object(ci_web_beta, "hosted_only"), patch.object(ci_web_beta, "facts", return_value={}), \
                patch.object(ci_web_beta, "save"), patch.object(ci_web_beta, "run", return_value=0) as run, \
                patch.object(ci_web_beta.subprocess, "run") as validator, contextlib.redirect_stdout(io.StringIO()):
            result = ci_web_beta.main(["native-regression", "--scope", "native"])
        self.assertEqual(0, result)
        run.assert_called_once_with([ci_web_beta.sys.executable, "development/tools/run_tests.py", "--suite", "full",
            "--profile", "native-web", "--jobs", "1", "--json-report", "ci-results/native-tests.json"], 300)
        validator.assert_not_called()

    def test_phase_cannot_run_under_wrong_scope(self):
        with patch.object(ci_web_beta, "hosted_only"), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                ci_web_beta.main(["regression", "--scope", "native"])

    def test_scoped_summary_requires_expected_phases_and_complete_suite(self):
        cases = [("PASS", 0), ("FAIL", 1), ("BLOCKED", 1), ("SKIPPED", 1), ("NOT RUN", 1),
                 (None, 1), ("malformed", 1), ("[]", 1), ('{"outcome":[]}', 1)]
        for scope in ("common", "native"):
            for outcome, expected_exit in cases:
                with self.subTest(scope=scope, outcome=outcome), tempfile.TemporaryDirectory() as temporary:
                    results = Path(temporary)
                    for phase in ci_web_beta.PLANS[scope]:
                        (results / (phase + ".json")).write_text(json.dumps(dict(outcome="PASS")))
                    required = results / (ci_web_beta.PLANS[scope][-1] + ".json")
                    if outcome is None:
                        required.unlink()
                    elif outcome in ("malformed", "[]", '{"outcome":[]}'):
                        required.write_text(outcome)
                    else:
                        required.write_text(json.dumps(dict(outcome=outcome)))
                    # Unassigned phase failures must not pollute a narrower job.
                    for other in ci_web_beta.PLANS["native" if scope == "common" else "common"]:
                        (results / (other + ".json")).write_text('{"outcome":"FAIL"}')
                    with patch.object(ci_web_beta, "RESULTS", results), patch.object(ci_web_beta, "facts", return_value={}), \
                            patch.object(ci_web_beta, "suite_summary", return_value=(True, "suite counts")), \
                            patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(results / "summary.md"), "CI_JOB_STATUS": "success"}), \
                            contextlib.redirect_stdout(io.StringIO()):
                        result = ci_web_beta.summary(scope)
                    self.assertEqual(expected_exit, result)
                    report = json.loads((results / "summary.json").read_text())
                    self.assertEqual(list(ci_web_beta.PLANS[scope]), report["expected"])
                    self.assertIn("Assigned elsewhere", (results / "summary.md").read_text(encoding="utf-8"))

    def test_summary_fails_closed_for_cancelled_failed_job_and_bad_suite(self):
        for status, suite in (("cancelled", True), ("failure", True), ("success", False), ("success", ValueError())):
            with self.subTest(status=status, suite=suite), tempfile.TemporaryDirectory() as temporary:
                results = Path(temporary)
                for phase in ci_web_beta.PLANS["common"]:
                    (results / (phase + ".json")).write_text('{"outcome":"PASS"}')
                with patch.object(ci_web_beta, "RESULTS", results), patch.object(ci_web_beta, "facts", return_value={}), \
                        patch.object(ci_web_beta, "suite_summary", side_effect=suite if isinstance(suite, Exception) else None,
                                     return_value=(suite, "suite status")), \
                        patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(results / "summary.md"), "CI_JOB_STATUS": status}), \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(1, ci_web_beta.summary("common"))

    def test_suite_report_cannot_lose_selected_files_or_counts(self):
        for scope in ("common", "native"):
            expected = (run_tests.FULL_ONLY_PATTERNS + run_tests.QUICK_PATTERNS if scope == "common"
                        else run_tests.NATIVE_WEB_PATTERNS["win32"])
            rows = [dict(file=name, tests=1, passed=1, exit_code=0, skips=[]) for name in expected]
            for mutation in ("none", "drop", "empty", "null", "missing-count", "missing-report"):
                with self.subTest(scope=scope, mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                    results = Path(temporary)
                    altered = [dict(row) for row in rows]
                    if mutation == "drop":
                        altered.pop()
                    if mutation == "empty":
                        altered = []
                    if mutation == "missing-count":
                        altered[0]["passed"] = None
                    report = results / ("full.json" if scope == "common" else "native-tests.json")
                    if mutation != "missing-report":
                        report.write_text(json.dumps(dict(files=None if mutation == "null" else altered)))
                    with patch.object(ci_web_beta, "RESULTS", results), patch("sys.platform", "win32"), \
                            contextlib.redirect_stdout(io.StringIO()):
                        if mutation in ("drop", "empty", "null", "missing-report"):
                            with self.assertRaises((ValueError, TypeError, OSError)):
                                ci_web_beta.suite_summary(scope)
                        else:
                            success, _ = ci_web_beta.suite_summary(scope)
                            self.assertEqual(mutation == "none", success)

    def test_suite_notices_prioritize_late_failures_before_earlier_skips(self):
        rows = [dict(file="test_skip.py", tests=30, passed=0, exit_code=0,
                     skips=[dict(test=f"test_platform_{i}", reason="other platform") for i in range(30)]),
                dict(file="test_late.py", tests=1, passed=None, exit_code=1, skips=[],
                     failed_tests=["test_late (example.Tests.test_late)"],
                     diagnostics=["AssertionError: bounded UI condition timed out"])]
        with tempfile.TemporaryDirectory() as temporary:
            results = Path(temporary)
            (results / "full.json").write_text(json.dumps(dict(files=rows)))
            with patch.object(ci_web_beta, "RESULTS", results), \
                    patch.object(run_tests, "FULL_ONLY_PATTERNS", ()), \
                    patch.object(run_tests, "QUICK_PATTERNS", ("test_skip.py", "test_late.py")), \
                    patch.object(ci_web_beta, "notice") as notice:
                success, _ = ci_web_beta.suite_summary("common")
        self.assertFalse(success)
        self.assertEqual(["suite", "failure test_late.py", "failed test"],
                         [call.args[0] for call in notice.call_args_list[:3]])
        self.assertEqual(dict(exit_code=1, diagnostics=["AssertionError: bounded UI condition timed out"]),
                         notice.call_args_list[1].args[1])
        self.assertEqual(30, sum(call.args[0] == "skip" for call in notice.call_args_list))

    def test_registered_browser_boundaries_preserve_url_and_return_failure_truthfully(self):
        from src.web import native_windows, native_macos
        url = "http://127.0.0.1:1234/#bootstrap=synthetic"
        with patch.object(native_windows.os, "startfile", create=True) as start:
            self.assertTrue(native_windows.open_registered_browser(url))
        start.assert_called_once_with(url)
        with patch.object(native_windows.os, "startfile", side_effect=OSError(), create=True):
            with self.assertRaises(OSError):
                native_windows.open_registered_browser(url)
        for code in (0, 1):
            with patch.object(native_macos.subprocess, "run", return_value=SimpleNamespace(returncode=code)) as run:
                self.assertEqual(code == 0, native_macos.open_registered_browser(url))
            self.assertEqual(["/usr/bin/open", url], run.call_args.args[0])
            self.assertEqual(5, run.call_args.kwargs["timeout"])

    def test_regression_workers_preserve_full_suite_and_deadlines(self):
        for platform, jobs in (("win32", "1"), ("darwin", "4"), ("linux", "4")):
            with self.subTest(platform=platform), \
                    patch.object(ci_web_beta, "hosted_only"), \
                    patch.object(ci_web_beta, "facts", return_value={}), \
                    patch.object(ci_web_beta, "save"), \
                    patch.object(ci_web_beta, "run", return_value=0) as suite, \
                    patch.object(ci_web_beta.subprocess, "run") as validator, \
                    patch("sys.platform", platform), \
                    patch("sys.argv", ["ci", "regression", "--scope", "common"]), \
                    contextlib.redirect_stdout(io.StringIO()):
                validator.return_value.returncode = 0
                validator.return_value.stdout = "PASS"

                result = ci_web_beta.main()

                self.assertEqual(0, result)
                suite.assert_called_once_with(
                    [ci_web_beta.sys.executable, "development/tools/run_tests.py", "--suite", "full",
                     "--jobs", jobs, "--json-report", "ci-results/full.json"], 900)
                self.assertEqual(180, validator.call_args.kwargs["timeout"])

    def test_workstation_cannot_enter_hosted_probe(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(SystemExit, "not authorized on a workstation"):
                ci_web_beta.hosted_only()

    def test_native_command_failure_keeps_only_allowlisted_lifecycle_codes(self):
        from development.tests.integration.ci_native_web import command_failure

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'lifecycle.log').write_text(
                '1 starting\n2 private-source-value\n3 tray_unavailable\n4 instance_conflict\n', encoding='ascii')
            result = SimpleNamespace(returncode=1, stderr=b'private traceback/path\nInstanceConflict: instance_start_timeout\n')

            evidence = command_failure(result, SimpleNamespace(directory=directory))

        self.assertEqual(dict(returncode=1, lifecycle_errors=['tray_unavailable', 'instance_conflict'],
                              error_code='instance_start_timeout'), evidence)

    def test_preflight_observer_preserves_call_deadline_result_and_exceptions(self):
        from unittest.mock import Mock

        command = ['python', 'entry.py', '--preflight-macos']
        result = SimpleNamespace(returncode=3)
        timeout = ci_web_beta.subprocess.TimeoutExpired(command, 10, output='private-output')
        unavailable = OSError('private-path')
        for outcome in (result, timeout, unavailable, FileNotFoundError('private-executable')):
            with self.subTest(outcome=type(outcome).__name__):
                run = Mock(return_value=outcome if outcome is result else None,
                           side_effect=outcome if isinstance(outcome, Exception) else None)
                records = []
                observed = ci_web_beta.observe_preflight(run, records.append)

                with patch.object(ci_web_beta.time, 'monotonic', side_effect=[1, 11.125]):
                    if isinstance(outcome, Exception):
                        with self.assertRaises(type(outcome)) as raised:
                            observed(command, timeout=10, stdin=-3, stdout=-3, stderr=-3, check=False)
                        self.assertIs(outcome, raised.exception)
                    else:
                        self.assertIs(result, observed(command, timeout=10, stdin=-3, stdout=-3, stderr=-3, check=False))

                run.assert_called_once_with(command, timeout=10, stdin=-3, stdout=-3, stderr=-3, check=False)
                classification = 'TimeoutExpired' if isinstance(outcome, ci_web_beta.subprocess.TimeoutExpired) else 'OSError'
                expected = dict(outcome=classification, seconds=10.125)
                if outcome is result:
                    expected = dict(outcome='returned', returncode=3, seconds=10.125)
                self.assertEqual([expected], records)

    def test_synthetic_sessions_fixture_captures_and_joins_without_watch_publication(self):
        import shutil
        from development.tests.fixtures.web_reports import SyntheticSessionsRuntime

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "config").mkdir()
            shutil.copyfile(ci_web_beta.ROOT / "config/default-config.jsonc", root / "config/default-config.jsonc")
            runtime = SyntheticSessionsRuntime(root, clock_ms=lambda: 123_456_789)
            token = runtime.details.open("root", "live")
            runtime.start()
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    captured = runtime.details.page(token, 0, begin=True)
                    if captured["result"]:
                        break
                    runtime.stopping.wait(.01)
                self.assertIsNotNone(captured["result"])
                self.assertEqual(123_456_789, captured['result']['observed_at_ms'])
                self.assertEqual('<script>PRIVATE_TEXT</script>', captured["result"]["view"]["prompt_blocks"][0]["title"])
            finally:
                runtime.close()
            self.assertFalse(runtime.thread.is_alive())

    def test_browser_report_fixture_uses_acquisition_clock_without_changing_fixed_clock_default(self):
        from unittest.mock import Mock
        from development.tests.fixtures.web_reports import current_report, finite_report
        from src.reports import ReportRequest

        fixed, current = Mock(), Mock()
        finite_report(fixed, ReportRequest())
        with patch('development.tests.fixtures.web_reports.time.time', return_value=8_000_000):
            current_report(current, ReportRequest())

        fixed_result = json.loads(fixed.send.call_args.args[0][1])
        current_result = json.loads(current.send.call_args.args[0][1])
        self.assertIsNone(current_result['error'])
        self.assertEqual(4000, fixed_result['source']['observed_at_ms'])
        self.assertEqual(8_000_000_000, current_result['source']['observed_at_ms'])
        self.assertEqual(8_000_000_000, current_result['observed_at_ms'])

    def test_provisioning_blocked_is_not_relabelled_as_test_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            results = Path(temporary)
            (results / "browser.json").write_text(json.dumps(dict(outcome="BLOCKED", reason="tool unavailable")))
            with patch.object(ci_web_beta, "RESULTS", results), patch.object(ci_web_beta, "hosted_only"), \
                    patch.object(ci_web_beta, "facts", return_value={}), patch.object(ci_web_beta, "save"), \
                    patch.object(ci_web_beta, "run", return_value=1), patch("sys.argv", ["ci", "browser", "--scope", "common"]), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                result = ci_web_beta.main()
        self.assertEqual(1, result)
        self.assertEqual("BLOCKED", json.loads(output.getvalue())["outcome"])

    def test_report_preserves_named_skips_failures_and_missing_counts(self):
        outputs = [
            ("test_a.py", 0, 0.1, "test_a (example.Tests.test_a) ... ok\ntest_b (example.Tests.test_b) ... skipped 'Windows only'\nRan 2 tests in 0.1s\n\nOK (skipped=1)"),
            ("test_b.py", 1, 0.1, "AssertionError: C:\\Users\\synthetic\\file http://127.0.0.1/#bootstrap=secret\nRan 3 tests in 0.1s\n\nFAILED (failures=1, errors=1, skipped=1)"),
            ("test_c.py", 124, 1, "subprocess.TimeoutExpired: Command ['private-token', 'C:\\Users\\synthetic\\file'] timed out after 20 seconds\nTIMEOUT after 1s"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            with patch.object(run_tests, "QUICK_PATTERNS", tuple(row[0] for row in outputs)), \
                    patch.object(run_tests, "_run_pattern", side_effect=outputs), contextlib.redirect_stdout(io.StringIO()):
                result = run_tests.main(["--jobs", "1", "--json-report", str(path)])
            report = json.loads(path.read_text())["files"]
        self.assertEqual(1, result)
        self.assertEqual(1, report[0]["skipped"])
        self.assertEqual(1, report[0]["passed"])
        self.assertEqual("'Windows only'", report[0]["skips"][0]["reason"])
        self.assertEqual(1, report[1]["failures"])
        self.assertEqual(1, report[1]["errors"])
        self.assertIsNone(report[1]["passed"])
        self.assertEqual(["AssertionError: <path> <url>"], report[1]["diagnostics"])
        self.assertIsNone(report[2]["tests"])
        self.assertEqual("FAIL", report[2]["outcome"])
        self.assertEqual(["subprocess.TimeoutExpired: child deadline exceeded"], report[2]["diagnostics"])


if __name__ == "__main__":
    unittest.main()
