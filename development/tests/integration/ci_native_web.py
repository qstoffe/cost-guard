"""Hosted-only native smoke using real shipped APIs with an offline entry shim.

The shim replaces ONLY the disposable checkout entry: no source/provider/Watch
composition, no system browser. Native adapter, HTTP, locks, identity, restart and
source guard are the shipped implementation. This is not the workstation probe.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tools.ci_web_beta import hosted_only, save
from src.web.instance_state import InstanceStore
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.web.lifecycle import control, launch, stop_existing
from src.web.process_identity import process_identity

SHIM = '''import os, sys
import socket
import time, json
from pathlib import Path
started = time.monotonic()
trace = Path(os.environ['CG_CI_STATE']) / 'ci-startup.json'
def mark(stage):
    trace.write_text(json.dumps(dict(stage=stage, seconds=round(time.monotonic()-started, 3))))
mark('imports')
from unittest.mock import patch
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.web.instance_state import InstanceStore
from src.web.lifecycle import launch
from src.web.main import main
mark('imports_complete')
if sys.platform == 'darwin':
    from src.web.objc_bridge import ObjC
    original_send = ObjC.send
    def traced_send(api, receiver, selector, *args):
        mark(selector)
        result = original_send(api, receiver, selector, *args)
        mark(selector + ':returned')
        return result
    ObjC.send = traced_send
root = Path(__file__).resolve().parent
real_connect = socket.socket.connect
def offline_connect(stream, address):
    if address[0] != '127.0.0.1':
        raise OSError('offline_ci_probe')
    return real_connect(stream, address)
socket.socket.connect = offline_connect
original = WebHost.__init__
def isolated(self, *args, **kwargs):
    kwargs['jobs'] = ReportJobs()
    original(self, *args, **kwargs)
store_init = InstanceStore.__init__
def private(self, root, **kwargs):
    store_init(self, root, data_home=Path(os.environ['CG_CI_STATE']))
with patch.object(WebHost, '__init__', isolated), patch.object(WebHost, 'open_browser', return_value=False), patch.object(InstanceStore, '__init__', private):
    if sys.argv[1:] in (['--launch-macos'], ['--launch-windows']):
        module = 'src.web.native_windows' if os.name == 'nt' else 'src.web.native_macos'
        launch(root, module, opener=lambda url: False)
        raise SystemExit(0)
    raise SystemExit(main())
'''


def until(predicate, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("bounded_native_condition_timeout")


def detached(root, home):
    store = InstanceStore(root, data_home=home)
    module = "src.web.native_windows" if os.name == "nt" else "src.web.native_macos"
    environment = dict(os.environ, CG_CI_STATE=str(home))
    original_spawn = subprocess.Popen

    def spawn(*args, **kwargs):
        return original_spawn(*args, **dict(kwargs, env=environment))

    try:
        with patch("src.web.lifecycle.InstanceStore", return_value=store), patch("src.web.lifecycle.subprocess.Popen", side_effect=spawn):
            first = launch(root, module, opener=lambda url: False)
            state = store.read()
            assert state and control(state, "status")["ready"] and not first.browser_opened
            assert control(state, "open")["ready"]
            assert store.read()["nonce"] == first.instance
            second = launch(root, module, opener=lambda url: False)
            assert second.instance != first.instance
            assert process_identity(state["pid"]) != state["process"]
            state = store.read()
            if os.name == "nt":
                from development.tests.integration.probe_windows_web import command
                from src.web.win32_tray import EXIT
                command(state["pid"], EXIT)
            else:
                control(state, "stop")
            # Do not hold read handles against Windows' delete-on-close cleanup.
            until(lambda: process_identity(state["pid"]) != state["process"])
            assert store.read() is None
            # Actual executable .command plumbing, but shim suppresses Finder/browser.
            if sys.platform == "darwin":
                entry = root / "macos/Beta/Cost Guard Web.command"
                assert os.access(entry, os.X_OK)
                result = subprocess.run([str(entry)], cwd=home, env=environment,
                                        capture_output=True, timeout=45)
                assert result.returncode == 0
            else:
                entry = root / "windows/Beta/Cost Guard Web.cmd"
                result = subprocess.run(["cmd.exe", "/d", "/c", str(entry)], cwd=home,
                                        env=environment, capture_output=True, timeout=45)
                assert result.returncode == 0
            state = store.read()
            assert state and control(state, "status")["ready"]
            (root / "src/ci_owned_change.py").write_text("# synthetic source change\n")
            until(lambda: process_identity(state["pid"]) != state["process"])
            assert store.read() is None
    except Exception as error:
        trace = home / "ci-startup.json"
        if trace.is_file():
            error.ci_trace = json.loads(trace.read_text())
        raise
    finally:
        current = store.read()
        if current:
            stop_existing(store, current)
    return dict(outcome="PASS", checks=["detached native host / private OS locks / HTTP ownership",
        "Open retains instance", "deliberate restart retires original PID", "owned Exit/stop",
        "spaces and Unicode source path", "source change removes native host and private record"],
        command="PASS (real .command; offline entry shim)" if sys.platform == "darwin" else "PASS (real .cmd/PowerShell; offline entry shim)")


def macos_cache(root, home):
    from src.web.macos_app import prepare_app
    store = InstanceStore(root, data_home=home)
    first = prepare_app(root, store)
    stamp = (first / "Contents/MacOS/applet").stat().st_mtime_ns
    assert prepare_app(root, store) == first
    assert (first / "Contents/MacOS/applet").stat().st_mtime_ns == stamp
    with (root / "macos/Beta/launcher.applescript").open("a") as stream:
        stream.write("\n-- synthetic fingerprint change\n")
    assert prepare_app(root, store) != first
    return dict(outcome="PASS", checks=["in-box osacompile", "verified cache reuse", "source fingerprint rebuild"],
                osacompile="/usr/bin/osacompile (OS-bundled; no SDK/package download)")


def macos_fault(root):
    from src.web.native_macos import MacHost
    from src.web.macos_status import StatusItem

    class FaultItem(StatusItem):
        injected = False

        def poll(self):
            if self.owner.ready and not self.injected:
                self.injected = True
                def fault():
                    raise RuntimeError("synthetic_http_fault")
                self.owner.server.handle_request = fault
            return super().poll()

    adapter = MacHost(FaultItem())
    owner = WebHost(root, jobs=ReportJobs())
    owner.run_gui(adapter)
    assert owner.ready and adapter.tray.injected
    assert owner.failure and owner.stopped.is_set() and not owner.thread.is_alive()
    assert adapter.tray.item is None and adapter.tray.timer is None
    return dict(outcome="PASS", checks=["actual AppKit item removed after HTTP-owner fault"])


def main():
    hosted_only()
    evidence = dict(outcome="NOT RUN", checks={}, limitations=["NOT VERIFIED: physical desktop clicks, visual icon/menu, Finder/Gatekeeper, default browser, accessibility",
        "Synthetic entry bypasses real source/provider acquisition and OS default-browser launch; not an end-to-end consumer launcher proof"])
    try:
        with tempfile.TemporaryDirectory(prefix="cg-ci-native-") as temporary:
            base = Path(temporary).resolve()
            root = base / "Source space å 日本語"
            root.mkdir()
            for name in ("src", "macos", "windows", "config"):
                shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__", "user-config.jsonc"))
            (root / "cost-guard-web.py").write_text(SHIM, encoding="utf-8")
            home = base / "private"
            home.mkdir()
            if os.name == "nt":
                from development.tests.integration.probe_windows_web import adapter_probe
                evidence["checks"]["adapter"] = adapter_probe(root, ReportJobs)
            elif sys.platform == "darwin":
                from development.tests.integration.probe_macos_web import probe
                from src.web.objc_bridge import ObjC
                timings = {}
                send = ObjC.send

                def timed_send(api, receiver, selector, *args):
                    started = time.monotonic()
                    try:
                        return send(api, receiver, selector, *args)
                    finally:
                        timings[selector] = round(timings.get(selector, 0) + time.monotonic() - started, 4)

                initialize = ObjC.__init__

                def timed_initialize(api):
                    started = time.monotonic()
                    try:
                        initialize(api)
                    finally:
                        timings["framework_load"] = round(time.monotonic() - started, 4)

                with patch.object(ObjC, "send", timed_send), patch.object(ObjC, "__init__", timed_initialize):
                    evidence["checks"]["adapter"] = probe(root, ReportJobs)
                evidence["native_api_seconds"] = {key: value for key, value in timings.items() if value >= 0.05}
                # NSApplication is process-global; a second adapter in the same
                # process is not a fresh native launch. Exercise fault separately.
                result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--http-fault", str(root)],
                                        cwd=ROOT, timeout=60, check=False)
                assert result.returncode == 0
                evidence["checks"]["http_fault"] = {"outcome": "PASS", "checks": ["fresh-process AppKit cleanup on HTTP fault"]}
                evidence["checks"]["osacompile"] = macos_cache(root, home)
            else:
                raise RuntimeError("unsupported_native_platform")
            evidence["checks"]["lifecycle"] = detached(root, home)
        evidence["outcome"] = "PASS"
    except Exception as error:
        evidence.update(outcome="FAIL", reason=type(error).__name__)
        if str(error) in {"tray_unavailable", "unsafe_instance_path", "app_preparation_failed",
                          "instance_start_timeout", "gui_or_server_start_failed", "safe_force_stop_unavailable"}:
            evidence["error_code"] = str(error)
        if hasattr(error, "ci_trace"):
            evidence["last_child_stage"] = error.ci_trace
        # Preserve causal source locations, not raw paths/state/exception payloads.
        import traceback
        evidence["failure_locations"] = [dict(file=Path(frame.filename).name, line=frame.lineno, function=frame.name)
                                         for frame in traceback.extract_tb(error.__traceback__)]
    save("native", evidence)
    return int(evidence["outcome"] == "FAIL")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--http-fault":
        hosted_only()
        macos_fault(Path(sys.argv[2]))
        raise SystemExit(0)
    raise SystemExit(main())
