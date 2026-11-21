"""Physical usage is not duplicated by prompt attribution or source disappearance."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from development.tests.fixtures.session_snapshots import make_snapshot
from src.analysis import analyze_snapshot
from src.application.request_archive_projection import request_roster
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_requests import RequestRoster


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
        latest = replace(roster, requests=(child,), attribution=((child.key, "other-prompt"),))
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
                SELECT clock_ms,logical_prompt_id,input_tokens,output_tokens,billed,input_cost,pricing
                FROM archive_requests WHERE source='trusted' AND session_id='child'
            """).fetchall()
            links = db.execute("""
                SELECT root_id,prompt_id FROM archive_prompt_attribution WHERE source='trusted' AND request_key=?
                ORDER BY root_id,prompt_id
            """, (child.key,)).fetchall()
            payloads = db.execute("SELECT count(*) FROM archive_requests WHERE source='separate'").fetchone()[0]

        self.assertEqual([(1400, "cu", 20, 5, "0.20", "0.11", "pricing-v1")], observations)
        self.assertEqual([("other", "other-prompt"), ("root", "u_sub")], links)
        self.assertEqual(1, payloads)
        self.assertEqual(2, restarted.session_page("trusted").total)
        archive_state = restarted.source_state("trusted")
        restarted.clear_confirmed_sessions("trusted", archive_state)
        with restarted._connect(read=True) as db:
            self.assertEqual([("separate",)], db.execute("SELECT DISTINCT source FROM archive_requests").fetchall())

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

    def test_partial_source_cannot_supply_archive_replacement(self):
        snapshot = make_snapshot()
        bundle = analyze_snapshot(snapshot, now_ms=10_000)

        partial = request_roster(replace(snapshot, complete=False), bundle, reference("pricing-v1", None))

        self.assertIsNone(partial)
