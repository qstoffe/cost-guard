"""Owned synthetic Sessions host using shipped HTTP/auth/assets and real DTO owners.

Stdin commands alter only in-memory synthetic history; no personal source/provider.
"""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from pathlib import Path
import shutil
import sys
from threading import Event, Lock, Thread
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
from src.watch.detail_capture import DetailCapture
from development.tests.fixtures.detail_child import run_owned_fixture


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
        self.catalog = SessionCatalog(clock_ms=lambda: self.service.now_ms, timezone_id=self.service.timezone_id)
        self.unavailable = False
        self.scalar_hold = False
        self.catalog_clock_offset = 0
        self.catalog.clock = lambda: time.monotonic() + self.catalog_clock_offset
        self.live_root = None
        self.parity = False
        self.date_shell = None
        self.quota_fixture = None
        self.observation_lock = Lock()
        self.detail_mode = None
        self.detail_paused = False
        self.detail_clock_offset = 0
        self.details.clock = lambda: time.monotonic() + self.detail_clock_offset
        self.detail_capture = DetailCapture(run_owned_fixture, no_progress_seconds=3)
        self.detail_pool = ThreadPoolExecutor(max_workers=1)
        self.detail_future = None
        self.service.source.source_instance = 'synthetic-detail'
        self.thread = Thread(target=self.run)

    def start(self):
        self.thread.start()

    def run(self):
        while not self.stopping.is_set():
            with self.observation_lock:
                self.observe()
            self.stopping.wait(.25)

    def observe(self):
        observation = observe_catalog(self.service.source, include_archived_revisions=True)
        self.catalog.observe(observation, unavailable=self.unavailable)
        if not self.unavailable:
            self.details.observe_source(observation)
        if self.live_root and not self.unavailable:
            snapshot = self.service.source.snapshots[self.live_root]
            capture, _ = capture_rows(self.service, snapshot.root)
            if capture.catalog_prompt is not None:
                prompt, start, running, ended = capture.catalog_prompt
                self.catalog.observe_prompts(((snapshot.root, snapshot.source_revision, capture.observed_at_ms,
                    prompt, start, running, None, ended),))
        if self.detail_paused:
            pass
        elif self.detail_mode is None:
            self.details.tick(self.service, unavailable=self.unavailable)
        elif self.detail_future is None or self.detail_future.done():
            if self.detail_future is not None:
                self.detail_future.result()
            self.detail_future = self.detail_pool.submit(self.detail_capture.capture,
                self.details, self.service.source, dict(detail_test=self.detail_mode,
                    detail_snapshots=dict(self.service.source.snapshots)), self.service.now_ms,
                unavailable=self.unavailable)
        if not self.scalar_hold and self.catalog.needed():
            self.catalog.tick(self.service)
        frame = summary_watch()
        if self.quota_fixture is not None:
            from src.application.session_quota import source_scope
            self.details.observe_accounts(self.quota_fixture, source_scope(self.service.source), self.service.now_ms)
            frame = replace(frame, quota=self.quota_fixture)
        if self.parity:
            from src.watch.models import WatchCard, WatchRow
            snapshot = self.service.source.snapshots["root-0000"]
            capture, _ = capture_rows(self.service, snapshot.root, fresh=snapshot)
            card = WatchCard(snapshot.root.session_id, snapshot.root.title, "",
                tuple(WatchRow(snapshot.root.session_id, snapshot.root.title, row) for row in capture.rows),
                state="observed", observed_at_ms=self.service.now_ms)
            frame = replace(frame, now_ms=self.service.now_ms, active_cards=(), history_cards=(card,),
                recent_finished_cards=())
        zone = self.service.timezone_id
        if self.date_shell:
            from datetime import datetime
            from src.watch.invocation import invocation_scope
            from src.watch.models import ShellTiming, ToolInvocation, ToolObservation
            zone, elapsed = self.date_shell
            start = int(datetime.fromisoformat('2026-03-29T00:45:20.123Z').timestamp() * 1000)
            identity = invocation_scope(self.service.source.snapshots['root-0000'].root.provenance)
            call = ToolInvocation('fixture-call', 'fixture-observation', 'command:\npython fixture_task.py',
                'Sensitive argument/value redacted.', 'shell', start,
                shell_timing=ShellTiming('execution', 3_220_000, 1_200_000, 2))
            tool = ToolObservation(running_tool='shell', running_ms=elapsed, running_invocations=(call,),
                running_invocation_count=1)
            base = frame.active_cards[0]
            card = replace(base, session_id='root-0000', invocation_verified=True, activity_scope=identity,
                rows=(replace(base.rows[0], session_id='root-0000', tool=tool),),
                focal_id=base.rows[0].prompt.event_id)
            frame = replace(frame, now_ms=start + elapsed, active_cards=(card,))
        view = project_live(frame, zone).to_json()
        self.publish("live", dict(state="running", view=view, source_observed_at_ms=self.service.now_ms,
            catalog_hint=self.catalog.live_hint(), detail_hints=self.details.live_hints()))

    def close(self):
        self.stopping.set()
        self.detail_capture.cancel()
        self.thread.join(5)
        self.detail_pool.shutdown(wait=True, cancel_futures=True)
        if self.thread.is_alive():
            raise RuntimeError("fixture_shutdown_timeout")


def main():
    if sys.platform == 'win32':
        import multiprocessing
        executable = Path(sys.executable).with_name('pythonw.exe')
        if not executable.is_file():
            raise RuntimeError('fixture_gui_interpreter_unavailable')
        multiprocessing.set_executable(str(executable))
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
    source.snapshots = {key: replace(value, complete=True) for key, value in source.snapshots.items()}
    service = report_service(owner, source, now_ms=10_000_000)
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
                source.snapshots["root-0120"] = replace(make_root_snapshot(120, 1, month_start_ms=1000), complete=True)
            elif command.startswith("date-shell-"):
                cases = {"date-shell-open": ("Europe/Stockholm", 60_000),
                         "date-shell-tick": ("Europe/Stockholm", 61_000),
                         "date-shell-zone": ("America/New_York", 62_000),
                         "date-shell-clear": None}
                with host.live.observation_lock:
                    host.live.date_shell = cases[command]
            elif command.startswith("quick-aborts"):
                from development.tests.fixtures.quick_aborts import quick_aborts
                from development.tests.fixtures.claude_alias import catalog
                snapshot = quick_aborts(second_model=command != "quick-aborts-unknown",
                    running=command == "quick-aborts-running")
                with host.live.observation_lock:
                    source.snapshots = {"root": snapshot}
                    service.pricing_provider.catalog = catalog()
                    service.invalidate_roots(("root",))
                    with host.live.details.lock:
                        if "root" in host.live.details.histories:
                            host.live.details.histories["root"]["due"] = 0
                    host.live.observe()
            elif command.startswith("quota-"):
                if command == "quota-observe":
                    print(json.dumps(dict(ok=True, history_reads=source.load_count,
                        leases=len(host.live.details.leases))), flush=True)
                    continue
                from development.tests.fixtures.session_quota import configure
                with host.live.observation_lock:
                    configure(host.live, command)
            elif command.startswith("running-"):
                from development.tests.fixtures.catalog_running import configure
                with host.live.observation_lock:
                    configure(host.live, command)
            elif command == "parity-observe":
                print(json.dumps(dict(ok=True, source_instance="synthetic-month",
                    roots=len(source.snapshots), history_reads=source.load_count,
                    metrics=dict(host.live.catalog.metrics))), flush=True)
                continue
            elif command.startswith("parity-"):
                from development.tests.fixtures.catalog_prompt_activity import finished_snapshot, at
                service.now_ms = at("02:00:00")
                service.config["timezone"] = "UTC"
                if command == "parity-source":
                    source.snapshots = {"root-0000": finished_snapshot()}
                elif command == "parity-new-prompt":
                    source.snapshots["root-0000"] = replace(finished_snapshot(finished=at("01:52:00")),
                        source_revision=command)
                else:
                    snapshot = source.snapshots["root-0000"]
                    root = replace(snapshot.root, updated_at_ms=at("01:59:00"),
                        archived_at_ms=at("01:52:00") if command == "parity-archive" else None)
                    sessions = (root,)
                    if command == "parity-child-metadata":
                        sessions += (replace(root, session_id="child", parent_session_id=root.session_id),)
                    source.snapshots[root.session_id] = replace(snapshot, root=root, sessions=sessions,
                        source_revision=command)
                host.live.parity = True
                host.live.catalog.observe(observe_catalog(source, include_archived_revisions=True),
                    timezone_id=service.timezone_id)
                host.live.scalar_hold = False
            elif command.startswith("detail-values-"):
                from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot
                from src.domain import TokenUsage
                snapshot = make_uncompacted_snapshot(running=True)
                if command in ("detail-values-partial", "detail-values-correction"):
                    snapshot = replace(snapshot, invocations=tuple(replace(item,
                        tokens=TokenUsage(input=20, known_fields=("input",)))
                        if item.invocation_id == "i_next" else item for item in snapshot.invocations),
                        complete=command == "detail-values-correction")
                if command == "detail-values-epoch":
                    source.observation_epoch = "different-epoch"
                source.snapshots["root"] = replace(snapshot, source_revision=command,
                    root=replace(snapshot.root, active=True, updated_at_ms=service.now_ms))
                with host.live.details.lock:
                    if "root" in host.live.details.histories:
                        host.live.details.histories["root"]["due"] = 0
            elif command in ("activity-source", "activity-update", "activity-correction"):
                from development.tests.fixtures.session_activity import activity_snapshot
                snapshot = activity_snapshot(60 if command == "activity-source" else 61)
                if command == "activity-correction":
                    messages = tuple(replace(message, parts=tuple(replace(part, data={
                        **part.data, "state": {**part.data["state"], "input": {"filePath": "src/corrected.py"},
                                             "error": "EACCES"}})
                        if part.data.get("callID") == "physical-0000" else part for part in message.parts))
                        for message in snapshot.messages)
                    snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts))
                source.snapshots["root"] = replace(snapshot, source_revision=command,
                    root=replace(snapshot.root, active=command != "activity-correction",
                                 updated_at_ms=service.now_ms))
                source.skill_origins_for_session = lambda _: {"auto-github-api": "custom"}
                with host.live.details.lock:
                    if "root" in host.live.details.histories:
                        host.live.details.histories["root"]["due"] = 0
            elif command.startswith("model-details-"):
                from development.tests.fixtures.model_details import scoped_snapshot
                with host.live.observation_lock:
                    if command == "model-details-source":
                        cases = ("one", "child-same", "child-effort", "child-model", "main-models",
                                 "main-efforts", "separate-efforts", "running-child", "unknown-main")
                        source.snapshots = {f"details-{case}": scoped_snapshot(case, f"details-{case}") for case in cases}
                        from development.tests.fixtures.model_subagent_history import native_tree
                        for name, effort in (("native-same", "high"), ("native-effort", "max")):
                            source.snapshots[f"details-{name}"] = scoped_snapshot(name, f"details-{name}",
                                native_tree(child_effort=effort, day_offset=0))
                    else:
                        case = command.removeprefix("model-details-")
                        source.snapshots["details-child-same"] = scoped_snapshot(case, "details-child-same")
                    host.live.catalog.observe(observe_catalog(source, include_archived_revisions=True))
                    with host.live.details.lock:
                        for history in host.live.details.histories.values():
                            history["due"] = 0
            elif command in ("models-source", "models-update"):
                from development.tests.fixtures.sessions_models import MODELS_DAY_START, model_fixture_prices, models_source
                with host.live.observation_lock:
                    service.now_ms = MODELS_DAY_START + 3_600_000
                    models_source(source, updated=command == "models-update")
                    service.catalog = service.comparison_pricing_catalog = model_fixture_prices(
                        service.pricing_provider.get_catalog(), source)
                    host.live.catalog.observe(observe_catalog(source, include_archived_revisions=True))
            elif command == "period-source":
                now, day = 1_794_571_200_000, 86_400_000  # 2026-11-13 12:00 UTC
                service.now_ms = now
                activities = ([now - 1000] * 30 + [now - 3 * day] * 40 +
                    [now - 20 * day] * 50 + [now - (31 + index % 699) * day for index in range(4880)])
                samples = SyntheticMonthSource(5000, 1, month_start_ms=now - 730 * day)
                values = {}
                for index, ((key, snapshot), activity) in enumerate(zip(samples.snapshots.items(), activities)):
                    snapshot = make_root_snapshot(index, 2 if index == 2 else 1,
                        month_start_ms=activity - (1300 if index == 2 else 300) - index * 60_000)
                    root = replace(snapshot.root, updated_at_ms=activity)
                    events = tuple(replace(event, metadata={**event.metadata,
                        "variant": "high" if index == 1 or index == 2 and number else "default"})
                        for number, event in enumerate(snapshot.events))
                    values[key] = replace(snapshot, root=root, sessions=(root,), events=events,
                        source_revision=f"period-{index}", complete=True)
                with host.live.observation_lock:
                    source.snapshots = values
                    # This scenario starts from a cold 5,000-root catalog, not
                    # 4,880 live arrivals in the preceding scenario's source.
                    host.live.catalog = SessionCatalog(clock_ms=lambda: service.now_ms,
                        timezone_id=service.timezone_id)
                    host.live.catalog.observe(observe_catalog(source, include_archived_revisions=True))
                    host.live.scalar_hold = False
            elif command == "period-empty":
                service.now_ms += 2 * 86_400_000
            elif command == 'detail-quiet-stall':
                with host.live.observation_lock, host.live.details.lock:
                    host.live.detail_paused = True
                    entry = host.live.details.histories['root-0000']
                    entry['attempt'] = None
                    entry['acquisition'].update(phase='queued', changed_at=host.live.details.clock() - 120)
            elif command == 'detail-quiet-recover':
                with host.live.observation_lock:
                    host.live.detail_clock_offset += 31
                    source.snapshots['root-0000'] = replace(
                        make_root_snapshot(0, 1002, month_start_ms=1000), source_revision='quiet-fresh', complete=True)
                    host.live.detail_paused = False
            elif command in ('detail-blocked', 'detail-recover', 'detail-progress', 'detail-delayed'):
                host.live.detail_mode = {'detail-blocked': 'blocked', 'detail-recover': 'fast',
                    'detail-progress': 'progress', 'detail-delayed': 'delayed'}[command]
            elif command == 'detail-observe':
                lane = host.live.detail_capture
                print(json.dumps(dict(ok=True, started=lane.started_count, retired=lane.retired_count,
                    active=lane.process is not None, metrics=lane.last_metrics,
                    entries=[dict(key=key, **host.live.details.acquisition_status(entry))
                        for key, entry in host.live.details.histories.items()])), flush=True)
                continue
            elif command.startswith('catalog-idle-'):
                from development.tests.fixtures.sessions_idle import configure
                with host.live.observation_lock:
                    result = configure(host.live, command)
                print(json.dumps(result), flush=True)
                continue
            elif command.startswith('catalog-'):
                host.live.scalar_hold = True
                catalog = host.live.catalog
                if command == 'catalog-navigation-source':
                    with host.live.observation_lock:
                        source.snapshots = SyntheticMonthSource(324, 1, month_start_ms=1000).snapshots
                        catalog = host.live.catalog = SessionCatalog(clock_ms=lambda: service.now_ms,
                            timezone_id=service.timezone_id)
                        catalog.observe(observe_catalog(source, include_archived_revisions=True))
                        catalog.tick(service)  # Establish dependencies with no interested roots.
                if command == 'catalog-navigation-arrive':
                    for number in (324, 325):
                        source.snapshots[f'root-{number:04d}'] = make_root_snapshot(number, 1, month_start_ms=1000)
                    source.snapshots['root-0000'] = replace(source.snapshots['root-0000'], source_revision='hot')
                    catalog.observe(observe_catalog(source, include_archived_revisions=True))
                if command == 'catalog-navigation-observe':
                    print(json.dumps(dict(ok=True, roots=len(catalog.roots), qualified=len(catalog.valid),
                        arrivals_qualified=sum(key in catalog.valid for key in ('root-0324', 'root-0325')),
                        metrics=dict(catalog.metrics))), flush=True)
                    continue
                if command == 'catalog-large':
                    source.snapshots = SyntheticMonthSource(3217, 1, month_start_ms=1000).snapshots
                    source.snapshots = {key: replace(snapshot, root=replace(snapshot.root,
                        created_at_ms=1000 + index * 1000, updated_at_ms=2000 + index * 1000))
                        for index, (key, snapshot) in enumerate(source.snapshots.items())}
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
                        catalog.activity_valid.clear()
                    if command in ('catalog-partial', 'catalog-index', 'catalog-period-warm-history',
                                   'catalog-navigation-partial', 'catalog-navigation-finish'):
                        for number, (key, root) in enumerate(catalog.roots.items()):
                            if command == 'catalog-partial' and number >= 428:
                                break
                            if command == 'catalog-navigation-partial' and number >= 20:
                                break
                            if command == 'catalog-navigation-finish' and (number < 20 or number >= 324):
                                continue
                            if command == 'catalog-period-warm-history' and key in catalog.valid:
                                continue
                            catalog.rows[key] = SessionUsageRow(key, root.title, f'Model {number:04}', False,
                                Decimal(number) / 1000, number, duration_ms=number * 1000, context_tokens=number,
                                last_activity_ms=catalog.activity[key])
                            catalog.valid[key] = catalog.revisions[key], catalog.clock()
                            catalog.activity_valid[key] = catalog.revisions[key]
                            catalog.failures.pop(key, None)
                            catalog.failure_counts.pop(key, None)
                            catalog.failure_reasons.pop(key, None)
                    if command == 'catalog-page-cold':
                        keys = sorted(catalog.roots, reverse=True)[25:50]
                        for key in keys:
                            catalog.valid.pop(key, None)
                            catalog.activity_valid.pop(key, None)
                    if command == 'catalog-page-four-partial':
                        keys = sorted(catalog.roots, reverse=True)[75:100]
                        for key in keys[13:]:
                            catalog.valid.pop(key, None)
                            catalog.activity_valid.pop(key, None)
                            catalog.failures[key] = catalog.revisions[key], False
                            catalog.failure_counts[key] = 5
                            catalog.failure_reasons[key] = 'connection_timeout'
                    if command == 'catalog-churn':
                        for key in [key for key in catalog.roots if key not in catalog.valid and key != 'root-0000'][:20]:
                            number = int(key.split('-')[1])
                            catalog.rows[key] = SessionUsageRow(key, catalog.roots[key].title, f'Model {number:04}', False,
                                Decimal(number) / 1000, number, duration_ms=number * 1000, context_tokens=number,
                                last_activity_ms=catalog.activity[key])
                            catalog.valid[key] = catalog.revisions[key], catalog.clock()
                            catalog.activity_valid[key] = catalog.revisions[key]
                if command == 'catalog-navigation-resume':
                    host.live.scalar_hold = False
            elif command in ("fail", "recover"):
                host.live.unavailable = command == "fail"
            elif command == "end":
                source.snapshots["root-0000"] = replace(make_root_snapshot(0, 1002, month_start_ms=1000),
                    source_revision="ended", complete=True)
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
                with host.live.observation_lock:
                    if command == "live-resume":
                        # A recovered capture must be newer than the outage cutoff.
                        service.now_ms += 1000
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
