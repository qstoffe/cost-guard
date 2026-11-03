"""Bounded read-only Mini projection probe against the real installed source.

No HTTP/native UI/inference or OpenCode stop. Direct acquisition avoids conflating
source correctness with the separate WebHost ten-second shutdown deadline.
"""
from decimal import Decimal
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.application.live_projection import project_live
from src.web.composition import live_acquisition


def main():
    started = time.monotonic()
    driver = live_acquisition()
    checked = 0
    try:
        deadline = started + 90
        while time.monotonic() < deadline:
            frame = driver.tick()
            if driver.terminal:
                raise RuntimeError("source_terminal")
            if frame is None:
                time.sleep(.25)
                continue
            wire = project_live(frame).to_json()
            history = wire['history_cards']
            assert len(history) <= 5 and len({card['session_id'] for card in history}) == len(history)
            finishes = []
            for card in history:
                assert len(card['rows']) == 1
                prompt = card['rows'][0]['prompt']
                assert not prompt['in_progress']
                finished = prompt['completed_at_ms']
                finishes.append(finished or 0)
                if finished is None:
                    assert prompt['display']['finished_clock'] == '—'
            assert finishes == sorted(finishes)
            running = wire["running"]
            expected = {(card["session_id"], row["prompt"]["event_id"]): row
                for card in wire["active_cards"] for row in card["rows"]
                if row["prompt"]["event_id"] == card["focal_id"] and row["prompt"]["in_progress"]
                    and not row["prompt"]["is_compaction"]}
            if running["count"] is not None:
                assert running["count"] == len(expected)
                assert Decimal(running["ccost"]) == sum((Decimal(row["prompt"]["ccost"]) for row in expected.values()), Decimal(0))
                assert running["duration_ms"] == max((row["watch_duration_ms"] for row in expected.values()), default=None)
                checked += 1
            if checked >= 3 and wire["daily_usage"] is not None:
                accounts = (wire["accounts"] or {}).get("accounts", [])
                print(json.dumps({"source": frame.source_label, "coherent_publications_checked": checked,
                    "running_count": running["count"], "running_complete": running["complete"],
                    "running_cost_complete": not running["unresolved_cost"], "accounts": len(accounts),
                    "primary_period_costs_available": sum(item["primary"]["cost"] is not None for item in accounts),
                    "finished_history_cards": len(history), "known_finish_times": sum(bool(value) for value in finishes),
                    "single_acquisition_owner": True, "seconds": round(time.monotonic() - started, 3)}))
                break
            time.sleep(.25)
        else:
            raise RuntimeError("mini_source_timeout")
    finally:
        closing = time.monotonic()
        driver.close()
        print(json.dumps({"owned_acquisition_closed": True, "close_seconds": round(time.monotonic() - closing, 3),
            "shared_opencode_untouched": True}))


if __name__ == "__main__":
    main()
