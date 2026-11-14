"""Finite synthetic native-source timeline through real Web capture/publication."""
from pathlib import Path
from contextlib import closing
import tempfile

from .subagent_sessions import assistant, incident_source, link
from .watch_runtime import make_service
from src.application.live_projection import project_live
from src.sources.opencode_v2 import OpenCodeV2Source
from src.watch.card_workers import CardWorkers
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import observe_catalog


def stopped_parent_captures():
    with incident_source(end=0) as (source, native), tempfile.TemporaryDirectory() as temp:
        native.messages["ses_current"] = native.messages["ses_current"][:2]
        native.messages["ses_current"][1] = assistant("a1", 3100, None, content=[link(end=0)])
        native.messages["ses_current_child"][1] = assistant("ca", 3400, None)
        native.active = {"ses_current": {"type": "running"}, "ses_current_child": {"type": "running"}}
        registration = source.registration_path
        counter = 0

        def service(now):
            nonlocal counter
            counter += 1
            return make_service(str(Path(temp) / str(counter)),
                OpenCodeV2Source(registration, timeout_seconds=2), now_ms=now)[2]

        with closing(CardWorkers(service, workers=1)) as workers:
            cards = WatchCards(workers, started_at_ms=4500)
            for stage, now in (("initial", 4500), ("stopped", 5000), ("repeated", 10_000),
                               ("terminal", 13_000), ("history", 80_000)):
                if stage == "stopped":
                    native.messages["ses_current"][1] = assistant("a1", 3100, 4000, content=[link()])
                    native.messages["ses_current"][1].update(
                        error={"name": "MessageAbortedError"}, finish="error")
                    native.active.pop("ses_current")
                elif stage == "terminal":
                    native.active = {}
                    native.messages["ses_current_child"][1] = assistant("ca", 3400, 12_000, count=200_000)
                reports = service(now)
                cards.catalog(observe_catalog(reports.source))
                entry = cards.sessions["ses_current"]
                workers._capture(entry.root, entry.generation, now, entry.snapshot,
                    tuple(row.event_id for row in entry.capture.rows) if entry.capture else ())
                for result in workers.drain():
                    if result.phase != "timing":
                        cards.accept(result, now)
                active, history, state = cards.project(now)
                frame = WatchProjection("Watch", "synthetic", (), now_ms=now, active_cards=active,
                    history_cards=history, cards_state=state, history_state=cards.history.state,
                    history_epoch=cards.history.epoch)
                yield stage, reports, cards, frame


def stopped_parent_frames():
    return [project_live(frame).to_json() for _, _, _, frame in stopped_parent_captures()]
