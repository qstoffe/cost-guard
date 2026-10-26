"""Opt-in read-only real-installation probe; no GUI, model inference or service stop.

Only this process's Web host is started/stopped. Normal disposable Cost Guard cache
may be populated. Output is bounded status/count evidence, never history or secrets.
"""
import http.client
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.web.host import WebHost
from src.web.lifecycle import control


def probe():
    owner = WebHost(ROOT)
    cookie = csrf = None

    def request(method, route, value=None):
        headers = {"Origin": owner.server.origin}
        if cookie:
            headers.update({"Cookie": cookie, "X-CG-CSRF": csrf})
        body = None
        if value is not None:
            body = json.dumps(value)
            headers["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection("127.0.0.1", owner.server.server_port, timeout=3)
        try:
            connection.request(method, route, body, headers)
            response = connection.getresponse()
            payload = json.loads(response.read(8 * 1024 * 1024 + 1))
            if response.status not in {200, 202}:
                raise RuntimeError("probe_request_failed")
            return payload, response.getheader("Set-Cookie")
        finally:
            connection.close()

    try:
        owner.start()
        owner.publish_ready()
        session, handoff = request("POST", "/api/bootstrap", {"credential": owner.server.session.bootstrap()})
        cookie, csrf = handoff.split(";", 1)[0], session["csrf"]
        initial, _ = request("GET", "/api/status")
        if initial["lifecycle"]["instance"] != owner.nonce:
            raise RuntimeError("probe_identity_failed")
        job, _ = request("POST", "/api/reports", {"kind": "sessions", "session_limit": 1})
        deadline = time.monotonic() + 125
        while True:
            result, _ = request("GET", "/api/jobs/" + job["id"])
            if result["status"] in {"complete", "failed", "cancelled"}:
                break
            if time.monotonic() > deadline:
                raise RuntimeError("probe_report_timeout")
            time.sleep(0.1)
        if result["status"] != "complete" or result["result"]["source"]["status"] != "acquired":
            raise RuntimeError("probe_source_unavailable")
        state = {"port": owner.server.server_port, "control": owner.control,
                 "nonce": owner.nonce, "build": owner.identity()["build"]}
        control(state, "stop")
        if not owner.stopped.wait(10):
            raise RuntimeError("probe_shutdown_timeout")
        if owner.failure:
            raise RuntimeError("probe_host_failed")
        return {"http": "ready", "source": "acquired", "job": result["status"],
                "authenticated_stop": "passed", "owned_thread_stopped": owner.stopped.is_set(),
                "source_guard": owner.guard.status, "native_gui": "not_run", "model_requests": 0}
    finally:
        owner.close()


if __name__ == "__main__":
    try:
        print(json.dumps(probe()))
    except Exception as error:
        print(json.dumps({"probe": "failed", "error_type": type(error).__name__}))
        raise SystemExit(1)
