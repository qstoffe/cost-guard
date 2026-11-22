"""Current subagent usage joins the initiating prompt, never a session residual."""
from decimal import Decimal as D
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import io
import tempfile
import unittest

from development.tests.fixtures.pricing_catalog import catalog, threshold_catalog
from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.subagent_sessions import assistant, incident_source, link, user
from development.tests.fixtures.watch_runtime import MutableSource
from src.analysis import analyze_snapshot
from src.analysis.cache import AnalysisDependencies, DerivedAnalysisCache, analyze_with_cache
from src.analysis.causal import trace_entries
from src.analysis.ai_stats import period_stats
from src.reports.ai_stats_evidence import payload, decoded
from src.analysis.session_cost import reconcile_session_cost
from src.analysis.valuation import comparison_cost
from src.application.display import with_display
from src.application.live_projection import project_live
from src.application.projection import block as export_block
from src.cache import CacheDatabase, CacheRepository
from src.domain import BackgroundActivity, ModelRef, TokenUsage
from src.presentation import ReportRenderer
from src.reports.models import ReportKind, ReportProjection
from src.reports.prompt_rows import PromptRowProjector
from src.reports.prompts import build_prompt_block
from src.watch.models import WatchCard, WatchProjection, WatchRow
from src.watch.tools import observe_tools


class SubagentAttributionTests(unittest.TestCase):
    def test_native_incident_includes_child_once_after_canonical_loading(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        prices = catalog()
        bundle = analyze_snapshot(snapshot, now_ms=20_000)
        self.assertEqual(1, len(bundle.prompts))
        record = bundle.prompts[0]
        row = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=prices, config={}).prompt(record)
        total = comparison_cost(trace_entries(snapshot), prices.reference_valuation)

        self.assertEqual(3, record.model_calls)
        self.assertEqual(("ses_current_child",), record.linked_session_ids)
        self.assertEqual(D(224), row.ccost)  # main 2*(10+1+10+40), child 20+2+20+60
        self.assertEqual(total.ccost, row.ccost)
        self.assertEqual((D(21), D(203)), (row.incoming_context_ccost, row.extra_ccost))
        self.assertEqual(row.ccost, row.incoming_context_ccost + row.extra_ccost)
        self.assertEqual((D(122), D(102)), tuple(p.known_ccost for p in row.cost_parts))
        self.assertEqual(("high", "low"), tuple(p.variant for p in row.cost_parts))
        self.assertEqual(1, row.linked_agent_count)
        self.assertEqual((25, 25, 25, 25), row.token_mix_percent)
        self.assertEqual((("subagent", 1),), observe_tools(snapshot, "u1").tool_counts)
        compact = payload(bundle, prices, snapshot, {}, now=20_000)
        # JSON persistence must preserve physical root/child provenance, not prompt text.
        import json
        restored, _facts, _matched = decoded(json.loads(json.dumps(compact)), snapshot.root)
        stats = period_stats((restored,), prices.reference_valuation, period='all',
                             start=None, now=20_000, zone='UTC')
        amounts = {m.metric: m for m in stats.metrics}
        self.assertEqual((D(224), D(102)),
                         (amounts['total-cost'].value, amounts['subagent-cost'].value))
        self.assertEqual(row.ccost, amounts['total-cost'].value)
        self.assertEqual((('ses_current', None), ('ses_current_child', 'ses_current')),
                         restored.session_parents)
        legacy = dict(compact)
        del legacy['session_parents']
        old, _facts, _matched = decoded(legacy, snapshot.root)
        self.assertEqual(D(102), next(m.value for m in period_stats((old,), prices.reference_valuation,
            period='all', start=None, now=20_000, zone='UTC').metrics if m.metric == 'subagent-cost'))

    def project(self, snapshot, prices=None):
        prices = prices or catalog()
        bundle = analyze_snapshot(snapshot, now_ms=20_000)
        block = build_prompt_block(session_id=snapshot.root.session_id, title="Synthetic", bundle=bundle,
            snapshot=snapshot, catalog=prices, config={}, snapshot_running_metrics=True)
        return bundle, block

    def test_report_cli_full_web_and_mini_share_corrected_cost_calls_models_and_mix(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        _, block = self.project(snapshot)
        row = block.rows[0]
        wire = export_block(block, details=True).to_json()
        card = WatchCard("ses_current", "Synthetic", "u1", (WatchRow("ses_current", "Synthetic", row),), "observed")
        live = project_live(WatchProjection("Watch", "Synthetic", (), now_ms=20_000,
            active_cards=(card,), history_cards=(replace(card, focal_id=""),))).to_json()
        for prompt in (wire["rows"][0], live["active_cards"][0]["rows"][0]["prompt"],
                       live["history_cards"][0]["rows"][0]["prompt"]):
            self.assertEqual((D(224), 3), (D(prompt["ccost"]), prompt["calls"]))
            self.assertTrue(prompt["has_additional_model"])
            self.assertEqual([25, 25, 25, 25], prompt["token_mix_percent"])
        displayed = live["active_cards"][0]["rows"][0]["prompt"]
        self.assertIn("Sub Agents:\n• github-copilot/claude-test — Low — (102 Credits)", displayed["display"]["cost_detail_help"])
        self.assertIn("github-copilot/claude-test", displayed["display"]["model_detail_help"])
        self.assertIn("— ($1.02)", displayed["display_units"]["usd"]["cost_detail_help"])
        stream = io.StringIO()
        ReportRenderer({}, stream=stream, color_enabled=False, terminal_width=180).render(
            ReportProjection(ReportKind.SESSION, "Synthetic", "v2", prompt_blocks=(block,)))
        self.assertIn("224", stream.getvalue())
        self.assertIn("*", stream.getvalue())
        self.assertEqual((D(224), 3), (block.total_ccost, block.total_calls))

    def test_tied_custom_call_and_replayed_native_part_do_not_close_verified_launch(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")

        parent = next(m for m in snapshot.messages if m.message_id == "a1")
        native = next(p for p in parent.parts if p.kind == "tool")
        custom = replace(
            native,
            part_id="custom-at-native-start",
            data={
                "tool": "custom-worker",
                "callID": "custom-call",
                "state": {
                    "status": "completed",
                    "input": {},
                    "time": {"start": 3200, "end": 3300},
                    "output": "done",
                },
            },
        )
        expected_calls = [
            ("ses_current", "a1"),
            ("ses_current_child", "ca"),
            ("ses_current", "a2"),
        ]

        for label, batch in (
            ("custom first", (custom, native, deepcopy(native))),
            ("verified first", (native, custom, deepcopy(native))),
        ):
            with self.subTest(order=label):
                parts = tuple(
                    item for p in parent.parts for item in (batch if p == native else (p,))
                )
                messages = tuple(
                    replace(m, parts=parts) if m == parent else m for m in snapshot.messages
                )
                candidate = replace(
                    snapshot,
                    messages=messages,
                    parts=tuple(p for m in messages for p in m.parts),
                )

                bundle, block = self.project(candidate)

                self.assertEqual(1, len(bundle.prompts))
                record, = bundle.prompts
                self.assertCountEqual(
                    expected_calls,
                    [(entry.session_id, entry.message_id) for entry in record.entries],
                )
                self.assertIn(
                    ("ses_current_child", "verified"),
                    [(item.session_id, item.attribution) for item in record.agent_coverage],
                )
                row, = export_block(block, details=True).to_json()["rows"]
                self.assertEqual((61 + 102 + 61, 3), (D(row["ccost"]), row["calls"]))

    def test_multiple_nested_overlapping_and_duplicate_links_union_real_request_identities(self):
        with incident_source() as (source, server):
            duplicate = deepcopy(server.messages["ses_current"][1]["content"][0])
            overlapping = link(start=3250)
            overlapping.update(id="overlap", callID="overlap-call")
            sibling = link(child="ses_sibling", start=3250)
            sibling.update(id="sibling", callID="sibling-call")
            server.messages["ses_current"][1]["content"].extend((duplicate, overlapping, sibling))
            nested = link(child="ses_nested", start=3450, end=3700)
            server.messages["ses_current_child"][1]["content"] = [nested]
            template = server.sessions[1]
            server.sessions.extend(({**template, "id": "ses_sibling"},
                                    {**template, "id": "ses_nested", "parentID": "ses_current_child"}))
            server.messages["ses_sibling"] = [user("su", 3300), assistant("sa", 3400, 3800, model="claude-test")]
            server.messages["ses_nested"] = [user("nu", 3500), assistant("na", 3550, 3600)]
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        record = bundle.prompts[0]
        self.assertEqual(5, record.model_calls)
        self.assertEqual(3, len(record.linked_session_ids))
        self.assertEqual(D(387), block.total_ccost)
        self.assertEqual(5, len({(entry.session_id, entry.message_id) for entry in record.entries}))
        self.assertEqual(block.total_ccost, comparison_cost(trace_entries(snapshot), catalog().reference_valuation).ccost)
        self.assertEqual(4, observe_tools(snapshot, "u1").tool_count)

    def test_background_child_belongs_to_initiator_across_new_prompt_and_late_completion(self):
        with incident_source(background=True, end=3250) as (source, server):
            server.messages["ses_current"].insert(2, user("u2", 3500))
            server.messages["ses_current_child"][1]["time"]["completed"] = 4800
            # Replayed launch data in a newer prompt cannot steal the old call.
            server.messages["ses_current"][4]["content"] = [link(background=True, end=3250)]
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        self.assertEqual({"u1": 2, "u2": 1}, {record.prompt_id: record.model_calls for record in bundle.prompts})
        first, second = bundle.prompts
        self.assertEqual(("ses_current_child",), first.linked_session_ids)
        self.assertEqual((), second.linked_session_ids)
        self.assertEqual(1800, first.execution_duration_ms)
        self.assertEqual(4800, first.terminal_time_ms)
        self.assertEqual((D(163), D(61)), tuple(row.ccost for row in block.rows))

    def test_nested_background_child_can_finish_after_its_foreground_parent_returns(self):
        with incident_source() as (source, server):
            server.sessions.append({**server.sessions[1], "id": "ses_nested", "parentID": "ses_current_child"})
            server.messages["ses_current_child"][1]["content"] = [link(
                child="ses_nested", start=3450, end=3500, background=True)]
            server.messages["ses_nested"] = [user("nu", 3500), assistant("na", 4200, 4400)]
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        self.assertEqual((4, 2, D(285)),
            (bundle.prompts[0].model_calls, len(bundle.prompts[0].linked_session_ids), block.total_ccost))
        self.assertEqual(block.total_ccost, comparison_cost(trace_entries(snapshot), catalog().reference_valuation).ccost)

    def test_running_children_created_during_prompt_then_terminal_updates_duration(self):
        with incident_source(end=0) as (source, server):
            server.sessions[1]["time"]["created"] = 3300
            server.active = {"ses_current_child": {"type": "running"}}
            server.messages["ses_current"] = server.messages["ses_current"][:2]
            server.messages["ses_current_child"][1] = assistant("ca", 3400, None, model="claude-test")
            running = source.load_session_snapshot("ses_current")
            record = analyze_snapshot(running, now_ms=4700).prompts[0]
            self.assertTrue(record.in_progress)
            self.assertFalse(analyze_snapshot(running, now_ms=4700).cacheable)
            self.assertEqual(1700, record.execution_duration_ms)
            server.active = {}
            server.sessions[1]["time"]["updated"] = 5200
            server.messages["ses_current_child"][1] = assistant("ca", 3400, 5000, model="claude-test")
            server.messages["ses_current"][1]["content"] = [link(end=5200)]
            server.messages["ses_current"].extend((user("notice", 5300, "done", "synthetic"),
                                                  assistant("a2", 5400, 5500)))
            finished = source.load_session_snapshot("ses_current")
        record = analyze_snapshot(finished, now_ms=20_000).prompts[0]
        self.assertFalse(record.in_progress)
        self.assertTrue(record.completed_successfully)
        self.assertEqual((3, 2500, 5500), (record.model_calls, record.execution_duration_ms, record.terminal_time_ms))

    def test_inferred_custom_child_turns_are_partitioned_in_detail_and_watch_rows(self):
        with incident_source(name="custom-worker") as (source, server):
            server.messages["ses_current"].extend((
                user("u2", 5000),
                assistant("a3", 5100, 6500),
            ))
            server.messages["ses_current_child"].extend((
                user("cu2", 4600),
                assistant("ca2", 4700, 4900, model="claude-test"),
                user("cu3", 5300),
                assistant("ca3", 5400, 5550, model="claude-test"),
            ))
            snapshot = source.load_session_snapshot("ses_current")

        bundle, block = self.project(snapshot)

        root, child = "ses_current", "ses_current_child"
        expected = (
            ("u1", [(root, "a1"), (root, "a2"), (child, "ca"), (child, "ca2")], 326),
            ("u2", [(root, "a3"), (child, "ca3")], 163),
        )
        detail_rows = export_block(block, details=True).to_json()["rows"]
        self.assertEqual(2, len(bundle.prompts))
        self.assertEqual(2, len(detail_rows))
        self.assertEqual(2, len(block.rows))

        # Independent physical ledger: three GPT requests at 61 and three Claude
        # requests at 102. Each must occur in its particular charging row.
        physical = [(inv.session_id, inv.message_id) for inv in snapshot.invocations]
        self.assertCountEqual([key for _, keys, _ in expected for key in keys], physical)
        for index, (uid, keys, cost) in enumerate(expected):
            with self.subTest(prompt=uid):
                record = bundle.prompts[index]
                self.assertCountEqual(keys, [(e.session_id, e.message_id) for e in record.entries])
                self.assertIn(
                    (child, "inferred"),
                    [(item.session_id, item.attribution) for item in record.agent_coverage],
                )
                row = block.rows[index]
                card = WatchCard(root, "Synthetic", uid, (WatchRow(root, "Synthetic", row),), "observed")
                live = project_live(WatchProjection(
                    "Watch", "Synthetic", (), now_ms=20_000,
                    active_cards=(card,), history_cards=(replace(card, focal_id=""),),
                )).to_json()
                for view in (
                    detail_rows[index],
                    live["active_cards"][0]["rows"][0]["prompt"],
                    live["history_cards"][0]["rows"][0]["prompt"],
                ):
                    self.assertEqual((D(cost), len(keys)), (D(view["ccost"]), view["calls"]))
        self.assertEqual(D(3 * 61 + 3 * 102), sum(row.ccost for row in block.rows))
        self.assertEqual((D(489), 6), (block.total_ccost, block.total_calls))

        stream = io.StringIO()
        ReportRenderer({}, stream=stream, color_enabled=False, terminal_width=180).render(
            ReportProjection(ReportKind.SESSION, "Synthetic", "v2", prompt_blocks=(block,))
        )
        text = stream.getvalue()
        actual = []
        for line in text.splitlines():
            if not line.lstrip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 3:
                continue
            label = cells[0]
            if label.endswith("#1 work") or label.endswith("#2 work") or label == "Total":
                actual.append((label.split("#")[-1], cells[1], cells[2]))
        self.assertEqual(
            [("1 work", "326", "4"), ("2 work", "163", "2"), ("Total", "489", "6")],
            actual,
        )
        self.assertEqual(
            2, text.count("Some subagent work linked by prompt timing; not verified by a tool call.")
        )

    def test_later_native_launch_without_a_new_child_turn_is_visible_but_not_charged_again(self):
        with incident_source() as (source, server):
            server.messages["ses_current"].extend((
                user("u2", 4900),
                assistant("b1", 5000, 6100, content=[
                    {**link(start=5100, end=6000), "id": "later-link", "callID": "later-call"},
                ]),
            ))
            snapshot = source.load_session_snapshot("ses_current")

        bundle, block = self.project(snapshot)

        first, later = bundle.prompts
        root, child = "ses_current", "ses_current_child"
        self.assertCountEqual(
            [(root, "a1"), (root, "a2"), (child, "ca")],
            [(e.session_id, e.message_id) for e in first.entries],
        )
        self.assertEqual([(root, "b1")], [(e.session_id, e.message_id) for e in later.entries])
        self.assertIn(child, [item.session_id for item in later.agent_coverage])
        self.assertEqual((3, 1), (first.model_calls, later.model_calls))
        self.assertEqual((D(224), D(61)), tuple(row.ccost for row in block.rows))

    def test_observed_turn_and_pending_turn_keep_the_known_cost_until_a_real_request_arrives(self):
        with incident_source() as (source, server):
            server.messages["ses_current"].extend((
                user("u2", 4900),
                assistant("b1", 5000, 6100, content=[
                    {**link(start=5100, end=6000), "id": "later-link", "callID": "later-call"},
                ]),
            ))
            server.messages["ses_current_child"].append(user("cu2", 5200))
            server.active = {"ses_current_child": {"type": "running"}}
            pending = source.load_session_snapshot("ses_current")

            server.messages["ses_current_child"].append(
                assistant("ca2", 5300, 5600, model="claude-test")
            )
            server.active = {}
            observed = source.load_session_snapshot("ses_current")

        for frame, later_child_calls, later_cost in (
            (pending, [], 61),
            (observed, [("ses_current_child", "ca2")], 163),
        ):
            with self.subTest(later_cost=later_cost):
                bundle, block = self.project(frame)
                first, later = bundle.prompts
                self.assertCountEqual(
                    [("ses_current", "a1"), ("ses_current", "a2"), ("ses_current_child", "ca")],
                    [(e.session_id, e.message_id) for e in first.entries],
                )
                self.assertCountEqual(
                    [("ses_current", "b1"), *later_child_calls],
                    [(e.session_id, e.message_id) for e in later.entries],
                )
                self.assertEqual((D(224), D(later_cost)), tuple(row.ccost for row in block.rows))
                self.assertIn("ses_current_child", [item.session_id for item in later.agent_coverage])
                if not later_child_calls:
                    self.assertTrue(later.subagent_active)

    def test_ownerless_continuation_and_busy_grandchild_cannot_be_charged_to_two_root_rows(self):
        root, child, nested = "ses_current", "ses_current_child", "ses_nested"
        with incident_source(background=True, end=3250) as (source, server):
            server.sessions.append({**server.sessions[1], "id": nested, "parentID": child})
            server.messages[root].extend((
                user("u2", 4900),
                assistant("b1", 5000, 5850, content=[
                    {**link(start=5100, end=5800), "id": "second-link", "callID": "second-call"},
                ]),
                user("u3", 5900),
                assistant("b2", 6000, 7100, content=[
                    {**link(start=6100, end=7000), "id": "third-link", "callID": "third-call"},
                ]),
            ))
            server.messages[child] = [
                user("cu", 3300),
                assistant("ca", 3400, 3800, model="claude-test", content=[
                    {**link(child=nested, start=3450, end=3500, background=True),
                     "id": "nested-first", "callID": "nested-first-call"},
                ]),
                {"id": "compact-child", "type": "compaction", "time": {"created": 3850}},
                assistant("bridge", 3950, 6500, model="claude-test"),
                user("cu2", 6560),
                assistant("ca2", 6600, 6900, model="claude-test", content=[
                    {**link(child=nested, start=6610, end=6880),
                     "id": "nested-again", "callID": "nested-again-call"},
                ]),
            ]
            # First nested launch owns a real turn. The later launch addresses
            # the same session while that request is busy, with no new user turn.
            server.messages[nested] = [
                user("nu", 3480),
                assistant("busy", 3490, 6840, model="claude-test"),
            ]
            loaded = source.load_session_snapshot(root)

        # Exercise normalized input with a missing parent reference rather than
        # relying on V2's automatic latest-user relink to produce this condition.
        snapshot = replace(loaded, messages=tuple(
            replace(m, parent_message_id=None)
            if (m.session_id, m.message_id) == (child, "bridge") else m
            for m in loaded.messages
        ))
        physical = [(inv.session_id, inv.message_id) for inv in snapshot.invocations]
        self.assertCountEqual(
            [(root, "a1"), (root, "a2"), (root, "b1"), (root, "b2"),
             (child, "ca"), (child, "bridge"), (child, "ca2"), (nested, "busy")],
            physical,
        )

        bundle, _block = self.project(snapshot)

        rows = [[(e.session_id, e.message_id) for e in r.entries] for r in bundle.prompts]
        self.assertEqual(3, len(rows))
        for index, key in enumerate(((root, "a1"), (root, "b1"), (root, "b2"))):
            self.assertIn(key, rows[index])
        self.assertIn((child, "ca"), rows[0])
        self.assertIn((child, "ca2"), rows[2])
        # Do not choose an owner for ambiguous work. Check each physical key
        # against the charging rows *before* any whole-tree union or dedup.
        for key in physical:
            with self.subTest(request=key):
                self.assertLessEqual(sum(row.count(key) for row in rows), 1, rows)

    def test_one_row_retains_known_child_cost_and_marks_the_missing_turn(self):
        root, child = "ses_current", "ses_current_child"
        with incident_source() as (source, server):
            server.messages[child].extend((
                user("cu2", 4300),
                assistant("ca2", 4350, 4450, model="claude-test"),
            ))
            loaded = source.load_session_snapshot(root)

        # The turn and completed assistant are observed. Only the second
        # request's usage observation is unavailable; this is not a zero call.
        missing_key = (child, "ca2")
        self.assertEqual(
            1, sum((inv.session_id, inv.message_id) == missing_key for inv in loaded.invocations)
        )
        snapshot = replace(loaded, invocations=tuple(
            inv for inv in loaded.invocations if (inv.session_id, inv.message_id) != missing_key
        ))

        bundle, block = self.project(snapshot)

        record, = bundle.prompts
        self.assertEqual(
            [("mixed", "usage-unavailable")],
            [(item.attribution, item.state) for item in record.agent_coverage if item.session_id == child],
        )
        self.assertCountEqual(
            [(root, "a1"), (root, "a2"), (child, "ca")],
            [(e.session_id, e.message_id) for e in record.entries],
        )
        row, = block.rows
        self.assertEqual((D(224), 3), (row.ccost, record.model_calls))
        card = WatchCard(root, "Synthetic", "u1", (WatchRow(root, "Synthetic", row),), "observed")
        detail, = with_display(
            export_block(block, details=True), now_ms=20_000
        ).to_json()["rows"]
        live = project_live(WatchProjection(
            "Watch", "Synthetic", (), now_ms=20_000,
            active_cards=(card,), history_cards=(replace(card, focal_id=""),),
        )).to_json()
        for name, view in (
            ("detail", detail),
            ("active", live["active_cards"][0]["rows"][0]["prompt"]),
            ("history", live["history_cards"][0]["rows"][0]["prompt"]),
        ):
            with self.subTest(view=name):
                self.assertEqual((D(224), 3), (D(view["ccost"]), view["calls"]))
                self.assertIs(view["unresolved_cost"], True)
                display = view["display"]
                self.assertEqual(
                    "Linked child usage/cost unverified. Shown reference CCost covers "
                    "observed usage, not a proven zero upstream bill.",
                    display["mini_cost_coverage_help"],
                )
                self.assertIn("102 Credits", display["cost_detail_help"])
                self.assertIn("Request usage unavailable", display["cost_detail_help"])
                self.assertIn("Verified and timing-inferred work", display["cost_detail_help"])

    def test_idless_background_end_releases_only_a_unique_message_and_start_match(self):
        root, child = "ses_current", "ses_current_child"
        with incident_source(background=True, end=3250) as (source, server):
            server.messages[root].extend((user("u2", 5000), assistant("a3", 5100, 6500)))
            server.messages[child].extend((
                user("cu2", 5300),
                assistant("ca2", 5400, 5550, model="claude-test"),
            ))
            loaded = source.load_session_snapshot(root)

        physical = [(inv.session_id, inv.message_id) for inv in loaded.invocations]
        self.assertCountEqual(
            [(root, "a1"), (root, "a2"), (root, "a3"), (child, "ca"), (child, "ca2")],
            physical,
        )
        parent = next(m for m in loaded.messages if (m.session_id, m.message_id) == (root, "a1"))
        native = next(p for p in parent.parts if p.kind == "tool")
        for start, second_keys, second_cost in (
            (3200, [(root, "a3")], 61),
            (3230, [(root, "a3"), (child, "ca2")], 163),
        ):
            with self.subTest(custom_start=start):
                custom = replace(
                    native, part_id="custom", created_at_ms=start, updated_at_ms=3250,
                    data={
                        "tool": "custom-worker", "callID": "another",
                        "state": {
                            "status": "completed", "input": {"background": True},
                            "time": {"start": start, "end": 3250},
                        },
                    },
                )
                messages = tuple(
                    replace(m, parts=(*m.parts, custom)) if m == parent else m for m in loaded.messages
                )
                ended = BackgroundActivity(
                    "id-less", root, "custom-job", start, "a1", running=False, ended_at_ms=4600
                )
                frame = replace(
                    loaded, messages=messages, parts=tuple(p for m in messages for p in m.parts),
                    background=(*loaded.background, ended),
                )

                bundle, block = self.project(frame)

                first, second = bundle.prompts
                self.assertCountEqual(
                    [(root, "a1"), (root, "a2"), (child, "ca")],
                    [(e.session_id, e.message_id) for e in first.entries],
                )
                self.assertIn(
                    (child, "verified"), [(a.session_id, a.attribution) for a in first.agent_coverage]
                )
                self.assertCountEqual(second_keys, [(e.session_id, e.message_id) for e in second.entries])
                self.assertEqual((D(224), D(second_cost)), tuple(row.ccost for row in block.rows))

    def test_equal_root_prompt_timestamps_do_not_resolve_child_ownership_by_sort_order(self):
        root, child = "ses_current", "ses_current_child"
        with incident_source() as (source, server):
            server.messages[root] = [
                user("u1", 3000),
                user("u2", 3000),
                assistant("a1", 3100, 4000),
                assistant("a2", 3150, 4100),
            ]
            loaded = source.load_session_snapshot(root)

        # The flattened V2 fixture relinks both assistants to the last user.
        # Give each root request an explicit owner at both normalized layers.
        owners = {"a1": "u1", "a2": "u2"}
        snapshot = replace(
            loaded,
            messages=tuple(
                replace(m, parent_message_id=owners[m.message_id])
                if m.session_id == root and m.message_id in owners else m
                for m in loaded.messages
            ),
            invocations=tuple(
                replace(inv, initiating_event_id=owners[inv.message_id])
                if inv.session_id == root and inv.message_id in owners else inv
                for inv in loaded.invocations
            ),
        )

        self.assertCountEqual(
            [(root, "a1"), (root, "a2"), (child, "ca")],
            [(inv.session_id, inv.message_id) for inv in snapshot.invocations],
        )
        bundle, block = self.project(snapshot)

        self.assertEqual(2, len(bundle.prompts))
        self.assertCountEqual(
            [(root, "a1"), (root, "a2")],
            [(e.session_id, e.message_id) for r in bundle.prompts for e in r.entries],
        )
        self.assertEqual([1, 1], [r.model_calls for r in bundle.prompts])
        self.assertEqual([D(61), D(61)], [row.ccost for row in block.rows])

    def test_matching_child_id_parent_and_timing_cannot_cross_source_instances(self):
        root, child = "ses_current", "ses_current_child"
        with incident_source(name="custom-worker") as (source, server):
            # Include a child part so its nested and flat representations both
            # participate in the same source-identity change.
            server.messages[child][1] = assistant(
                "ca", 3400, 3800, model="claude-test",
                content=[{
                    "type": "tool", "id": "child-read", "callID": "child-read-call",
                    "name": "read", "time": {"created": 3500, "ran": 3500, "completed": 3600},
                    "state": {"status": "completed", "input": {}, "output": "done"},
                }],
            )
            local = source.load_session_snapshot(root)

        self.assertTrue(any(p.session_id == child for p in local.parts))
        foreign_instance = local.root.provenance.source_instance + "-other"

        def move_child(entity):
            if entity.session_id != child:
                return entity
            return replace(entity, provenance=replace(entity.provenance, source_instance=foreign_instance))

        foreign = replace(
            local,
            sessions=tuple(move_child(s) for s in local.sessions),
            messages=tuple(
                replace(move_child(m), parts=tuple(move_child(p) for p in m.parts))
                for m in local.messages
            ),
            parts=tuple(move_child(p) for p in local.parts),
            events=tuple(move_child(e) for e in local.events),
            invocations=tuple(move_child(inv) for inv in local.invocations),
        )

        for name, snapshot, child_calls, expected_cost in (
            ("same instance", local, [(child, "ca")], 224),
            ("foreign instance", foreign, [], 122),
        ):
            with self.subTest(source=name):
                bundle, block = self.project(snapshot)
                record, = bundle.prompts
                self.assertCountEqual(
                    [(root, "a1"), (root, "a2"), *child_calls],
                    [(entry.session_id, entry.message_id) for entry in record.entries],
                )
                self.assertEqual(2 + len(child_calls), record.model_calls)
                row, = block.rows
                self.assertEqual(D(expected_cost), row.ccost)

    def test_reusing_a_background_child_opens_a_new_window_without_cross_prompt_charges(self):
        with incident_source(background=True, end=3250) as (source, server):
            server.messages["ses_current"].extend((user("u2", 4900),
                assistant("b1", 5000, 6100, content=[{**link(start=5100, end=6000),
                    "id": "new-link", "callID": "new-call"}])))
            server.messages["ses_current_child"].extend((user("cu2", 5200),
                assistant("ca2", 5300, 5500, model="claude-test")))
            snapshot = source.load_session_snapshot("ses_current")
        bundle, block = self.project(snapshot)
        self.assertEqual((3, 2), tuple(record.model_calls for record in bundle.prompts))
        self.assertEqual((D(224), D(163)), tuple(row.ccost for row in block.rows))
        assigned = [(entry.session_id, entry.message_id) for record in bundle.prompts for entry in record.entries]
        self.assertEqual(len(assigned), len(set(assigned)))

    def test_cache_algorithm_and_late_source_revision_rebuild_both_views_without_residuals(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        early = replace(snapshot, invocations=tuple(i for i in snapshot.invocations if i.session_id == "ses_current"),
            source_revision="early")
        source = MutableSource(early)
        deps = AnalysisDependencies("cfg", "price")
        with tempfile.TemporaryDirectory() as directory:
            database = CacheDatabase(Path(directory)); database.initialize()
            repo = CacheRepository(database)
            cache = DerivedAnalysisCache(repo)
            analyze_with_cache(source, early.root, cache, AnalysisDependencies("cfg", "price", "v78-analysis-15-linked-agent-evidence"), analyze_snapshot)
            rebuilt = analyze_with_cache(source, early.root, cache, deps, analyze_snapshot)
            self.assertFalse(rebuilt.cache_hit)
            before = reconcile_session_cost(repo, early, catalog())
            source.snapshot = replace(snapshot, source_revision="late")
            after = analyze_with_cache(source, snapshot.root, cache, deps, analyze_snapshot)
            total = reconcile_session_cost(repo, source.snapshot, catalog())
            repeated = analyze_with_cache(source, snapshot.root, cache, deps, analyze_snapshot)
            self.assertFalse(after.cache_hit)
            self.assertTrue(repeated.cache_hit)
            self.assertEqual((2, 3), (rebuilt.bundle.prompts[0].model_calls, after.bundle.prompts[0].model_calls))
            self.assertEqual((D(122), D(224), 1), (before.total.ccost, total.total.ccost, total.valued_requests))
            self.assertEqual(after.bundle, repeated.bundle)

    def test_zero_unknown_and_partial_children_keep_honest_reference_coverage_and_billing(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        for kind in ("zero", "unpriced", "partial"):
            invocations = []
            for invocation in snapshot.invocations:
                if invocation.session_id == "ses_current_child":
                    changes = {"tokens": TokenUsage()} if kind == "zero" else (
                        {"model": ModelRef("github-copilot", "unpriced")} if kind == "unpriced" else
                        {"tokens": replace(invocation.tokens, known_fields=("input",))})
                    invocation = replace(invocation, **changes)
                invocations.append(invocation)
            changed = replace(snapshot, invocations=tuple(invocations))
            _, block = self.project(changed)
            row = block.rows[0]
            with self.subTest(kind=kind):
                self.assertEqual((3, 1), (row.calls, row.linked_agent_count))
                self.assertEqual(kind != "zero", row.unresolved_cost)
                self.assertEqual(kind != "partial", row.token_mix_percent is not None)
                self.assertIsNone(row.billed_cost)  # native zero is not reference billing
                self.assertEqual(D(142) if kind == "partial" else D(122), row.ccost)

    def test_child_uses_its_own_price_tier_even_when_it_shares_the_parent_model(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        invocations = tuple(replace(i, model=ModelRef("github-copilot", "gpt-test"),
            tokens=TokenUsage(input=100001, output=1000)) if i.session_id == "ses_current_child" else i
            for i in snapshot.invocations)
        _, block = self.project(replace(snapshot, invocations=invocations), threshold_catalog())
        row = block.rows[0]
        self.assertEqual((D(244), D("20.8002"), D("264.8002")), (row.main_ccost, row.subagent_ccost, row.ccost))
        self.assertEqual(("high", "low"), tuple(p.variant for p in row.cost_parts))

    def test_child_usage_without_a_recorded_parent_request_is_not_dropped_or_relabelled(self):
        with incident_source() as (source, _server):
            snapshot = source.load_session_snapshot("ses_current")
        child_only = replace(snapshot, invocations=tuple(i for i in snapshot.invocations if i.session_id != "ses_current"))
        bundle, block = self.project(child_only)
        record = bundle.prompts[0]
        self.assertEqual((1, 0, "gpt-test"), (record.model_calls, record.root_entry_count, record.main_model_id))
        self.assertEqual((D(0), D(102)), (block.rows[0].main_ccost, block.rows[0].subagent_ccost))

    def test_legitimate_unallocatable_and_compaction_residuals_are_not_assigned_to_prompt(self):
        with incident_source() as (source, server):
            server.messages["ses_current_child"].append(assistant("unassigned", 6000, 6200, model="claude-test"))
            snapshot = source.load_session_snapshot("ses_current")
        _, block = self.project(snapshot)
        self.assertEqual(D(224), block.rows[0].ccost)
        self.assertEqual(D(326), comparison_cost(trace_entries(snapshot), catalog().reference_valuation).ccost)
        legacy = make_snapshot()
        bundle, block = self.project(legacy)
        prompt_cost = sum(row.ccost for row in block.rows if not row.is_compaction)
        compact_cost = sum(row.ccost for row in block.rows if row.is_compaction)
        self.assertGreater(compact_cost, 0)
        self.assertEqual(block.total_ccost, prompt_cost + compact_cost)


if __name__ == "__main__":
    unittest.main()
