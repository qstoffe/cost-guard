"""Period population precedence over the real source-fenced display archive."""
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from development.tests.fixtures.session_snapshots import DAY, make_snapshot, one_request
from src.analysis import analyze_snapshot
from src.application.archive_stats_population import ArchiveStatsPopulation, PopulationState
from src.application.archive_stats_tokens import ArchiveStatsTokens
from src.application.request_archive_projection import request_roster
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_stats_evidence import StatsCapture, StatsInterval
from src.cache.display_usage_reader import USAGE_SLICE
from src.pricing.catalog import PricingCatalog

START = DAY * 25
NOW = START + 4000


class ArchiveStatsPopulationTests(TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.history = DisplayHistory(Path(folder.name))
        self.history.initialize()
        snapshot = one_request(running=False)
        self.template = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=NOW),
                                       PricingCatalog(()), config={})
        self.request, = self.template.requests
        self.build = ArchiveStatsPopulation("source", "UTC", NOW)
        self.addCleanup(self.build.close)

    def request_for(self, root, key, *, clock=START + 20, message=None, step=None, fork=None, ordinal=0):
        identity = replace(self.request.stats_identity, message_key=(message or key).ljust(32, b"-"),
                           step_key=step.ljust(32, b"-") if step is not None else None)
        return replace(self.request, key=key, clock_ms=clock, dedup_tree=root, session_id=root,
                       ordinal=ordinal, response=None, fork_key=fork, stats_identity=identity)

    def record(self, root, requests, *, intervals=(), previous=None, pricing=None, pending=False):
        revision = "second" if previous else "first"
        children = tuple(sorted({(row.session_id, root) for row in requests if row.session_id != root}))
        roster = replace(self.template, requests=requests, attribution=(), prompts=None,
                         pricing=pricing or self.template.pricing,
                         stats=StatsCapture(intervals, pending, None, ((root, None), *children)))
        self.history.commit_sessions("source", (SessionChange(
            SessionFact(root, revision, root), previous, previous_progress=int(previous is not None),
            request_roster=roster),))

    def prepare(self, expected=PopulationState.READY):
        for turns in range(150):
            state = self.build.step(self.history, eligible=lambda: True)
            if state is not PopulationState.MORE:
                self.assertIs(expected, state)
                return turns + 1
        self.fail("population did not reach its terminal state")

    def test_step_reconciliation_changes_fork_winner_before_completion_filter(self):
        fallback = self.request_for("primary", b"fallback", message=b"m", fork=b"clone", ordinal=0)
        future_step = self.request_for("primary", b"step", message=b"m", step=b"part", clock=NOW + 1)
        replica = self.request_for("replica", b"replica", fork=b"clone", ordinal=1)
        self.record("primary", (fallback, future_step))
        self.record("replica", (replica,))

        self.prepare()

        self.assertEqual((b"replica",), self.build.page("today").keys)
        self.assertEqual((b"replica",), self.build.page("all").keys)
        self.assertFalse(self.build.gaps)

    def test_excludes_proven_old_root_but_keeps_root_with_unknown_geometry(self):
        fallback = self.request_for("current", b"fallback", message=b"m")
        old_step = self.request_for("old", b"old-step", message=b"m", step=b"old", clock=START - 1)
        uncertain_step = self.request_for("unknown", b"unknown-step", message=b"second", step=b"part", clock=START - 2)
        second = self.request_for("current", b"second", message=b"second")
        self.record("current", (fallback, second))
        self.record("old", (old_step,))
        self.record("unknown", (uncertain_step,), intervals=(StatsInterval("unknown", "prompt", "prompt",
                                                                           START - 30, None, False),))

        self.prepare()

        self.assertEqual((b"fallback",), self.build.page("today").keys)
        self.assertEqual((b"old-step", b"unknown-step"), self.build.page("all").keys)
        self.assertFalse(self.build.gaps)

    def test_pages_pinned_keys_across_a_source_append_and_retains_missing_root(self):
        keys = tuple(f"call-{index:03}".encode() for index in range(USAGE_SLICE * 2 + 1))
        self.record("original", tuple(self.request_for("original", key) for key in keys))
        checkpoint = self.history.session_checkpoints("source", ("original",))["original"]
        self.history.commit_sessions("source", missing=(("original", checkpoint),))
        self.assertIs(PopulationState.MORE, self.build.step(self.history, eligible=lambda: True))
        self.record("fresh", (self.request_for("fresh", b"append"),))

        self.assertGreater(self.prepare(), 10)

        first = self.build.page("all")
        second = self.build.page("all", after=first.next_cursor)
        final = self.build.page("all", after=second.next_cursor)
        self.assertEqual(keys[:USAGE_SLICE], first.keys)
        self.assertEqual(keys[USAGE_SLICE:USAGE_SLICE * 2], second.keys)
        self.assertEqual(keys[-1:], final.keys)
        self.assertIsNone(final.next_cursor)

    def test_real_correction_invalidates_a_paused_population(self):
        original = self.request_for("root", b"request")
        self.record("root", (original,))
        self.assertIs(PopulationState.MORE, self.build.step(self.history, eligible=lambda: True))
        self.record("root", (replace(original, clock_ms=START + 100),), previous="first")

        self.prepare(PopulationState.STALE)

        with self.assertRaisesRegex(ValueError, "stats_population_not_available"):
            self.build.page("all")

    def test_fork_population_keeps_all_distinct_requests_in_winning_tree(self):
        first = self.request_for("parallel", b"first", fork=b"shared", ordinal=30)
        second = self.request_for("parallel", b"second", fork=b"shared", ordinal=10)
        later = self.request_for("replica", b"replica", fork=b"shared", ordinal=0)
        self.record("parallel", (first, second))
        self.record("replica", (later,))

        self.prepare()

        self.assertEqual((b"first", b"second"), self.build.page("all").keys)
        self.assertFalse(self.build.gaps)

    def test_duplicate_slot_and_unavailable_recipe_are_explicit_unknowns(self):
        a = self.request_for("root", b"a", message=b"shared")
        b = self.request_for("root", b"b", message=b"shared")
        known = self.request_for("root", b"known")
        no_recipe = replace(self.request_for("root", b"old"), stats_identity=None)
        self.record("root", (a, b, known, no_recipe))

        self.prepare()

        self.assertEqual((b"known",), self.build.page("all").keys)
        self.assertEqual(set(self.build.scopes), self.build.gaps)

    def publish_tokens(self, at=NOW):
        build = ArchiveStatsTokens("source", "UTC", at)
        self.addCleanup(build.close)
        for _ in range(100):
            if not build.step(self.history, eligible=lambda: True):
                self.assertIsNotNone(build.publication)
                return build
        self.fail("token projection did not finish")

    def test_observed_tokens_are_nullable_scoped_and_durable_across_disappearance(self):
        current = replace(self.request_for("root", b"current"), tokens=(2, 10, 30, 1, 3), known=0b1001)
        older = replace(self.request_for("root", b"older", clock=START - 1), tokens=(5, 1, 2, 2, 4), known=0b1111)
        later = replace(self.request_for("root", b"later", clock=NOW + 5), tokens=(16, 0, 0, 0, 0), known=0b1111)
        self.record("root", (current, older, later))
        self.publish_tokens()
        checkpoint = self.history.session_checkpoints("source", ("root",))["root"]
        self.history.commit_sessions("source", missing=(("root", checkpoint),))

        self.history = DisplayHistory(self.history.path.parent.parent)
        self.history.initialize()
        self.assertEqual(6, self.history.stats_view("source", "UTC", "today", START, NOW)[1][0].observed)
        self.assertEqual(20, self.history.stats_view("source", "UTC", "all", None, NOW)[1][0].observed)
        self.assertIsNone(self.history.stats_view("separate", "UTC", "all", None, NOW)[1])
        self.assertIsNone(self.history.stats_view("source", "Asia/Tokyo", "all", None, NOW)[1])
        self.assertIsNone(self.history.stats_view("source", "UTC", "today", START + DAY, NOW + DAY)[1])
        self.assertFalse(self.history.stats_tokens_due("source", "UTC", self.build.scopes, NOW + 4))
        self.assertTrue(self.history.stats_tokens_due("source", "UTC", self.build.scopes, NOW + 5))

        self.publish_tokens(NOW + 5)
        row, as_of = self.history.stats_view("source", "UTC", "today", START, NOW + 5)[1]
        self.assertEqual((22, True, NOW + 5), (row.observed, row.usage_gaps, as_of))
        self.history.clear_confirmed_sessions("source", self.history.source_state("source"))
        self.assertIsNone(self.history.stats_view("source", "UTC", "all", None, NOW + 5)[1])

    def test_missing_recipe_cannot_publish_plausible_but_unreconciled_token_total(self):
        known = self.request_for("root", b"known")
        unknown = replace(self.request_for("root", b"unknown"), stats_identity=None)
        self.record("root", (known, unknown))

        self.publish_tokens()

        row, _ = self.history.stats_view("source", "UTC", "all", None, NOW)[1]
        self.assertTrue(row.population_gaps)
        self.assertIsNone(row.observed)

    def test_old_missing_recipe_does_not_blank_provably_unrelated_recent_scopes(self):
        recent = replace(self.request_for("recent", b"known"), tokens=(10, 0, 0, 0, 0), known=0b1111)
        old = replace(self.request_for("old", b"lost", clock=START - 2 * DAY), stats_identity=None)
        self.record("recent", (recent,))
        self.record("old", (old,))

        self.publish_tokens()

        today = self.history.stats_view("source", "UTC", "today", START, NOW)[1][0]
        lifetime = self.history.stats_view("source", "UTC", "all", None, NOW)[1][0]
        self.assertEqual((10, False), (today.observed, today.population_gaps))
        self.assertEqual((None, True), (lifetime.observed, lifetime.population_gaps))

    def test_reference_subtotal_is_exact_and_ignores_billed_only_requests(self):
        full = replace(self.request_for("root", b"known"), category_costs=tuple(
            map(Decimal, ("0.7", "0.00000000000000000000015", "0", "0.05"))))
        billed = replace(self.request_for("root", b"billed"), category_costs=None,
                         billed=Decimal("20"), currency="USD", disposition="billed")
        self.record("root", (full, billed), pricing="reference-v1")

        with localcontext() as ctx:
            ctx.prec = 8
            self.publish_tokens()

        row = self.history.stats_view("source", "UTC", "today", START, NOW)[1][0]
        self.assertEqual((Decimal("0.75000000000000000000015"), 1, 2),
                         (row.reference_ccost, row.priced, row.requests))

    def test_different_reference_signatures_withhold_only_ascribed_scope_cost(self):
        current = replace(self.request_for("new", b"new"), category_costs=(Decimal(".1"),) * 4)
        prior = replace(self.request_for("old", b"old", clock=START - DAY), category_costs=(Decimal(".2"),) * 4)
        self.record("new", (current,), pricing="price-new")
        self.record("old", (prior,), pricing="price-old")

        self.publish_tokens()

        today = self.history.stats_view("source", "UTC", "today", START, NOW)[1][0]
        lifetime = self.history.stats_view("source", "UTC", "all", None, NOW)[1][0]
        self.assertEqual(Decimal("0.4"), today.reference_ccost)
        self.assertIsNotNone(lifetime.observed)
        self.assertTrue(lifetime.mixed_prices)
        self.assertIsNone(lifetime.reference_ccost)

    def test_subagent_reference_uses_linked_execution_not_billed_cost_and_survives_source_removal(self):
        snapshot = make_snapshot()
        reference = PricingCatalog(())
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=NOW), reference, config={})
        executing_child, = tuple(row for row in roster.requests if row.session_id == "child")
        self.assertEqual("root", executing_child.dedup_tree)
        priced = tuple(replace(row, category_costs=(Decimal(2 if row.session_id == "child" else 1),) * 4)
                       for row in roster.requests)
        self.history.commit_sessions("source", (SessionChange(
            SessionFact("root", "first", "Root"), None, previous_progress=0,
            request_roster=replace(roster, requests=priced)),))
        self.publish_tokens()
        checkpoint = self.history.session_checkpoints("source", ("root",))["root"]
        self.history.commit_sessions("source", missing=(("root", checkpoint),))
        self.history = DisplayHistory(self.history.path.parent.parent)
        self.history.initialize()
        self.publish_tokens()

        recent = self.history.stats_view("source", "UTC", "today", START, NOW)[1][0]
        lifetime = self.history.stats_view("source", "UTC", "all", None, NOW)[1][0]

        self.assertIsNone(recent.subagent_reference_ccost)
        self.assertEqual(Decimal(8), lifetime.subagent_reference_ccost)
        self.assertNotEqual(lifetime.reference_ccost, lifetime.subagent_reference_ccost)

    def test_subagent_cost_counts_fork_survivor_once_and_qualifies_its_own_pricing(self):
        costs = (Decimal("0.25"),) * 4
        first = replace(self.request_for("a", b"first", fork=b"clone", ordinal=0),
                        session_id="a-child", category_costs=costs)
        clone = replace(self.request_for("b", b"clone", fork=b"clone", ordinal=1),
                        session_id="b-child", category_costs=costs)
        root = replace(self.request_for("c", b"root"), category_costs=costs)
        self.record("a", (first,), pricing="child-price")
        self.record("b", (clone,), pricing="child-price")
        self.record("c", (root,), pricing="other-price")
        self.publish_tokens()

        row, _ = self.history.stats_view("source", "UTC", "today", START, NOW)[1]

        self.assertEqual(2, row.requests)
        self.assertIsNone(row.reference_ccost)
        self.assertEqual(Decimal(1), row.subagent_reference_ccost)
