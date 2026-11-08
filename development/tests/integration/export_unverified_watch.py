"""Actual native adapter/capture/detail exports for the shared hidden DOM probe."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.execution_lifecycle import checkpoint_timeline
from development.tests.fixtures.opencode_v2_service import source_with_current_service
from development.tests.fixtures.watch_runtime import make_service
from src.application.live_projection import project_live
from src.application.projection import project
from src.reports.session_history import SessionHistory
from src.sources.opencode_v2 import OpenCodeV2Source
from src.watch.card_workers import CardWorkers
from src.watch.cards import WatchCards
from src.watch.models import WatchProjection
from src.watch.observers import observe_catalog
from src.watch.running import running_prompts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    with source_with_current_service() as (source, native, registration), tempfile.TemporaryDirectory() as temp:
        checkpoint_timeline(native, assistant=True, usage=True)
        services = []

        def service(now):
            reader = OpenCodeV2Source(registration, timeout_seconds=2)
            services.append(reader)
            return make_service(str(Path(temp) / str(len(services))), reader, now_ms=now)[2]

        workers = CardWorkers(service, workers=1)
        cards, history = WatchCards(workers), SessionHistory()
        frames, details = [], []
        try:
            for index, now in enumerate((10_000, 4_000_000, 8_000_000, 8_100_000)):
                native.active = {'ses_current': {'type': 'running'}} if index == 0 else {}
                if index == 3:
                    native.messages['ses_current'].append({'id': 'final_idle', 'type': 'idle',
                        'outcome': 'failed', 'time': {'created': 8_050_000}})
                cards.catalog(observe_catalog(source))
                entry = cards.sessions['ses_current']
                workers._capture(entry.root, entry.generation, now, entry.snapshot, ())
                for result in workers.drain():
                    if result.phase != 'timing':
                        cards.accept(result, now)
                active, earlier, state = cards.project(now)
                frames.append(project_live(WatchProjection('Watch', 'synthetic', (), now_ms=now,
                    active_cards=active, history_cards=earlier, cards_state=state,
                    history_state=cards.history.state, history_epoch=cards.history.epoch,
                    running=running_prompts(active, state))).to_json())
                report, _ = history.acquire(service(now), 'ses_current')
                details.append(project(report, prompt_details=True).to_json())
            args.output.write_text(json.dumps({'stopped': 'ses_current', 'unverified': True,
                'frames': frames, 'details': details}), encoding='utf-8')
        finally:
            workers.close()
            for reader in services:
                reader.close_reads()
    print(json.dumps({'status': 'ok', 'synthetic': True, 'frames': len(frames)}))


if __name__ == '__main__':
    main()
