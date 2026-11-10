"""Read-only installation source/instance proof with bounded natural worker retirement.

Normal providers are retained. No inference, browser, source mutation or shared
service stop; outputs contain only enum/count/timing evidence, never session data.
"""
import http.client
import json
import multiprocessing
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.web.composition import live_acquisition
from src.web.host import WebHost
from src.web.jobs import ReportJobs


def main():
    baseline = set(threading.enumerate())
    owners = []

    def acquire():
        driver = live_acquisition()
        owners.append(driver)
        return driver

    host = WebHost(ROOT, jobs=ReportJobs(), live_factory=acquire)
    host.benchmark.next_due = float("inf")  # Unrelated public benchmark is outside this check.
    connections = []
    evidence = {"outcome": "FAIL", "normal_providers_retained": True}
    try:
        host.start()

        def request(path, cookie=None, value=None):
            connection = http.client.HTTPConnection("127.0.0.1", host.server.server_port, timeout=3)
            headers = {"Host": host.server.host}
            if cookie:
                headers["Cookie"] = cookie
            if value is not None:
                headers.update({"Origin": host.server.origin, "Content-Type": "application/json"})
            connection.request("POST" if value is not None else "GET", path,
                None if value is None else json.dumps(value), headers)
            response = connection.getresponse()
            if path == "/api/events":
                connections.append(connection)
                return response
            try:
                assert response.status == 200
                result = json.loads(response.read())
                return result, response
            finally:
                connection.close()

        _, response = request("/api/bootstrap", value={"credential": host.server.session.bootstrap()})
        cookie = response.getheader("Set-Cookie").split(";", 1)[0]
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            first, response = request("/api/live", cookie)
            live = first["values"].get("live", {})
            if live.get("state") == "running" and live.get("view"):
                break
            time.sleep(.1)
        else:
            raise RuntimeError("source_generation_observation_timeout")
        assert len(owners) == 1
        selected = owners[0].coordinator.selection.selected
        assert selected in {"v1", "v2"} and live["source_generation"] == selected
        assert response.getheader("X-CG-Instance") == first["instance_id"]
        for _ in range(2):
            stream = request("/api/events", cookie)
            assert stream.status == 200
            for _ in range(32):
                line = stream.readline()
                if line.startswith(b"id: "):
                    assert line.decode().strip().startswith("id: " + first["instance_id"] + ":")
                    break
            else:
                raise RuntimeError("source_generation_stream_identity_missing")
        time.sleep(1.2)
        latest, _ = request("/api/live", cookie)
        assert latest["instance_id"] == first["instance_id"] and latest["sequence"] > first["sequence"]
        assert latest["values"]["live"]["source_generation"] == selected
        assert latest["values"]["live"]["view"]["started_at_ms"] == live["view"]["started_at_ms"]
        evidence.update(selected=selected, live_owners=len(owners), streams_verified=2,
            instance_verified=True, sequence_advanced=True, source_generation_verified=True)
        evidence["outcome"] = "PASS"
    finally:
        for connection in connections:
            connection.close()
        host.close()
        remaining = [t for t in threading.enumerate() if t not in baseline and t.name.startswith("cost-guard-")]
        evidence["initial_remaining_workers"] = len(remaining)
        evidence["initial_remaining_processes"] = len(multiprocessing.active_children())
        started = time.monotonic()
        deadline = started + 45
        for worker in remaining:
            worker.join(max(0, deadline - time.monotonic()))
        alive = [worker for worker in remaining if worker.is_alive()]
        evidence.update(retirement_seconds=round(time.monotonic() - started, 3),
            final_remaining_workers=len(alive), final_remaining_processes=len(multiprocessing.active_children()))
        if alive:
            frames = sys._current_frames()
            evidence["remaining"] = [{"worker": worker.name, "frames": [
                {"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
                for frame in traceback.extract_stack(frames[worker.ident])[-6:]]}
                for worker in alive if worker.ident in frames]
        if alive or evidence["final_remaining_processes"]:
            evidence["outcome"] = "FAIL"
        print(json.dumps(evidence))
        assert not alive and not multiprocessing.active_children(), "source_generation_workers_remaining"


if __name__ == "__main__":
    main()
