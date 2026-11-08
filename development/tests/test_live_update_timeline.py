"""Known synthetic source updates must reach accepted active content, not heartbeat-only PASS."""
from types import SimpleNamespace
import unittest

from development.tests.fixtures.historical_web_source import WireHistory
from src.application.contracts import record


class LiveUpdateTimelineTests(unittest.TestCase):
    def test_owned_source_updates_keep_membership_and_exclude_running_root_from_history_oracle(self):
        source = WireHistory(64, 2, 1794053593853, 0, active_probe=True)
        initial_ids = {row['id'] for row in source.sessions}

        change = source.active_update(1)

        self.assertEqual(1, change['ordinal'])
        self.assertGreater(change['changed_at'], 0)
        self.assertEqual(initial_ids, {row['id'] for row in source.sessions})
        self.assertNotIn('ses_fixture_00000', source.winners)
        self.assertEqual({'ses_fixture_00000': {'type':'running'}}, source.active)
        messages = source.messages['ses_fixture_00000']
        self.assertEqual('ses_fixture_00000_live_update_u1', messages[-2]['id'])
        self.assertNotIn('completed', messages[-1]['time'])
        self.assertEqual('stop', messages[-3]['finish'])
        self.assertEqual('session.updated', source.events[-1]['type'])
        with self.assertRaisesRegex(RuntimeError, 'nonsequential_fixture_update'):
            source.active_update(3)

    def test_rejected_or_inactive_rows_and_heartbeat_cannot_count_as_accepted_or_published_update(self):
        from development.tests.fixtures.live_update_timeline import LiveUpdateTimeline
        now = [10.0]
        row = SimpleNamespace(event_id='ses_fixture_00000_live_update_u1', in_progress=True)
        entry = SimpleNamespace(generation=2, verified_generation=0, capture=None)

        def accept(result, _now):
            if result.generation == entry.generation:
                entry.verified_generation = entry.generation
                entry.capture = SimpleNamespace(rows=(row,))

        cards = SimpleNamespace(accept=accept, sessions={'synthetic':entry})
        timeline = LiveUpdateTimeline(clock=lambda: now[0])
        timeline.attach_cards(cards)
        cards.accept(SimpleNamespace(session_id='synthetic', generation=1, phase='rows'), 10000)
        timeline.publication(record(view=record(active_cards=())))
        self.assertEqual({}, timeline.summary()['accepted'])
        self.assertEqual({}, timeline.summary()['published'])

        cards.accept(SimpleNamespace(session_id='synthetic', generation=2, phase='rows'), 10000)
        now[0] = 10.5
        timeline.publication(record(view=record(active_cards=(record(rows=(record(prompt=record(
            event_id=row.event_id, in_progress=False)),)),))))
        self.assertEqual({}, timeline.summary()['published'])
        timeline.publication(record(view=record(active_cards=(record(rows=(record(prompt=record(
            event_id=row.event_id, in_progress=True)),)),))))

        self.assertEqual({1:10.0}, timeline.summary()['accepted'])
        self.assertEqual({1:10.5}, timeline.summary()['published'])

    def test_numeric_deadline_lateness_and_stage_spans_do_not_change_return_values(self):
        from development.tests.fixtures.live_update_timeline import LiveUpdateTimeline
        now = [2.5]
        cpu = [1.0]
        owner = SimpleNamespace(source=SimpleNamespace(), service_completed=lambda: 'completed')

        def account_history():
            now[0] += .5
            cpu[0] += .125
            return 'history'

        owner._account_history = account_history

        def tick():
            now[0] += .25
            return 'frame'

        driver = SimpleNamespace(coordinator=owner, tick=tick)
        runtime = SimpleNamespace(_publish_frame=lambda *_: 'published')
        timeline = LiveUpdateTimeline(clock=lambda: now[0], cpu_clock=lambda: cpu[0])
        timeline.attach_runtime(runtime, driver)
        publication_due = 2.0  # The real runtime's existing loop-local scalar.

        self.assertEqual('frame', driver.tick())
        self.assertEqual('completed', owner.service_completed())
        self.assertEqual('history', owner._account_history())

        summary = timeline.summary()
        self.assertEqual(.5, summary['publication_turns'][0]['deadline_lateness_seconds'])
        self.assertEqual(.25, summary['publication_turns'][0]['seconds'])
        self.assertEqual(['driver_tick', 'completion_turn', 'account_history'], [row['stage'] for row in summary['spans']])
        self.assertEqual((.5, .125), tuple(summary['spans'][-1][key] for key in ('seconds', 'thread_cpu_seconds')))


if __name__ == '__main__':
    unittest.main()
