"""Synthetic macOS contracts only: never loads AppKit or opens UI on any OS."""
import contextlib
import ctypes as C
import io
from pathlib import Path
import subprocess
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
            self.assertEqual(macos_launch.launch_macos(ROOT), 4)
        self.assertEqual(launch.call_args.args, (ROOT, "src.web.native_macos"))
        self.assertEqual([call.args[0] for call in store.return_value.log.call_args_list],
                         ["app_preparation_failed", "browser_open_failed"])
        self.assertIn("continuing with .command", output.getvalue())
        self.assertIn("Web is running", output.getvalue())

    def test_wrong_os_does_not_touch_state_or_native_api(self):
        with patch.object(macos_launch.sys, "platform", "win32"), \
                patch.object(macos_launch, "InstanceStore") as store, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(macos_launch.launch_macos(ROOT), 1)
        store.assert_not_called()

    def test_source_launcher_is_relative_and_does_not_control_terminal(self):
        source = (ROOT / "macos/Beta/Cost Guard Web.command").read_text()
        self.assertTrue(source.startswith("#!/bin/zsh\n"))
        self.assertIn('$(dirname "$0")/../..', source)
        self.assertIn("(3,11)", source)
        self.assertIn("--launch-macos", source)
        self.assertNotIn("osascript", source)
        self.assertNotIn("kill", source)


if __name__ == "__main__":
    unittest.main()
