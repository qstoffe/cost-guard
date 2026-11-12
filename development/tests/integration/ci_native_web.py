"""Hosted-only native smoke using real shipped APIs with an offline entry shim.

The shim replaces ONLY the disposable checkout entry: no source/provider/Watch
composition. One separately recorded hosted-only system handoff is permitted.
Native adapter, HTTP, locks, identity, restart and
source guard are the shipped implementation. This is not the workstation probe.
"""
import json
import os
from pathlib import Path
import shutil
import shlex
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

LAUNCH_ERRORS = {"tray_unavailable", "unsafe_instance_path", "app_preparation_failed",
                  "instance_start_timeout", "instance_start_conflict", "gui_or_server_start_failed",
                  "safe_force_stop_unavailable", "configuration_unavailable", "instance_conflict"}

SHIM = '''import os, sys
import socket
import time, json
from pathlib import Path
started = time.monotonic()
mode = 'wrapper' if sys.argv[1:] in (['--launch-macos'], ['--launch-windows']) else 'preflight' if sys.argv[1:] == ['--preflight-macos'] else 'host'
case = os.environ['CG_CI_CASE']
trace = Path(os.environ['CG_CI_STATE']) / ('ci-startup-' + case + '-' + mode + '.json')
marks = []
def mark(stage):
    elapsed = round(time.monotonic()-started, 3)
    marks.append(dict(stage=stage, seconds=elapsed))
    trace.write_text(json.dumps(dict(stage=stage, seconds=elapsed, events=marks[-24:])))
mark('imports')
from src.web.main import main
mark('main_imported')
from development.tools.ci_web_beta import hosted_only, observe_preflight
hosted_only()
if sys.platform == 'darwin':
    from src.web.macos_status import StatusItem
    def native_boundary(method, phase):
        def observed(item, *args, **kwargs):
            flag = '_ci_observed_' + phase
            if getattr(item, flag, False):
                return method(item, *args, **kwargs)
            setattr(item, flag, True)
            mark('native_' + phase)
            result = method(item, *args, **kwargs)
            mark('native_' + phase + ':returned')
            return result
        return observed
    for phase in ('install', 'poll', 'close'):
        setattr(StatusItem, phase, native_boundary(getattr(StatusItem, phase), phase))
    from src.web.startup import StartupProgress, STAGES
    progress_call = StartupProgress.__call__
    def progress(self, stage):
        if stage in STAGES:
            mark('launcher_' + stage)
        return progress_call(self, stage)
    StartupProgress.__call__ = progress
    if mode == 'wrapper':
        import subprocess
        real_run = subprocess.run
        receipt = Path(os.environ['CG_CI_STATE']) / ('ci-preflight-' + case + '.json')
        observed = observe_preflight(real_run, lambda value: receipt.write_text(json.dumps(value)))
        def traced_run(*args, **kwargs):
            command = args[0] if args else kwargs.get('args')
            if isinstance(command, (list, tuple)) and len(command) == 3 and command[-1] == '--preflight-macos':
                return observed(*args, **kwargs)
            return real_run(*args, **kwargs)
        subprocess.run = traced_run
root = Path(__file__).resolve().parent
real_connect = socket.socket.connect
def offline_connect(stream, address):
    if address[0] != '127.0.0.1':
        raise OSError('offline_ci_probe')
    return real_connect(stream, address)
socket.socket.connect = offline_connect
if mode == 'preflight':
    # Production main owns native preflight; no host/acquisition/state is used.
    mark('imports_complete')
    raise SystemExit(main())
from unittest.mock import patch
mark('mock_imported')
from src.web.host import WebHost
mark('host_imported')
from src.web.jobs import ReportJobs
from src.web.instance_state import InstanceStore
from src.web.lifecycle import launch
mark('core_imported')
mark('imports_complete')
original = WebHost.__init__
def isolated(self, *args, **kwargs):
    kwargs['jobs'] = ReportJobs()
    original(self, *args, **kwargs)
store_init = InstanceStore.__init__
def private(self, root, **kwargs):
    store_init(self, root, data_home=Path(os.environ['CG_CI_STATE']))
def registered_once(url):
    # The existing one-handoff budget now exercises the actual shell/main/wrapper.
    hosted_only()
    receipt = Path(os.environ['CG_CI_STATE']) / 'handoff.json'
    if receipt.exists():
        return False
    store = InstanceStore(root)
    state = store.read()
    assert state and url.startswith(f"http://127.0.0.1:{state['port']}/#bootstrap=")
    try:
        accepted = bool(real_opener(url))
        result = dict(outcome='ACCEPTED' if accepted else 'UNAVAILABLE', accepted=accepted)
    except OSError as error:
        result = dict(outcome='UNAVAILABLE', accepted=False, reason=type(error).__name__)
    result.update(attempts=1, owned_loopback_destination=True, page_rendering='NOT VERIFIED')
    receipt.write_text(json.dumps(result))
    return result['accepted']
module = 'src.web.native_windows' if os.name == 'nt' else 'src.web.native_macos'
import importlib
adapter = importlib.import_module(module)
real_opener = adapter.open_registered_browser
with patch.object(WebHost, '__init__', isolated), patch.object(WebHost, 'open_browser', return_value=False), patch.object(InstanceStore, '__init__', private), patch.object(adapter, 'open_registered_browser', registered_once):
    raise SystemExit(main())
'''


def until(predicate, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("bounded_native_condition_timeout")


def command_failure(result, store):
    # The production wrapper handles exceptions and prints user guidance. Its
    # bounded lifecycle log retains the exact safe code even without a traceback.
    evidence = dict(returncode=result.returncode)
    path = store.directory / 'lifecycle.log'
    if path.is_file():
        codes = [line.split()[-1] for line in path.read_text(encoding='ascii').splitlines()[-16:] if line.split()]
        evidence['lifecycle_errors'] = [code for code in codes if code in LAUNCH_ERRORS]
    for code in sorted(LAUNCH_ERRORS):
        suffix = b'InstanceConflict: ' + code.encode('ascii')
        if any(line.endswith(suffix) for line in result.stderr.splitlines()):
            evidence['error_code'] = code
            break
    return evidence


def preflight_observations(home):
    values = []
    for case in ('shell-1', 'shell-2', 'shell-3'):
        path = home / ('ci-preflight-' + case + '.json')
        if path.is_file():
            value = dict(case=case, **json.loads(path.read_text()))
            trace = home / ('ci-startup-' + case + '-preflight.json')
            if trace.is_file():
                value['child'] = json.loads(trace.read_text())
            values.append(value)
    return values


def macos_python_fixture(root, home, environment):
    """Actual CI interpreter in disposable standard non-PATH layouts, no install."""
    user = home / 'fixture-user'
    version = '.'.join(map(str, sys.version_info[:2]))
    primary = user / f'Library/Frameworks/Python.framework/Versions/{version}/bin/python3'
    fallback = user / f'.pyenv/versions/{version}/bin/python3'
    for executable in (primary, fallback):
        executable.parent.mkdir(parents=True)
        executable.symlink_to(sys.executable)
    binary = home / 'shell-utilities'
    binary.mkdir()
    for name in ('dirname', 'sleep'):
        (binary / name).symlink_to(shutil.which(name))
    environment.update(HOME=str(user), PATH=str(binary))
    # Hosted images also have eligible global Python installs. Relocate just
    # global roots in this disposable copy, as in the standard-layout unit cases;
    # otherwise they can win before the fixture whose removal we must exercise.
    resolver = root / 'src/python_discovery.sh'
    source = resolver.read_text()
    for prefix in ('/Library', '/opt/homebrew', '/usr/local'):
        source = source.replace(' ' + prefix + '/', ' "' + str(home / 'fixture-system') + '"' + prefix + '/')
    resolver.write_text(source)
    # This exact environment has no PATH Python, no interactive profile or developer shell.
    selected = subprocess.run(['/bin/zsh', '-c',
        'source "$1"; cg_find_python || exit 8; print -r -- "$PYTHON"', 'discovery',
        str(root / 'src/python_discovery.sh')], env=environment, capture_output=True, timeout=25)
    same = selected.returncode == 0 and Path(selected.stdout.decode().strip()).resolve() == Path(sys.executable).resolve()
    if not same:
        error = AssertionError('non_path_real_interpreter_selection_failed')
        # Fixed scalar evidence only; subprocess output may contain private paths/errors.
        error.ci_discovery = dict(exit_code=selected.returncode, same_real_interpreter=same,
            output_bytes=len(selected.stdout), stderr_bytes=len(selected.stderr),
            primary_exists=primary.is_file(), fallback_exists=fallback.is_file())
        raise error
    return primary, dict(outcome='PASS', actual_python=version, path_python=False,
        install_tree='synthetic user Python.org framework plus pyenv fallback',
        interpreter='real CI Python; symlinks only, global roots relocated in disposable source copy')


def detached(root, home):
    store = InstanceStore(root, data_home=home)
    module = "src.web.native_windows" if os.name == "nt" else "src.web.native_macos"
    case = 'lifecycle-first'
    environment = dict(os.environ, CG_CI_STATE=str(home), CG_CI_CASE=case)
    original_spawn = subprocess.Popen
    identities = {}
    identity_checks = []
    handoff = {}
    result = None
    discovery = {}

    def observed_identity(pid):
        current = process_identity(pid)
        if current:
            initial = identities.setdefault(pid, current)
            identity_checks.append(dict(same_birth=current['birth'] == initial['birth'],
                                        same_image=current['image'] == initial['image']))
        return current

    def spawn(*args, **kwargs):
        return original_spawn(*args, **dict(kwargs, env=environment))

    try:
        with patch("src.web.lifecycle.InstanceStore", return_value=store), patch("src.web.lifecycle.subprocess.Popen", side_effect=spawn), \
                patch("src.web.lifecycle.process_identity", side_effect=observed_identity):
            first = launch(root, module, opener=lambda url: False)
            state = store.read()
            assert state and control(state, "status")["ready"]
            assert not first.browser_opened
            assert control(state, "open")["ready"]
            assert store.read()["nonce"] == first.instance
            case = environment['CG_CI_CASE'] = 'lifecycle-restart'
            second = launch(root, module, opener=lambda url: False)
            assert not second.browser_opened and control(store.read(), "status")["ready"]
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
            # Actual moved shell -> production main -> launch wrapper, including
            # config/native preflight and macOS helper preparation. Only acquisition
            # and private test state are isolated; one OS handoff remains the budget.
            preferences = root / 'config/user-config.jsonc'
            saved = '{"webSettings":{"theme":"classic","miniWatchSize":"remember-last"}}\n'
            preferences.write_text(saved)
            entry = root / ('macos/Cost-Guard-Web.command' if sys.platform == 'darwin' else 'windows/Cost-Guard-Web.cmd')
            command = [str(entry)] if sys.platform == 'darwin' else ['cmd.exe', '/d', '/c', str(entry)]
            if sys.platform == 'darwin':
                assert os.access(entry, os.X_OK)
                primary, discovery = macos_python_fixture(root, home, environment)
            for attempt in range(3 if sys.platform == 'darwin' else 2):
                if attempt == 2:
                    from src.web.macos_app import app_source
                    primary.unlink()  # Fixture-owned symlink only; installed Python stays intact.
                    literal = app_source(root).split('do shell script "', 1)[1].split('"\n', 1)[0]
                    command = shlex.split(json.loads('"' + literal + '"'))
                case = environment['CG_CI_CASE'] = 'shell-' + str(attempt + 1)
                previous = store.read()
                result = subprocess.run(command, cwd=home, env=environment, capture_output=True, timeout=60)
                assert result.returncode in (0, 4), 'production_launch_wrapper_failed'
                handoff = json.loads((home / 'handoff.json').read_text())
                expected_exit = 0 if attempt == 0 and handoff['accepted'] else 4
                assert result.returncode == expected_exit, 'browser_handoff_exit_mismatch'
                state = store.read()
                assert state and control(state, 'status')['ready']
                assert preferences.read_text() == saved
                assert InstanceStore(root, data_home=home).directory == store.directory
                if previous:
                    assert previous['nonce'] != state['nonce']
                    assert process_identity(previous['pid']) != previous['process']
                if sys.platform == 'darwin':
                    assert b'Cost Guard.app' in result.stdout, 'production_helper_preparation_not_observed'
                    if attempt == 2:
                        discovery['generated_command_after_primary_removed'] = 'PASS (real fallback interpreter and native startup)'
            state = store.read()
            assert state and control(state, "status")["ready"]
            (root / "src/ci_owned_change.py").write_text("# synthetic source change\n")
            until(lambda: process_identity(state["pid"]) != state["process"])
            assert store.read() is None
    except Exception as error:
        if result is not None and result.returncode:
            # The captured traceback can contain private state/paths. Publish only
            # the exit status and exact known lifecycle code, never raw output.
            error.ci_command = command_failure(result, store)
        error.ci_trace = {}
        for mode in ('wrapper', 'preflight', 'host'):
            trace = home / ('ci-startup-' + case + '-' + mode + '.json')
            if trace.is_file():
                error.ci_trace[mode] = json.loads(trace.read_text())
        error.ci_preflight = preflight_observations(home)
        raise
    finally:
        current = store.read()
        if current:
            stop_existing(store, current)
    return dict(outcome="PASS", installed_python=discovery, registered_browser_handoff=handoff, startup_identity_checks=identity_checks,
        preflight_observations=preflight_observations(home), checks=["detached native host / private OS locks / HTTP ownership",
        "Open retains instance", "deliberate restart retires original PID", "owned Exit/stop",
         "spaces and Unicode source path", "production launcher preflight / restart / unchanged preferences and checkout identity",
         "source change removes native host and private record"],
        command="PASS (real moved shell / production wrapper; offline acquisition only)")


def macos_cache(root, home):
    from src.web.macos_app import prepare_app
    store = InstanceStore(root, data_home=home)
    first = prepare_app(root, store)
    stamp = (first / "Contents/MacOS/applet").stat().st_mtime_ns
    assert prepare_app(root, store) == first
    assert (first / "Contents/MacOS/applet").stat().st_mtime_ns == stamp
    with (root / "macos/launcher.applescript").open("a") as stream:
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
    evidence = dict(outcome="NOT RUN", checks={}, limitations=["NOT VERIFIED: physical desktop clicks, visual icon/menu, Finder/Gatekeeper, default-browser rendering, accessibility",
        "Synthetic entry bypasses real source/provider acquisition and stubs menu browser dispatch; moved shell calls production launch wrapper with one recorded OS handoff, not physical consumer-desktop proof"])
    try:
        with tempfile.TemporaryDirectory(prefix="cg-ci-native-") as temporary:
            base = Path(temporary).resolve()
            root = base / "Source space å 日本語"
            root.mkdir()
            for name in ("src", "macos", "windows", "config"):
                shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__", "user-config.jsonc"))
            support = root / 'development/tools'
            support.mkdir(parents=True)
            shutil.copyfile(ROOT / 'development/tools/ci_web_beta.py', support / 'ci_web_beta.py')
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
        if str(error) in LAUNCH_ERRORS:
            evidence["error_code"] = str(error)
        if hasattr(error, "ci_command"):
            evidence["command_failure"] = error.ci_command
        if hasattr(error, "ci_trace"):
            evidence["last_child_stage"] = error.ci_trace
        if hasattr(error, "ci_preflight"):
            evidence['preflight_observations'] = error.ci_preflight
        if hasattr(error, 'ci_discovery'):
            evidence['python_discovery'] = error.ci_discovery
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
