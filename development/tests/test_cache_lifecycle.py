"""Real SQLite retention/rehydration, explicit clocks, isolation and bounded writes."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import time
from types import SimpleNamespace
import unittest

from development.tests.fixtures.session_snapshots import history, make_snapshot
from src.analysis.cache import AnalysisDependencies, DerivedAnalysisCache, analyze_with_cache
from src.analysis.core import analyze_snapshot
from src.cache import CacheDatabase, CacheRepository
from src.cache.lifecycle import CacheLifecycle, HOUR_MS, PRUNE_ROWS, RETENTION_MS, TOUCH_ROWS
from src.cache.repository import CacheEntry
from src.cache.session_scope import SessionScope, root_key, snapshot_scope

DAY = 86_400_000
NOW = 1_800_000_000_000
OLD = NOW - 40 * DAY


class CacheLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = CacheDatabase(Path(temporary.name))
        self.database.initialize()
        self.repository = CacheRepository(self.database)
        self.wall = OLD / 1000
        self.lifecycle = CacheLifecycle(self.database, wall_clock=lambda: self.wall)

    def put(self, key, activity=OLD, *, namespace='derived-analysis', revision='r'):
        self.repository.put(namespace, key, {'answer': 42}, source_revision=revision,
            algorithm_version='test', session_scope=SessionScope(key, activity))

    def used(self):
        with self.database.connect() as connection:
            return dict(connection.execute('SELECT cache_key,used_ms FROM cache_entry_lifecycle'))

    def test_two_clocks_unknowns_passive_writes_and_rehydration(self):
        for key, activity in [('active-recently', NOW - DAY), ('viewed-yesterday', OLD),
                ('obsolete', OLD), ('unknown-activity', None), ('unknown-use', OLD)]:
            self.put(key, activity)
        self.repository.put('pricing.github-copilot', 'authority', {'keep': True})
        self.lifecycle.note_use(['active-recently', 'viewed-yesterday', 'obsolete', 'unknown-activity'])
        self.lifecycle.flush()
        self.wall = (NOW - DAY) / 1000
        self.lifecycle.note_use(['viewed-yesterday'])
        self.lifecycle.flush()
        # Housekeeping/passive refresh changes payload write time, never viewed-at.
        self.put('obsolete')
        self.wall = NOW / 1000

        deleted = self.lifecycle.prune(dict.fromkeys(
            ['active-recently', 'viewed-yesterday', 'obsolete', 'unknown-activity', 'unknown-use'], 'r'))

        self.assertEqual(1, deleted)
        self.assertIsNone(self.repository.get('derived-analysis', 'obsolete'))
        for key in ('active-recently', 'viewed-yesterday', 'unknown-activity', 'unknown-use'):
            self.assertEqual({'answer': 42}, self.repository.get('derived-analysis', key).payload)
        self.assertEqual({'keep': True}, self.repository.get('pricing.github-copilot', 'authority').payload)
        self.assertEqual(OLD, self.used()['active-recently'])
        self.assertEqual(NOW - DAY, self.used()['viewed-yesterday'])
        # Reconstructible, not a source deletion: the same old result can be published anew.
        self.put('obsolete')
        self.lifecycle.note_use(['obsolete'])
        self.lifecycle.flush()
        self.assertEqual({'answer': 42}, self.repository.get('derived-analysis', 'obsolete').payload)
        self.assertEqual(NOW, self.used()['obsolete'])

    def test_real_derived_cache_miss_rehydrates_same_authoritative_snapshot(self):
        snapshot = replace(history([(OLD - 1000, OLD)]), complete=True)
        source = SimpleNamespace(get_session_tree_revision=lambda _id: snapshot.source_revision,
            load_session_snapshot=lambda _id: snapshot)
        cache = DerivedAnalysisCache(self.repository)
        dependencies = AnalysisDependencies('config', 'pricing')
        analyzer = lambda value: analyze_snapshot(value, now_ms=NOW)
        first = analyze_with_cache(source, snapshot.root, cache, dependencies, analyzer)
        digest = root_key(snapshot.root.provenance, snapshot.root.session_id)
        self.lifecycle.note_use([digest])
        self.lifecycle.flush()
        self.wall = NOW / 1000

        self.assertEqual(1, self.lifecycle.prune({digest: snapshot.source_revision}))
        rebuilt = analyze_with_cache(source, snapshot.root, cache, dependencies, analyzer)
        warm = analyze_with_cache(source, snapshot.root, cache, dependencies, analyzer)

        self.assertFalse(first.cache_hit)
        self.assertFalse(rebuilt.cache_hit)
        self.assertTrue(warm.cache_hit)
        self.assertEqual(first.bundle, rebuilt.bundle)
        self.assertEqual(first.bundle, warm.bundle)
        self.assertIs(source.load_session_snapshot('root'), snapshot)

    def test_hourly_touch_coalescing_retains_full_rolling_window(self):
        self.put('one')
        self.lifecycle.note_use(['one'])
        self.assertEqual(1, self.lifecycle.flush())
        self.wall += 3599
        self.lifecycle.note_use(['one'])
        self.assertEqual({}, self.lifecycle.pending)
        self.assertEqual(OLD, self.used()['one'])
        self.assertEqual(0, self.lifecycle.prune({'one': 'r'}, now_ms=OLD + RETENTION_MS + HOUR_MS - 1))
        self.assertEqual(1, self.lifecycle.prune({'one': 'r'}, now_ms=OLD + RETENTION_MS + HOUR_MS + 1))

    def test_pending_demand_changed_revision_and_absent_identity_are_protected(self):
        for key in ('pending', 'changed', 'restarted', 'old'):
            self.put(key)
        self.lifecycle.note_use(['pending', 'changed', 'restarted', 'old'])
        self.lifecycle.flush()
        self.wall = NOW / 1000
        self.lifecycle.note_use(['pending'])

        self.assertEqual(1, self.lifecycle.prune({'pending': 'r', 'changed': 'new', 'old': 'r'}))

        self.assertIsNone(self.repository.get('derived-analysis', 'old'))
        self.assertTrue(all(self.repository.get('derived-analysis', key) for key in ('pending', 'changed', 'restarted')))

    def test_batch_limits_and_real_writer_contention_are_fail_soft(self):
        for number in range(TOUCH_ROWS + 3):
            # One root can have many entries: bound entry updates, not root count.
            self.repository.put('derived-analysis', str(number), number, source_revision='r',
                session_scope=SessionScope('group', OLD))
        self.lifecycle.note_use(['group'])
        self.assertEqual(TOUCH_ROWS, self.lifecycle.flush())
        self.assertIn('group', self.lifecycle.pending)
        self.assertEqual(3, self.lifecycle.flush())
        self.wall = NOW / 1000
        self.put('other')
        with self.database.connect() as writer:
            writer.execute('BEGIN IMMEDIATE')
            started = time.monotonic()
            self.assertEqual(0, self.lifecycle.prune({'group': 'r'}))
            self.assertLess(time.monotonic() - started, 0.5)
            self.lifecycle.note_use(['other'])
            self.assertEqual(0, self.lifecycle.flush())
            self.assertIn('other', self.lifecycle.pending)
        self.assertEqual(PRUNE_ROWS, self.lifecycle.prune({'group': 'r'}))
        self.assertEqual(TOUCH_ROWS + 3 - PRUNE_ROWS, len(self.repository.get_many('derived-analysis', map(str, range(TOUCH_ROWS + 3)))))

    def test_cancel_rolls_back_and_deferred_candidates_do_not_starve_tail(self):
        for number in range(PRUNE_ROWS + 1):
            self.put(str(number))
        self.lifecycle.note_use(map(str, range(PRUNE_ROWS + 1)))
        self.lifecycle.flush()
        self.wall = NOW / 1000
        checks = 0
        def allowed():
            nonlocal checks
            checks += 1
            return checks < 3
        self.assertEqual(0, self.lifecycle.prune(dict.fromkeys(map(str, range(PRUNE_ROWS + 1)), 'r'), allowed=allowed))
        self.assertEqual(PRUNE_ROWS + 1, len(self.used()))
        self.assertEqual(0, self.lifecycle.prune({str(PRUNE_ROWS): 'r'}))
        self.assertEqual(1, self.lifecycle.prune({str(PRUNE_ROWS): 'r'}))

    def test_replacement_metadata_is_atomic_and_unknown_evidence_does_not_inherit_activity(self):
        self.put('one')
        self.lifecycle.note_use(['one'])
        self.lifecycle.flush()
        entry = CacheEntry('derived-analysis', 'one', {'new': True}, 'new', 'algorithm', SessionScope('one', None))
        self.repository.put_many([entry])
        self.assertEqual(OLD, self.used()['one'])
        self.wall = NOW / 1000
        self.assertEqual(0, self.lifecycle.prune({'one': 'new'}))
        self.repository.put('derived-analysis', 'one', {'legacy': True}, source_revision='new')
        self.assertEqual({}, self.used())

    def test_additive_migration_never_reads_or_rewrites_existing_payloads(self):
        with self.database.connect() as connection:
            connection.execute('DROP TABLE cache_entry_lifecycle')
            connection.execute("INSERT INTO cache_entries(namespace,cache_key,payload_json) VALUES('derived-analysis','legacy','not-json')")
        self.database.initialize()
        self.assertEqual({}, self.used())
        with self.database.connect() as connection:
            self.assertEqual('not-json', connection.execute("SELECT payload_json FROM cache_entries WHERE cache_key='legacy'").fetchone()[0])
            plan = connection.execute('EXPLAIN QUERY PLAN SELECT namespace FROM cache_entry_lifecycle '
                'WHERE activity_ms IS NOT NULL AND used_ms IS NOT NULL AND max(activity_ms,used_ms+3600000)<?', (NOW,)).fetchall()
        self.assertIn('cache_lifecycle_expiry', str(plan))

    def test_activity_uses_child_execution_not_root_metadata_and_unknown_times_defer(self):
        base = replace(make_snapshot(), complete=True)
        child = replace(base.invocations[1], completed_at_ms=NOW - DAY)
        snapshot = replace(base, invocations=(base.invocations[0], child, *base.invocations[2:]))
        self.assertEqual(NOW - DAY, snapshot_scope(snapshot).activity_ms)
        self.assertEqual(3300, snapshot_scope(base).activity_ms, 'root updated-at is 5000, not prompt activity')
        self.assertIsNone(snapshot_scope(replace(snapshot, complete=False)).activity_ms)
        self.assertIsNone(snapshot_scope(replace(snapshot, sessions=(replace(base.root, active=True),))).activity_ms)
        self.assertIsNone(snapshot_scope(replace(snapshot, invocations=(replace(child, completed_at_ms=None),))).activity_ms)
        other = replace(base.root.provenance, source_instance='restarted')
        self.assertNotEqual(snapshot_scope(base).root_key, root_key(other, base.root.session_id))


if __name__ == '__main__':
    unittest.main()
