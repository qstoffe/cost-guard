"""Owned synthetic Sessions host using shipped HTTP/auth/assets and real DTO owners.

Stdin commands alter only in-memory synthetic history; no personal source/provider.
"""
from dataclasses import replace
from decimal import Decimal
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
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.fixtures.web_help_reports import HelpAuditJobs
from src.application.live_projection import project_live
from src.application.session_catalog import SessionCatalog
from src.application.session_detail import SessionDetails
from src.domain import ModelRef
from src.reports.watch_capture import capture_rows
from src.reports.models import SessionUsageRow
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
        self.scalar_hold = False
        self.live_root = None
        self.thread = Thread(target=self.run)

    def start(self):
        self.thread.start()

    def run(self):
        while not self.stopping.is_set():
            observation = observe_catalog(self.service.source, include_archived_revisions=True)
            self.catalog.observe(observation, unavailable=self.unavailable)
            if self.live_root and not self.unavailable:
                root = self.service.source.snapshots[self.live_root].root
                capture, _ = capture_rows(self.service, root)
                self.catalog.observe_prompts(((root, any(row.in_progress for row in capture.rows), 0),))
            self.details.tick(self.service, unavailable=self.unavailable)
            if not self.scalar_hold and self.catalog.needed():
                self.catalog.tick(self.service)
            view = project_live(summary_watch(), "UTC").to_json()
            self.publish("live", dict(state="running", view=view, source_observed_at_ms=self.service.now_ms))
            self.stopping.wait(.25)

    def close(self):
        self.stopping.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError("fixture_shutdown_timeout")


def main():
    if sys.argv[1] == '--real-source':
        from src.web.composition import live_acquisition
        host = WebHost(ROOT, live_factory=live_acquisition)
        host.start()
        host.publish_ready()
        print(json.dumps(dict(url=host.browser_url())), flush=True)
        try:
            for line in sys.stdin:
                if json.loads(line)['command'] == 'stop':
                    break
                catalog = host.live.driver.coordinator
                print(json.dumps(dict(ok=True, observed=catalog.catalog_observation is not None)), flush=True)
        finally:
            host.close()
        return
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
            elif command.startswith('catalog-'):
                host.live.scalar_hold = True
                catalog = host.live.catalog
                if command == 'catalog-large':
                    source.snapshots = SyntheticMonthSource(3217, 1, month_start_ms=1000).snapshots
                    catalog.observe(observe_catalog(source, include_archived_revisions=True))
                if command == 'catalog-churn':
                    snapshot = source.snapshots['root-0000']
                    source.snapshots['root-0000'] = replace(snapshot,
                        root=replace(snapshot.root, active=True, updated_at_ms=catalog.generation + 2000),
                        source_revision=f'churn-{catalog.generation}')
                    catalog.observe(observe_catalog(source, include_archived_revisions=True))
                with catalog.lock:
                    if command == 'catalog-clear':
                        catalog.valid.clear()
                    if command in ('catalog-partial', 'catalog-index'):
                        for number, (key, root) in enumerate(catalog.roots.items()):
                            if command == 'catalog-partial' and number >= 428:
                                break
                            catalog.rows[key] = SessionUsageRow(key, root.title, f'Model {number:04}', False,
                                Decimal(number) / 1000, number, duration_ms=number * 1000, context_tokens=number)
                            catalog.valid[key] = catalog.revisions[key], catalog.clock()
                    if command == 'catalog-page-cold':
                        keys = sorted(catalog.roots, reverse=True)[50:100]
                        for key in keys:
                            catalog.valid.pop(key, None)
                    if command == 'catalog-churn':
                        for key in [key for key in catalog.roots if key not in catalog.valid and key != 'root-0000'][:20]:
                            number = int(key.split('-')[1])
                            catalog.rows[key] = SessionUsageRow(key, catalog.roots[key].title, f'Model {number:04}', False,
                                Decimal(number) / 1000, number, duration_ms=number * 1000, context_tokens=number)
                            catalog.valid[key] = catalog.revisions[key], catalog.clock()
            elif command in ("fail", "recover"):
                host.live.unavailable = command == "fail"
            elif command == "end":
                source.snapshots["root-0000"] = replace(make_root_snapshot(0, 1002, month_start_ms=1000), source_revision="ended")
            elif command in ("hold-captures", "resume-captures"):
                jobs.hold = command == "hold-captures"
            elif command in ("live-cold", "live-progress", "live-finish", "live-resume"):
                count = {"live-cold": 1, "live-progress": 2, "live-finish": 2, "live-resume": 3}[command]
                snapshot = make_root_snapshot(121, count, month_start_ms=1000)
                snapshot = replace(snapshot, invocations=tuple(replace(item,
                    tokens=replace(item.tokens, input=count * 1_000_000)) for item in snapshot.invocations))
                if command != "live-finish":
                    aid = snapshot.messages[-1].message_id
                    snapshot = replace(snapshot, root=replace(snapshot.root, active=True),
                        messages=tuple(replace(item, completed_at_ms=None, finish_reason=None)
                                       if item.message_id == aid else item for item in snapshot.messages),
                        invocations=tuple(replace(item, completed_at_ms=None, finish_reason=None)
                                          if item.message_id == aid else item for item in snapshot.invocations))
                if count > 1:
                    snapshot = replace(snapshot, invocations=tuple(replace(item,
                        model=ModelRef("other-provider", "gpt-test", "Long localized model display name"))
                        if index else item for index, item in enumerate(snapshot.invocations)))
                source.snapshots[snapshot.root.session_id] = replace(snapshot,
                    sessions=(snapshot.root,), source_revision=command, complete=True)
                host.live.live_root = snapshot.root.session_id
                host.live.scalar_hold = command == "live-cold"
            elif command == "live-hydrate":
                host.live.scalar_hold = False
            elif command == "stop":
                break
            print(json.dumps(dict(ok=True, command=command)), flush=True)
    finally:
        host.close()
        owner.doCleanups()


if __name__ == "__main__":
    main()
