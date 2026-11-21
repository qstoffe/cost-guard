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
from threading import Event, Thread, current_thread
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.historical_web_source import FixtureServer, WireHistory
from development.tests.fixtures.pricing_catalog import catalog as prices
from development.tests.fixtures.web_help_reports import HelpAuditJobs
from src.application.session_catalog import SessionCatalog
from src.application.session_detail import SessionDetails
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
        self.revision_times = {}

    def tick(self, service):
        if not self.hold:
            super().tick(service)

    def observe(self, observation, **kwargs):
        if observation is not None:
            for key, revision in observation.revisions.items():
                if self.revisions.get(key) != revision:
                    self.revision_times[key] = int(time.time() * 1000)
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


class MeasuredDetails(SessionDetails):
    def __init__(self):
        super().__init__()
        self.started = self.published = 0
        self.started_ms = self.published_ms = None

    def claim(self, **kwargs):
        result = super().claim(**kwargs)
        if result is not None:
            self.started += 1
            self.started_ms = int(time.time() * 1000)
        return result

    def finish(self, key, attempt, outcome):
        super().finish(key, attempt, outcome)
        if not outcome.get('error'):
            self.published += 1
            self.published_ms = int(time.time() * 1000)


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
    detail_gate = Event()
    detail_gate.set()

    def service(now):
        source = OpenCodeV2Source(registration)
        report = ReportService(selection=SourceSelection(source, "v2", (), source.probe()),
            pricing_provider=Prices(), account_provider=None, account_providers=(),
            cache_repository=CacheRepository(database), config=config, now_ms=now)
        if current_thread().name.startswith('cost-guard-detail'):
            root = report.root_for_session

            def gated_root(key):
                if not detail_gate.wait(15):
                    raise TimeoutError('fixture detail gate not released')
                return root(key)

            report.root_for_session = gated_root
        return report

    def driver():
        reports = service(int(time.time() * 1000))
        return LiveAcquisition(WebWatchCoordinator(selection=reports.selection, report_service=reports,
            config=config, service_factory=service, record_observations=False))

    host = WebHost(config_root, live_factory=driver, jobs=HelpAuditJobs())
    catalog = ControlledCatalog()
    host.live.catalog = catalog
    host.live.details = MeasuredDetails()
    host.start()
    host.publish_ready()
    print(json.dumps(dict(url=host.browser_url())), flush=True)
    events = {}
    try:
        for line in sys.stdin:
            command = json.loads(line)["command"]
            if command == "stop":
                break
            if command == 'detail-hold':
                detail_gate.clear()
            elif command == 'detail-release':
                detail_gate.set()
            elif command == 'detail-metadata':
                with owner.lock:
                    item = next(row for row in owner.sessions if row['id'] == 'ses_fixture_00000')
                    item['title'] = 'Renamed fixture session'
                    item['time']['updated'] += 1
                    owner.events.append(dict(type='session.updated', data=dict(sessionID=item['id'])))
            elif command.startswith("detail-update"):
                count = 10 if command == "detail-update-burst" else 1
                for _ in range(count):
                    owner.active_update(owner.update_ordinal + 1)
                print(json.dumps(dict(ok=True, ordinal=owner.update_ordinal,
                    event_ms=int(time.time() * 1000))), flush=True)
                continue
            elif command == "detail-telemetry":
                with owner.lock:
                    sid = "ses_fixture_00000"
                    request = owner.messages[sid][-1]
                    request["tokens"]["cache"].pop("write", None)
                    request["finish"] = "stop"
                    request["time"]["completed"] = int(time.time() * 1000)
                    owner.active = {}
                    next(row for row in owner.sessions if row["id"] == sid)["time"]["updated"] += 1
                    owner.events.append(dict(type="message.updated", data=dict(sessionID=sid)))
            elif command == "detail-telemetry-recover":
                with owner.lock:
                    sid = "ses_fixture_00000"
                    owner.messages[sid][-1]["tokens"]["cache"]["write"] = 0
                    next(row for row in owner.sessions if row["id"] == sid)["time"]["updated"] += 1
                    owner.events.append(dict(type="message.updated", data=dict(sessionID=sid)))
            elif command == "detail-metrics":
                details = host.live.details
                with details.lock:
                    entries = {key: dict(generation=entry["generation"], due=entry["due"],
                        validated=entry.get("validated"), phase=entry["acquisition"]["phase"])
                        for key, entry in details.histories.items()}
                print(json.dumps(dict(ok=True, entries=entries, source=owner.snapshot(),
                    owner=dict(started=details.started, published=details.published,
                        started_ms=details.started_ms, published_ms=details.published_ms),
                    revision_times=catalog.revision_times, observations=catalog.observations)), flush=True)
                continue
            elif command == "arrival-seed":
                with catalog.lock:
                    for key, root in catalog.roots.items():
                        catalog.rows[key] = SessionUsageRow(key, root.title, "GPT Test", False, Decimal("1"), 1,
                            last_activity_ms=catalog.activity[key], duration_ms=1000, context_tokens=100)
                        catalog.valid[key] = catalog.revisions[key], catalog.clock()
                        catalog.activity_valid[key] = catalog.revisions[key]
            elif command.startswith(("arrival-new-", "arrival-burst-")):
                first = int(command.rsplit("-", 1)[1])
                now = int(time.time() * 1000)
                count = 25 if command.startswith("arrival-burst-") else 1
                with owner.lock:
                    for number in range(first, first + count):
                        key = f"ses_arrival_{number}"
                        owner.sessions.insert(0, dict(id=key, projectID="prj_fixture", title=f"Real source title {number}",
                            location=dict(directory="/fixture/repository"), agent="build",
                            model=dict(providerID="openai", id="gpt-test-1", variant="medium"),
                            time=dict(created=now, updated=now)))
                        owner.messages[key] = []
                        # Alternate announced and externally observed/coalesced
                        # inserts. The latter intentionally has no source SSE.
                        if count == 1 or first % 2 == 0:
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
        detail_gate.set()
        host.close()
        owner.stopping.set()
        server.shutdown()
        server.close_connections()
        server.join_handlers(5)
        server.server_close()
        thread.join(5)


if __name__ == "__main__":
    main()
