"""Explicit opt-in Windows UI probe; opens only this checkout's Beta browser/tray.

Run with --allow-native-ui only with current user approval. No model/provider calls,
downloads or service changes. Never included in automatic Quick/Full test suites.
"""
import ctypes as c
from ctypes import wintypes as w
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.web.host import WebHost
from src.web.instance_state import InstanceStore
from src.web.lifecycle import control, launch, stop_existing
from src.web.native_windows import WindowsHost
from src.web.process_identity import process_identity
from src.web.win32_tray import OPEN, EXIT, _bind
from src.web.win32_tray import Tray
from src.web.windows_launch import launch_windows


def until(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise RuntimeError("native_probe_timeout")


def window(pid):
    user = c.WinDLL("user32", use_last_error=True)
    callback = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    enum = _bind(user, "EnumWindows", w.BOOL, [callback, w.LPARAM])
    get_pid = _bind(user, "GetWindowThreadProcessId", w.DWORD, [w.HWND, c.POINTER(w.DWORD)])
    title = _bind(user, "GetWindowTextW", c.c_int, [w.HWND, w.LPWSTR, c.c_int])
    matches = []

    def visit(hwnd, _):
        found = w.DWORD()
        get_pid(hwnd, c.byref(found))
        text = c.create_unicode_buffer(128)
        title(hwnd, text, 128)
        if found.value == pid and text.value == "Cost Guard Web Beta":
            matches.append(hwnd)
        return True

    enum(callback(visit), 0)
    return matches[0] if len(matches) == 1 else None


def command(pid, identifier):
    hwnd = until(lambda: window(pid))
    user = c.WinDLL("user32", use_last_error=True)
    post = _bind(user, "PostMessageW", w.BOOL, [w.HWND, w.UINT, w.WPARAM, w.LPARAM])
    if not post(hwnd, 0x111, identifier, 0):
        raise RuntimeError("native_command_failed")


def adapter_probe():
    """Real native menu handles/message delivery, failed Open and owner-loss cleanup."""
    owner = WebHost(ROOT)
    adapter = WindowsHost()
    tray = adapter.tray
    count = _bind(tray.user, "GetMenuItemCount", c.c_int, [w.HMENU])
    text = _bind(tray.user, "GetMenuStringW", c.c_int,
                 [w.HMENU, w.UINT, w.LPWSTR, c.c_int, w.UINT])
    labels = []
    for index in range(count(tray.menu)):
        buffer = c.create_unicode_buffer(64)
        text(tray.menu, index, buffer, 64, 0x400)
        labels.append(buffer.value)
    assert labels == ["Open Cost Guard", "Exit Cost Guard"]
    notifications = []
    failures = []
    original = tray.browser_failed

    def notice():
        notifications.append("browser_open_failed")
        original()

    def signals():
        try:
            until(lambda: owner.ready)
            command(os.getpid(), OPEN)
            until(lambda: notifications)
            assert not owner.stopping.is_set()
            command(os.getpid(), EXIT)
        except BaseException as error:
            failures.append(type(error).__name__)
            owner.stop()

    thread = Thread(target=signals)
    thread.start()
    try:
        with patch.object(owner, "open_browser", return_value=False) as browser, \
                patch.object(tray, "browser_failed", side_effect=notice):
            owner.run_gui(adapter)
        thread.join(25)
        assert not thread.is_alive() and not failures
        assert browser.call_count == 1 and owner.reason == "menu"
        assert owner.stopped.is_set() and not tray.installed and not tray.hwnd
    finally:
        owner.stop()
        thread.join(25)
        adapter.close()
        owner.close()
    # A failed HTTP worker must unwind a real icon, not leave a GUI-only application.
    owner = WebHost(ROOT)
    adapter = WindowsHost()
    with patch.object(owner, "_serve", wraps=owner._serve):
        original_start = owner.start

        def start():
            original_start()
            owner.server.handle_request = lambda: (_ for _ in ()).throw(RuntimeError("probe"))

        with patch.object(owner, "start", side_effect=start):
            owner.run_gui(adapter)
    assert owner.failure and owner.stopped.is_set() and not adapter.tray.installed
    return {"native_menu_labels": labels, "menu_open_failure_retry": "passed",
            "menu_exit": "passed", "http_fault_removes_icon": "passed"}


def detached_probe():
    store = InstanceStore(ROOT)
    if store.read():
        raise RuntimeError("probe_requires_no_existing_instance")
    launchers = []
    marker = ROOT / "windows/Beta/native-probe-source-change.py"
    if marker.exists():
        raise RuntimeError("probe_marker_already_exists")
    state = None
    try:
        # Actual .cmd from an unrelated cwd; CREATE_NEW_CONSOLE is a transient window.
        batch = ROOT / "windows/Beta/Cost Guard Web.cmd"
        launcher = subprocess.Popen(["cmd.exe", "/d", "/c", str(batch)],
                                    cwd=store.directory, creationflags=subprocess.CREATE_NEW_CONSOLE)
        launchers.append(launcher)
        assert launcher.wait(timeout=35) == 0
        state = until(store.read)
        assert control(state, "status")["ready"]
        assert window(state["pid"])
        # No inherited console: attempt attach in a separate no-console probe process.
        check = subprocess.run([sys.executable, "-c",
                                "import ctypes,sys; k=ctypes.WinDLL('kernel32',use_last_error=True); "
                                "ok=k.AttachConsole(int(sys.argv[1])); "
                                "raise SystemExit(1 if ok else 0)", str(state["pid"])],
                               creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
        assert check.returncode == 0
        initial = state["nonce"]
        failed_tray = Tray()
        with patch("src.web.native_windows.Tray", return_value=failed_tray), \
                patch.object(failed_tray.shell, "Shell_NotifyIconW", return_value=False), \
                contextlib.redirect_stdout(io.StringIO()):
            assert launch_windows(ROOT) == 1
        assert store.read()["nonce"] == initial and control(state, "status")["ready"]
        command(state["pid"], OPEN)
        time.sleep(0.3)
        assert store.read()["nonce"] == initial
        # Concurrent actual lifecycle calls use a real OS lock and native child.
        code = ("import sys; from pathlib import Path; from src.web.lifecycle import launch; "
                "r=launch(Path.cwd(),'src.web.native_windows',opener=lambda u:True); "
                "print(r.instance,flush=True)")
        for _ in range(2):
            launchers.append(subprocess.Popen([sys.executable, "-c", code], cwd=ROOT,
                                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL))
        replies = [child.communicate(timeout=35)[0].strip() for child in launchers[1:]]
        assert all(child.returncode == 0 for child in launchers[1:])
        assert replies[0] == replies[1]
        state = store.read()
        assert state["nonce"] != initial
        assert control(state, "status")["ready"]
        # Verified restart then bounded source-change shutdown of only this host.
        result = launch(ROOT, "src.web.native_windows", opener=lambda url: False)
        state = store.read()
        assert not result.browser_opened and control(state, "status")["ready"]
        pid, birth = state["pid"], state["process"]
        marker.write_text("# Owned native probe marker\n", encoding="utf-8")
        until(lambda: process_identity(pid) != birth, seconds=15)
        assert not window(pid) and store.read() is None
        return {"cmd_transient_console_exit": "passed", "detached_host_survives": "passed",
                "no_inherited_console": "passed", "open_keeps_instance": "passed",
                "concurrent_launch_coalesces": "passed", "deliberate_restart": "passed",
                "failed_browser_keeps_host": "passed", "source_change_removes_gui": "passed"}
    finally:
        marker.unlink(missing_ok=True)
        for child in launchers:
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)
        current = store.read()
        if current:
            stop_existing(store, current)


def source_zip_probe():
    """ShellExecute the real .cmd in a no-Git source copy with spaces and Unicode."""
    with tempfile.TemporaryDirectory(prefix="native-source-", dir=ROOT / "development/tests") as directory:
        snapshot = Path(directory) / "Source ZIP space å"
        snapshot.mkdir()
        for name in ("src", "windows"):
            shutil.copytree(ROOT / name, snapshot / name, ignore=shutil.ignore_patterns("__pycache__"))
        (snapshot / "config").mkdir()
        shutil.copy2(ROOT / "config/default-config.jsonc", snapshot / "config/default-config.jsonc")
        shutil.copy2(ROOT / "cost-guard-web.py", snapshot / "cost-guard-web.py")
        store = InstanceStore(snapshot)
        try:
            os.startfile(snapshot / "windows/Beta/Cost Guard Web.cmd")
            state = until(store.read, seconds=35)
            assert control(state, "status")["ready"]
            assert window(state["pid"])
            command(state["pid"], EXIT)
            until(lambda: process_identity(state["pid"]) != state["process"])
            assert store.read() is None
        finally:
            current = store.read()
            if current:
                stop_existing(store, current)
    return {"shell_execute_source_zip_unicode_space": "passed"}


def watch_and_detached_probe():
    """Keep the real, redirected CLI Watch alive across Web restart and exit."""
    with tempfile.TemporaryFile() as output:
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        child = subprocess.Popen([sys.executable, "cost-guard.py", "--watch"], cwd=ROOT,
                                 stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                                 env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            result = detached_probe()

            def rendered():
                if child.poll() is not None:
                    raise RuntimeError("cli_watch_stopped_with_web")
                output.seek(0)
                return b"Total today" in output.read()

            until(rendered, seconds=60)
            result["independent_cli_watch_after_web_restart_exit"] = "passed"
            return result
        finally:
            if child.poll() is None:
                child.terminate()  # Only this exact probe-owned CLI process.
            child.wait(timeout=5)


if __name__ == "__main__":
    if os.name != "nt" or sys.argv[1:] != ["--allow-native-ui"]:
        raise SystemExit("Requires Windows and explicit --allow-native-ui approval.")
    real_connect = socket.socket.connect

    def offline_connect(stream, address):
        if address[0] != "127.0.0.1":
            raise OSError("offline_probe")
        return real_connect(stream, address)

    with patch.object(socket.socket, "connect", offline_connect):
        evidence = adapter_probe()
    evidence["offline_native_shell_external_connections_denied"] = "passed"
    evidence.update(watch_and_detached_probe())
    evidence["injected_tray_api_failure_preserves_existing_host"] = "passed"
    evidence.update(source_zip_probe())
    evidence.update({"model_requests": 0, "physical_explorer_double_click": "not_run",
                     "visual_light_dark_review": "not_run"})
    print(json.dumps(evidence))
