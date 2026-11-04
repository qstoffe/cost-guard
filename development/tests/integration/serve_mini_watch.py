"""Private-stdio synthetic host for the bounded headless Mini browser probe.

Uses shipped HTTP/assets/CSP/session/SSE and disposable Settings. No real source,
provider, browser launch or inference. The one-use URL stays inside the probe pipe.
"""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from threading import Timer

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.watch_summary import summary_watch
from development.tests.fixtures.web_reports import finite_report
from src.application.live_projection import project_live
from src.analysis.timezones import local_day_start_ms
from src.watch.models import WatchRow
from src.watch.running import running_prompts
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "config").mkdir()
        shutil.copyfile(ROOT / "config/default-config.jsonc", root / "config/default-config.jsonc")
        host = WebHost(root, jobs=ReportJobs(target=finite_report))
        timer = Timer(180, host.stop)
        frame = summary_watch()
        now = int(time.time() * 1000)
        frame = replace(frame, now_ms=now, daily_usage=replace(frame.daily_usage,
            day_start_ms=local_day_start_ms('UTC', now_ms=now), observed_at_ms=now))
        base = frame.active_cards[0]
        cards = tuple(replace(base, focal_id=str(index), rows=(WatchRow(base.session_id, base.title,
            replace(base.rows[0].prompt, event_id=str(index), prompt_number=22 + index,
                at_ms=frame.now_ms - duration, duration_ms=duration,
                ccost=Decimal(cost), unresolved_cost=False, cost_estimated=False)),))
            for index, duration, cost in ((1, 600_000, "1.25"), (2, 1_200_000, "2.75")))
        frame = replace(frame, active_cards=cards, running=running_prompts(cards, "observed"))

        def publish(state="running", value=frame):
            value = replace(value, now_ms=int(time.time() * 1000))
            host.events.publish("live", {"state": state, "source_observed_at_ms": value.now_ms,
                "view": project_live(value).to_json()})

        try:
            host.start()
            host.publish_ready()
            publish()
            timer.start()
            print(json.dumps({"url": host.browser_url()}), flush=True)
            for line in sys.stdin:
                command = json.loads(line)["command"]
                if command == "stop":
                    host.stop()
                    print('{"ok":true}', flush=True)
                    break
                if command == "terminal":
                    ended = replace(cards[1], rows=(replace(cards[1].rows[0],
                        prompt=replace(cards[1].rows[0].prompt, in_progress=False, completed_successfully=True)),))
                    current = (cards[0], ended)
                    publish(value=replace(frame, active_cards=current, running=running_prompts(current, "observed")))
                elif command == "empty":
                    publish(value=replace(frame, active_cards=(), running=running_prompts((), "observed")))
                elif command == "recovering":
                    publish(state="recovering")
                elif command == "unavailable":
                    publish(value=replace(frame, active_cards=(), cards_state='unavailable',
                        running=running_prompts((), 'unavailable'), daily_state='retrying', quota_stale=True))
                elif command == "running":
                    publish()
                elif command.startswith('density-'):
                    _, prompts, accounts, *flags = command.split('-')
                    current = tuple(replace(cards[0], focal_id=str(index),
                        title='Long session title ' * 30 if flags else cards[0].title,
                        rows=(replace(cards[0].rows[0], prompt=replace(cards[0].rows[0].prompt,
                            event_id=str(index), prompt_number=index + 23, at_ms=frame.now_ms - 10000 + index)),))
                        for index in range(int(prompts)))
                    quota = replace(frame.quota, accounts=tuple(replace(item, label=f'Subscription {index + 1}')
                        for index, item in enumerate(frame.quota.accounts[:int(accounts)])))
                    warning = 'warning' in flags
                    publish(state='recovering' if warning else 'running', value=replace(frame,
                        active_cards=current, quota=quota, quota_stale=warning,
                        daily_state='retrying' if warning else frame.daily_state,
                        running=running_prompts(current, 'observed')))
                else:
                    raise ValueError("unsupported_probe_command")
                print('{"ok":true}', flush=True)
        finally:
            timer.cancel()
            host.close()


if __name__ == "__main__":
    main()
