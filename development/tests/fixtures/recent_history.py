"""Controlled canonical source → bounded capture → Live fixture; no native data."""
from dataclasses import replace
from time import perf_counter

from development.tests.fixtures.history_acquisition import CaptureWorkers
from development.tests.fixtures.synthetic_month import SyntheticMonthSource, make_root_snapshot
from development.tests.fixtures.watch_runtime import make_service
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import observe_catalog


class DelayedArchiveWorkers(CaptureWorkers):
    def __init__(self, service):
        super().__init__(service)
        self.delayed = True

    def drain(self):
        held = self.jobs.pop("root-0000", None) if self.delayed else None
        results = super().drain()
        if held is not None:
            self.jobs["root-0000"] = held
        return results


class RecentHistoryFixture:
    def __init__(self, directory, started_at_ms, roots=5000):
        self.started_at_ms = started_at_ms
        self.now_ms = started_at_ms + 100_000
        self.source = SyntheticMonthSource(roots, 1, month_start_ms=1000)
        self.source.snapshots = {key: replace(value, complete=True) for key, value in self.source.snapshots.items()}
        self.service = make_service(directory, self.source, now_ms=self.now_ms)[2]
        self.workers = DelayedArchiveWorkers(self.service)
        self.cards = WatchCards(self.workers, started_at_ms=started_at_ms)
        self.cards.catalog(observe_catalog(self.source))
        self.cards.tick(self.now_ms)
        self.timings = []

    def finish(self, index, prompts=1):
        began = perf_counter()
        at = self.started_at_ms + 1000 + index
        snapshot = make_root_snapshot(index, prompts, month_start_ms=at - index * 60_000)
        old = self.source.snapshots.get(snapshot.root.session_id)
        if old is not None:
            snapshot = replace(snapshot, root=replace(snapshot.root, created_at_ms=old.root.created_at_ms))
        snapshot = replace(snapshot, source_revision=f"recent-{index}-{prompts}", complete=True)
        self.source.snapshots[snapshot.root.session_id] = snapshot
        visible = perf_counter()
        self.cards.catalog(observe_catalog(self.source))
        detected = perf_counter()
        self.cards.tick(self.now_ms)
        admitted = perf_counter()
        assert snapshot.root.session_id in self.workers.jobs
        assert len(self.workers.jobs) <= 4
        self.cards.tick(self.now_ms)
        captured = perf_counter()
        frame = self.frame()
        published = perf_counter()
        self.timings.append(dict(source_start_ms=at + (prompts - 1) * 1000,
            source_finish_ms=at + (prompts - 1) * 1000 + 300,
            source_ms=(visible - began) * 1000, detection_ms=(detected - visible) * 1000,
            admission_ms=(admitted - detected) * 1000, capture_ms=(captured - admitted) * 1000,
            projection_ms=(published - captured) * 1000, total_ms=(published - began) * 1000))
        return frame

    def frame(self):
        active, history, state = self.cards.project(self.now_ms)
        proof = self.cards.history
        return WatchProjection("Watch", "controlled source", (), active_cards=active,
            history_cards=history, recent_finished_cards=self.cards.recent.project(self.cards, self.now_ms),
            cards_state=state, history_state=proof.state, history_scope=proof.scope,
            history_epoch=proof.epoch, history_checked=proof.checked, history_total=proof.total,
            now_ms=self.now_ms, watch_started_at_ms=self.started_at_ms)

    def converge(self):
        self.workers.delayed = False
        for _ in range(len(self.source.snapshots) + 10):
            self.cards.tick(self.now_ms)
            frame = self.frame()
            if frame.history_state == "observed":
                return frame
        raise AssertionError("cold archive did not converge")
