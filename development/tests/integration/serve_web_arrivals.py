"""Owned native-V2 wire source + unmodified shared Live/Watch/HTTP/SSE owners.

Only the scalar lane is deliberately gated to prove title/running visibility
does not wait for it. Initial scalar facts are controlled warm fixture values.
No personal sources, accounts, external APIs or model calls.
"""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import shutil
import sys
from threading import Thread
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.historical_web_source import FixtureServer, WireHistory
from development.tests.fixtures.pricing_catalog import catalog as prices
from development.tests.fixtures.web_help_reports import HelpAuditJobs
from src.application.session_catalog import SessionCatalog
from src.cache import CacheDatabase, CacheRepository
from src.config import load_configuration
from src.domain import ModelRef
from src.reports import ReportService
from src.reports.models import SessionUsageRow
from src.sources.opencode_v2 import OpenCodeV2Source
from src.sources.selection import SourceSelection
from src.watch.acquisition import LiveAcquisition
from src.watch.web_coordinator import WebWatchCoordinator
from src.web.host import WebHost


class ControlledCatalog(SessionCatalog):
    def __init__(self):
        super().__init__()
        self.hold = True
        self.observations = {}

    def tick(self, service):
        if not self.hold:
            super().tick(service)

    def observe(self, observation, **kwargs):
        super().observe(observation, **kwargs)
        for key in self.roots:
            self.observations.setdefault(key, {}).setdefault("title_ms", int(time.time() * 1000))

    def observe_prompts(self, evidence):
        evidence = tuple(evidence)
        super().observe_prompts(evidence)
        for root, running, age, prompt, start in evidence:
            if running and prompt and start and age <= 15:
                self.observations.setdefault(root.session_id, {}).setdefault("running_ms", int(time.time() * 1000))


class Prices:
    def get_catalog(self):
        value = prices()
        return replace(value, models=tuple(replace(value.models[0], model=ModelRef("openai", f"gpt-test-{i}"))
                                           for i in (1, 2)))


def main():
    config_root = Path(sys.argv[1])
    config_root.mkdir(parents=True, exist_ok=True)
    (config_root / "config").mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "config/default-config.jsonc", config_root / "config/default-config.jsonc")
    owner = WireHistory(25, 1, int(time.time() * 1000), 0)
    server = FixtureServer(owner)
    thread = Thread(target=server.serve_forever, kwargs=dict(poll_interval=.05), daemon=True)
    thread.start()
    registration = config_root / "service.json"
    registration.write_text(json.dumps(dict(url=f"http://127.0.0.1:{server.server_port}", pid=4242)), encoding="utf-8")
    database = CacheDatabase(config_root)
    database.initialize()
    config = dict(load_configuration(ROOT).values, timezone="UTC", watchStartupEarlierSessions=0)

    def service(now):
        source = OpenCodeV2Source(registration)
        return ReportService(selection=SourceSelection(source, "v2", (), source.probe()),
            pricing_provider=Prices(), account_provider=None, account_providers=(),
            cache_repository=CacheRepository(database), config=config, now_ms=now)

    def driver():
        reports = service(int(time.time() * 1000))
        return LiveAcquisition(WebWatchCoordinator(selection=reports.selection, report_service=reports,
            config=config, service_factory=service, record_observations=False))

    host = WebHost(config_root, live_factory=driver, jobs=HelpAuditJobs())
    catalog = ControlledCatalog()
    host.live.catalog = catalog
    host.start()
    host.publish_ready()
    print(json.dumps(dict(url=host.browser_url())), flush=True)
    events = {}
    try:
        for line in sys.stdin:
            command = json.loads(line)["command"]
            if command == "stop":
                break
            if command == "arrival-seed":
                with catalog.lock:
                    for key, root in catalog.roots.items():
                        catalog.rows[key] = SessionUsageRow(key, root.title, "GPT Test", False, Decimal("1"), 1,
                            last_activity_ms=catalog.activity[key], duration_ms=1000, context_tokens=100)
                        catalog.valid[key] = catalog.revisions[key], catalog.clock()
                        catalog.activity_valid[key] = catalog.revisions[key]
            elif command.startswith("arrival-new-"):
                number = int(command.rsplit("-", 1)[1])
                key = f"ses_arrival_{number}"
                now = int(time.time() * 1000)
                with owner.lock:
                    owner.sessions.insert(0, dict(id=key, projectID="prj_fixture", title=f"Real source title {number}",
                        location=dict(directory="/fixture/repository"), agent="build",
                        model=dict(providerID="openai", id="gpt-test-1", variant="medium"),
                        time=dict(created=now, updated=now)))
                    owner.messages[key] = []
                    owner.events.append(dict(type="session.created", data=dict(sessionID=key)))
                events[key] = dict(title_event_ms=now)
            elif command.startswith("arrival-running-"):
                number = int(command.rsplit("-", 1)[1])
                key, now = f"ses_arrival_{number}", int(time.time() * 1000)
                with owner.lock:
                    owner.messages[key] = [
                        dict(id=key + "_u", type="user", text="Synthetic prompt", files=[], agents=[], time=dict(created=now-1)),
                        dict(id=key + "_a", type="assistant", agent="build",
                            model=dict(providerID="openai", id="gpt-test-1", variant="medium"),
                            content=[dict(type="text", text="Synthetic stream")], cost=.01,
                            tokens=dict(input=1000, output=100, reasoning=0, cache=dict(read=0, write=0)),
                            time=dict(created=now))]
                    next(row for row in owner.sessions if row["id"] == key)["time"]["updated"] = now
                    owner.active = {key: dict(type="running")}
                    owner.events.append(dict(type="message.updated", data=dict(sessionID=key)))
                events[key]["running_event_ms"] = now
            elif command == "arrival-hydrate":
                catalog.hold = False
            elif command == "arrival-hold":
                catalog.hold = True
                job = host.live.driver.coordinator.catalog_job
                if job is not None:
                    job.result(timeout=10)
            elif command == "arrival-observe":
                print(json.dumps(dict(ok=True, events=events, observed=catalog.observations,
                    source=owner.snapshot(), metrics=catalog.metrics, failure=str(host.live.failure))), flush=True)
                continue
            print(json.dumps(dict(ok=True)), flush=True)
    finally:
        host.close()
        owner.stopping.set()
        server.shutdown()
        server.close_connections()
        server.join_handlers(5)
        server.server_close()
        thread.join(5)


if __name__ == "__main__":
    main()
