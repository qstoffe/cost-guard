"""End-to-end lifecycle controls and truthful primary/cleanup diagnostics."""
from contextlib import redirect_stdout
import io
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from development.tests.fixtures.web_lifecycle import run_cycle
from development.tests.integration.web_live_observations import ProbeObservations, probe_lifecycle


class RepeatabilityTests(unittest.TestCase):
    def test_serial_coherent_daily_cards_and_stream_owns_no_orphans(self):
        run_cycle()

    def test_cancelled_report_two_subscribers_and_repeated_close(self):
        run_cycle(competing=True)

    def test_failed_daily_is_not_empty_success(self):
        run_cycle(failed_daily=True)

    def test_authenticated_http_timeout_is_real_and_does_not_prevent_shutdown(self):
        run_cycle(http_timeout=True)

    def test_probe_preserves_primary_and_cleanup_exception_objects(self):
        primary, cleanup = TimeoutError('private-source'), RuntimeError('private-cleanup')
        host = SimpleNamespace(live=None, stop=Mock(), close=Mock(side_effect=cleanup))
        output = io.StringIO()
        observations = ProbeObservations()
        observations.stage = 'daily'
        with redirect_stdout(output), self.assertRaises(ExceptionGroup) as caught:
            with probe_lifecycle(host, [], observations):
                raise primary
        self.assertEqual((primary, cleanup), caught.exception.exceptions)
        self.assertIn('http_timeout', output.getvalue())
        self.assertIn('"phase": "daily"', output.getvalue())
        self.assertNotIn('private-', output.getvalue())


if __name__ == '__main__':
    unittest.main()
