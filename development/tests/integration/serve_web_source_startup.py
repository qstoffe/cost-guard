"""Synthetic production HTTP/startup fixture controlled only through parent stdin.

No real installation, GUI, model or provider is touched. The fake wake publishes
registration only after release; actual authenticated V2 readiness is re-probed.
"""
from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from threading import Event
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.opencode_v2_service import FakeV2Service, fixture
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.watch_runtime import MutableSource, make_service
from development.tests.fixtures.report_loading import LoadingJobs
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.selection import SourceSelector
from src.watch.acquisition import LiveAcquisition
from src.watch.coordinator import WatchCoordinator
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.web.dispatch import DataDispatcher


def startup_report(sender, request):
    """Current canonical synthetic publication in a real owned finite child."""
    import time
    jobs = LoadingJobs()
    key = jobs.submit(request)
    result = jobs.jobs[key]['result']
    result['source'] = dict(status='acquired', observed_at_ms=int(time.time() * 1000),
                            identity=request.source_identity)
    sender.send(('result', json.dumps(result).encode('utf-8')))
    sender.close()


def main():
    if sys.platform == "win32":
        import multiprocessing
        multiprocessing.set_executable(str(Path(sys.executable).with_name("pythonw.exe")))
    with ExitStack() as stack:
        temporary = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        service = stack.enter_context(FakeV2Service(fixture()))
        registration = temporary / "service.json"
        selector = SourceSelector(inspect_migration_gap=False,
            v2_factory=lambda: OpenCodeV2Source(registration, timeout_seconds=0.2))
        release, entered = Event(), Event()
        counts = {"wake": 0, "acquire": 0}

        def wake(*args, **kwargs):
            counts["wake"] += 1
            entered.set()
            if not release.wait(15):
                raise RuntimeError("fixture_wake_gate_timeout")
            if sys.argv[1] == "failure":
                return  # CLI success without readiness must not connect.
            registration.write_text(json.dumps({"url": service.url, "pid": 4242,
                "password": "secret"}), encoding="utf-8")

        def acquire(*, selection=None):
            if selection is None:
                selection = selector.select("v2")
            counts["acquire"] += 1
            selection.source.close_reads()
            config, selected, report, _ = make_service(temporary, MutableSource(make_snapshot()))
            return LiveAcquisition(WatchCoordinator(selection=selected,
                report_service=report, config=config, clock_ms=lambda: 4000))

        stack.enter_context(patch("src.web.source_startup.load_configuration",
            return_value=Mock(values={"openCode": {"source": "v2"}})))
        stack.enter_context(patch("src.web.source_startup.SourceSelector", return_value=selector))
        stack.enter_context(patch("src.web.source_startup.find_opencode_executable", return_value="opencode"))
        stack.enter_context(patch("src.web.source_startup.wake_cli_service", side_effect=wake))
        stack.enter_context(patch("src.web.composition.live_acquisition", side_effect=acquire))
        host = WebHost(ROOT)
        host.jobs = ReportJobs(target=startup_report)
        host.dispatcher = DataDispatcher(host.jobs)
        # Synthetic Live config must never be compared with real installation
        # dependencies. The dispatcher and HTTP still use their production owners.
        host.dependencies = None
        stack.callback(host.close)
        host.start()
        host.publish_ready()
        if not entered.wait(2):
            raise RuntimeError("fixture_startup_missing")
        # Private bootstrap goes only to the owned probe's pipe, never evidence.
        print(json.dumps({"url": host.browser_url()}), flush=True)
        for line in sys.stdin:
            command = line.strip()
            if command == "release":
                release.set()
            elif command == "counts":
                print(json.dumps(counts), flush=True)
            elif command == "stop":
                break
        release.set()


if __name__ == "__main__":
    main()
