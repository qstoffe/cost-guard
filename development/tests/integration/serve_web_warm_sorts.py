"""Real HTTP/controller/Live host over the owned warm-sort regression source."""
from pathlib import Path
import json
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.catalog_warm_sorts import NOW, WarmSortSource
from development.tests.fixtures.compact_reports import report_service
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.integration.serve_web_sessions import CaptureJobs, FixtureRuntime
from src.application.live_projection import project_live
from src.reports.watch_capture import capture_rows
from src.watch.observers import observe_catalog
from src.web.host import WebHost


class WarmRuntime(FixtureRuntime):
    def observe(self):
        self.catalog.observe(observe_catalog(self.service.source, include_archived_revisions=True),
            unavailable=self.unavailable)
        snapshot = self.service.source.snapshots["root-0000"]
        capture, _ = capture_rows(self.service, snapshot.root, fresh=snapshot)
        if capture.catalog_prompt is not None:
            prompt, start, running, ended = capture.catalog_prompt
            self.catalog.observe_prompts(((snapshot.root, snapshot.source_revision, capture.observed_at_ms,
                prompt, start, running, None, ended),))
        if not self.scalar_hold and self.catalog.needed():
            self.catalog.tick(self.service)
        view = project_live(summary_watch(), self.service.timezone_id).to_json()
        self.publish("live", dict(state="running", view=view, source_observed_at_ms=NOW,
            catalog_hint=self.catalog.live_hint()))


def main():
    config = Path(sys.argv[1])
    (config / "config").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "config/default-config.jsonc", config / "config/default-config.jsonc")
    owner, source = unittest.TestCase(), WarmSortSource()
    service = report_service(owner, source, now_ms=NOW)
    host = WebHost(config, jobs=CaptureJobs())
    runtime = WarmRuntime(service, host.events.publish)
    host.live = runtime
    runtime.scalar_hold = True
    runtime.observe()
    warm = runtime.catalog.page(navigation=1)
    for _ in range(24):
        runtime.catalog_clock_offset += 6
        runtime.catalog.tick(service)
        warm = runtime.catalog.page(token=warm["token"], navigation=1)
        if not warm["pending_sort"]:
            break
    assert not warm["pending_sort"]
    runtime.catalog.leases.clear()
    host.start()
    host.publish_ready()
    print(json.dumps(dict(url=host.browser_url())), flush=True)
    try:
        for line in sys.stdin:
            command = json.loads(line)["command"]
            with runtime.observation_lock:
                if command.startswith("warm-stream-"):
                    source.stream(int(command.removeprefix("warm-stream-")))
                elif command == "warm-pending":
                    from dataclasses import replace
                    snapshot = source.snapshots["root-0042"]
                    source.snapshots["root-0042"] = replace(snapshot, source_revision="pending")
                elif command == "warm-fill":
                    runtime.catalog_clock_offset += 6
                    runtime.catalog.tick(service)
                elif command == "warm-finish":
                    source.finish()
                elif command == "warm-fail":
                    runtime.unavailable = True
                elif command == "warm-recover":
                    runtime.unavailable = False
                elif command != "warm-observe":
                    raise ValueError(command)
                runtime.observe()
                print(json.dumps(dict(ok=True, history_reads=source.load_count, reads=dict(source.reads),
                    metrics=dict(runtime.catalog.metrics), generation=runtime.catalog.generation,
                    revisions=dict(runtime.catalog.revisions))), flush=True)
    finally:
        host.close()
        owner.doCleanups()


if __name__ == "__main__":
    main()
