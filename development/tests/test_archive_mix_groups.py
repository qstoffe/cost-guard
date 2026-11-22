"""Model/publisher populations reuse pinned physical facts and logical prompts."""
from contextlib import closing
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from development.tests.fixtures.session_snapshots import make_snapshot
from src.analysis import analyze_snapshot
from src.application.archive_mix_build import ArchiveMixBuild, MixBuildState
from src.application.archive_mix_groups import MixGroupStage
from src.application.archive_mix_refresh import ArchiveMixRefresh
from src.application.request_archive_projection import request_roster
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_mix_groups import MixGroupRow, mix_groups_schema, read_groups, stage_groups
from src.cache.display_mix_identity import MixIdentity
from src.cache.display_mix_order import MIX_GROUP_SORTS
from src.cache.display_usage_reader import UsageInput
from src.domain import ModelPricing, ModelRef
from src.pricing.catalog import PricingCatalog


def usage(provider, model, *, clock=100, prompt="one", session="root", amount="0.10000000000000000017"):
    return UsageInput(b"one", clock, session, prompt, provider, model, model, None, (7, 3, 0, 5, 1),
                      0b1111, (Decimal(amount), Decimal(0), Decimal(0), Decimal("0.25")), "p1")


class ArchiveMixGroupsTests(TestCase):
    def test_cross_slice_prompt_counts_and_publisher_route_conflicts_stay_independent(self):
        identities = {"gpt-5": MixIdentity("GPT-5", "OpenAI")}
        entries = (usage("github-copilot", "gpt-5"), usage("openrouter", "gpt-5"),
                   usage("github-copilot", "gpt-5", session="child"), usage("github-copilot", "gpt-5", clock=None),
                   usage("openrouter", "other"), usage("openai", "other"), usage("openai", "secret", clock=200))

        with closing(sqlite3.connect("")) as db:
            stage = MixGroupStage(db, lambda clock: ("all",) if clock is None else ("all", "today") if clock <= 100 else ())
            with db:
                stage.add(entries[:2], identities)
                stage.add(entries[2:], identities)
            rows = {}
            cursor = ("", "", "")
            while page := tuple(stage.page(cursor, 2)):
                for key, group, prompts in page:
                    rows[key] = group.label, group.publisher, group.totals.mix(prompts)
                cursor = page[-1][0]

        qualified = rows["all", "model", "gpt5"]
        self.assertEqual(("GPT-5", "OpenAI"), qualified[:2])
        self.assertEqual((4, 2, (28, 12, 0, 24)), (qualified[2].request_count, qualified[2].sample_size, qualified[2].totals))
        self.assertEqual(Decimal("0.40000000000000000068"), qualified[2].costs[0])
        ambiguous = rows["today", "model", "other"]
        self.assertEqual(("other", "Unknown / unverified", 2), (*ambiguous[:2], ambiguous[2].request_count))
        self.assertEqual(3, rows["today", "publisher", "OpenAI"][2].request_count)
        self.assertEqual(2, rows["today", "publisher", "Unknown / unverified"][2].request_count)
        self.assertNotIn(("all", "model", "secret"), rows)

    def test_without_catalog_a_provider_route_does_not_supply_identity(self):
        item = usage("openai", "fixture-model")
        with closing(sqlite3.connect("")) as db:
            stage = MixGroupStage(db, lambda _: ("all",))
            with db:
                stage.add((item,))
            result = tuple(stage.page(("", "", ""), 2))

        self.assertEqual([("all", "model", "fixturemodel"), ("all", "publisher", "Unknown / unverified")],
                         [row[0] for row in result])

    def test_group_pages_are_invisible_until_matching_totals_commit(self):
        now = 10_000
        snapshot = make_snapshot()
        reference = SimpleNamespace(analysis_signature="p1", reference_category_valuation=lambda *_: None)
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=now), reference)
        entry = roster.requests[0]
        entries = tuple(replace(entry, key=i.to_bytes(2, "big"), model=f"model-{i:02}", fork_key=None,
                                category_costs=None) for i in range(29))
        with TemporaryDirectory() as directory:
            history = DisplayHistory(Path(directory))
            history.initialize()
            history.commit_sessions("bound", (SessionChange(SessionFact("root", "r1", "Root"), None,
                previous_progress=0, request_roster=replace(roster, requests=entries, attribution=())),))
            with ArchiveMixBuild("bound", "UTC", now, grouped=True) as build:
                first, staged = build.step(history), build.step(history)
                hidden = history.mix_group_page("bound", "UTC", "all", None, now, "model")
                for _ in range(10):
                    completed = build.step(history)
                    if completed is not MixBuildState.MORE:
                        break
            order = ("model", "asc")
            token, as_of, _, rows, after = history.mix_group_page("bound", "UTC", "all", None, now, "model", order=order)
            _, _, _, tail, end = history.mix_group_page("bound", "UTC", "all", None, now, "model", after,
                                                       known=token, order=order)
            _, _, _, reset, _ = history.mix_group_page("bound", "UTC", "all", None, now, "model", after,
                                                      known="old", order=order)
            foreign = history.mix_group_page("unbound", "UTC", "all", None, now, "model")
            summary, current = history.mix_total("bound", "UTC", "all", None, now)
            with ArchiveMixBuild("bound", "UTC", now + 1, grouped=True) as stale_build:
                stale_build.step(history)
                stale_build.step(history)
                history.commit_sessions("bound", (SessionChange(SessionFact("root", "r2", "Root"), "r1",
                    previous_progress=1, request_roster=replace(roster,
                        requests=(replace(entries[0], clock_ms=now + 20),), attribution=())),))
                rejected = stale_build.step(history)
            inactive = history.reclaim_mix_groups("bound")
            retained = history.mix_group_page("bound", "UTC", "all", None, now + 1, "model", order=order)
            history.clear_confirmed_sessions("bound", history.source_state("bound"))
            deleted = history.mix_group_page("bound", "UTC", "all", None, now, "model")

        self.assertEqual((MixBuildState.MORE, MixBuildState.MORE, MixBuildState.PUBLISHED), (first, staged, completed))
        self.assertIsNone(hidden)
        self.assertIsNone(foreign)
        self.assertIsNone(deleted)
        self.assertEqual(MixBuildState.STALE, rejected)
        self.assertEqual(32, inactive)
        self.assertEqual((token, as_of, order, rows, after), retained)
        self.assertEqual((25, 4, None), (len(rows), len(tail), end))
        self.assertEqual(rows, reset)
        self.assertEqual((now, True, 29), (as_of, current, summary.calls))
        self.assertEqual(tuple(f"model{i:02}" for i in range(29)), tuple(row.identity for row in (*rows, *tail)))
        self.assertEqual(sum(row.calls for row in (*rows, *tail)), summary.calls)

    def test_metadata_only_change_and_held_catalog_keep_scope_and_last_qualified_names(self):
        now = 1_750_000_000_000
        snapshot = make_snapshot()
        price = SimpleNamespace(analysis_signature="p1", reference_category_valuation=lambda *_: None)
        roster = request_roster(snapshot, analyze_snapshot(snapshot, now_ms=10_000), price)
        entry = replace(roster.requests[0], key=b"base", model="fixture-77", recorded_model="fixture-77",
                        clock_ms=now, fork_key=None, dedup_tree=None, category_costs=None)
        model = ModelPricing(ModelRef("github-copilot", "fixture-77", display_name="Verified label"), "USD",
                             per_million_input=Decimal(1), metadata={"manufacturer": "Original publisher"})
        fresh = PricingCatalog((model,), retrieved_at_ms=now - 1, source_revision="verified")
        new_names = replace(fresh, models=(replace(model, metadata={"manufacturer": "Revised publisher"}),))

        def held():
            raise sqlite3.OperationalError("synthetic held price cache")

        def refresh(history, reference, time_ms, source="trusted"):
            progress = ArchiveMixRefresh(grouped=True)
            for _ in range(12):
                published = progress.advance(history, source, "UTC", "scope", time_ms,
                                             eligible=lambda: True, reference=reference)
                if not progress.due("scope"):
                    progress.withdraw()
                    return published
            self.fail("group projection did not terminate")

        def commit(history, source, root_id, request):
            history.commit_sessions(source, (SessionChange(SessionFact(root_id, "r1", root_id), None,
                previous_progress=0, request_roster=replace(roster, requests=(request,), attribution=(), prompts=None)),),
                archive_epoch=history.source_state(source).archive_epoch)

        def groups(history, source, kind="model"):
            return history.mix_group_page(source, "UTC", "all", None, now + 10, kind)[3]

        with TemporaryDirectory() as directory:
            history = DisplayHistory(Path(directory))
            history.initialize()
            commit(history, "trusted", "root", entry)
            original = refresh(history, lambda: fresh, now)
            previous, = groups(history, "trusted")

            # Another process/restart sees a held catalog and a new request.
            restarted = DisplayHistory(Path(directory))
            restarted.initialize()
            commit(restarted, "trusted", "new-root", replace(entry, key=b"new", clock_ms=now + 1))
            held_commit = refresh(restarted, held, now + 2)
            warm, = groups(restarted, "trusted")
            other_source = replace(entry, provider="openai")
            commit(restarted, "foreign", "root", other_source)
            refresh(restarted, held, now + 2, source="foreign")
            foreign, = groups(restarted, "foreign")

            revised = refresh(restarted, lambda: new_names, now + 2)
            changed, = groups(restarted, "trusted", "publisher")
            no_change = refresh(restarted, lambda: new_names, now + 3)
            older = replace(fresh, retrieved_at_ms=now - 5)
            outdated = refresh(restarted, lambda: older, now + 3)
            final, = groups(restarted, "trusted")
            self.assertIsNotNone(restarted.clear_confirmed_sessions("trusted", restarted.source_state("trusted")))
            commit(restarted, "trusted", "again", entry)
            refresh(restarted, held, now + 3)
            after_clear, = groups(restarted, "trusted")

        self.assertEqual(fresh.analysis_signature, new_names.analysis_signature)
        self.assertEqual(("Verified label", "Original Publisher", 1), (previous.label, previous.publisher, previous.calls))
        self.assertEqual(("Verified label", "Original Publisher", 2), (warm.label, warm.publisher, warm.calls))
        self.assertEqual(("fixture-77", "Unknown / unverified"), (foreign.label, foreign.publisher))
        self.assertGreater(held_commit.version.revision, original.version.revision)
        self.assertEqual(held_commit.version, revised.version)
        self.assertEqual(held_commit.end_ms, revised.end_ms)
        self.assertNotEqual(held_commit.group_marks["all"], revised.group_marks["all"])
        self.assertEqual(("Revised Publisher", 2, None), (changed.label, changed.calls, changed.costs))
        self.assertIsNone(no_change)
        self.assertIsNone(outdated)
        self.assertEqual(("Verified label", "Revised Publisher"), (final.label, final.publisher))
        self.assertEqual(("fixture-77", "Unknown / unverified"), (after_clear.label, after_clear.publisher))

    @staticmethod
    def group_store(db):
        db.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE sources(source TEXT PRIMARY KEY);
            CREATE TABLE archive_mix_state(source TEXT PRIMARY KEY);
        """ + mix_groups_schema())

    def test_every_sort_paginates_exact_values_and_leaves_unknowns_last(self):
        huge = 10 ** 24
        fixtures = [
            MixGroupRow("all", "model", f"model-{i:02}",
                        "Unknown model" if i % 13 == 0 else f"Name {i % 20:02}",
                        "Unknown / unverified" if i % 12 == 0 else f"Publisher {i % 4}",
                        i % 5, i % 7 + 1, int(i % 11 != 0), None if i % 9 == 0 else huge + (i * 7 % 59),
                        (None, 1, 0, 1) if i % 8 == 0 else (huge + i % 3, huge + i % 5, i % 13, 2),
                        None if i % 11 == 0 else
                        (Decimal("1e24"), Decimal(i % 17).scaleb(-18), Decimal(0), Decimal(0)))
            for i in range(64)
        ]

        def expected_value(row, sort):
            index = {"input": 0, "cache": 1, "write": 2, "output": 3}.get(sort)
            if index is not None:
                return Fraction(row.totals[index], sum(row.totals)) if None not in row.totals else None
            return {"publisher": None if row.publisher == "Unknown / unverified" else row.publisher.lower(),
                    "model": None if row.label == "Unknown model" else row.label.lower(), "prompts": row.prompts,
                    "calls": row.calls, "tokens": row.known_volume,
                    "ccost": sum(map(Fraction, row.costs)) if row.costs is not None else None}[sort]

        with closing(sqlite3.connect(":memory:")) as db:
            self.group_store(db)
            stage_groups(db, "source", "run", fixtures[:32])
            stage_groups(db, "source", "run", fixtures[32:])
            for sort in MIX_GROUP_SORTS:
                keys = {row.identity: expected_value(row, sort) for row in fixtures}
                for direction in ("asc", "desc"):
                    with self.subTest(sort=sort, direction=direction):
                        expected = sorted((key for key in keys if keys[key] is not None),
                                          key=lambda key: (keys[key], key), reverse=direction == "desc")
                        expected.extend(sorted((key for key in keys if keys[key] is None), reverse=direction == "desc"))
                        received, cursor = [], ""
                        for _ in range(3):
                            page, cursor = read_groups(db, "source", "run", "all", "model", cursor, (sort, direction))
                            received.extend(row.identity for row in page)
                        self.assertIsNone(cursor)
                        self.assertEqual(expected, received)

    def test_deep_tied_seek_does_not_walk_skipped_rows(self):
        common = MixGroupRow("all", "model", "", "Model", "Publisher", 1, 1, 0, 1, (1, 0, 0, 0), None)
        with closing(sqlite3.connect(":memory:")) as db:
            self.group_store(db)
            for start in range(0, 8192, 32):
                stage_groups(db, "source", "run", tuple(replace(common, identity=f"{i:05}") for i in range(start, start + 32)))
            steps = []
            db.set_progress_handler(lambda: steps.append(1) or 0, 100)

            ascending, _ = read_groups(db, "source", "run", "all", "model", "07000", ("input", "asc"))
            descending, _ = read_groups(db, "source", "run", "all", "model", "01000", ("input", "desc"))
            unknown, _ = read_groups(db, "source", "run", "all", "model", "07000", ("ccost", "asc"))

        self.assertEqual([f"{i:05}" for i in range(7001, 7026)], [row.identity for row in ascending])
        self.assertEqual([f"{i:05}" for i in range(999, 974, -1)], [row.identity for row in descending])
        self.assertEqual(ascending, unknown)
        self.assertLess(len(steps), 100, "a deep seek must not scan the preceding thousands of ties")
