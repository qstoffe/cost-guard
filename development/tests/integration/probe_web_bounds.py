"""Finite synthetic replay/slow-tab/resume stress; no UI, source or model calls."""
import json
from pathlib import Path
import sys
import time
import tracemalloc
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.web.events import EventHub, MAX_REPLAY_BYTES
from src.web.security import BrowserSession


def probe():
    tracemalloc.start()
    started = time.perf_counter()
    hub = EventHub("synthetic")
    snapshots = 0
    max_bytes = 0
    payload = "x" * 16384
    for sequence in range(5000):
        hub.publish("live", {"state": "running", "sequence": sequence, "view": payload})
        if sequence % 50 == 0:
            for _ in range(3):
                current = hub.snapshot()
                assert current["values"]["live"]["sequence"] == sequence
                snapshots += 1
        assert len(hub.replay) <= 32 and hub.bytes <= MAX_REPLAY_BYTES
        max_bytes = max(max_bytes, hub.bytes)
    _, stale = hub.read("synthetic:1", timeout=0)
    assert len(stale) == 1 and b"event: resync" in stale[0]
    _, replaced = hub.read("old:5000", timeout=0)
    assert b"event: resync" in replaced[0]
    # A virtual wall/monotonic jump is NOT a real OS suspend/resume observation.
    with patch("src.web.security.time.monotonic", return_value=100):
        session = BrowserSession("synthetic")
        token, _ = session.exchange(session.bootstrap())
    with patch("src.web.security.time.monotonic", return_value=100 + 9 * 3600):
        assert not session.authenticated(f"{session.cookie_name}={token}")
    hub.close("source_changed")
    assert "terminal" in hub.snapshot()["values"]
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return dict(publications=5000, simulated_tabs=3, tab_snapshots=snapshots,
                replay_events=len(hub.replay), max_replay_bytes=max_bytes,
                traced_peak_bytes=peak, elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                slow_client_gap="resync", replaced_instance="resync", virtual_resume_auth="expired",
                physical_suspend_resume="not_run", model_requests=0)


if __name__ == "__main__":
    print(json.dumps(probe()))
