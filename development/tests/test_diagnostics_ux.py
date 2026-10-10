"""Minimal Diagnostics result screen, metadata evidence in the ZIP and stop-error help."""
from __future__ import annotations

import errno
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from zipfile import BadZipFile, ZipFile

from development.tools import collect_diagnostics as diag
from development.tools import diagnostic_screen
from development.tools.diagnostic_logs import create_bundle
from development.tools.diagnostic_metadata import model_metadata_section
from src.cache import CacheDatabase
from src.config import load_configuration
from src.pricing.metadata_health import MetadataHealthStore
from src.pricing.release_metadata import MetadataAttempt, SourceResult
from src.presentation import WatchRenderer
from src.runtime_errors import RuntimeErrors, diagnostics_hint
from src.version import mode_heading

ROOT = Path(__file__).resolve().parents[2]
EMAIL = str(load_configuration(ROOT).values["diagnostics"]["supportEmail"])


def minimal_data() -> dict:
    return {"schema_version": 2, "generated_at_utc": "2026-10-08T00:00:00+00:00",
            "cost_guard": {"version": "test"}, "environment": {"python_version": "3", "platform": "test"}}


class ResultScreenTests(unittest.TestCase):
    def test_redirected_success_is_plain_and_contains_only_the_agreed_text(self) -> None:
        stream = io.StringIO()
        path = Path("C:/") / ("very-long-folder-name-" * 12) / "cost-guard-diagnostics.zip"
        diagnostic_screen.render_result(stream, path=path, email=EMAIL)
        self.assertEqual(
            f"\nDiagnostic file successfully created!\n\n{path}\n\n"
            f"Please attach this file to an email and send it to:\n{EMAIL}\n\n", stream.getvalue())
        self.assertNotIn("\x1b", stream.getvalue())

    def test_terminal_success_clears_screen_and_colors_heading_green(self) -> None:
        stream = io.StringIO()
        with mock.patch.object(diagnostic_screen, "_ansi_terminal", return_value=True), \
             mock.patch.dict(os.environ, {"NO_COLOR": ""}):
            diagnostic_screen.render_result(stream, path="/x/cost-guard-diagnostics.zip", email=EMAIL)
        text = stream.getvalue()
        self.assertTrue(text.startswith(diagnostic_screen.CLEAR + "\x1b[1;92mDiagnostic file successfully created!\x1b[0m"))
        self.assertTrue(text.endswith(EMAIL + "\x1b[0m\n\n"))

    def test_failure_is_red_short_and_safe(self) -> None:
        stream = io.StringIO()
        with mock.patch.object(diagnostic_screen, "_ansi_terminal", return_value=True), \
             mock.patch.dict(os.environ, {"NO_COLOR": ""}):
            diagnostic_screen.render_result(stream, error=PermissionError("C:/secret/path"))
        text = stream.getvalue()
        self.assertIn("\x1b[1;91mDiagnostic file creation failed!\x1b[0m", text)
        self.assertIn("Reason: The diagnostics folder is not writable", text)
        self.assertNotIn("secret", text)
        self.assertTrue(text.endswith("program.\n\n"))
        self.assertIn("disk is full", diagnostic_screen.failure_reason(OSError(errno.ENOSPC, "x")))
        self.assertIn("verified", diagnostic_screen.failure_reason(BadZipFile()))


class MainFlowTests(unittest.TestCase):
    def run_main(self, tmp: str, *, bundle_error: BaseException | None = None):
        stdout, stderr = io.StringIO(), io.StringIO()
        patches = [
            mock.patch.object(diag, "collect", return_value=minimal_data()),
            mock.patch.object(diag, "_macos_compatibility_checks", return_value={"ok": True}),
            mock.patch.object(diag, "run_full_validation", return_value={"tier": "full-local", "ok": False}),
            mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr),
        ]
        if bundle_error is not None:
            patches.append(mock.patch.object(diag, "create_bundle", side_effect=bundle_error))
        for item in patches:
            item.start()
        try:
            code = diag.main(["--no-network", "--snapshots", "0", "--output-dir", tmp])
        finally:
            for item in reversed(patches):
                item.stop()
        return code, stdout.getvalue()

    def test_failed_tests_with_verified_zip_still_end_with_plain_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_main(tmp)
            bundle = (Path(tmp) / "cost-guard-diagnostics.zip").resolve()
            self.assertEqual(0, code)
            self.assertTrue(bundle.is_file())
            self.assertEqual(f"{mode_heading('Diagnostics')}\n\nDiagnostic file successfully created!\n\n{bundle}\n\n"
                             f"Please attach this file to an email and send it to:\n{EMAIL}\n\n", out)
            for hidden in ("Archived", "removed", "Review", "automatically", "Tests completed"):
                self.assertNotIn(hidden, out)

    def test_zip_failure_is_short_and_non_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_main(tmp, bundle_error=PermissionError("locked"))
        self.assertEqual(1, code)
        self.assertTrue(out.endswith("\nDiagnostic file creation failed!\n\nReason: The diagnostics folder is not "
                                      "writable or the ZIP file is open in another program.\n\n"))


class BundleEvidenceTests(unittest.TestCase):
    def test_failed_publish_preserves_previous_zip_and_leaves_no_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "diagnostics" / "cost-guard-diagnostics.zip"
            create_bundle(target, root=Path(tmp), json_bytes=b"{}", text_bytes=b"first", include_logs=False)
            before = target.read_bytes()
            with mock.patch.object(Path, "replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    create_bundle(target, root=Path(tmp), json_bytes=b"{}", text_bytes=b"second", include_logs=False)
            self.assertEqual(before, target.read_bytes())
            self.assertEqual([target], list(target.parent.iterdir()))

    def test_self_healed_metadata_failure_is_in_the_zip_and_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = MetadataHealthStore(root)
            store.record(MetadataAttempt((SourceResult("models.dev", "failed", "http_error", "fetch", http_status=403),),
                                         32, 0, False), 1_000, reason="missing_release_dates")
            store.record(MetadataAttempt((SourceResult("models.dev", "ok", "partial_matches", "complete", matched=31),),
                                         32, 31, False), 61_000, reason="retry_after_failure")
            section = model_metadata_section(root, {}, network=False, database_factory=CacheDatabase)
            self.assertFalse(CacheDatabase(root).paths.database.exists())
            self.assertEqual(["models.dev"], section["summary"]["recovered_sources"])
            self.assertEqual([], section["summary"]["failing_sources"])
            self.assertEqual(["failure_started", "recovered"], [e["event"] for e in section["failure_events"]])
            self.assertEqual(403, section["summary"]["sources"]["models.dev"]["last_error"]["http_status"])
            target = root / "diagnostics" / "cost-guard-diagnostics.zip"
            create_bundle(target, root=root, json_bytes=b"{}", text_bytes=b"ok")
            with ZipFile(target) as archive:
                names = archive.namelist()
            self.assertIn("state/model-metadata.json", names)
            self.assertTrue(any(name.startswith("logs/errors/cost-guard-metadata-") for name in names))
            self.assertTrue(any(name.startswith("logs/recovery/cost-guard-metadata-") for name in names))
            self.assertTrue((root / "cache/state/model-metadata.json").exists())  # live retry state kept


class StopHelpTests(unittest.TestCase):
    def test_hint_points_at_this_installation_per_platform(self) -> None:
        root = Path(tempfile.gettempdir()) / "Cost Guard"
        for platform, target in (
            ("win32", str(root / "development" / "windows" / "Cost Guard Diagnostics.cmd")),
            ("darwin", str(root / "development" / "macos" / "Cost Guard Diagnostics.command")),
            ("linux", str(root / "development" / "tools" / "collect_diagnostics.py")),
        ):
            with mock.patch("sys.platform", platform):
                hint = diagnostics_hint(root)
            self.assertIn("Need help? Run Cost Guard Diagnostics:", hint)
            self.assertIn(target, hint)

    def test_fatal_report_adds_hint_except_inside_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for mode, expected in (("startup", True), ("Diagnostics", False)):
                stream = io.StringIO()
                try:
                    raise RuntimeError("secret")
                except RuntimeError as exc:
                    RuntimeErrors(Path(tmp), mode=mode, stream=stream).fatal(exc)
                self.assertIn("COST GUARD FAILED", stream.getvalue())
                self.assertEqual(expected, "Need help? Run Cost Guard Diagnostics:" in stream.getvalue())

    def test_only_stopping_errors_show_the_hint(self) -> None:
        from src import bootstrap
        from src.sources.errors import SourceSchemaError
        from src.watch.coordinator import WatchedSessionEnded

        for failure, expected in ((SourceSchemaError("schema is not supported"), True),
                                  (WatchedSessionEnded("ended"), False), (KeyboardInterrupt(), False)):
            class Coordinator:
                def __init__(self, **_kwargs):
                    pass

                def initialize(self):
                    return None

                def run_forever(self, *_args, **_kwargs):
                    raise failure

            stdout = io.StringIO()
            with mock.patch.object(bootstrap, "_select_source", return_value=mock.Mock(selected="v1", warnings=())), \
                 mock.patch.object(bootstrap, "WatchCoordinator", Coordinator), \
                 mock.patch.object(bootstrap, "ReportService"), mock.patch.object(bootstrap, "CacheDatabase"), \
                 mock.patch.object(bootstrap, "CacheRepository"), \
                 mock.patch.object(bootstrap, "GitHubCopilotPricingProvider"), \
                 mock.patch.object(bootstrap, "_account_providers", return_value=()), \
                 mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", io.StringIO()):
                bootstrap.main(["--watch"])
            self.assertEqual(expected, "Need help? Run Cost Guard Diagnostics:" in stdout.getvalue(), failure)


class WatchStartupColorTests(unittest.TestCase):
    def test_startup_loading_is_default_white_but_statuses_keep_their_color(self) -> None:
        stream = io.StringIO()
        renderer = WatchRenderer({"colors": {"activeRunning": {"foreground": "Yellow"}}}, stream=stream, interactive=True)
        renderer.render_initializing("V2")
        renderer.render_startup_status("Watch: [####----] 50% / Analyzing")
        self.assertNotIn("\x1b[93m", stream.getvalue())
        renderer.render_startup_status("Watch: Waiting for OpenCode source", active=True)
        self.assertIn("\x1b[93mWatch: Waiting for OpenCode source\x1b[0m", stream.getvalue())


class WatchEvidenceTests(unittest.TestCase):
    def test_headless_watch_smoke_reports_geometry_and_counts_without_private_text(self) -> None:
        from development.fixtures.report_runtime import FakePricingProvider
        from development.fixtures.session_snapshots import make_snapshot
        from development.fixtures.watch_runtime import MutableSource, make_service, openai_account
        from development.tools.diagnostic_watch import watch_evidence

        with tempfile.TemporaryDirectory() as tmp:
            source = MutableSource(make_snapshot(running=True))
            config, selection, service, db = make_service(tmp, source)
            quota = service.build_watch_quota(quota_snapshots=(openai_account().account,), query_account=False)
            with mock.patch("src.watch.observation_diagnostics.record_scan") as record:
                result = watch_evidence(selection, config, service.cache_repository, quota=quota,
                                        pricing_provider=FakePricingProvider())
            record.assert_not_called()
        self.assertEqual(1, result["running_rows"])
        self.assertEqual(1, result["rendered_accounts"])
        self.assertEqual({"80", "120", "160"}, set(result["renders"]))
        for width, render in result["renders"].items():
            self.assertEqual(0, render["flowing_overflow_lines"], width)
            self.assertLessEqual(render["max_flowing_width"], int(width))
        def leaves(value):
            if isinstance(value, dict):
                for item in value.values():
                    yield from leaves(item)
            else:
                yield value

        # Numbers/flags only: no title, prompt, model, session or path text can leak.
        self.assertTrue(all(value is None or isinstance(value, (bool, int, float)) for value in leaves(result)))

    def test_terminal_facts_are_booleans_and_sizes_only(self) -> None:
        from development.tools.diagnostic_watch import terminal_facts

        with mock.patch.dict(os.environ, {"WT_SESSION": "private-guid", "COLORTERM": "truecolor"}):
            facts = terminal_facts()
        self.assertIs(True, facts["windows_terminal"])
        self.assertNotIn("private-guid", repr(facts))


if __name__ == "__main__":
    unittest.main()
