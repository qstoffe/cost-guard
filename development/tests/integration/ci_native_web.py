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
from src.web.jobs import ReportJobs
from src.web.lifecycle import control, launch, stop_existing
from src.web.process_identity import process_identity

SHIM = '''import os, sys
from pathlib import Path
from unittest.mock import patch
from src.web.host import WebHost
from src.web.jobs import ReportJobs
from src.web.instance_state import InstanceStore
from src.web.lifecycle import launch
from src.web.main import main
root = Path(__file__).resolve().parent
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
            until(lambda: store.read() is None)
            # Actual executable .command plumbing, but shim suppresses Finder/browser.
            if sys.platform == "darwin":
                entry = root / "macos/Beta/Cost Guard Web.command"
                assert os.access(entry, os.X_OK)
                result = subprocess.run([str(entry)], cwd=home, env=environment,
                                        capture_output=True, timeout=45)
                assert result.returncode == 0
            else:
                launch(root, module, opener=lambda url: False)
            state = store.read()
            assert state and control(state, "status")["ready"]
            (root / "src/ci_owned_change.py").write_text("# synthetic source change\n")
            until(lambda: store.read() is None, seconds=20)
            until(lambda: process_identity(state["pid"]) != state["process"])
    finally:
        current = store.read()
        if current:
            stop_existing(store, current)
    return dict(outcome="PASS", checks=["detached native host / private OS locks / HTTP ownership",
        "Open retains instance", "deliberate restart retires original PID", "owned Exit/stop",
        "spaces and Unicode source path", "source change removes native host and private record"],
        command="PASS (real .command; offline entry shim)" if sys.platform == "darwin" else "NOT VERIFIED (.cmd/UI handoff)")


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


def main():
    hosted_only()
    evidence = dict(outcome="NOT RUN", checks={}, limitations=["NOT VERIFIED: physical desktop clicks, visual icon/menu, Finder/Gatekeeper, default browser, accessibility",
        "Synthetic entry bypasses real source/provider acquisition and OS default-browser launch; not an end-to-end consumer launcher proof"])
    try:
        with tempfile.TemporaryDirectory(prefix="cg-ci-native-") as temporary:
            base = Path(temporary)
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
                evidence["checks"]["adapter"] = probe(root, ReportJobs)
                evidence["checks"]["osacompile"] = macos_cache(root, home)
            else:
                raise RuntimeError("unsupported_native_platform")
            evidence["checks"]["lifecycle"] = detached(root, home)
        evidence["outcome"] = "PASS"
    except Exception as error:
        evidence.update(outcome="FAIL", reason=type(error).__name__)
        # Tracebacks contain only disposable synthetic data, but stay in Actions log,
        # never the retained artifacts; bootstrap/control credentials are not printed.
        import traceback
        traceback.print_exc()
    save("native", evidence)
    return int(evidence["outcome"] == "FAIL")


if __name__ == "__main__":
    raise SystemExit(main())
