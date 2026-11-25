"""Execution ancestry, canonical identities and event-time subagent cost oracles."""
from dataclasses import replace
from decimal import Decimal
import unittest

from development.tests.fixtures.active_hour import epoch
from development.tests.test_ai_stats_tokens import entry
from src.analysis.ai_stats import StatsRoot, StatsObservation
from src.analysis.timezones import calendar_periods
from src.domain import TokenUsage


class SubagentStatsTests(unittest.TestCase):
    NOW = epoch('2026-11-12T12:00:00+00:00')

    def request(self, sid, *, parent='root', root='root', stamp=None, message=None, amount=10):
        return replace(entry(sid, self.NOW - 1000 if stamp is None else stamp,
                             TokenUsage(output=amount), message=message or sid),
                       parent_session_id=parent, root_session_id=root)

    def metrics(self, roots, *, now=None, period='all', valuation=None, zone='UTC'):
        now = now or self.NOW
        return {m.metric: m for m in StatsObservation(roots, valuation or (lambda _m, t: Decimal(t.output)),
            now=now, zone=zone).period(period=period, start=dict(calendar_periods(zone, now))[period]).metrics}

    def test_root_followups_compaction_empty_launch_and_pending_fallback_are_never_child_cost(self):
        main = self.request('root', parent=None)
        summary = replace(main, message_id='summary', summary=True)
        root = StatsRoot('root', 'Root', (main, summary), (), session_parents=(('unused-child', 'root'),))
        pending = StatsRoot('pending', 'Pending', (), ((self.NOW - 2000, 1000, False),), cost_pending=True)

        metrics = self.metrics((root, pending))

        self.assertEqual(Decimal('20.003'), metrics['total-cost'].value)
        self.assertEqual(0, metrics['subagent-cost'].value)
        self.assertEqual((), metrics['subagent-cost'].podium)

    def test_unknown_foreign_cycles_and_conflicting_ancestry_are_not_promoted(self):
        entries = (self.request('unknown', parent=None, root=None),
                   self.request('foreign', root='other'),
                   self.request('orphan', parent='absent'),
                   self.request('cycle', parent='cycle'),
                   self.request('conflict'))
        entries = tuple(replace(e, completed_at_ms=self.NOW - 1000 - i) for i, e in enumerate(entries))
        root = StatsRoot('root', 'Root', entries, (), session_parents=(('conflict', 'other'),))

        metrics = self.metrics((root,))

        self.assertEqual(50, metrics['total-cost'].value)
        self.assertEqual(0, metrics['subagent-cost'].value)
        self.assertEqual('partial', metrics['subagent-cost'].status)
        self.assertIn('unknown-subagent-ancestry', metrics['subagent-cost'].reasons)

    def test_no_request_intermediate_parent_and_nested_step_clone_siblings_count_once(self):
        child = self.request('child', parent='intermediate')
        step = replace(child, step_part_id='step')
        clone = replace(step, session_id='clone-child', root_session_id='clone-root',
                        parent_session_id='clone-root', message_id='cloned')
        sibling = self.request('sibling', message='independent', stamp=self.NOW - 500)
        root = StatsRoot('root', 'Root', (child, step, step, sibling), (),
                         session_parents=(('intermediate', 'root'),))
        cloned = StatsRoot('clone-root', 'Clone', (clone,), ())

        metrics = self.metrics((cloned, root))

        self.assertEqual(20, metrics['total-cost'].value)
        self.assertEqual(20, metrics['subagent-cost'].value)
        self.assertEqual(20, metrics['subagent-cost'].podium[0].value)

    def test_foreign_source_cannot_borrow_the_matching_session_tree(self):
        child = replace(self.request('child'), source_instance='expected')
        foreign = replace(child, source_instance='foreign', message_id='foreign', completed_at_ms=self.NOW - 500)
        root = StatsRoot('root', 'Root', (child, foreign), (), source_instance='expected')

        metrics = self.metrics((root,))

        self.assertEqual(20, metrics['total-cost'].value)
        self.assertEqual(10, metrics['subagent-cost'].value)
        self.assertIn('unknown-subagent-ancestry', metrics['subagent-cost'].reasons)

    def test_estimated_partial_usage_reuses_total_value_but_not_unattributed_pending_residual(self):
        partial = replace(self.request('child'), tokens=TokenUsage(input=4, known_fields=('input',)))
        root = StatsRoot('root', 'Root', (partial,), ())
        pending = StatsRoot('pending', 'Pending', (), ((self.NOW - 2000, 1000, False),), cost_pending=True)

        metrics = self.metrics((root, pending), valuation=lambda *_: None)

        self.assertEqual(Decimal('.003012'), metrics['subagent-cost'].value)
        self.assertEqual(Decimal('.006012'), metrics['total-cost'].value)
        self.assertEqual(metrics['subagent-cost'].value, metrics['subagent-cost'].podium[0].value)

    def test_all_periods_use_child_completion_not_parent_activity_and_dst_local_midnight(self):
        for now in (self.NOW, epoch('2026-03-29T12:00:00+00:00'), epoch('2026-10-25T12:00:00+00:00')):
            for period, start in calendar_periods('Europe/Stockholm', now):
                boundary = start if start is not None else now - 100_000
                main = self.request('root', parent=None, stamp=now - 500, amount=100)
                before = self.request('old', stamp=boundary - 1, amount=20)
                at = self.request('child', stamp=boundary, amount=30)
                late = self.request('late', parent='child', stamp=now - 1, amount=40)
                missing = self.request('missing', stamp=0, amount=50)
                future = self.request('future', stamp=now + 1, amount=60)
                root = StatsRoot('root', 'Root', (main, before, at, late, missing, future),
                                 ((boundary - 10000, 1000, False),), source_complete=False)

                metrics = self.metrics((root,), now=now, period=period, zone='Europe/Stockholm')

                with self.subTest(now=now, period=period):
                    self.assertEqual(140 if start is None else 70, metrics['subagent-cost'].value)
                    self.assertEqual(240 if start is None else 170, metrics['total-cost'].value)


if __name__ == '__main__':
    unittest.main()
