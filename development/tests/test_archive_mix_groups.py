"""Model/publisher populations reuse pinned physical facts and logical prompts."""
from contextlib import closing
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from development.tests.fixtures.session_snapshots import make_snapshot
from src.analysis import analyze_snapshot
from src.application.archive_mix_build import ArchiveMixBuild, MixBuildState
from src.application.archive_mix_groups import MixGroupStage
from src.application.request_archive_projection import request_roster
from src.cache.display_history import DisplayHistory, SessionChange, SessionFact
from src.cache.display_usage_reader import UsageInput


def usage(provider, model, *, clock=100, prompt="one", session="root", amount="0.10000000000000000017"):
    return UsageInput(b"one", clock, session, prompt, provider, model, model, None, (7, 3, 0, 5, 1),
                      0b1111, (Decimal(amount), Decimal(0), Decimal(0), Decimal("0.25")), "p1")


class ArchiveMixGroupsTests(TestCase):
    def test_cross_slice_prompt_counts_and_publisher_route_conflicts_stay_independent(self):
        catalog = SimpleNamespace(analysis_signature="p1", resolve_reference=lambda model: (
            SimpleNamespace(model=SimpleNamespace(model="gpt-5", display_name="GPT-5"),
                            metadata={"publisher": "OpenAI"}) if model.lower() == "gpt-5" else None))
        entries = (usage("github-copilot", "gpt-5"), usage("openrouter", "gpt-5"),
                   usage("github-copilot", "gpt-5", session="child"), usage("github-copilot", "gpt-5", clock=None),
                   usage("openrouter", "other"), usage("openai", "other"), usage("openai", "secret", clock=200))

        with closing(sqlite3.connect("")) as db:
            stage = MixGroupStage(db, lambda clock: ("all",) if clock is None else ("all", "today") if clock <= 100 else (),
                                  reference=catalog)
            with db:
                stage.add(entries[:2])
                stage.add(entries[2:])
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
        self.assertEqual(4, rows["today", "publisher", "OpenAI"][2].request_count)
        self.assertEqual(1, rows["today", "publisher", "Unknown / unverified"][2].request_count)
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
            token, as_of, rows, after = history.mix_group_page("bound", "UTC", "all", None, now, "model")
            _, _, tail, end = history.mix_group_page("bound", "UTC", "all", None, now, "model", after, known=token)
            _, _, reset, _ = history.mix_group_page("bound", "UTC", "all", None, now, "model", after, known="old")
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
            retained = history.mix_group_page("bound", "UTC", "all", None, now + 1, "model")
            history.clear_confirmed_sessions("bound", history.source_state("bound"))
            deleted = history.mix_group_page("bound", "UTC", "all", None, now, "model")

        self.assertEqual((MixBuildState.MORE, MixBuildState.MORE, MixBuildState.PUBLISHED), (first, staged, completed))
        self.assertIsNone(hidden)
        self.assertIsNone(foreign)
        self.assertIsNone(deleted)
        self.assertEqual(MixBuildState.STALE, rejected)
        self.assertEqual(32, inactive)
        self.assertEqual((token, as_of, rows, after), retained)
        self.assertEqual((25, 4, None), (len(rows), len(tail), end))
        self.assertEqual(rows, reset)
        self.assertEqual((now, True, 29), (as_of, current, summary.calls))
        self.assertEqual(tuple(f"model{i:02}" for i in range(29)), tuple(row.identity for row in (*rows, *tail)))
        self.assertEqual(sum(row.calls for row in (*rows, *tail)), summary.calls)
