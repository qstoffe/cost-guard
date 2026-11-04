"""Independent native browser handoffs without real clipboard or desktop effects."""
from concurrent.futures import ThreadPoolExecutor
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import Mock, patch

from src.web.host import WebHost
from src.web.native_windows import WindowsHost
from src.web.security import BOOTSTRAP_LIMIT, BrowserSession
from src.web.win32_tray import COPY, EXIT, OPEN, NotifyData, Tray, _bind


class BrowserLinksTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Hidden Win32 menu; no icon or clipboard installation')
    def test_native_menu_has_exact_open_copy_exit_order_and_labels(self):
        tray = Tray()
        count = _bind(tray.user, 'GetMenuItemCount', c.c_int, [w.HMENU])
        identifier = _bind(tray.user, 'GetMenuItemID', w.UINT, [w.HMENU, c.c_int])
        text = _bind(tray.user, 'GetMenuStringW', c.c_int,
                     [w.HMENU, w.UINT, w.LPWSTR, c.c_int, w.UINT])
        try:
            self.assertEqual(3, count(tray.menu))
            labels, identifiers = [], []
            for index in range(3):
                buffer = c.create_unicode_buffer(100)
                self.assertGreater(text(tray.menu, index, buffer, len(buffer), 0x400), 0)
                labels.append(buffer.value)
                identifiers.append(identifier(tray.menu, index))
            self.assertEqual([OPEN, COPY, EXIT], identifiers)
            self.assertEqual(['Open Cost Guard', 'Copy Cost Guard link', 'Exit Cost Guard'], labels)
            self.assertFalse(tray.installed)
        finally:
            tray.close()

    def test_pending_links_redeem_independently_once_without_revoking_session_or_csrf(self):
        session = BrowserSession()
        launcher = session.bootstrap()
        opened = session.bootstrap(renew=True)
        copied = session.bootstrap(renew=True)

        first = session.exchange(opened)
        cookie = f'{session.cookie_name}={first[0]}'
        second = session.exchange(launcher)
        third = session.exchange(copied)
        self.assertEqual(3, len({first[0], second[0], third[0]}))
        self.assertEqual(first[1], second[1])
        self.assertEqual(first[1], third[1])
        self.assertEqual(first, session.exchange(session.bootstrap(renew=True), cookie))
        for token in (launcher, opened, copied):
            self.assertIsNone(session.exchange(token))
        self.assertTrue(session.authenticated(cookie))
        self.assertTrue(session.csrf(first[1]))
        self.assertFalse(BrowserSession().authenticated(cookie))
        self.assertIsNone(BrowserSession().exchange(copied))

    def test_browser_activity_slides_repeated_weeks_without_rotating_credentials(self):
        now = Mock(return_value=1000)
        session = BrowserSession(clock=now)
        bearer, csrf = session.exchange(session.bootstrap())
        cookie = f'{session.cookie_name}={bearer}'
        # Daily activity crosses the old eight-hour boundary and three weeks.
        for day in range(1, 22):
            now.return_value = 1000 + day * 86400
            self.assertTrue(session.authenticated(cookie))
            self.assertEqual(bearer, session.activity(cookie))
            self.assertTrue(session.csrf(csrf))
        last_activity = now.return_value
        now.return_value += 6 * 86400 + 86399
        self.assertTrue(session.authenticated(cookie))
        now.return_value = last_activity + 7 * 86400
        self.assertFalse(session.authenticated(cookie))
        self.assertIsNone(session.activity(cookie), 'expired bearer cannot be revived')
        replacement, same_csrf = session.exchange(session.bootstrap())
        self.assertNotEqual(bearer, replacement)
        self.assertEqual(csrf, same_csrf)
        self.assertFalse(session.authenticated(cookie))

    def test_independent_browser_expiry_and_concurrent_renewal_are_coalesced(self):
        now = Mock(return_value=1000)
        session = BrowserSession(clock=now)
        chrome, csrf = session.exchange(session.bootstrap())
        edge, edge_csrf = session.exchange(session.bootstrap(renew=True))
        chrome_cookie = f'{session.cookie_name}={chrome}'
        edge_cookie = f'{session.cookie_name}={edge}'
        now.return_value += 3600
        with ThreadPoolExecutor(max_workers=8) as pool:
            renewals = list(pool.map(session.activity, [chrome_cookie] * 8))
        self.assertEqual(1, renewals.count(chrome))
        self.assertEqual(edge, session.activity(edge_cookie), 'another browser cannot consume renewal')
        self.assertEqual(csrf, edge_csrf)
        for day in range(1, 8):
            now.return_value = 1000 + 3600 + day * 86400
            session.activity(chrome_cookie)
        self.assertTrue(session.authenticated(chrome_cookie))
        self.assertFalse(session.authenticated(edge_cookie))
        self.assertTrue(session.csrf(csrf))

    def test_suspend_counts_as_idle_even_when_monotonic_clock_does_not_advance(self):
        now = Mock(return_value=1000)
        session = BrowserSession(clock=now)
        with patch('src.web.security.time.monotonic', return_value=100):
            bearer, _ = session.exchange(session.bootstrap())
            cookie = f'{session.cookie_name}={bearer}'
            now.return_value += 7 * 86400
            self.assertFalse(session.authenticated(cookie))
            self.assertIsNone(session.activity(cookie))

    def test_expiry_prunes_each_link_and_later_handoff_is_fresh(self):
        session = BrowserSession()
        with patch('src.web.security.time.monotonic', return_value=100):
            first = session.bootstrap()
        with patch('src.web.security.time.monotonic', return_value=110):
            second = session.bootstrap(renew=True)
        with patch('src.web.security.time.monotonic', return_value=220):
            self.assertIsNone(session.exchange(first))
            self.assertIsNotNone(session.exchange(second))
            fresh = session.bootstrap()
        self.assertNotIn(fresh, (first, second))
        self.assertIsNone(session.exchange(None))
        self.assertIsNone(session.exchange('å'))

    def test_capacity_rejects_excess_without_invalidating_existing_links_then_recovers(self):
        session = BrowserSession()
        with patch('src.web.security.time.monotonic', return_value=100):
            tokens = [session.bootstrap(renew=True) for _ in range(BOOTSTRAP_LIMIT)]
            with self.assertRaisesRegex(RuntimeError, '^bootstrap_capacity$'):
                session.bootstrap(renew=True)
            for token in tokens:
                self.assertIsNotNone(session.exchange(token))
            self.assertNotIn(session.bootstrap(renew=True), tokens)
        with patch('src.web.security.time.monotonic', return_value=220):
            self.assertNotIn(session.bootstrap(), tokens)
            self.assertEqual(1, len(session._pending))

    def test_concurrent_handoffs_and_duplicate_redemption_are_serialized(self):
        session = BrowserSession()
        with ThreadPoolExecutor(max_workers=8) as pool:
            tokens = list(pool.map(lambda _: session.bootstrap(renew=True), range(8)))
            outcomes = list(pool.map(session.exchange, tokens + tokens))
        self.assertEqual(8, len(set(tokens)))
        self.assertEqual(8, sum(result is not None for result in outcomes))

    def test_host_copy_uses_same_origin_does_not_open_and_failed_copy_releases_only_its_link(self):
        host = WebHost(Path.cwd(), jobs=Mock())
        host.server = Mock(origin='http://127.0.0.1:49123', session=BrowserSession())
        host.ready = True
        opener, copier = Mock(return_value=True), Mock()
        host.open_browser(opener)
        pending_open = opener.call_args.args[0].split('#bootstrap=')[1]
        copier.side_effect = OSError('private credential must not escape')
        self.assertFalse(host.copy_browser_link(copier))
        self.assertEqual(1, len(host.server.session._pending))
        copier.side_effect = None

        self.assertTrue(host.copy_browser_link(copier))

        copied = copier.call_args.args[0]
        self.assertTrue(copied.startswith('http://127.0.0.1:49123/#bootstrap='))
        self.assertNotEqual(pending_open, copied.split('#bootstrap=')[1])
        self.assertIsNotNone(host.server.session.exchange(pending_open))
        self.assertIsNotNone(host.server.session.exchange(copied.split('#bootstrap=')[1]))
        opener.assert_called_once()
        self.assertFalse(host.stopping.is_set())
        host.stop()
        self.assertFalse(host.copy_browser_link(copier))
        self.assertEqual(2, copier.call_count)

    def test_copy_worker_is_coalesced_and_does_not_delay_exit_or_call_browser(self):
        entered, release = Event(), Event()
        owner = Mock(stopping=Event(), stopped=Event())
        def copy(copier):
            entered.set()
            release.wait(3)
            copier('http://127.0.0.1:49123/#bootstrap=synthetic')
            return True
        owner.copy_browser_link.side_effect = copy
        adapter = WindowsHost(tray=Mock(hwnd=123))
        with patch('src.web.native_windows.copy_text') as clipboard:
            try:
                adapter.dispatch(owner, [COPY])
                self.assertTrue(entered.wait(1))
                adapter.dispatch(owner, [COPY, COPY])
                adapter.dispatch(owner, [EXIT, COPY])
                owner.stop.assert_called_once_with('menu')
            finally:
                release.set()
                adapter.close()
        self.assertFalse(adapter.copy_thread.is_alive())
        owner.copy_browser_link.assert_called_once()
        owner.open_browser.assert_not_called()
        clipboard.assert_called_once_with(123, 'http://127.0.0.1:49123/#bootstrap=synthetic')

    def test_copy_software_fault_is_revoked_and_transferred_to_host_not_silently_retried(self):
        host = WebHost(Path.cwd(), jobs=Mock())
        host.server = Mock(origin='http://127.0.0.1:49123', session=BrowserSession())
        host.ready = True
        fault = ValueError('private')
        adapter = WindowsHost(tray=Mock(hwnd=123))
        with patch('src.web.native_windows.copy_text', side_effect=fault):
            adapter.dispatch(host, [COPY])
            adapter.close()
        self.assertIs(fault, host.failure)
        self.assertEqual('runtime_fault', host.reason)
        self.assertEqual({}, host.server.session._pending)
        self.assertTrue(adapter.copy_results.empty())

    def test_copy_result_feedback_is_on_pump_and_failure_allows_retry(self):
        owner = Mock(stopping=Event(), stopped=Event())
        owner.copy_browser_link.return_value = False
        tray = Mock()
        adapter = WindowsHost(tray)
        adapter.dispatch(owner, [COPY])
        adapter.copy_thread.join(3)
        # Do not allow another worker to overfill the bounded result queue.
        adapter.dispatch(owner, [COPY])
        owner.copy_browser_link.assert_called_once()
        tray.poll.side_effect = lambda: owner.stopped.set() or []
        adapter.run(owner)
        tray.link_copied.assert_called_once_with(False)
        owner.stopped.clear()
        owner.copy_browser_link.return_value = True
        adapter.dispatch(owner, [COPY])
        adapter.copy_thread.join(3)
        adapter.run(owner)
        self.assertEqual(True, tray.link_copied.call_args.args[0])
        self.assertEqual(2, owner.copy_browser_link.call_count)
        owner.stop.assert_not_called()
        adapter.close()

    def test_copy_command_and_feedback_keep_native_ownership_and_fixed_nonsecret_text(self):
        tray = object.__new__(Tray)
        tray.events, tray.taskbar_created = [], 77
        tray.user, tray.shell = Mock(), Mock()
        tray.data = NotifyData()
        tray._window_message(123, 0x111, COPY, 0)
        self.assertEqual([COPY], tray.events)
        for success, expected in ((True, 'Link copied.'), (False, 'Retry Copy Cost Guard link.')):
            tray.link_copied(success)
            self.assertIn(expected, tray.data.szInfo)
            self.assertNotIn('bootstrap', tray.data.szInfo)
            self.assertNotIn('http', tray.data.szInfo)
            self.assertEqual(7, tray.data.uFlags)
        tray.install = Mock()
        tray._window_message(123, 77, 0, 0)
        tray.install.assert_called_once()


if __name__ == '__main__':
    unittest.main()
