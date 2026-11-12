"""Synthetic macOS contracts only: never loads AppKit or opens UI on any OS."""
import contextlib
import ctypes as C
import io
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import Mock, patch

from src.web import macos_launch, native_macos
from src.web import objc_bridge
from src.web.macos_status import StatusItem
from src.web.objc_bridge import BOOL, DOUBLE, INTEGER, MASK, PTR, ObjC, require_main_thread
from src.web.process_identity import InstanceConflict

ROOT = Path(__file__).resolve().parents[2]


class CocoaRecorder:
    """Records typed native calls without pretending to execute Cocoa."""
    def __init__(self):
        self.calls = []
        self.next_id = 100
        self.actions = None
        self.fail = None

    def cls(self, name):
        return name

    def string(self, value):
        return value

    def selector(self, value):
        return value

    def target(self, enqueue, tick, failed):
        self.actions = enqueue, tick
        return 99

    def send(self, receiver, selector, result=PTR, *arguments):
        self.calls.append((receiver, selector, result, arguments))
        if selector == self.fail:
            return None
        if selector == "setActivationPolicy:":
            return True
        self.next_id += 1
        return self.next_id if result else None


class MacWebTests(unittest.TestCase):
    def test_registered_native_callbacks_are_retained_and_only_enqueue_actions(self):
        api = ObjC.__new__(ObjC)
        api.lib = Mock()
        api.lib.objc_allocateClassPair.return_value = 123
        api.cls = lambda _: 456
        api.selector = lambda _: 789
        api.send = lambda *_: 987
        events, ticks, faults = [], [], []
        fault = TypeError("private")
        def tick():
            ticks.append("tick")
            if len(ticks) > 1:
                raise fault
        target = api.target(events.append, tick, faults.append)
        retained_api, callbacks = objc_bridge._registered_callbacks[-1]
        for callback in callbacks:
            callback(1, 2, 3)
        self.assertEqual(target, 987)
        self.assertIs(retained_api, api)
        self.assertEqual(events, ["open", "exit"])
        self.assertEqual(ticks, ["tick"])
        self.assertEqual(faults, [])
        callbacks[2](1, 2, 3)
        self.assertEqual(faults, [fault])
        self.assertEqual(api.lib.class_addMethod.call_count, 3)
        self.assertTrue(all(call.args[3] == b"v@:@" for call in api.lib.class_addMethod.call_args_list))

    def test_callback_fault_is_reported_to_owner_and_raised_outside_ctypes(self):
        api = CocoaRecorder()
        tray = StatusItem(api)
        owner = Mock(stopping=Event(), stopped=Event())
        tray.watch(owner)
        tray.install()
        fault = TypeError("private")
        tray._failed(fault)
        with self.assertRaises(TypeError) as raised:
            tray.poll()
        tray.close()
        self.assertIs(raised.exception, fault)
        self.assertIs(owner.failure, fault)
        owner.stop.assert_called_once_with("runtime_fault")

    def test_typed_message_dispatch_preserves_64bit_pointer_and_double(self):
        seen = []
        implementation = C.CFUNCTYPE(PTR, PTR, PTR, DOUBLE)(
            lambda receiver, selector, length: seen.append((receiver, selector, length)) or 0x1234567890)
        api = ObjC.__new__(ObjC)
        api.address = C.cast(implementation, PTR).value
        api.messages = {}
        api.selector = lambda _: 0x2345678901
        result = api.send(0x3456789012, "statusItemWithLength:", PTR, (DOUBLE, -1.0))
        self.assertEqual(result, 0x1234567890)
        self.assertEqual(seen, [(0x3456789012, 0x2345678901, -1.0)])
        self.assertEqual(len(api.messages), 1)

    def test_native_resources_menu_signatures_timer_and_idempotent_close(self):
        api = CocoaRecorder()
        tray = StatusItem(api)
        owner = Mock(stopping=Event(), stopped=Event())
        tray.watch(owner)
        tray.install()
        installed_item, menu = tray.item, tray.menu
        api.actions[0]("open")
        self.assertEqual(tray.poll(), ["open"])
        api.actions[1]()
        self.assertFalse(any(call[1] == "cancelTracking" for call in api.calls))
        owner.stopped.set()
        api.actions[1]()
        self.assertIn((menu, "cancelTracking", None, ()), api.calls)
        tray.browser_failed()
        tray.close()
        tray.close()
        titles = [call[3][0][1] for call in api.calls if call[1] == "initWithTitle:action:keyEquivalent:"]
        self.assertEqual(titles, ["Open Cost Guard", "Exit Cost Guard"])
        lengths = [call[3] for call in api.calls if call[1] == "statusItemWithLength:"]
        self.assertEqual(lengths, [((DOUBLE, -1.0),)])
        self.assertIn((tray.app, "setActivationPolicy:", BOOL, ((INTEGER, 1),)), api.calls)
        pump = [call for call in api.calls if call[1] == "nextEventMatchingMask:untilDate:inMode:dequeue:"][0]
        self.assertEqual(pump[3][0], (MASK, 0xffffffffffffffff))
        self.assertEqual(pump[3][-1], (BOOL, True))
        modes = [call[3][1][1] for call in api.calls if call[1] == "addTimer:forMode:"]
        self.assertEqual(modes, ["NSDefaultRunLoopMode", "NSEventTrackingRunLoopMode"])
        removals = [call for call in api.calls if call[1] == "removeStatusItem:"]
        self.assertEqual(len(removals), 1)
        self.assertEqual(removals[0][3], ((PTR, installed_item),))

    def test_install_failure_still_removes_partial_status_item(self):
        api = CocoaRecorder()
        api.fail = "button"
        tray = StatusItem(api)
        with self.assertRaisesRegex(InstanceConflict, "tray_unavailable"):
            tray.install()
        tray.close()
        self.assertEqual(len([call for call in api.calls if call[1] == "removeStatusItem:"]), 1)

    def test_gui_main_thread_is_enforced_before_loading_frameworks(self):
        errors = []
        def worker():
            try:
                require_main_thread()
            except InstanceConflict as error:
                errors.append(str(error))
        thread = Thread(target=worker)
        thread.start()
        thread.join(2)
        self.assertEqual(errors, ["tray_unavailable"])

    def test_preflight_finally_closes_partial_gui(self):
        tray = Mock()
        tray.install.side_effect = InstanceConflict("tray_unavailable")
        with patch.object(native_macos, "StatusItem", return_value=tray):
            with self.assertRaises(InstanceConflict):
                native_macos.preflight()
        tray.close.assert_called_once()

    def test_fresh_preflight_dispatch_does_not_import_web_host(self):
        script = '''import importlib.abc, sys
class RejectHost(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'src.web.host':
            raise AssertionError('preflight imported the report-host composition')
sys.meta_path.insert(0, RejectHost())
from src.web.main import main
from src.web import native_macos
calls = []
def ready():
    calls.append('ready')
def failed():
    calls.append('failed')
    raise RuntimeError('synthetic native failure')
sys.argv = ['cost-guard-web.py', '--preflight-macos']
native_macos.preflight = ready
assert main() == 0
native_macos.preflight = failed
assert main() == 3
assert calls == ['ready', 'failed']
assert 'src.web.host' not in sys.modules
print('PASS isolated production preflight dispatch')
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('PASS isolated production preflight dispatch\n', result.stdout)

    def test_readiness_after_first_native_poll_and_host_loss_returns(self):
        owner = Mock(stopping=Event(), stopped=Event())
        calls = []
        tray = Mock()
        tray.install.side_effect = lambda: calls.append("install")
        def poll():
            calls.append("poll")
            if calls.count("poll") == 2:
                owner.stopped.set()
            return []
        tray.poll.side_effect = poll
        owner.publish_ready.side_effect = lambda: calls.append("ready")
        adapter = native_macos.MacHost(tray)
        adapter.run(owner)
        adapter.close()
        self.assertEqual(calls, ["install", "poll", "ready", "poll"])
        tray.watch.assert_called_once_with(owner)
        tray.close.assert_called_once()

    def test_failed_install_or_pump_never_publishes_ready(self):
        for operation in ("install", "poll"):
            owner = Mock(stopping=Event(), stopped=Event())
            tray = Mock()
            getattr(tray, operation).side_effect = InstanceConflict("tray_unavailable")
            with self.subTest(operation=operation), self.assertRaises(InstanceConflict):
                native_macos.MacHost(tray).run(owner)
            owner.publish_ready.assert_not_called()

    def test_open_coalesces_and_exit_does_not_wait_for_browser(self):
        owner = Mock(stopping=Event(), stopped=Event())
        entered, release = Event(), Event()
        def browser(**_):
            entered.set()
            release.wait(3)
            return True
        owner.open_browser.side_effect = browser
        adapter = native_macos.MacHost(Mock())
        try:
            adapter.dispatch(owner, ["open"])
            self.assertTrue(entered.wait(1))
            adapter.dispatch(owner, ["open", "open"])
            adapter.dispatch(owner, ["exit", "open"])
            owner.stop.assert_called_once_with("menu")
            owner.open_browser.assert_called_once()
        finally:
            release.set()
            adapter.close()
        self.assertFalse(adapter.open_thread.is_alive())

    def test_browser_worker_fault_reaches_shared_stop_owner(self):
        owner = Mock(stopping=Event(), stopped=Event())
        fault = SystemExit("private")
        owner.open_browser.side_effect = fault
        adapter = native_macos.MacHost(Mock())
        adapter.dispatch(owner, ["open"])
        adapter.close()
        self.assertIs(owner.failure, fault)
        owner.stop.assert_called_once_with("runtime_fault")

    def test_browser_failure_keeps_menu_and_reports_without_stopping(self):
        owner = Mock(stopping=Event(), stopped=Event())
        tray = Mock()
        adapter = native_macos.MacHost(tray)
        adapter.results.put(False)
        def poll():
            if tray.browser_failed.called:
                owner.stopped.set()
            return []
        tray.poll.side_effect = poll
        adapter.run(owner)
        adapter.close()
        tray.browser_failed.assert_called_once()
        owner.store.log.assert_called_once_with("browser_open_failed")
        owner.stop.assert_not_called()

    def test_browser_uses_fixed_system_open_with_single_url_argument(self):
        url = "http://127.0.0.1:1234/#bootstrap=synthetic"
        with patch.object(native_macos.subprocess, "run", return_value=Mock(returncode=0)) as run:
            self.assertTrue(native_macos.open_registered_browser(url))
        self.assertEqual(run.call_args.args[0], ["/usr/bin/open", url])
        self.assertEqual(run.call_args.kwargs["timeout"], 5)
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_preflight_crash_or_timeout_preserves_existing_instance(self):
        for failure in (Mock(returncode=-6), subprocess.TimeoutExpired("preflight", 10)):
            with self.subTest(failure=failure), patch.object(macos_launch.sys, "platform", "darwin"), \
                    patch.object(macos_launch, "InstanceStore", return_value=Mock()), \
                    patch.object(macos_launch, "load_configuration"), \
                    patch.object(macos_launch.subprocess, "run") as run, \
                    patch.object(macos_launch, "launch") as launch, \
                    patch.object(macos_launch, "prepare_app") as prepare, \
                    contextlib.redirect_stdout(io.StringIO()):
                if isinstance(failure, Exception):
                    run.side_effect = failure
                else:
                    run.return_value = failure
                self.assertEqual(macos_launch.launch_macos(ROOT), 1)
                launch.assert_not_called()
                prepare.assert_not_called()

    def test_failed_app_preparation_keeps_command_fallback_and_menu_on_browser_failure(self):
        output = io.StringIO()
        with patch.object(macos_launch.sys, "platform", "darwin"), \
                patch.object(macos_launch, "InstanceStore", return_value=Mock()) as store, \
                patch.object(macos_launch, "load_configuration"), \
                patch.object(macos_launch, "native_preflight"), \
                patch.object(macos_launch, "prepare_app", side_effect=InstanceConflict("app_preparation_failed")), \
                patch.object(macos_launch, "launch", return_value=Mock(browser_opened=False)) as launch, \
                 contextlib.redirect_stdout(output):
            store.return_value.log.side_effect = OSError('PRIVATE_DIAGNOSTIC_PATH')
            self.assertEqual(macos_launch.launch_macos(ROOT), 4)
        self.assertEqual(launch.call_args.args, (ROOT, "src.web.native_macos"))
        self.assertEqual([call.args[0] for call in store.return_value.log.call_args_list],
                         ["app_preparation_failed", "browser_open_failed"])
        self.assertIn("continuing with .command", output.getvalue())
        self.assertIn("Web is running", output.getvalue())
        self.assertNotIn('PRIVATE_DIAGNOSTIC_PATH', output.getvalue())

    def test_wrong_os_does_not_touch_state_or_native_api(self):
        with patch.object(macos_launch.sys, "platform", "win32"), \
                patch.object(macos_launch, "InstanceStore") as store, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(macos_launch.launch_macos(ROOT), 1)
        store.assert_not_called()

    @unittest.skipUnless(shutil.which('zsh') and hasattr(os, 'openpty'), 'zsh/PTY unavailable; native macOS CI owns shell execution')
    def test_command_activity_and_exit_codes_without_native_or_browser_work(self):
        # A fake interpreter tests shell lifetime only, not discovery correctness/AppKit.
        with tempfile.TemporaryDirectory(prefix="web command å ' quote ") as directory:
            root = Path(directory)
            beta = root / 'macos'; beta.mkdir(parents=True)
            command = beta / 'Cost-Guard-Web.command'
            shutil.copyfile(ROOT / 'macos/Cost-Guard-Web.command', command)
            (root / 'src').mkdir()
            shutil.copyfile(ROOT / 'src/python_discovery.sh', root / 'src/python_discovery.sh')
            binary = root / 'bin'; binary.mkdir()
            python = binary / 'python3'
            python.write_text('''#!/bin/sh
if [ "$1" = "-I" ]; then printf 'CGPY|3|13|darwin|%s\n' "$0"; sleep 0.4; exit 0; fi
printf 'Cost Guard startup: Checking native support\\n'
printf 'ENTRY:%s|%s|%s\\n' "$1" "$2" "$3"
sleep 0.4
exit "$CG_FAKE_EXIT"
''', encoding='utf-8')
            python.chmod(0o700)
            for code in (0, 4):
                with self.subTest(exit_code=code):
                    master, slave = os.openpty()
                    try:
                        env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'], CG_FAKE_EXIT=str(code))
                        child = subprocess.run([shutil.which('zsh'), str(command)], cwd=root, env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=slave, timeout=5)
                        self.assertEqual(code, child.returncode)
                        self.assertIn(b'Checking native support', child.stdout)
                        self.assertIn(('ENTRY:-u|' + str(root / 'cost-guard-web.py') + '|--launch-macos').encode(), child.stdout)
                        # Darwin may discard queued PTY output on the last slave
                        # close. Read while our slave remains open, with a deadline.
                        readable, _, _ = select.select([master], [], [], 1)
                        self.assertTrue(readable, 'TTY activity must be observable before closing the slave')
                        activity = os.read(master, 8192).decode('utf-8')
                        self.assertIn('Launching web', activity)
                        self.assertIn('[|]', activity)
                        self.assertIn('[/]', activity)
                    finally:
                        os.close(slave)
                        os.close(master)

    @unittest.skipUnless(shutil.which('zsh'), 'native macOS CI owns zsh execution')
    def test_moved_legacy_commands_resolve_cli_and_preserve_exit_without_gui(self):
        with tempfile.TemporaryDirectory(prefix="legacy å ' space ") as directory:
            root = Path(directory)
            legacy = root / 'macos/Legacy'
            legacy.mkdir(parents=True)
            binary = root / 'bin'
            binary.mkdir()
            python = binary / 'python3'
            (root / 'src').mkdir()
            shutil.copyfile(ROOT / 'src/python_discovery.sh', root / 'src/python_discovery.sh')
            python.write_text('''#!/bin/sh
if [ "$1" = "-I" ]; then printf 'CGPY|3|13|darwin|%s\n' "$0"; exit 0; fi
printf 'ENTRY:%s|%s\\n' "$1" "${2-}"
exit 17
''', encoding='utf-8')
            python.chmod(0o700)
            for name, argument in (('Cost-Guard.command', ''), ('Cost-Guard-Watch.command', '--watch')):
                command = legacy / name
                shutil.copyfile(ROOT / 'macos/Legacy' / name, command)
                result = subprocess.run([shutil.which('zsh'), str(command)], cwd=binary,
                    env=dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH']),
                    stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
                self.assertEqual(17, result.returncode, result.stderr)
                self.assertIn(('ENTRY:' + str(root / 'cost-guard-cli.py') + '|' + argument).encode(), result.stdout)

    def test_source_launcher_is_relative_and_does_not_control_terminal(self):
        source = (ROOT / "macos/Cost-Guard-Web.command").read_text(encoding="utf-8")
        self.assertTrue(source.startswith("#!/bin/zsh\n"))
        self.assertIn('$(dirname "$0")/.."', source)
        self.assertIn('source "$CG_ROOT/src/python_discovery.sh"', source)
        self.assertIn("--launch-macos", source)
        self.assertNotIn("osascript", source)
        self.assertEqual(source.count('kill '), 1)
        self.assertIn('kill "$SPINNER"', source, 'Only the display-only child may be stopped')
        self.assertIn('SPINNER=$!', source)
        self.assertIn('trap stop_activity EXIT', source)
        self.assertIn("trap 'exit 130' INT", source)
        self.assertIn("trap 'exit 143' TERM", source)
        self.assertIn('Launching web…', source)
        self.assertIn('RESULT=$?', source)
        self.assertIn('exit $RESULT', source)

    @unittest.skipUnless(shutil.which('zsh'), 'native macOS CI owns zsh execution')
    def test_versioned_framework_homebrew_and_user_installs_without_path(self):
        # Real zsh/globs/processes in synthetic install trees, never system installs.
        layouts = ('Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                   'opt/homebrew/opt/python@3.13/bin/python3.13',
                   'usr/local/opt/python@3.13/bin/python3.13',
                   'home/Library/Frameworks/Python.framework/Versions/3.13/bin/python3',
                   'home/.pyenv/versions/3.13.2/bin/python3',
                   'home/.local/share/uv/python/cpython-3.13.2-macos-aarch64-none/bin/python3')
        for layout in layouts:
            with self.subTest(layout=layout), tempfile.TemporaryDirectory(prefix="python å ' space ") as directory:
                root = Path(directory)
                executable = root / layout
                executable.parent.mkdir(parents=True)
                executable.write_text('#!/bin/sh\nprintf "CGPY|3|13|darwin|%s\\n" "$0"\n')
                executable.chmod(0o700)
                resolver = (ROOT / 'src/python_discovery.sh').read_text()
                # Relocate only OS-owned roots into an isolated, representative tree.
                for prefix in ('/Library', '/opt/homebrew', '/usr/local'):
                    resolver = resolver.replace(' ' + prefix + '/', ' "' + str(root) + '"' + prefix + '/')
                source = root / 'discovery.sh'
                source.write_text(resolver)
                script = root / 'probe.zsh'
                script.write_text('source "$1"\ncg_find_python || exit 9\nprint -r -- "$PYTHON"\n')
                result = subprocess.run([shutil.which('zsh'), str(script), str(source)],
                    env=dict(os.environ, HOME=str(root / 'home'), PATH=''),
                    capture_output=True, text=True, timeout=8)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(str(executable.resolve()), result.stdout.strip())

    @unittest.skipUnless(shutil.which('zsh'), 'native macOS CI owns zsh execution')
    def test_discovery_skips_old_broken_hanging_and_duplicate_candidates(self):
        with tempfile.TemporaryDirectory(prefix='python å space ') as directory:
            root = Path(directory)
            scripts = {
                'old': '#!/bin/sh\nprintf "CGPY|3|10|darwin|%s\\n" "$0"\n',
                'broken': '#!/bin/sh\necho private-url-token\nexit 2\n',
                'hanging': '#!/bin/sh\nexec /bin/sleep 30\n',
                'good': '#!/bin/sh\nprintf "CGPY|3|13|darwin|%s\\n" "$0"\n',
            }
            for name, text in scripts.items():
                (root / name).write_text(text)
                (root / name).chmod(0o700)
            (root / 'duplicate').symlink_to(root / 'old')
            probe = root / 'probe.zsh'
            probe.write_text('''source "$1"
cg_python_candidates() { print -rl -- "$2/old" "$2/duplicate" "$2/broken" "$2/hanging" "$2/good"; }
# Function positional parameters are local; capture the fixture root explicitly.
fixture="$2"
cg_python_candidates() { print -rl -- "$fixture/old" "$fixture/duplicate" "$fixture/broken" "$fixture/hanging" "$fixture/good"; }
cg_find_python || exit 8
print -r -- "$PYTHON"
cg_python_candidates() { print -r -- "$fixture/old"; }
cg_find_python && exit 9
[[ "$CG_PYTHON_FAILURE" == old ]] || exit 10
cg_python_candidates() { print -r -- "$fixture/broken"; }
cg_find_python && exit 11
[[ "$CG_PYTHON_FAILURE" == broken ]] || exit 12
cg_python_candidates() { return 0; }
cg_find_python && exit 13
[[ "$CG_PYTHON_FAILURE" == missing ]] || exit 14
cg_python_failure
''')
            result = subprocess.run([shutil.which('zsh'), str(probe), str(ROOT / 'src/python_discovery.sh'), str(root)],
                                    capture_output=True, text=True, timeout=12)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn(str(root / 'good'), result.stdout)
            self.assertIn('START\n\nReason: No usable Python', result.stdout)
            self.assertNotIn('private-url-token', result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
