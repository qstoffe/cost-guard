"""Physical usage is not duplicated by prompt attribution or source disappearance."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from development.tests.fixtures.session_snapshots import make_snapshot
from src.analysis import analyze_snapshot
from src.analysis.valuation import unique_usage
from src.application.request_archive_projection import request_roster
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_requests import RequestRoster, unqualified_forks
from src.cache.display_usage_reader import USAGE_SLICE


def reference(signature, prices):
    return SimpleNamespace(analysis_signature=signature, reference_category_valuation=lambda _model, _tokens: prices)


class DisplayRequestTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.history = DisplayHistory(self.root)
        self.history.initialize()

    def test_one_physical_request_keeps_its_clock_and_separate_causal_links(self):
        snapshot = make_snapshot()
        prices = (Decimal("0.11"), Decimal("0.22"), Decimal("0.33"), Decimal("0.44"))
        bundle = analyze_snapshot(snapshot, now_ms=10_000)
        roster = request_roster(snapshot, bundle, reference("pricing-v1", prices))
        child, = (entry for entry in roster.requests if entry.session_id == "child")
        standalone = replace(child, dedup_tree=None, ordinal=0, logical_prompt_id=None)
        latest = replace(roster, requests=(standalone,), attribution=((child.key, "other-prompt"),))
        self.history.commit_sessions("trusted", (SessionChange(SessionFact("root", "r1", "Root"), None,
                                     previous_progress=0, request_roster=roster),))
        self.history.commit_sessions("trusted", (SessionChange(SessionFact("other", "r1", "Other"), None,
                                     previous_progress=0, request_roster=latest),))
        self.history.commit_sessions("separate", (SessionChange(SessionFact("other", "r1", "Separate"), None,
                                     previous_progress=0, request_roster=latest),))
        checkpoint = self.history.session_checkpoints("trusted", ("root",))["root"]

        self.history.commit_sessions("trusted", missing=(("root", checkpoint),))
        restarted = DisplayHistory(self.root)
        restarted.initialize()
        with restarted._connect(read=True) as db:
            observations = db.execute("""
                SELECT clock_ms,logical_prompt_id,input_tokens,output_tokens,billed,input_cost,pricing,
                       dedup_tree,request_ordinal
                FROM archive_requests WHERE source='trusted' AND session_id='child'
            """).fetchall()
            links = db.execute("""
                SELECT root_id,prompt_id FROM archive_prompt_attribution WHERE source='trusted' AND request_key=?
                ORDER BY root_id,prompt_id
            """, (child.key,)).fetchall()
            payloads = db.execute("SELECT count(*) FROM archive_requests WHERE source='separate'").fetchone()[0]

        self.assertEqual([(1400, "cu", 20, 5, "0.20", "0.11", "pricing-v1", "root", child.ordinal)], observations)
        self.assertEqual([("other", "other-prompt"), ("root", "u_sub")], links)
        self.assertEqual(1, payloads)
        self.assertEqual(2, restarted.session_page("trusted").total)
        archive_state = restarted.source_state("trusted")
        restarted.clear_confirmed_sessions("trusted", archive_state)
        with restarted._connect(read=True) as db:
            self.assertEqual([("separate",)], db.execute("SELECT DISTINCT source FROM archive_requests").fetchall())
            self.assertEqual([], db.execute("SELECT source FROM archive_fork_trees").fetchall())

    def test_unpriced_refresh_preserves_compatible_price_but_not_after_token_correction(self):
        snapshot = make_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=10_000)
        priced = request_roster(snapshot, bundle, reference("pricing-v1", (Decimal(1),) * 4))
        original = next(entry for entry in priced.requests if entry.session_id == "child")

        def write(revision, previous, progress, request, price_revision):
            self.history.commit_sessions("trusted", (SessionChange(SessionFact("root", revision, "Root"), previous,
                previous_progress=progress, request_roster=RequestRoster(price_revision, (request,), ())),))

        write("r1", None, 0, original, "pricing-v1")
        unpriced = replace(original, category_costs=None)
        write("r2", "r1", 1, unpriced, "pricing-v2")
        with self.history._connect(read=True) as db:
            last_priced = db.execute("SELECT input_tokens,input_cost,pricing FROM archive_requests").fetchone()
        corrected = replace(unpriced, tokens=(22, *unpriced.tokens[1:]))
        write("r3", "r2", 1, corrected, "pricing-v2")  # Stale progress.
        with self.history._connect(read=True) as db:
            after_stale = db.execute("SELECT input_tokens,input_cost,pricing FROM archive_requests").fetchone()
        write("r3", "r2", 2, corrected, "pricing-v2")
        with self.history._connect(read=True) as db:
            current = db.execute("SELECT input_tokens,input_cost,pricing FROM archive_requests").fetchone()

        self.assertEqual((20, "1", "pricing-v1"), last_priced)
        self.assertEqual(last_priced, after_stale)
        self.assertEqual((22, None, None), current)

    def test_long_session_publishes_its_whole_roster(self):
        snapshot = make_snapshot()
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000),
                                reference("pricing-v1", (Decimal(1),) * 4))
        requests = tuple(replace(roster.requests[0], key=index.to_bytes(4, "big"), fork_key=None, ordinal=index)
                         for index in range(5000))
        long_roster = replace(roster, requests=requests,
                              attribution=tuple((request.key, "prompt") for request in requests))

        self.history.commit_sessions("trusted", (SessionChange(SessionFact("root", "r1", "Long"), None,
                                     previous_progress=0, request_roster=long_roster),))

        with self.history._connect(read=True) as db:
            stored = db.execute("SELECT count(*) FROM archive_requests").fetchone()[0]
            attributed = db.execute("SELECT count(*) FROM archive_prompt_attribution").fetchone()[0]
        self.assertEqual((5000, 5000), (stored, attributed))

    def test_usage_cursor_keeps_exact_population_across_membership_and_stops_on_correction(self):
        snapshot = make_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=10_000)
        prices = (Decimal("0.000000000000000000000151"), Decimal(0), Decimal(0), Decimal("1.11"))
        roster = request_roster(snapshot, bundle, reference("pricing-v1", prices))
        child = next(request for request in roster.requests if request.session_id == "child")
        requests = tuple(replace(child, key=index.to_bytes(4, "big"), fork_key=None)
                         for index in range(USAGE_SLICE + 2))
        # The first page may consist of only disqualified rows; its raw key must
        # still advance the bounded traversal instead of stopping at "no facts".
        early = tuple(replace(item, fork_key=b"unqualified", dedup_tree=None) for item in requests[:-2])
        roster = replace(roster, requests=(*early, *requests[-2:]), attribution=())
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r1", "Root"), None,
            previous_progress=0, request_roster=roster),))
        first = self.history.usage_inputs("bound")
        checkpoint = self.history.session_checkpoints("bound", ("root",))["root"]
        self.history.commit_sessions("bound", missing=(("root", checkpoint),))

        tail = self.history.usage_inputs("bound", expected=first.version, after=first.next_cursor)
        foreign = self.history.usage_inputs("other")
        checkpoint = self.history.session_checkpoints("bound", ("root",))["root"]
        correction = replace(requests[-1], clock_ms=2222)
        self.history.commit_sessions("bound", (SessionChange(SessionFact("root", "r2", "Root"), "r1",
            previous_progress=checkpoint.progress, request_roster=replace(roster, requests=(correction,))),))
        stale = self.history.usage_inputs("bound", expected=first.version, after=first.next_cursor)
        revised = self.history.usage_inputs("bound", after=first.next_cursor)

        self.assertEqual((), first.entries)
        self.assertEqual((1400,) * USAGE_SLICE, first.unqualified_clocks)
        self.assertEqual((first.version.revision, requests[USAGE_SLICE - 1].key), first.next_cursor)
        self.assertEqual(first.version, tail.version)
        self.assertEqual(tuple(request.key for request in requests[-2:]), tuple(item.request_key for item in tail.entries))
        self.assertEqual((prices, prices), tuple(item.category_costs for item in tail.entries))
        self.assertEqual(("child", "cu", 1400), (tail.entries[0].session_id, tail.entries[0].logical_prompt_id,
                                                   tail.entries[0].clock_ms))
        self.assertIsNone(tail.next_cursor)
        self.assertEqual((), foreign.entries)
        self.assertIsNone(stale)
        self.assertEqual((1400, 2222), tuple(item.clock_ms for item in revised.entries))

    def test_unchanged_fact_does_not_advance_usage_revision_but_explicit_clear_invalidates_it(self):
        snapshot = make_snapshot()
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000),
                                reference("pricing-v1", (Decimal(1),) * 4))
        for current, previous, progress in (("r1", None, 0), ("r2", "r1", 1)):
            self.history.commit_sessions("bound", (SessionChange(SessionFact("root", current, "Root"), previous,
                previous_progress=progress, request_roster=roster),))
            if previous is None:
                original = self.history.usage_inputs("bound").version

        confirmed = self.history.usage_inputs("bound", expected=original)
        cleared = self.history.clear_confirmed_sessions("bound", self.history.source_state("bound"))
        old = self.history.usage_inputs("bound", expected=original)
        new = self.history.usage_inputs("bound")

        self.assertEqual(original, confirmed.version)
        self.assertTrue(confirmed.entries)
        self.assertIsNone(old)
        self.assertEqual(cleared.archive_epoch, new.version.archive_epoch)
        self.assertEqual((), new.entries)

    def test_partial_source_cannot_supply_archive_replacement(self):
        snapshot = make_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=10_000)

        partial = request_roster(replace(snapshot, complete=False), bundle, reference("pricing-v1", None))

        self.assertIsNone(partial)

    def test_global_fork_selection_preserves_sibling_multiplicity_and_repairs_old_group(self):
        snapshot = make_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=10_000)
        priced = request_roster(snapshot, bundle, reference("pricing-v1", (Decimal(1),) * 4))
        first = next(entry for entry in priced.requests if entry.session_id == "child")
        sibling = replace(first, key=b"second-physical-call", ordinal=11)
        clone = replace(first, key=b"forked-physical-call", dedup_tree="clone", ordinal=0)
        for root, requests in (("root", (first, sibling)), ("clone", (clone,))):
            roster = RequestRoster("pricing-v1", requests, ())
            self.history.commit_sessions("trusted", (SessionChange(SessionFact(root, "r1", root), None,
                previous_progress=0, request_roster=roster),))
        with self.history._connect(read=True) as db:
            before = {key for key, in db.execute("SELECT request_key FROM archive_countable_requests")}

        corrected = replace(sibling, fork_key=b"corrected-fingerprint")
        self.history.commit_sessions("trusted", (SessionChange(SessionFact("root", "r2", "root"), "r1",
            previous_progress=1, request_roster=RequestRoster("pricing-v1", (first, corrected), ())),))
        with self.history._connect(read=True) as db:
            after = {key for key, in db.execute("SELECT request_key FROM archive_countable_requests")}

        self.assertEqual({first.key, sibling.key}, before)
        self.assertEqual({clone.key, corrected.key}, after)

    def test_append_that_changes_fork_winner_withdraws_the_older_population(self):
        snapshot = make_snapshot()
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000), reference("p1", None))
        old = replace(next(item for item in roster.requests if item.session_id == "child"), ordinal=4)
        late_replica = replace(old, key=b"late-replica", dedup_tree="late", ordinal=9)
        winning_replica = replace(old, key=b"winning-replica", dedup_tree="winner", ordinal=2)

        def append(root, request):
            self.history.commit_sessions("bound", (SessionChange(SessionFact(root, "r1", root), None,
                previous_progress=0, request_roster=replace(roster, requests=(request,), attribution=())),))

        append("root", old)
        version = self.history.usage_inputs("bound").version
        append("late", late_replica)
        preserved = self.history.usage_inputs("bound", expected=version)
        append("winner", winning_replica)
        withdrawn = self.history.usage_inputs("bound", expected=version)
        current = self.history.usage_inputs("bound")

        self.assertEqual((old.key,), tuple(row.request_key for row in preserved.entries))
        self.assertIsNone(withdrawn)
        self.assertEqual((winning_replica.key,), tuple(row.request_key for row in current.entries))

    def test_real_projection_matches_canonical_fork_selection_even_when_loser_arrives_first(self):
        parent = make_snapshot()
        child = next(session for session in parent.sessions if session.session_id == "child")
        original = next(item for item in parent.invocations if item.session_id == "child")
        clone = replace(child, session_id="fork", parent_session_id=None)
        child_view = replace(parent, root=child, sessions=(child,), events=(), messages=(),
                             invocations=(original,))
        fork_view = replace(child_view, root=clone, sessions=(clone,),
                            invocations=(replace(original, session_id="fork"),))
        price = reference("p1", (Decimal(1),) * 4)
        bundles = tuple(analyze_snapshot(snapshot, now_ms=10_000) for snapshot in (child_view, fork_view, parent))
        rosters = tuple(request_roster(snapshot, bundle, price)
                        for snapshot, bundle in zip((child_view, fork_view, parent), bundles))
        child_capture, = rosters[0].requests
        clone_capture, = rosters[1].requests
        all_entries = [entry for bundle in bundles for entry in bundle.trace_entries]
        canonical = {entry.session_id for entry in unique_usage(all_entries) if entry.completed_at_ms == 1400}

        for root, roster in zip(("child", "fork", "root"), rosters):
            self.history.commit_sessions("trusted", (SessionChange(SessionFact(root, "r1", root), None,
                                        previous_progress=0, request_roster=roster),))
        with self.history._connect(read=True) as db:
            selected = db.execute("""
                SELECT request_key FROM archive_countable_requests WHERE source='trusted' AND clock_ms=1400
            """).fetchall()
            assigned = db.execute("SELECT dedup_tree,logical_prompt_id FROM archive_requests WHERE request_key=?",
                                  (child_capture.key,)).fetchone()

        self.assertIsNone(child_capture.dedup_tree)
        self.assertEqual({"fork"}, canonical)  # Earlier ordinal at the same clock, despite the child ID sorting first.
        self.assertEqual([(clone_capture.key,)], selected)
        self.assertEqual(("root", "cu"), assigned)

    def test_qualified_reparenting_moves_physical_request_without_retracting_old_evidence(self):
        parent = make_snapshot()
        new_parent = replace(parent.root, session_id="new-root")
        child = next(session for session in parent.sessions if session.session_id == "child")
        moved = replace(child, parent_session_id="new-root")
        reparented = replace(parent, root=new_parent, sessions=(new_parent, moved), events=(), messages=(),
                             invocations=tuple(item for item in parent.invocations if item.session_id == "child"))
        price = reference("p1", (Decimal(1),) * 4)
        first = request_roster(parent, analyze_snapshot(parent, now_ms=10_000), price)
        latest = request_roster(reparented, analyze_snapshot(reparented, now_ms=10_000), price)
        child_key = latest.requests[0].key
        self.history.commit_sessions("trusted", (SessionChange(SessionFact("root", "r1", "Root"), None,
                                    previous_progress=0, request_roster=first),))

        self.history.commit_sessions("trusted", (SessionChange(SessionFact("new-root", "r1", "New"), None,
                                    previous_progress=0, request_roster=latest),))
        with self.history._connect(read=True) as db:
            tree = db.execute("SELECT dedup_tree,logical_prompt_id FROM archive_requests WHERE request_key=?",
                              (child_key,)).fetchone()
            ranks = db.execute("""
                SELECT dedup_tree,multiplicity FROM archive_fork_trees WHERE fork_key=?
            """, (latest.requests[0].fork_key,)).fetchall()
            owners = db.execute("""
                SELECT root_id FROM archive_request_membership WHERE request_key=? ORDER BY root_id
            """, (child_key,)).fetchall()

        self.assertEqual(("new-root", "cu"), tree)
        self.assertEqual([("new-root", 1)], ranks)
        self.assertEqual([("new-root",), ("root",)], owners)

    def test_source_missing_requests_report_unproven_fork_membership(self):
        snapshot = make_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=10_000)
        roster = request_roster(snapshot, bundle, reference("p1", (Decimal(1),) * 4))
        roster = replace(roster, requests=tuple(replace(item, dedup_tree=None) for item in roster.requests))
        child = next(request for request in roster.requests if request.session_id == "child")
        self.history.commit_sessions("trusted", (SessionChange(SessionFact("root", "r1", "Root"), None,
                                    previous_progress=0, request_roster=roster),))
        checkpoint = self.history.session_checkpoints("trusted", ("root",))["root"]
        self.history.commit_sessions("trusted", missing=(("root", checkpoint),))
        restarted = DisplayHistory(self.root)
        restarted.initialize()
        with restarted._connect(read=True) as db:
            physical = db.execute("SELECT clock_ms,input_tokens,input_cost FROM archive_requests WHERE request_key=?",
                                  (child.key,)).fetchone()
            countable = db.execute("SELECT count(*) FROM archive_countable_requests").fetchone()[0]
            inside_gap = unqualified_forks(db, "trusted", start_ms=1400, end_ms=1400)
            outside_gap = unqualified_forks(db, "trusted", end_ms=1399)
            foreign_gap = unqualified_forks(db, "separate")

        self.assertEqual((1400, 20, "1"), physical)
        self.assertEqual(0, countable)
        self.assertTrue(inside_gap)
        self.assertFalse(outside_gap)
        self.assertFalse(foreign_gap)
