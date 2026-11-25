from __future__ import annotations

import io
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from development.tests.fixtures.session_snapshots import make_snapshot, make_uncompacted_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from development.tests.test_v783_regressions import _Pricing, _Source
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import IntegrationHealth, ProviderCapabilities
from src.presentation import WatchRenderer
from src.reports import ReportService
from src.sources.model_availability import OpenCodeModelAvailabilitySource
from src.sources.selection import SourceSelection
from src.watch import WatchCoordinator

ROOT = Path(__file__).resolve().parents[2]


class _UnavailableAccount:
    capabilities = ProviderCapabilities(account_quota=True)
    included_usage = False

    def __init__(self, provider_id: str = "openai") -> None:
        self.provider_id = provider_id
        self.quota_calls = 0

    def probe(self):
        return IntegrationHealth(False, False, "not configured")

    def get_quota_snapshot(self):
        self.quota_calls += 1
        raise AssertionError("an unavailable account provider must not be queried")


class V784RegressionTests(unittest.TestCase):
    def test_opencode_model_listing_executes_windows_cmd_shim_through_comspec(self) -> None:
        completed = SimpleNamespace(returncode=0, stdout="github-copilot/gpt-test\n")
        with mock.patch("src.sources.model_availability.shutil.which", return_value=r"C:\Tools\opencode.cmd"), \
             mock.patch.dict("src.sources.model_availability.os.environ", {"COMSPEC": r"C:\Windows\System32\cmd.exe"}), \
             mock.patch("src.sources.model_availability.subprocess.run", return_value=completed) as run:
            source = OpenCodeModelAvailabilitySource()
            self.assertEqual(("github-copilot/gpt-test",), source.available_model_ids())
        command = run.call_args.args[0]
        self.assertEqual(r"C:\Windows\System32\cmd.exe", command[0])
        self.assertEqual(["/d", "/s", "/c"], command[1:4])
        self.assertIn("opencode.cmd", command[4].lower())
        self.assertTrue(command[4].lower().endswith("models"))

    def test_absent_account_provider_is_not_queried_or_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            database = CacheDatabase(Path(td))
            database.initialize()
            source = _Source()
            missing = _UnavailableAccount()
            service = ReportService(
                selection=SourceSelection(source, "v1", (), source.probe()),
                pricing_provider=_Pricing(),
                account_provider=None,
                account_providers=(missing,),
                cache_repository=CacheRepository(database),
                config=dict(load_configuration(ROOT).values),
                now_ms=4_000,
            )
            self.assertEqual((), service.account_quota_snapshots())
            self.assertEqual(0, missing.quota_calls)

    def test_running_prompt_uses_live_session_context_instead_of_na(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # This case is before compaction. The old shared fixture included a
            # later completed rewrite, which must invalidate this live estimate.
            source = MutableSource(make_uncompacted_snapshot(running=True))
            config, selection, service, _db = make_service(td, source)
            projection = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: 2_200).initialize().projection
            row = next(item for item in projection.rows if item.prompt.event_id == "u_next")
            self.assertIsNotNone(row.prompt.watch_delta_context_tokens)
            self.assertIsNotNone(row.prompt.watch_next_context_tokens)
            stream = io.StringIO()
            WatchRenderer(config, stream=stream, interactive=False).render(projection)
            running_line = next(line for line in stream.getvalue().splitlines() if "#2 " in line)
            self.assertNotIn("N/A", running_line)

    def test_completed_marker_expires_without_another_source_poll(self) -> None:
        clock = [2_200]
        with tempfile.TemporaryDirectory() as td:
            source = MutableSource(make_snapshot(running=True))
            config, selection, service, _db = make_service(td, source)
            watch = WatchCoordinator(selection=selection, report_service=service, config=config, clock_ms=lambda: clock[0])
            watch.initialize()
            source.snapshot = replace(make_snapshot(running=False), source_revision="v1-rev-2")
            clock[0] = 2_400
            completed = watch.poll_once().projection
            row = next(item for item in completed.rows if item.prompt.event_id == "u_next")
            self.assertEqual("✓", row.marker)
            loads_after_completion = source.load_count

            clock[0] += 30_001
            aged = watch.status_projection(seconds_until_check=1)
            row = next(item for item in aged.rows if item.prompt.event_id == "u_next")
            self.assertEqual("", row.marker)
            self.assertEqual(loads_after_completion, source.load_count, "marker aging must be presentation-only")


if __name__ == "__main__":
    unittest.main()
