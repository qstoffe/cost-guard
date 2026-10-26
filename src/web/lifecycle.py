"""Serialized detached launch/restart protocol shared by native launchers."""
from dataclasses import dataclass
import http.client
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import webbrowser

from .instance_state import InstanceStore, SCHEMA
from .process_identity import InstanceConflict, process_identity, terminate_owned

GRACE_SECONDS = 10
START_SECONDS = 15
GUI_MODULES = {"src.web.native_windows", "src.web.native_macos"}


def control(state, action):
    connection = http.client.HTTPConnection("127.0.0.1", state["port"], timeout=1)
    try:
        method = "GET" if action == "status" else "POST"
        connection.request(method, "/control/" + action,
                           headers={"X-CG-Control": state["control"], "Content-Length": "0"})
        response = connection.getresponse()
        if response.status != 200:
            raise InstanceConflict("instance_control_conflict")
        data = response.read(4097)
        if len(data) > 4096:
            raise InstanceConflict("instance_control_conflict")
        value = json.loads(data)
        if (value.get("nonce") != state["nonce"] or value.get("schema") != SCHEMA
                or value.get("build") != state["build"]):
            raise InstanceConflict("instance_control_conflict")
        return value
    except (ValueError, TypeError, AttributeError) as exc:
        raise InstanceConflict("instance_control_conflict") from exc
    finally:
        connection.close()


def stop_existing(store, state, *, grace=GRACE_SECONDS):
    actual = process_identity(state["pid"])
    if actual is None or actual != state["process"]:
        # Stale PID, including reuse: never contact/kill that process or its port.
        store.remove(state["nonce"])
        return
    try:
        control(state, "stop")
    except (OSError, http.client.HTTPException):
        pass  # Unresponsive, but private recorded birth identity still must match.
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if process_identity(state["pid"]) != state["process"]:
            store.remove(state["nonce"])
            return
        time.sleep(0.05)
    # Windows retains and checks the exact kernel process handle before termination.
    # Linux uses pidfd; platforms lacking an atomic handle refuse forced termination.
    terminate_owned(state["pid"], state["process"])
    deadline = time.monotonic() + 3
    while process_identity(state["pid"]) == state["process"]:
        if time.monotonic() >= deadline:
            raise InstanceConflict("instance_stop_timeout")
        time.sleep(0.05)
    store.remove(state["nonce"])


def spawn_detached(root, store, nonce, gui_module):
    if gui_module not in GUI_MODULES:
        raise InstanceConflict("gui_unavailable")
    entry = Path(root).resolve(strict=True) / "cost-guard-web.py"
    arguments = [sys.executable, str(entry), "--managed", nonce, gui_module]
    options = {"cwd": str(store.directory), "stdin": subprocess.DEVNULL,
               "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(arguments, **options)


@dataclass(frozen=True)
class LaunchResult:
    instance: str
    browser_opened: bool
    coalesced: bool


def launch(root, gui_module, *, opener=webbrowser.open):
    """Intentional invocation restarts; overlapping clicks reuse the ready winner.

    Only approved native adapters are accepted; a missing GUI can never leave a
    successfully advertised background host. OS entrypoints own native preflight.
    """
    invoked_ns = time.time_ns()
    store = InstanceStore(root)
    with store.lock(timeout=35):
        state = store.read()
        coalesced = bool(state and state["ready_ns"] >= invoked_ns)
        if coalesced:
            if process_identity(state["pid"]) != state["process"] or not control(state, "status")["ready"]:
                raise InstanceConflict("instance_not_ready")
        else:
            if state:
                stop_existing(store, state)
            nonce = secrets.token_hex(16)
            child = spawn_detached(root, store, nonce, gui_module)
            # Retain exact child's handle/identity for failed-start cleanup only.
            birth = process_identity(child.pid)
            deadline = time.monotonic() + START_SECONDS
            try:
                while True:
                    status = child.poll()
                    if status == 3:
                        raise InstanceConflict("tray_unavailable")
                    if status is not None:
                        raise InstanceConflict("gui_or_server_start_failed")
                    state = store.read()
                    if state and state["nonce"] == nonce:
                        if state["pid"] != child.pid or state["process"] != birth:
                            raise InstanceConflict("instance_start_conflict")
                        try:
                            if control(state, "status").get("ready"):
                                break
                        except (OSError, http.client.HTTPException):
                            pass  # Brief socket readiness race, still bounded by deadline.
                    if time.monotonic() >= deadline:
                        raise InstanceConflict("instance_start_timeout")
                    time.sleep(0.05)
            except BaseException:
                # Popen's own process handle is not an arbitrary PID; no unknown process kill.
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=3)
                store.remove(nonce)
                raise
        opened = control(state, "open")
        url = opened.get("url", "")
        prefix = f"http://127.0.0.1:{state['port']}/#bootstrap="
        if not isinstance(url, str) or not url.startswith(prefix) or len(url) > len(prefix) + 128:
            raise InstanceConflict("instance_control_conflict")
        try:
            browser_opened = bool(opener(url))
        except Exception:
            browser_opened = False  # Server stays managed; native icon can retry Open.
        return LaunchResult(state["nonce"], browser_opened, coalesced)
