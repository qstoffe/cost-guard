"""Opt-in owner attribution separates nested work and never retains call payloads."""
from pathlib import Path
from threading import Barrier, Event, Thread
from types import SimpleNamespace
import unittest


class OwnerCostTimelineTests(unittest.TestCase):
    def test_nested_stage_cpu_and_wall_are_exclusive_and_original_values_are_returned(self):
        from development.tests.fixtures.owner_cost_timeline import OwnerCostTimeline
        wall, cpu = [0.0], [0.0]
        observer = OwnerCostTimeline(Path('.'), clock=lambda: wall[0], cpu=lambda: cpu[0])

        def child(_private):
            wall[0] += 3
            cpu[0] += 2
            return 'child'

        owner = SimpleNamespace(child=child)
        observer.wrap(owner, 'child', 'child')

        def parent(private):
            self.assertEqual('child', owner.child(private))
            wall[0] += 4
            cpu[0] += 1
            return 'parent'

        owner.parent = parent
        observer.wrap(owner, 'parent', 'parent')

        self.assertEqual('parent', owner.parent('private argument never evidence'))

        stages = {row['stage']:row for row in observer.summary()['stages']}
        self.assertEqual(7, stages['parent']['wall_seconds'])
        self.assertEqual(3, stages['parent']['thread_cpu_seconds'])
        self.assertEqual(4, stages['parent']['exclusive_wall_seconds'])
        self.assertEqual(1, stages['parent']['exclusive_thread_cpu_seconds'])
        self.assertEqual(2, stages['child']['exclusive_thread_cpu_seconds'])
        self.assertNotIn('private argument', str(observer.summary()))
        observer.close()

    def test_failed_call_records_cost_and_unwinds_before_next_call(self):
        from development.tests.fixtures.owner_cost_timeline import OwnerCostTimeline
        observer = OwnerCostTimeline(Path('.'))

        def fail():
            raise ValueError('private failure payload')

        owner = SimpleNamespace(call=fail)
        observer.wrap(owner, 'call', 'failure')
        with self.assertRaises(ValueError):
            owner.call()
        self.assertEqual([], observer.current.stack)
        self.assertEqual(1, observer.summary()['stages'][0]['calls'])
        self.assertNotIn('private failure', str(observer.summary()))
        observer.close()
        self.assertIs(fail, owner.call)

    def test_thread_local_nesting_and_fixed_roles_do_not_mix_overlapping_calls(self):
        from development.tests.fixtures.owner_cost_timeline import OwnerCostTimeline
        observer = OwnerCostTimeline(Path('.'))
        barrier = Barrier(2)
        owner = SimpleNamespace(call=lambda: barrier.wait(timeout=2))
        observer.wrap(owner, 'call', 'overlap')
        threads = [Thread(target=owner.call, name=name) for name in
            ('cost-guard-cards_0', 'cost-guard-v2-history_0')]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(3)

        rows = observer.summary()['stages']
        self.assertEqual({'card', 'inner_hydration'}, {row['thread_role'] for row in rows})
        self.assertEqual([1, 1], [row['calls'] for row in rows])
        for row in rows:
            self.assertEqual(row['thread_cpu_seconds'], row['exclusive_thread_cpu_seconds'])
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        observer.close()

    def test_profile_window_is_bounded_sanitized_and_restores_inherited_method(self):
        from development.tests.fixtures.owner_cost_timeline import OwnerCostTimeline
        wall = [0.0]
        observer = OwnerCostTimeline(Path(__file__).resolve().parents[2], clock=lambda: wall[0])

        class Owner:
            def call(self, _private):
                return sum(range(100))

        owner = Owner()
        observer.wrap(owner, 'call', 'owner_turn', profile=True)
        results = []

        def observe():
            for instant in (1, 6, 9):
                wall[0] = instant
                results.append(owner.call('private payload'))

        thread = Thread(target=observe, name='cost-guard-live')
        thread.start()
        thread.join(3)

        profile = observer.summary()['function_profile']
        self.assertEqual([4950, 4950, 4950], results)
        self.assertEqual(1, profile['sampled_calls'])
        self.assertTrue(any(row['function'] == 'call' for row in profile['functions']))
        self.assertNotIn(str(Path(__file__).resolve().anchor), str(profile['functions']))
        self.assertNotIn('private payload', str(profile))
        observer.close()
        self.assertNotIn('call', vars(owner))
        self.assertEqual(4950, owner.call('anything'))

    def test_attach_uses_existing_owners_and_restores_class_functions(self):
        from development.tests.fixtures.owner_cost_timeline import OwnerCostTimeline
        from src.pricing.github_copilot import GitHubCopilotPricingProvider
        from src.reports.service import ReportService
        from src.sources import opencode_v2_snapshot
        from src.application.contracts import record
        from src.web import events
        original_pricing = GitHubCopilotPricingProvider.cached_catalog
        original_analysis = ReportService._analyze_snapshot
        original_hydration = opencode_v2_snapshot._read_tree
        original_json = events.json
        call = lambda *args, **kwargs: 'unchanged'
        cards = SimpleNamespace(**{name:call for name in
            ('catalog', 'accept', '_tick_costs', '_ranked_ids', 'project', 'tick')},
            workers=SimpleNamespace(drain=call), guidance=SimpleNamespace(tick=call, _refresh=call, _produce=call))
        owner = SimpleNamespace(cards=cards, source=SimpleNamespace(_list_native_sessions=call),
            **{name:call for name in ('_build_projection', '_refresh_quota', 'tick_catalog', 'tick_details',
                'service_completed', '_account_history', '_catalog_capture', '_detail_capture')})
        driver = SimpleNamespace(coordinator=owner, tick=call)
        runtime = SimpleNamespace(_publish_frame=call)
        observer = OwnerCostTimeline(Path('.'))
        try:
            observer.attach(runtime, driver)

            self.assertEqual('unchanged', driver.tick())
            self.assertEqual('unchanged', cards.tick(123))
            self.assertEqual('unchanged', cards.guidance.tick(cards, 123))
            self.assertEqual('unchanged', runtime._publish_frame(driver, None))
            hub = events.EventHub('synthetic')
            hub.publish('live', record(view=record(rows=(record(value=7),))))
            self.assertEqual({'view':{'rows':[{'value':7}]}}, hub.snapshot()['values']['live'])
            stages = {row['stage']:row for row in observer.summary()['stages']}
            self.assertEqual(1, stages['dto_conversion']['calls'])
            self.assertEqual(1, stages['event_encode']['calls'])
            self.assertEqual(1, stages['event_snapshot']['calls'])
            self.assertEqual(3, stages['event_json_dumps']['calls'])
            self.assertEqual(2, stages['event_json_loads']['calls'])
        finally:
            observer.close()

        self.assertIs(original_pricing, GitHubCopilotPricingProvider.cached_catalog)
        self.assertIs(original_analysis, ReportService._analyze_snapshot)
        self.assertIs(original_hydration, opencode_v2_snapshot._read_tree)
        self.assertIs(original_json, events.json)
        self.assertIs(call, driver.tick)

    def test_owner_function_profile_excludes_concurrent_foreign_thread_and_has_possible_times(self):
        from development.tests.fixtures.owner_cost_timeline import OwnerCostTimeline
        wall = [0.0]
        observer = OwnerCostTimeline(Path('.'), clock=lambda: wall[0])
        entered, finished = Event(), Event()

        def foreign_thread_only():
            return sum(range(100))

        def foreign_work():
            if entered.wait(3):
                for _ in range(1000):
                    foreign_thread_only()
            finished.set()

        def owner_work():
            entered.set()
            if not finished.wait(3):
                raise RuntimeError('owned fixture did not finish')
            return sum(range(1000))

        owner = SimpleNamespace(call=owner_work)
        observer.wrap(owner, 'call', 'owner_turn', profile=True)
        foreign = Thread(target=foreign_work, name='cost-guard-cards_0')
        foreign.start()
        wall[0] = 6
        thread = Thread(target=owner.call, name='cost-guard-live')
        thread.start()
        thread.join(4)
        foreign.join(4)

        profile = observer.summary()['function_profile']
        self.assertEqual(1, profile['sampled_calls'])
        self.assertNotIn('foreign_thread_only', {row['function'] for row in profile['functions']})
        for row in profile['functions']:
            self.assertGreaterEqual(row['inclusive_thread_cpu_seconds'], 0)
            self.assertLessEqual(row['own_thread_cpu_seconds'], profile['sampled_thread_cpu_seconds'] + .02)
        observer.close()


if __name__ == '__main__':
    unittest.main()
