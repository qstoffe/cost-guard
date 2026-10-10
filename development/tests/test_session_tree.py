"""Shared catalog traversal preserves detail/report/Watch metadata contracts."""
from dataclasses import replace
from itertools import permutations
import unittest

from development.fixtures.session_snapshots import make_snapshot
from src.domain.session_tree import root_activity, root_by_session, root_for_session
from src.watch.observers import _root_map


class SessionTreeTests(unittest.TestCase):
    def test_deep_descendants_map_to_root_independent_of_catalog_order(self):
        root, child = make_snapshot().sessions
        grandchild = replace(child, session_id="grandchild", parent_session_id=child.session_id,
                             updated_at_ms=9000)
        for sessions in permutations((root, child, grandchild)):
            with self.subTest(order=tuple(item.session_id for item in sessions)):
                self.assertEqual({"root": "root", "child": "root", "grandchild": "root"}, root_by_session(sessions))
                self.assertEqual({"root": 9000}, root_activity(sessions))
                self.assertEqual(root, root_for_session(sessions, "grandchild"))

    def test_missing_ancestor_has_metadata_but_is_not_a_detail_target(self):
        child = make_snapshot().sessions[1]

        self.assertEqual({"child": "child"}, root_by_session((child,)))
        self.assertEqual({"child": child.updated_at_ms}, root_activity((child,)))
        self.assertIsNone(root_for_session((child,), child.session_id))
        self.assertIsNone(root_for_session((child,), "unknown"))
        self.assertEqual(((), {"child": "child"}), _root_map((child,)))

    def test_cycles_are_bounded_and_preserve_first_traversal_resolution(self):
        root, child = make_snapshot().sessions
        cycle = (replace(root, parent_session_id=child.session_id), child)

        self.assertEqual({"root": "root", "child": "root"}, root_by_session(cycle))
        self.assertEqual({"root": 5000}, root_activity(cycle))
        self.assertEqual(cycle[0], root_for_session(cycle, "root"))
        self.assertEqual((), _root_map(cycle)[0])

    def test_creation_and_archive_count_as_tree_activity(self):
        root, child = make_snapshot().sessions
        created = replace(child, created_at_ms=8000, updated_at_ms=1000)
        archived = replace(child, archived_at_ms=9000)

        self.assertEqual({"root": 8000}, root_activity((root, created)))
        self.assertEqual({"root": 9000}, root_activity((root, archived)))
        self.assertEqual(root_activity((root, archived)), root_activity((root, archived), {"child": "root"}))

    def test_watch_filters_archived_roots_but_mapping_retains_them(self):
        root, child = make_snapshot().sessions
        archived = replace(root, session_id="archived", archived_at_ms=9000)

        roots, mapping = _root_map((archived, child, root))

        self.assertEqual((root,), roots)
        self.assertEqual("archived", mapping["archived"])
        self.assertEqual(archived, root_for_session((archived, child, root), "archived"))

    def test_empty_catalog_is_empty(self):
        self.assertEqual({}, root_by_session(()))
        self.assertEqual({}, root_activity(()))
        self.assertIsNone(root_for_session((), "unknown"))
