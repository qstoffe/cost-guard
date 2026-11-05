"""Owned synthetic Sessions host using shipped HTTP/auth/assets and real DTO owners.

Stdin commands alter only in-memory synthetic history; no personal source/provider.
"""
from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys
from threading import Event, Thread
import time
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.warning_projections import warning_prompt, warning_watch_projection
from development.tests.fixtures.web_help_reports import HelpAuditJobs
from src.analysis.context import PriceWarningSeverity
from src.application.live_projection import project_live
from src.application.session_catalog import SessionCatalog
from src.application.session_detail import SessionDetails
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.watch.observers import observe_catalog


class CaptureJobs(HelpAuditJobs):
    """Optional held synthetic captures exercise the shipped HTTP cancel control."""

    hold = False

    def submit(self, request):
        if not self.hold:
            return super().submit(request)
        key = uuid4().hex
        self.jobs[key] = dict(id=key, status="running", result=None, error=None,
                             progress=dict(phase="history", completed=1, total=10))
        return key

    def cancel(self, key):
        if key not in self.jobs:
            return False
        self.jobs[key].update(status="cancelled")
        return True


class FixtureRuntime:
    def __init__(self, service, publish):
        self.service = service
        self.publish = publish
        self.stopping = Event()
        self.details = SessionDetails()
        self.catalog = SessionCatalog()
        self.unavailable = False
        self.thread = Thread(target=self.run)

    def start(self):
        self.thread.start()

    def run(self):
        while not self.stopping.is_set():
            observation = observe_catalog(self.service.source, include_archived_revisions=True)
            self.catalog.observe(observation, unavailable=self.unavailable)
            self.details.tick(self.service, unavailable=self.unavailable)
            if self.catalog.needed():
                self.catalog.tick(self.service)
            view = project_live(warning_watch_projection(warning_prompt(PriceWarningSeverity.EXCEEDED)), "UTC").to_json()
            self.publish("live", dict(state="running", view=view, source_observed_at_ms=self.service.now_ms))
            self.stopping.wait(.25)

    def close(self):
        self.stopping.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError("fixture_shutdown_timeout")


def main():
    config = Path(sys.argv[1])
    (config / "config").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "config/default-config.jsonc", config / "config/default-config.jsonc")
    owner = unittest.TestCase()
    source = SyntheticMonthSource(120, 1, month_start_ms=1000)
    source.snapshots["root-0000"] = SyntheticMonthSource(1, 1001, month_start_ms=1000, running_roots=1).snapshots["root-0000"]
    service = report_service(owner, source, now_ms=100_000_000)
    jobs = CaptureJobs()
    host = WebHost(config, jobs=jobs)
    host.live = FixtureRuntime(service, host.events.publish)
    host.start()
    host.publish_ready()
    print(json.dumps(dict(url=host.browser_url())), flush=True)
    try:
        for line in sys.stdin:
            command = json.loads(line)["command"]
            if command == "arrive":
                source.snapshots["root-0120"] = make_root_snapshot(120, 1, month_start_ms=1000)
            elif command in ("fail", "recover"):
                host.live.unavailable = command == "fail"
            elif command == "end":
                source.snapshots["root-0000"] = replace(make_root_snapshot(0, 1002, month_start_ms=1000), source_revision="ended")
            elif command in ("hold-captures", "resume-captures"):
                jobs.hold = command == "hold-captures"
            elif command == "stop":
                break
            print(json.dumps(dict(ok=True, command=command)), flush=True)
    finally:
        host.close()
        owner.doCleanups()


if __name__ == "__main__":
    main()
