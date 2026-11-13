"""Offline scale/fairness measurements; synthetic clocks are not installation latency."""
from pathlib import Path
import json
import statistics
import sys
import tempfile
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.recent_history import RecentHistoryFixture


def main():
    with tempfile.TemporaryDirectory() as tmp:
        fixture = RecentHistoryFixture(tmp, 1_000_000_000)
        began, cpu = time.perf_counter(), time.process_time()
        tracemalloc.start()
        peak_captures = 0
        for index in range(5000, 5100):
            frame = fixture.finish(index)
            assert frame.history_epoch == 0 and frame.history_checked < frame.history_total
            assert frame.recent_finished_cards[-1].session_id == f"root-{index}"
            assert len(fixture.workers.jobs) <= 4
            peak_captures = max(peak_captures, sum(entry.capture is not None for entry in fixture.cards.sessions.values()))
        pending_reads = fixture.source.load_count
        assert pending_reads > 100, "cold historical siblings must make progress alongside new roots"
        frame = fixture.converge()
        assert frame.history_checked == frame.history_total == 5100
        assert len(frame.history_cards) == 5 and not frame.recent_finished_cards
        assert peak_captures <= 10 and fixture.source.load_count < 5400
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        timings = {key: dict(p50=statistics.median(sorted(row[key] for row in fixture.timings)),
            p95=sorted(row[key] for row in fixture.timings)[94]) for key in fixture.timings[0] if
            key.endswith("_ms") and key not in {"source_start_ms", "source_finish_ms"}}
        print(json.dumps(dict(outcome="PASS", roots=5100, new_completions=100, workers=4,
            old_reads_before_release=pending_reads - 100, source_reads=fixture.source.load_count,
            peak_retained_captures=peak_captures, peak_incremental_bytes=peak_bytes,
            elapsed_seconds=time.perf_counter() - began, cpu_seconds=time.process_time() - cpu,
            stages_ms=timings, qualification="Offline synthetic source; tracemalloc enabled; no authenticated HTTP or model calls.")))


if __name__ == "__main__":
    main()
