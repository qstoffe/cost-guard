"""Deterministic process/worker software-fault architecture and privacy gates."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

from src import runtime_errors as errors
from src.accounts.claude_transport import _ControlReader, ClaudeReaderFault
from src.presentation.progress import StartupProgress
from src.sources.errors import SourceUnavailableError
from src.watch.observers import LiveEventPump

ROOT = Path(__file__).resolve().parents[2]
ENTRY = runpy.run_path(str(ROOT / "cost-guard.py"))


def fail(kind=TypeError):
    private_local = "PRIVATE-LOCAL"
    raise kind("SECRET payload prompt auth@example.invalid " + private_local)


class RuntimeErrorTests(unittest.TestCase):
    def setUp(self):
        scratch = os.environ.get("OPENCODE_TOOLKIT_SESSION_SCRATCH")
        if scratch:
            Path(scratch).mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)
        self.output = io.StringIO()
        self.reporter = errors.RuntimeErrors(self.root, mode="test", stream=self.output)

    def tearDown(self):
        if errors._active is self.reporter:
            self.reporter.uninstall()
        self.temp.cleanup()

    def logs(self):
        return list((self.root / "logs/errors").glob("*.log"))

    def crashes(self):
        return list((self.root / "logs/crashes").glob("*.txt"))

    def logged(self):
        return "\n".join(path.read_text(encoding="utf-8") for path in self.logs())

    def test_healthy_startup_does_not_create_diagnostics(self):
        self.assertEqual(0, self.reporter.run(lambda: 0))
        self.assertFalse((self.root / "diagnostics").exists())

    def test_unhandled_exception_families_are_fatal_sanitized_and_unique(self):
        for kind in (TypeError, AttributeError, KeyError, IndexError, AssertionError, RuntimeError, OSError,
                     ImportError, ModuleNotFoundError, SyntaxError, SystemExit):
            with self.subTest(kind=kind):
                self.assertEqual(1, self.reporter.run(lambda: fail(kind)))
        self.assertEqual(1, len(self.logs()))
        self.assertEqual(11, len(self.crashes()))
        text = self.logged() + "\n".join(p.read_text() for p in self.crashes())
        for private in ("SECRET", "PRIVATE-LOCAL", "auth@example.invalid"):
            self.assertNotIn(private, text)
        for field in ("Cost Guard: v80.", "Python:", "OS:", "PID:", "Fingerprint:", "Error log:", "Crash report:"):
            self.assertIn(field, text)
        self.assertIn("in fail", text)
        self.assertIn("Traceback (most recent call last)", text)
        self.assertIn("COST GUARD FAILED", self.output.getvalue())
        self.assertNotIn("Traceback", self.output.getvalue())

    def test_entry_import_failure_owned_before_bootstrap(self):
        real_import = __import__
        def importing(name, *args, **kwargs):
            if name == "src.bootstrap":
                fail(ImportError)
            return real_import(name, *args, **kwargs)
        with patch("src.runtime_errors.RuntimeErrors", return_value=self.reporter), patch("builtins.__import__", side_effect=importing):
            self.assertEqual(1, ENTRY["run"]())
        self.assertEqual(1, len(self.crashes()))
        self.assertIn("Unhandled ImportError", self.output.getvalue())

    def test_minimal_boundary_import_failure_emergency(self):
        real_import = __import__
        def importing(name, *args, **kwargs):
            if name == "src.runtime_errors":
                fail(SyntaxError)
            return real_import(name, *args, **kwargs)
        with redirect_stderr(self.output), patch("builtins.__import__", side_effect=importing):
            self.assertEqual(1, ENTRY["run"]())
        self.assertIn("COST GUARD FAILED", self.output.getvalue())
        self.assertNotIn("SECRET", self.output.getvalue())

    def test_intentional_interrupt_and_expected_cli_config_are_not_software_errors(self):
        self.assertEqual(130, self.reporter.run(lambda: fail(KeyboardInterrupt)))
        from src.bootstrap import main
        from src.config import ConfigError
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(2, self.reporter.run(lambda: main(["--not-a-command"])))
            self.assertEqual(0, self.reporter.run(lambda: main(["--help"])))
            with patch("src.bootstrap.load_configuration", side_effect=ConfigError("Invalid config")):
                self.assertEqual(1, self.reporter.run(lambda: main([])))
        self.assertFalse(self.logs())
        self.assertFalse(self.crashes())

    def test_repetition_deduplicated_recovery_change_and_exit_summarized(self):
        self.reporter.install()
        def incident(kind=TypeError, component="poller"):
            try:
                fail(kind)
            except Exception as exc:
                errors.recoverable(exc, component)
        for _ in range(24):
            incident()
        self.assertEqual(1, self.logged().count("Traceback"))
        errors.recovered("poller")
        self.assertIn("Repeated 23 additional times", self.logged())
        self.assertIn("Component later recovered", self.logged())
        incident()
        incident(AttributeError)
        incident(component="other")
        self.reporter.flush()
        self.assertEqual(4, self.logged().count("Traceback"))
        self.assertIn("Failure changed", self.logged())

    def test_bounded_flush_preserves_repeat_total_without_traceback_spam(self):
        try:
            fail()
        except Exception as exc:
            with patch("src.runtime_errors.time.monotonic", return_value=0):
                self.reporter.recoverable(exc, "poller")
            with patch("src.runtime_errors.time.monotonic", return_value=61):
                self.reporter.recoverable(exc, "poller")
        self.assertIn("Repeated 1 additional times", self.logged())
        self.assertEqual(1, self.logged().count("Traceback"))

    def test_reporter_io_formatter_and_terminal_failures_preserve_original(self):
        for seam in ("_append", "_details", "_stack"):
            with self.subTest(seam=seam), patch.object(self.reporter, seam, side_effect=PermissionError("SECRET")):
                self.assertEqual(1, self.reporter.run(fail))
                self.assertIn("Unhandled TypeError", self.output.getvalue())
                self.assertIn("could not be written: PermissionError", self.output.getvalue())
        with patch.object(Path, "open", side_effect=PermissionError):
            self.assertEqual(1, self.reporter.run(fail))
        with patch.object(Path, "mkdir", side_effect=PermissionError):
            self.assertEqual(1, self.reporter.run(fail))
        broken = Mock()
        broken.write.side_effect = RuntimeError
        self.reporter.stream = broken
        with patch("src.runtime_errors.os.write") as sink:
            self.assertEqual(1, self.reporter.run(fail))
            self.assertIn(b"Unhandled TypeError", sink.call_args.args[1])

    def test_unclassified_real_thread_is_fatal_without_default_thread_traceback(self):
        def application():
            worker = threading.Thread(target=fail, name="synthetic-unclassified")
            worker.start()
            worker.join(timeout=2)
            errors.check_pending()
            return 0
        with redirect_stderr(io.StringIO()) as default:
            self.assertEqual(1, self.reporter.run(application))
        self.assertNotIn("Exception in thread", default.getvalue())
        self.assertEqual(1, len(self.crashes()))
        self.assertIn("Execution root: thread#", self.logged())

    def test_unraisable_is_sanitized_and_fatal_without_recursion(self):
        def application():
            try:
                fail()
            except Exception as exc:
                sys.unraisablehook(SimpleNamespace(exc_value=exc, exc_traceback=exc.__traceback__,
                                                   object="SECRET", err_msg="SECRET"))
            return 0
        self.assertEqual(1, self.reporter.run(application))
        self.assertEqual(1, len(self.crashes()))
        self.assertIn("unraisable", self.logged())
        self.assertNotIn("SECRET", self.logged())

    def test_chained_and_grouped_stacks_never_format_exception_payloads(self):
        class UnsafeMessage(Exception):
            def __str__(self):
                raise AssertionError("Do not format private payloads")
        def application():
            try:
                fail(UnsafeMessage)
            except Exception as first:
                raise ExceptionGroup("SECRET", [first, TypeError("SECRET")]) from first
        self.assertEqual(1, self.reporter.run(application))
        self.assertIn("UnsafeMessage", self.logged())
        self.assertIn("Chained exception", self.logged())
        self.assertNotIn("SECRET", self.logged())

    def test_recoverable_reporter_failure_escalates_original_not_reporting_error(self):
        def application():
            try:
                fail(TypeError)
            except Exception as exc:
                errors.recoverable(exc, "isolated")
            return 0
        with patch.object(self.reporter, "_append", side_effect=PermissionError):
            self.assertEqual(1, self.reporter.run(application))
        self.assertIn("Unhandled TypeError", self.output.getvalue())
        self.assertNotIn("Unhandled PermissionError", self.output.getvalue())

    def test_boundary_hook_installation_failure_is_owned(self):
        with patch.object(self.reporter, "install", side_effect=AttributeError):
            self.assertEqual(1, self.reporter.run(lambda: 0))
        self.assertEqual(1, len(self.crashes()))

    def test_sys_hook_and_hooks_restore(self):
        original = (sys.excepthook, threading.excepthook, sys.unraisablehook)
        self.reporter.install()
        try:
            fail()
        except Exception as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)
        self.reporter.uninstall()
        self.assertEqual(original, (sys.excepthook, threading.excepthook, sys.unraisablehook))
        self.assertEqual(1, len(self.crashes()))

    def test_progress_worker_isolated_visible_and_valid_report_can_continue(self):
        progress = StartupProgress(self.output, interactive=True, animate=False)
        progress._active = True
        with patch.object(progress, "_animate", side_effect=TypeError("SECRET")):
            self.assertEqual(0, self.reporter.run(lambda: (progress._animation_root(), progress.update("later"), progress.stop(), 0)[-1]))
        self.assertIn("ERROR: Startup animation", self.output.getvalue())
        self.assertFalse(progress.interactive)
        self.assertIn("Severity: recoverable", self.logged())
        self.assertFalse(self.crashes())

    def test_progress_failed_sink_uses_independent_stderr(self):
        progress = StartupProgress(self.output, interactive=True, animate=False, line_sink=Mock(side_effect=TypeError))
        with patch.object(progress, "_animate", side_effect=AttributeError), redirect_stderr(io.StringIO()) as fallback:
            self.assertEqual(0, self.reporter.run(lambda: (progress._animation_root(), 0)[-1]))
        self.assertIn("ERROR", fallback.getvalue())

    def test_event_worker_software_fault_logged_and_resync_error_state(self):
        source = SimpleNamespace(iter_changes=lambda: fail(AttributeError))
        pump = LiveEventPump(source)
        def application():
            pump._run()
            result = pump.get(0)
            self.assertTrue(result.resync_required)
            self.assertTrue(result.software_fault)
            self.assertIn("ERROR", result.error)
            return 0
        self.assertEqual(0, self.reporter.run(application))
        self.assertIn("watch-event-observer", self.logged())
        self.assertFalse(self.crashes())

    def test_event_worker_expected_source_outage_has_no_software_log(self):
        pump = LiveEventPump(SimpleNamespace(iter_changes=lambda: fail(SourceUnavailableError)))
        self.assertEqual(0, self.reporter.run(lambda: (pump._run(), 0)[-1]))
        self.assertTrue(pump.get(0).resync_required)
        self.assertFalse(self.logs())

    def test_claude_reader_fault_is_not_an_anonymous_transport_end(self):
        process = Mock()
        process.stdout.readline.side_effect = TypeError("SECRET")
        reader = None
        def application():
            nonlocal reader
            reader = _ControlReader(process, time.monotonic() + 2)
            reader.thread.join(timeout=2)
            with self.assertRaises(ClaudeReaderFault):
                reader.request("test", {})
            return 0
        self.assertEqual(0, self.reporter.run(application))
        self.assertIn("claude-metadata-reader", self.logged())
        self.assertFalse(self.crashes())

    def test_optional_provider_unknown_failure_is_visible_not_missing(self):
        from development.fixtures.watch_runtime import MutableSource, make_service
        _, _, service, _ = make_service(str(self.root), MutableSource())
        provider = Mock(provider_id="synthetic-provider")
        provider.probe.side_effect = TypeError("SECRET")
        service.account_providers = (provider,)
        def application():
            accounts = service.account_quota_snapshots()
            self.assertEqual(1, len(accounts))
            self.assertEqual("error", accounts[0].availability)
            self.assertIn("ERROR", accounts[0].reason)
            return 0
        self.assertEqual(0, self.reporter.run(application))
        self.assertIn("account-provider", self.logged())

    def test_provider_expected_timeout_auth_and_unavailability_do_not_log(self):
        from development.fixtures.watch_runtime import MutableSource, make_service
        from src.domain import AccountRef, AccountSnapshot
        _, _, service, _ = make_service(str(self.root), MutableSource())
        provider = Mock(provider_id="synthetic-provider")
        service.account_providers = (provider,)
        for availability, reason in (("unavailable", "auth_failure"), ("error", "network_failure")):
            provider.get_account_snapshots.return_value = (AccountSnapshot(AccountRef("test", "synthetic", source_account="fixture"), 1,
                "Test", availability=availability, observations={"parser_reason":reason}),)
            self.assertEqual(0, self.reporter.run(lambda: (service.account_quota_snapshots(), 0)[-1]))
        provider.get_account_snapshots.side_effect = TimeoutError
        self.assertEqual(0, self.reporter.run(lambda: (service.account_quota_snapshots(), 0)[-1]))
        self.assertFalse(self.logs())
        self.assertFalse(self.crashes())

    def test_pricing_network_outage_without_cache_is_operational_not_a_crash(self):
        from src.pricing.github_copilot import GitHubCopilotPricingProvider, PricingUnavailableError
        cache = Mock()
        cache.get.return_value = None
        provider = GitHubCopilotPricingProvider(cache=cache, fetch_text=lambda *args: fail(TimeoutError))
        def application():
            with self.assertRaises(PricingUnavailableError):
                provider.get_catalog()
            return 1
        self.assertEqual(1, self.reporter.run(application))
        self.assertFalse(self.logs())
        self.assertFalse(self.crashes())
        cache.get.side_effect = TypeError("unexpected cache defect")
        self.assertEqual(1, self.reporter.run(lambda: (provider.get_catalog(), 0)[-1]))
        self.assertEqual(1, len(self.crashes()))

    def test_software_account_failure_is_visible_in_watch_and_never_masked_by_stale_capacity(self):
        from dataclasses import replace
        from decimal import Decimal
        from src.domain import AccountRef, AccountSnapshot, QuotaComponent
        from src.reports.models import AccountProjection
        from src.presentation.accounts import account_capacity_parts
        from src.watch.accounts import reconcile_accounts
        before = AccountSnapshot(AccountRef("test", "synthetic", source_account="fixture"), 1, "Test",
            quotas=(QuotaComponent("Month", "fixed", remaining_fraction=Decimal("0.5")),))
        fault = replace(before, quotas=(), availability="error", reason="ERROR: Software fault",
                        observations={"parser_reason":"software_failure"})
        reconciled, _, _ = reconcile_accounts((before,), (fault,), {before.key:1}, now_ms=2, recovering=True)
        self.assertEqual(fault, reconciled[0])
        projection = AccountProjection(fault, "Test")
        parts = account_capacity_parts(projection, "UTC", now_ms=2, watch=True, recovering=True)
        self.assertIn("ERROR:", " ".join(str(part) for part in parts))
        self.assertFalse(reconciled[0].quotas)

    def test_watch_valuation_and_quota_projection_bugs_are_fatal_not_stale(self):
        from development.tests.test_watch_lifecycle import watch_for
        for method in ("token_category_valuation", "build_watch_quota"):
            with self.subTest(method=method), watch_for() as (watch, _):
                with patch.object(watch.report_service, method, side_effect=TypeError("SECRET")):
                    self.assertEqual(1, self.reporter.run(lambda: (watch.initialize(), 0)[-1]))
        self.assertEqual(2, len(self.crashes()))

    def test_watch_ctrl_c_and_scoped_lifecycle_do_not_log_software_errors(self):
        from development.tests.test_watch_lifecycle import watch_for
        from development.tests.test_watch_source_recovery import Recorder
        from src.watch.coordinator import WatchedSessionEnded
        for end in (KeyboardInterrupt, WatchedSessionEnded("expected archived root")):
            with watch_for(scoped=True) as (watch, _):
                initial = watch.initialize()
                with patch.object(watch, "_advance", side_effect=end):
                    self.assertEqual(0, self.reporter.run(lambda: (watch.run_forever(Recorder(), initial_cycle=initial), 0)[-1]))
        self.assertFalse(self.logs())
        self.assertFalse(self.crashes())

    def test_retired_worker_unknown_failure_is_fatal_not_silently_dropped(self):
        pump = LiveEventPump(SimpleNamespace(iter_changes=lambda: fail(TypeError)))
        pump._stop.set()
        self.assertEqual(1, self.reporter.run(lambda: (pump._run(), 0)[-1]))
        self.assertEqual(1, len(self.crashes()))

    def test_fatal_subprocess_nonzero_and_no_default_traceback(self):
        code = ("from pathlib import Path; from src.runtime_errors import RuntimeErrors; "
                f"raise SystemExit(RuntimeErrors(Path({str(self.root)!r})).run(lambda: 1/0))")
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(1, result.returncode)
        self.assertIn("COST GUARD FAILED", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(1, len(self.crashes()))

    def test_root_inventory_cannot_silently_gain_an_unreviewed_thread(self):
        import ast
        roots = []
        for path in (ROOT / "src").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Call) and ((isinstance(node.func, ast.Attribute) and node.func.attr == "Thread")
                        or (isinstance(node.func, ast.Name) and node.func.id == "Thread")):
                    roots.append(path.relative_to(ROOT).as_posix())
        # Reviewed in development/runtime-failures.md; claude_transport owns reader + bounded cleanup.
        self.assertEqual(sorted(["src/accounts/acquisition.py", "src/accounts/claude_transport.py",
                                 "src/accounts/claude_transport.py", "src/presentation/progress.py",
                                 "src/reports/model_comparison.py", "src/watch/model_discovery.py",
                                 "src/watch/observers.py"]), sorted(roots))

    def test_retention_30_days_only_owned_files_and_no_log_on_cleanup_failure(self):
        directory = self.root / "logs/errors"
        directory.mkdir(parents=True)
        old = directory / "cost-guard-errors-2000-01-01.log"
        recent = directory / f"cost-guard-errors-{datetime.now():%Y-%m-%d}.log"
        unrelated = directory / "private.txt"
        for path in (old, recent, unrelated):
            path.write_text("test")
        os.utime(old, (time.time() - 31 * 86400,) * 2)
        os.utime(unrelated, (time.time() - 31 * 86400,) * 2)
        self.reporter.cleanup()
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())
        self.assertTrue(unrelated.exists())
        with patch("src.runtime_errors.os.scandir", side_effect=PermissionError):
            self.reporter.cleanup()
        self.assertEqual("test", recent.read_text())

    def test_diagnostics_help_usage_and_preintegration_import_boundary(self):
        for arg, expected in (("--help", 0), ("--invalid", 2)):
            result = subprocess.run([sys.executable, str(ROOT / "development/tools/collect_diagnostics.py"), arg],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(expected, result.returncode)
            self.assertNotIn("COST GUARD FAILED", result.stderr)
        # runpy is the diagnostics boundary's import seam, not a production knob.
        with patch("src.runtime_errors.RuntimeErrors", return_value=self.reporter), patch("runpy.run_path", side_effect=TypeError("SECRET")):
            with self.assertRaises(SystemExit) as status:
                exec(compile((ROOT / "development/tools/collect_diagnostics.py").read_text(), "diagnostics", "exec"),
                     {"__name__": "__main__", "__file__": str(ROOT / "development/tools/collect_diagnostics.py")})
        self.assertEqual(1, status.exception.code)
        self.assertEqual(1, len(self.crashes()))


if __name__ == "__main__":
    unittest.main()
