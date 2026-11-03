"""Six native V2 roots through isolated captures and the four-slot card scheduler."""
import copy
from itertools import count
from pathlib import Path
import tempfile
from contextlib import ExitStack

from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.watch_runtime import make_service
from src.application.live_projection import project_live
from src.sources.opencode_v2 import OpenCodeV2Source
from src.watch.card_workers import CardWorkers
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import observe_catalog
from src.watch.running import running_prompts


def failed_resume(*, outcome="failed", error=None):
    return [
        {"id": "resume", "type": "synthetic", "text": "resume existing work",
         "time": {"created": 6000}},
        {"id": "system", "type": "system", "text": "provider unavailable",
         "time": {"created": 6100}},
        {"id": "terminal", "type": "idle", "outcome": outcome, "error": error,
         "time": {"created": 6200}},
    ]


class PreResponseWatch:
    stopped = "ses_5"

    def __enter__(self):
        self.stack = ExitStack()
        self.temp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.source, self.native, self.registration = self.stack.enter_context(source_with_current_service())
        session = self.native.sessions[0]
        messages = self.native.messages["ses_current"]
        assistant = messages[1]
        assistant.pop("finish")
        assistant["time"].pop("completed")
        assistant["content"] = []
        assistant["model"] = {"providerID": "github-copilot", "id": "gpt-test", "variant": "low"}
        self.native.sessions = []
        self.native.messages = {}
        for index in range(6):
            root = copy.deepcopy(session)
            root["id"] = f"ses_{index}"
            root["title"] = f"Synthetic root {index}"
            self.native.sessions.append(root)
            self.native.messages[root["id"]] = copy.deepcopy(messages)
        self.native.active = {root["id"]: {"type": "running"} for root in self.native.sessions}
        target = self.native.messages[self.stopped][1]
        target.pop("tokens")
        target.pop("cost")
        self.counter = count()
        self.workers = CardWorkers(self.service)
        self.stack.callback(self.workers.close)
        self.cards = WatchCards(self.workers)
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def service(self, now):
        key = next(self.counter)
        source = OpenCodeV2Source(self.registration, timeout_seconds=2)
        return make_service(str(Path(self.temp) / str(key)), source, now_ms=now)[2]

    def capture(self, now, *, churn=False):
        if churn:
            for root in self.native.sessions[:5]:
                root["time"]["updated"] += 1
        self.cards.catalog(observe_catalog(self.source))
        self.cards.tick(now)
        for future in tuple(self.workers.jobs.values()):
            future.result(timeout=10)
        for result in self.workers.drain():
            if result.phase != "timing":
                self.cards.accept(result, now)

    def export(self, now):
        active, history, state = self.cards.project(now)
        return project_live(WatchProjection("Watch", "synthetic V2", (), now_ms=now,
            active_cards=active, history_cards=history, cards_state=state,
            running=running_prompts(active, state))).to_json()

    def row(self, now):
        active, history, _ = self.cards.project(now)
        return next(row.prompt for card in active + history
                    if card.session_id == self.stopped for row in card.rows)

    def cold_capture(self, now):
        cold = WatchCards(self.workers)
        cold.catalog(observe_catalog(self.source))
        entry = cold.sessions[self.stopped]
        self.workers._capture(entry.root, entry.generation, now, None, ())
        for result in self.workers.drain():
            if result.phase != "timing":
                cold.accept(result, now)
        return cold
