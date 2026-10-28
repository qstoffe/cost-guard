"""Bounded client freshness and terminal-state regressions."""
from pathlib import Path
import io
import shutil
import subprocess
from threading import BoundedSemaphore
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.web.events import EventHub
from src.web.http import RequestHandler

ROOT = Path(__file__).resolve().parents[2]


class ConnectionTests(unittest.TestCase):
    def test_healthy_idle_stream_survives_old_rotation_deadline(self):
        hub = EventHub('fixture')
        reads = []

        def idle_read(cursor):
            reads.append(cursor)
            if len(reads) == 4:
                hub.close('menu')
            return hub.sequence, []

        hub.read = idle_read
        handler = RequestHandler.__new__(RequestHandler)
        handler.deadline = None
        handler.headers = {}
        slots = BoundedSemaphore(4)
        handler.server = SimpleNamespace(_streams=slots,
            lifecycle=SimpleNamespace(events=hub),
            session=SimpleNamespace(authenticated=lambda cookie: True))
        handler.wfile = io.BytesIO()
        handler.send_response_only = lambda code: None
        handler.send_header = lambda key, value: None
        handler.end_headers = lambda: None
        elapsed = iter(range(0, 1000, 30))

        with patch('src.web.http.time.monotonic', side_effect=lambda: next(elapsed)):
            handler.stream_events()

        self.assertEqual(4, len(reads), 'healthy stream must not be closed on a wall-clock timer')
        self.assertIn(b': heartbeat', handler.wfile.getvalue())
        self.assertIn(b'event: terminal', handler.wfile.getvalue())
        self.assertEqual(4, slots._value, 'stream admission is released on exit')

    def test_terminal_close_after_empty_read_still_reaches_browser(self):
        hub = EventHub('fixture')

        def closing_read(cursor):
            hub.close('source_changed')
            return 0, []

        hub.read = closing_read
        handler = RequestHandler.__new__(RequestHandler)
        handler.deadline = None
        handler.headers = {}
        handler.server = SimpleNamespace(_streams=BoundedSemaphore(4),
            lifecycle=SimpleNamespace(events=hub),
            session=SimpleNamespace(authenticated=lambda cookie: True))
        handler.wfile = io.BytesIO()
        handler.send_response_only = lambda code: None
        handler.send_header = lambda key, value: None
        handler.end_headers = lambda: None

        handler.stream_events()

        wire = handler.wfile.getvalue()
        self.assertEqual(1, wire.count(b'event: terminal'))
        self.assertIn(b'source_changed', wire)

    @unittest.skipUnless(shutil.which('node'), 'optional JavaScript runtime unavailable')
    def test_connection_watchdog_and_terminal_identity(self):
        result = subprocess.run(['node', 'development/tests/integration/web_connection.cjs'],
                                cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('web connection passed', result.stdout)
