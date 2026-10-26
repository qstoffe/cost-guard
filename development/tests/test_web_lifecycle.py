"""Deterministic lifecycle proof; no browser, native icon, provider or model requests."""
import http.client
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.web.change_guard import SourceGuard
from src.web.host import WebHost
from src.web.instance_state import InstanceStore, SCHEMA, checkout_identity
from src.web import lifecycle
from src.web.process_identity import InstanceConflict, process_identity, terminate_owned


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        # Lifecycle tests must not start real source/pricing/account acquisition.
        def idle_acquisition():
            return SimpleNamespace(tick=lambda: None, close=lambda: None,
                error=None, terminal=False, observed_at_ms=None,
                coordinator=SimpleNamespace(report_service=None,
                    today_ccost=SimpleNamespace(history_pending=False)))

        acquisition = patch("src.web.composition.live_acquisition", side_effect=idle_acquisition)
        acquisition.start()
        self.addCleanup(acquisition.stop)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "checkout space å"
        (self.root / "src/web/assets").mkdir(parents=True)
        self.source = self.root / "src/code.py"
        self.source.write_text("pass\n")
        self.home = self.base / "private"

    def store(self, root=None):
        return InstanceStore(root or self.root, data_home=self.home)

    def state(self, store, **changes):
        result = {"schema": SCHEMA, "checkout": store.key, "nonce": "a" * 32,
                  "control": "b" * 64, "pid": 1234,
                  "process": {"birth": "original", "image": "python"},
                  "port": 49152, "address": "127.0.0.1", "build": "test", "ready_ns": 1}
        result.update(changes)
        return result

    def test_guard_modification_addition_removal_rename_and_assets(self):
        for operation in ("modify", "add", "remove", "rename", "asset", "entry", "manifest"):
            with self.subTest(operation=operation):
                self.source.write_text("pass\n")
                guard = SourceGuard(self.root, interval=0)
                if operation == "modify":
                    self.source.write_text("changed = True\n")
                elif operation == "add":
                    (self.root / "src/new.py").write_text("pass")
                elif operation == "remove":
                    self.source.unlink()
                elif operation == "rename":
                    self.source.rename(self.root / "src/renamed.py")
                elif operation == "asset":
                    (self.root / "src/web/assets/app.js").write_text("changed")
                elif operation == "entry":
                    (self.root / "cost-guard-web.py").write_text("pass")
                else:
                    (self.root / "pyproject.toml").write_text("[project]")
                self.assertEqual(guard.check(), "source_changed")
                self.assertEqual(guard.check(), "source_changed")

    def test_guard_clock_exclusions_and_indistinguishable_metadata_limit(self):
        now = [10]
        guard = SourceGuard(self.root, clock=lambda: now[0])
        for name in ("development/a.py", "src/__pycache__/a.py", "src/cache/a.py",
                     "src/logs/a.py", ".git/a.py", ".venv/a.py", "README.md",
                     "config/user-config.jsonc", "src/a.pyc"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("ignored")
        info = self.source.stat()
        self.source.write_text("stop\n")  # Same size and restored mtime: documented best-effort miss.
        os.utime(self.source, ns=(info.st_atime_ns, info.st_mtime_ns))
        now[0] = 16
        self.assertEqual(guard.check(), "unchanged")
        self.source.write_text("real change")
        self.assertEqual(guard.check(), "unchanged")  # Cheap interval, not every request.
        now[0] = 22
        self.assertEqual(guard.check(), "source_changed")

    def test_transient_stat_failure_retains_baseline_and_retries(self):
        guard = SourceGuard(self.root, interval=0)
        with patch.object(guard, "_snapshot", side_effect=PermissionError()):
            self.assertEqual(guard.check(), "source_check_unavailable")
        self.assertEqual(guard.check(), "unchanged")
        self.source.unlink()
        self.assertEqual(guard.check(), "source_changed")

    def test_guard_does_not_follow_runtime_symlinks(self):
        outside = self.base / "outside"
        outside.mkdir()
        target = outside / "secret.py"
        target.write_text("original")
        try:
            (self.root / "src/linked").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("OS does not permit creating test symlinks")
        guard = SourceGuard(self.root, interval=0)
        target.write_text("external change must not be observed")
        self.assertEqual(guard.check(), "unchanged")
        (self.root / "src/linked").unlink()
        # Unallowlisted extensionless link is ignored, never traversed.
        self.assertEqual(guard.check(), "unchanged")

    def test_checkout_identity_state_atomicity_corruption_and_distinct_checkouts(self):
        store = self.store()
        self.assertEqual(checkout_identity(self.root / "src/.."), store.key)
        if os.name == "nt":
            self.assertEqual(checkout_identity(str(self.root).upper()), store.key)
        other = self.base / "other checkout"
        other.mkdir()
        self.assertNotEqual(self.store(other).key, store.key)
        state = self.state(store)
        store.write(state)
        self.assertEqual(store.read(), state)
        store.remove("c" * 32)
        self.assertTrue(store.state_path.exists())
        self.assertEqual(list(store.directory.glob("*.tmp")), [])
        store.state_path.write_text("{broken")
        with self.assertRaisesRegex(InstanceConflict, "corrupt_instance_state"):
            store.read()
        # Corruption is a conflict, not permission to kill or launch an unknown duplicate.
        with patch.object(lifecycle, "InstanceStore", return_value=store), patch.object(lifecycle, "spawn_detached") as spawn:
            with self.assertRaises(InstanceConflict):
                lifecycle.launch(self.root, "src.web.native_windows", opener=Mock())
            spawn.assert_not_called()

    def test_private_log_is_bounded_and_allowlisted(self):
        store = self.store()
        store.log("secret arbitrary diagnostic")
        path = store.directory / "lifecycle.log"
        self.assertNotIn("secret", path.read_text())
        path.write_text("x" * 33000)
        store.log("ready")
        self.assertLess(path.stat().st_size, 100)
        if os.name != "nt":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(store.directory.stat().st_mode & 0o777, 0o700)

    def test_os_lock_serializes_and_crash_releases_both_locks(self):
        store = self.store()
        code = ("from src.web.instance_state import InstanceStore; import sys; "
                "s=InstanceStore(sys.argv[1],data_home=sys.argv[2]); "
                "s.lock(timeout=0).__enter__()")
        # A separate interpreter, not another thread: the OS lock is what serializes.
        with store.lock():
            result = subprocess.run([sys.executable, "-c", code, str(self.root), str(self.home)],
                                    capture_output=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
        with store.lock(timeout=0):
            pass
        with store.lock(lifetime=True, timeout=0):
            with self.assertRaises(InstanceConflict):
                with self.store().lock(lifetime=True, timeout=0):
                    pass
        code = ("from src.web.instance_state import InstanceStore; import sys,time; "
                "s=InstanceStore(sys.argv[1],data_home=sys.argv[2]); "
                "a=s.lock(); b=s.lock(lifetime=True); a.__enter__(); b.__enter__(); "
                "print('locked',flush=True); time.sleep(30)")
        child = subprocess.Popen([sys.executable, "-c", code, str(self.root), str(self.home)],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            # Pipe read is bounded by a timer even if startup regresses.
            deadline = threading.Timer(5, child.kill)
            deadline.start()
            try:
                self.assertEqual(child.stdout.readline(), b"locked\r\n" if os.name == "nt" else b"locked\n")
            finally:
                deadline.cancel()
                deadline.join()
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
            child.stdout.close()
        with store.lock(timeout=0), store.lock(timeout=0, lifetime=True):
            pass

    def test_stale_and_reused_pids_never_contact_or_terminate(self):
        store = self.store()
        state = self.state(store)
        for actual in (None, {"birth": "reused", "image": "python"}):
            store.write(state)
            with patch.object(lifecycle, "process_identity", return_value=actual), \
                    patch.object(lifecycle, "control") as request, \
                    patch.object(lifecycle, "terminate_owned") as terminate:
                lifecycle.stop_existing(store, state, grace=0)
                request.assert_not_called()
                terminate.assert_not_called()
                self.assertIsNone(store.read())

    def test_unresponsive_owned_process_revalidates_before_forcing(self):
        store = self.store()
        state = self.state(store)
        store.write(state)
        with patch.object(lifecycle, "process_identity", side_effect=[state["process"], None]), \
                patch.object(lifecycle, "control", side_effect=TimeoutError()), \
                patch.object(lifecycle, "terminate_owned") as terminate:
            lifecycle.stop_existing(store, state, grace=0)
            terminate.assert_called_once_with(state["pid"], state["process"])
        self.assertIsNone(store.read())

    def test_unknown_port_occupant_is_conflict_not_kill_authority(self):
        store = self.store()
        state = self.state(store)
        store.write(state)
        with patch.object(lifecycle, "process_identity", return_value=state["process"]), \
                patch.object(lifecycle, "control", side_effect=InstanceConflict("instance_control_conflict")), \
                patch.object(lifecycle, "terminate_owned") as terminate:
            with self.assertRaises(InstanceConflict):
                lifecycle.stop_existing(store, state, grace=0)
            terminate.assert_not_called()
            self.assertEqual(store.read(), state)

    def test_native_process_birth_identity_and_owned_termination(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: child.poll() is None and child.kill())
        birth = process_identity(child.pid)
        self.assertIsNotNone(birth)
        with self.assertRaises(InstanceConflict):
            terminate_owned(child.pid, {**birth, "birth": "wrong"})
        self.assertIsNone(child.poll())
        if os.name == "nt" or hasattr(os, "pidfd_open"):
            terminate_owned(child.pid, birth)
            child.wait(timeout=5)
        else:
            child.terminate()
            child.wait(timeout=5)

    def test_detach_uses_private_cwd_and_no_inherited_console_handles(self):
        store = self.store()
        with patch.object(lifecycle.subprocess, "Popen") as popen:
            lifecycle.spawn_detached(self.root, store, "a" * 32, "src.web.native_windows")
        arguments, options = popen.call_args
        self.assertIn(str(self.root / "cost-guard-web.py"), arguments[0])
        self.assertEqual(options["cwd"], str(store.directory))
        self.assertTrue(options["close_fds"])
        for stream in ("stdin", "stdout", "stderr"):
            self.assertEqual(options[stream], subprocess.DEVNULL)
        if os.name == "nt":
            self.assertTrue(options["creationflags"] & subprocess.DETACHED_PROCESS)
        else:
            self.assertTrue(options["start_new_session"])

    def test_force_stopped_parent_does_not_orphan_a_blocked_owned_report(self):
        code = ("from src.web.jobs import ReportJobs; from src.reports import ReportRequest,ReportKind; "
                "from development.tests.fixtures.web_reports import finite_report; import time; "
                "jobs=ReportJobs(target=finite_report); jobs.submit(ReportRequest(ReportKind.TOKEN_MIX)); "
                "jobs.tick(); print(jobs._active[1].pid,flush=True); time.sleep(30)")
        parent = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        worker_pid = birth = None
        deadline = threading.Timer(8, parent.kill)
        deadline.start()
        try:
            worker_pid = int(parent.stdout.readline())
            birth = process_identity(worker_pid)
            self.assertIsNotNone(birth)
            parent.kill()  # Only our own Popen process; simulate host crash/force-stop.
            parent.wait(timeout=5)
            until = time.monotonic() + 5
            while process_identity(worker_pid) == birth and time.monotonic() < until:
                time.sleep(0.05)
            self.assertNotEqual(process_identity(worker_pid), birth)
        finally:
            deadline.cancel()
            deadline.join()
            if parent.poll() is None:
                parent.kill()
            parent.wait(timeout=5)
            parent.stdout.close()
            if worker_pid and birth and process_identity(worker_pid) == birth:
                terminate_owned(worker_pid, birth)

    def test_overlapping_launch_coalesces_and_failed_browser_is_not_server_failure(self):
        store = self.store()
        state = self.state(store, ready_ns=time.time_ns() + 10**12)
        store.write(state)
        reply = {"nonce": state["nonce"], "ready": True,
                 "url": f"http://127.0.0.1:{state['port']}/#bootstrap=short"}
        with patch.object(lifecycle, "InstanceStore", return_value=store), \
                patch.object(lifecycle, "process_identity", return_value=state["process"]), \
                patch.object(lifecycle, "control", return_value=reply), \
                patch.object(lifecycle, "spawn_detached") as spawn:
            result = lifecycle.launch(self.root, "src.web.native_windows", opener=Mock(side_effect=OSError()))
            self.assertTrue(result.coalesced)
            self.assertFalse(result.browser_opened)
            spawn.assert_not_called()
            self.assertEqual(store.read(), state)

    def test_same_build_deliberate_launch_restarts_and_waits_for_verified_shell(self):
        stages = []
        store = self.store()
        old = self.state(store)
        store.write(old)
        child = Mock(pid=9876)
        child.poll.return_value = None
        new = self.state(store, pid=child.pid, nonce="c" * 32, ready_ns=time.time_ns())

        def spawn(*args):
            new["nonce"] = args[2]
            store.write(new)
            return child

        def request(state, action):
            if action == "open":
                self.assertEqual(stages, ["arbitration", "restart", "host", "browser"])
            return {"ready": True, "url": f"http://127.0.0.1:{state['port']}/#bootstrap=short"}

        with patch.object(lifecycle, "InstanceStore", return_value=store), \
                patch.object(lifecycle, "stop_existing") as stop, \
                patch.object(lifecycle, "spawn_detached", side_effect=spawn), \
                patch.object(lifecycle, "process_identity", return_value=new["process"]), \
                patch.object(lifecycle, "control", side_effect=request):
            result = lifecycle.launch(self.root, "src.web.native_windows", opener=lambda url: True,
                                      progress=stages.append)
        stop.assert_called_once_with(store, old)
        self.assertFalse(result.coalesced)
        self.assertTrue(result.browser_opened)

    def test_startup_exec_keeps_birth_and_requires_current_recorded_image(self):
        initial = {"birth": "owned-start", "image": "launcher"}
        for current, recorded, accepted in (
            ({"birth": "owned-start", "image": "interpreter"}, {"birth": "owned-start", "image": "interpreter"}, True),
            ({"birth": "foreign-start", "image": "interpreter"}, {"birth": "foreign-start", "image": "interpreter"}, False),
            ({"birth": "owned-start", "image": "interpreter"}, {"birth": "owned-start", "image": "forged"}, False),
        ):
            with self.subTest(current=current, recorded=recorded):
                store = self.store()
                child = Mock(pid=9876)
                child.poll.return_value = None
                state = self.state(store, pid=child.pid, process=recorded, ready_ns=time.time_ns())

                def spawn(root, private_store, nonce, module):
                    state["nonce"] = nonce
                    store.write(state)
                    return child

                reply = {"ready": True, "url": f"http://127.0.0.1:{state['port']}/#bootstrap=synthetic"}
                with patch.object(lifecycle, "InstanceStore", return_value=store), \
                        patch.object(lifecycle, "spawn_detached", side_effect=spawn), \
                        patch.object(lifecycle, "process_identity", side_effect=[initial, current]), \
                        patch.object(lifecycle, "control", return_value=reply):
                    try:
                        if accepted:
                            self.assertTrue(lifecycle.launch(self.root, "src.web.native_macos", opener=lambda url: True).browser_opened)
                            child.terminate.assert_not_called()
                        else:
                            with self.assertRaisesRegex(InstanceConflict, "instance_start_conflict"):
                                lifecycle.launch(self.root, "src.web.native_macos", opener=lambda url: True)
                            child.terminate.assert_called_once()
                    finally:
                        store.remove(state["nonce"])

    def test_two_simultaneous_launches_have_one_winner_and_do_not_kill_it(self):
        store = self.store()
        child = Mock(pid=9876)
        child.poll.return_value = None
        first_spawned = threading.Event()
        second_invoked = threading.Event()
        outcomes, failures = [], []

        def clock():
            if threading.current_thread().name == "second-launch":
                second_invoked.set()
                return 11
            return 10

        def spawn(root, private_store, nonce, module):
            first_spawned.set()
            if not second_invoked.wait(3):
                raise AssertionError("second launch never entered")
            store.write(self.state(store, nonce=nonce, pid=9876, ready_ns=12))
            return child

        def request(state, action):
            return {"ready": True, "url": f"http://127.0.0.1:{state['port']}/#bootstrap=short"}

        def run():
            try:
                outcomes.append(lifecycle.launch(self.root, "src.web.native_windows", opener=lambda url: True))
            except Exception as error:
                failures.append(error)

        with patch.object(lifecycle, "InstanceStore", return_value=store), \
                patch.object(lifecycle.time, "time_ns", side_effect=clock), \
                patch.object(lifecycle, "spawn_detached", side_effect=spawn) as detached, \
                patch.object(lifecycle, "process_identity", return_value={"birth": "original", "image": "python"}), \
                patch.object(lifecycle, "control", side_effect=request), \
                patch.object(lifecycle, "stop_existing") as stop:
            first = threading.Thread(target=run, name="first-launch")
            second = threading.Thread(target=run, name="second-launch")
            first.start()
            self.assertTrue(first_spawned.wait(3))
            second.start()
            first.join(5)
            second.join(5)
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(failures, [])
            self.assertEqual(len(outcomes), 2)
            self.assertEqual({item.instance for item in outcomes}, {store.read()["nonce"]})
            self.assertEqual(sorted(item.coalesced for item in outcomes), [False, True])
            detached.assert_called_once()
            stop.assert_not_called()

    def test_source_change_stops_host_closes_socket_and_manual_start_uses_new_baseline(self):
        owner = WebHost(self.root)
        owner.guard.interval = 0
        owner.guard.next_check = 0
        owner.start()
        self.addCleanup(owner.close)
        owner.publish_ready()
        port = owner.server.server_port
        self.source.write_text("changed source\n")
        self.assertTrue(owner.stopped.wait(5))
        self.assertEqual(owner.reason, "source_changed")
        owner.stop("menu")
        self.assertEqual(owner.reason, "source_changed")
        owner.close()
        with self.assertRaises(OSError):
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            try:
                connection.request("GET", "/health")
            finally:
                connection.close()
        later = WebHost(self.root)
        later.start()
        self.addCleanup(later.close)
        later.publish_ready()
        self.assertNotEqual(later.nonce, owner.nonce)
        self.assertEqual(later.guard.check(), "unchanged")

    def test_gui_main_thread_readiness_cleanup_and_dead_http_not_healthy_icon(self):
        owner = WebHost(self.root, store=self.store())
        main_thread = threading.get_ident()
        calls = []

        class Gui:
            def run(self, host):
                calls.append(("run", threading.get_ident()))
                host.publish_ready()
                self.state = host.store.read()
                with patch.object(host.server, "handle_request", side_effect=RuntimeError("sensitive")):
                    if not host.stopped.wait(3):
                        raise AssertionError("server fault did not signal GUI")

            def close(self):
                calls.append(("close", threading.get_ident()))

        gui = Gui()
        owner.run_gui(gui)
        self.assertEqual(calls, [("run", main_thread), ("close", main_thread)])
        self.assertEqual(owner.reason, "runtime_fault")
        self.assertIsNone(owner.store.read())

    def test_gui_startup_failure_and_premature_return_close_server_and_jobs(self):
        for failure in (True, False):
            owner = WebHost(self.root)
            gui = Mock()
            if failure:
                gui.run.side_effect = RuntimeError("native GUI unavailable")
                with self.assertRaises(RuntimeError):
                    owner.run_gui(gui)
            else:
                owner.run_gui(gui)
            self.assertFalse(owner.ready)
            self.assertTrue(owner.stopped.is_set())
            gui.close.assert_called_once()

    def test_managed_fatal_failure_is_nonzero_sanitized_and_outside_checkout(self):
        from src.web import main
        store = self.store()
        gui = Mock()
        gui.run.side_effect = ValueError("private exception message must not be serialized")
        module = Mock()
        module.create_host.return_value = gui
        with patch.object(main, "InstanceStore", return_value=store), \
                patch.object(main.importlib, "import_module", return_value=module), \
                contextlib.redirect_stderr(io.StringIO()):
            result = main.managed(self.root, "a" * 32, "src.web.native_windows")
        self.assertEqual(result, 1)
        self.assertFalse((self.root / "logs").exists())
        logs = list(store.directory.rglob("*.log"))
        self.assertTrue(logs)
        for path in logs:
            self.assertNotIn("private exception message", path.read_text())
        self.assertIsNone(store.read())

    def test_failed_start_cleans_only_the_spawned_child_and_never_claims_ready(self):
        store = self.store()
        child = Mock(pid=9876)
        child.poll.return_value = 1
        with patch.object(lifecycle, "InstanceStore", return_value=store), \
                patch.object(lifecycle, "spawn_detached", return_value=child), \
                patch.object(lifecycle, "process_identity", return_value=None), \
                patch.object(lifecycle, "control") as request:
            with self.assertRaisesRegex(InstanceConflict, "gui_or_server_start_failed"):
                lifecycle.launch(self.root, "src.web.native_windows", opener=Mock())
            child.terminate.assert_not_called()
            request.assert_not_called()
        self.assertIsNone(store.read())

    def test_control_authentication_instance_identity_and_old_browser_cookie(self):
        owner = WebHost(self.root)
        owner.start()
        self.addCleanup(owner.close)
        owner.publish_ready()
        state = self.state(self.store(), nonce=owner.nonce, control=owner.control,
                           build=owner.identity()["build"], port=owner.server.server_port)
        self.assertTrue(lifecycle.control(state, "status")["ready"])
        with self.assertRaises(InstanceConflict):
            lifecycle.control({**state, "control": "0" * 64}, "stop")
        with self.assertRaises(InstanceConflict):
            lifecycle.control({**state, "nonce": "0" * 32}, "status")
        connection = http.client.HTTPConnection("127.0.0.1", state["port"], timeout=2)
        try:
            connection.request("POST", "/control/stop", headers={
                "Origin": owner.server.origin, "X-CG-Control": owner.control, "Content-Length": "0"})
            response = connection.getresponse()
            self.assertEqual(response.status, 403)
            response.read()
        finally:
            connection.close()
        self.assertFalse(owner.stopping.is_set())
        old_cookie, _ = owner.server.session.exchange(owner.server.session.bootstrap())
        # New Open link doesn't invalidate an already authenticated tab in same instance.
        owner.browser_url()
        current_cookie, _ = owner.server.session.exchange(owner.server.session.bootstrap())
        self.assertEqual(current_cookie, old_cookie)
        later = WebHost(self.root)
        self.addCleanup(later.close)
        self.assertFalse(later.authorized(owner.control))
        self.assertFalse(later.server)  # No server started just by construction.
        from src.web.security import BrowserSession
        self.assertFalse(BrowserSession().authenticated("cg_session=" + old_cookie))
        lifecycle.control(state, "stop")
        self.assertTrue(owner.stopped.wait(5))


if __name__ == "__main__":
    unittest.main()
