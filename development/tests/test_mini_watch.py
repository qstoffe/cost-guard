"""Canonical running aggregates and app-owned Mini lifecycle without a browser dependency."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
import json
import shutil
import subprocess
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from development.tests.fixtures.watch_summary import summary_watch
from development.tests.fixtures.context_deltas import context_snapshot, context_frame
from development.tests.fixtures.mini_context import handoff_snapshot, handoff_capture, handoff_frame
from development.tests.fixtures.pricing_catalog import catalog
from src.analysis.session_cost import SessionCost
from src.analysis.valuation import ComparisonCost
from src.application.live_projection import project_live
from src.analysis.timezones import resolve_timezone
from src.domain import EventKind, NormalizedEvent
from src.watch.models import WatchCard, WatchRow
from src.watch.running import running_prompts

ROOT = Path(__file__).resolve().parents[2]


class MiniWatchTests(unittest.TestCase):
    def setUp(self):
        self.frame = summary_watch()
        base = self.frame.active_cards[0].rows[0].prompt
        self.first = replace(base, event_id="one", ccost=D("1.25"), duration_ms=600_000,
            prompt_number=23, at_ms=1000, cost_estimated=False, unresolved_cost=False)
        self.second = replace(self.first, event_id="two", prompt_number=24, at_ms=2000,
            ccost=D("2.75"), duration_ms=1_200_000)
        self.cards = tuple(WatchCard("same-session", "Concurrent", row.event_id,
            (WatchRow("same-session", "Concurrent", row),), "observed",
            session_context=self.frame.active_cards[0].session_context,
            session_cost=self.frame.active_cards[0].session_cost, session_cost_state="observed", observed_at_ms=1000)
            for row in (self.first, self.second))

    def test_session_projection_shares_full_totals_not_prompt_values_and_current_context(self):
        partial = SessionCost(ComparisonCost(D("4582.125"), 2001, 2000), False, True)
        active = tuple(replace(card, session_cost=partial, session_cost_state="refreshing") for card in self.cards)
        earlier = replace(active[0], session_id="earlier", focal_id="",
            rows=(replace(active[0].rows[0], prompt=replace(self.first,
                in_progress=False, watch_next_context_tokens=17)),))

        frame = replace(self.frame, active_cards=active, history_cards=(earlier,))
        credits = project_live(frame).to_json()
        usd = project_live(frame, ccost_display_unit="usd").to_json()

        summaries = [card["session_summary"] for card in credits["active_cards"] + credits["history_cards"]]
        self.assertTrue(all(summary == summaries[0] for summary in summaries))
        self.assertEqual("4582.125", summaries[0]["cost"]["known_ccost"])
        self.assertEqual("?4583", summaries[0]["cost"]["display"]["known_ccost"])
        self.assertEqual("4583", summaries[0]["cost"]["display"]["account_ccost"])
        self.assertEqual("?$45.82", usd["history_cards"][0]["session_summary"]["cost"]["display"]["known_ccost"])
        self.assertEqual("$45.82", usd["history_cards"][0]["session_summary"]["cost"]["display"]["account_ccost"])
        self.assertEqual("refreshing", summaries[0]["state"])
        self.assertFalse(summaries[0]["cost"]["complete"])
        self.assertEqual(120000, summaries[0]["context"]["watch_next_context_tokens"])
        self.assertEqual(17, credits["history_cards"][0]["rows"][0]["live_context"]["watch_next_context_tokens"])
        self.assertEqual(["1.25", "2.75"], [card["rows"][0]["prompt"]["ccost"] for card in credits["active_cards"]])

    def test_quiet_subtotal_token_preserves_partial_unknown_and_zero_source_facts(self):
        for amount, observed, priced, complete, quiet, ordinary in (
                ("562", 3, 2, False, ("562", "$5.62"), ("?562", "?$5.62")),
                ("562", 3, 3, True, ("562", "$5.62"), ("562", "$5.62")),
                ("0", 0, 0, True, ("0", "$0.00"), ("0", "$0.00")),
                ("0", 1, 1, True, ("0", "$0.00"), ("0", "$0.00")),
                ("0", 1, 0, False, ("—", "—"), ("N/A", "N/A"))):
            cost = SessionCost(ComparisonCost(D(amount), observed, priced), complete, True)
            card = replace(self.cards[0], session_cost=cost, session_cost_state="observed")

            for index, unit in enumerate(("credits", "usd")):
                wire = project_live(replace(self.frame, active_cards=(card,)), ccost_display_unit=unit).to_json()
                total = wire["active_cards"][0]["session_summary"]["cost"]

                with self.subTest(amount=amount, observed=observed, priced=priced, unit=unit):
                    self.assertEqual(quiet[index], total["display"]["account_ccost"])
                    self.assertEqual(ordinary[index], total["display"]["known_ccost"])
                    self.assertEqual((amount, observed, priced, complete),
                        (total["known_ccost"], total["observed_requests"], total["priced_requests"], total["complete"]))

    def test_same_session_distinct_prompts_dedup_focals_not_context_or_compaction(self):
        context = WatchRow("same-session", "Concurrent", replace(self.first, event_id="context", ccost=D(999)))
        terminal = replace(self.cards[1], rows=(replace(self.cards[1].rows[0],
            prompt=replace(self.second, in_progress=False)),))
        compact = replace(self.cards[1], rows=(replace(self.cards[1].rows[0],
            prompt=replace(self.second, is_compaction=True)),))
        placeholder = WatchCard("pending", "Pending", "", ())
        cards = (replace(self.cards[0], rows=self.cards[0].rows + (context,)),
            self.cards[1], self.cards[0], terminal, compact, placeholder)

        result = running_prompts(cards, "observed")

        self.assertEqual((2, D(4), 1_200_000), (result.count, result.ccost, result.duration_ms))
        self.assertTrue(result.complete)
        self.assertFalse(result.unresolved_cost)
        # Ending the longest immediately removes its cost and allows max to decrease,
        # even though its terminal grace card is still visible.
        result = running_prompts((self.cards[0], terminal), "observed")
        self.assertEqual((1, D("1.25"), 600_000), (result.count, result.ccost, result.duration_ms))

    def test_active_and_historical_help_fields_keep_prepared_prompt_delta_and_preview(self):
        for delta, token in ((0, "0"), (4000, "+4k"), (-12000, "-12k"), (None, "N/A")):
            prompt = replace(self.first, preview="Bounded representative hint", watch_delta_context_tokens=delta,
                watch_next_context_tokens=17000)
            card = replace(self.cards[0], rows=(replace(self.cards[0].rows[0], prompt=prompt),))

            wire = project_live(replace(self.frame, active_cards=(card,),
                history_cards=(replace(card, focal_id=""),))).to_json()

            for kind in ("active_cards", "history_cards"):
                with self.subTest(delta=delta, kind=kind):
                    item = wire[kind][0]["rows"][0]
                    self.assertEqual("Bounded representative hint", item["prompt"]["preview"])
                    self.assertEqual(23, item["prompt"]["prompt_number"])
                    self.assertEqual(token, item["live_context"]["display"]["watch_delta_context_tokens"])
                    self.assertEqual("17k", item["live_context"]["display"]["watch_next_context_tokens"])
                    self.assertEqual("120k", wire[kind][0]["session_summary"]["context"]["display"]["watch_next_context_tokens"])

    def test_source_driven_running_history_and_revision_corrections_reach_live(self):
        for outputs, historical, next_tokens, delta, token in (
                ((12_000,), False, 112_000, 12_000, "+12k"),
                ((12_000, 5_000), False, 117_000, 17_000, "+17k"),
                ((12_000,), True, 112_000, 12_000, "+12k"),
                ((0,), True, 100_000, 0, "0"),
                ((), False, None, None, "N/A")):
            snapshot = context_snapshot(outputs=outputs, running=not historical, active=not historical)
            frame = context_frame(self.frame, snapshot, catalog(), historical=historical,
                                  session_next=300_000 if historical else None)
            wire = project_live(frame).to_json()
            card = wire['history_cards' if historical else 'active_cards'][0]
            row = card['rows'][0]
            with self.subTest(outputs=outputs, historical=historical):
                self.assertEqual(next_tokens, row['live_context']['watch_next_context_tokens'])
                self.assertEqual(delta, row['live_context']['watch_delta_context_tokens'])
                self.assertEqual(token, row['live_context']['display']['watch_delta_context_tokens'])
                self.assertEqual(delta, wire['rows'][0]['live_context']['watch_delta_context_tokens'])
                self.assertEqual(300_000 if historical else next_tokens,
                    card['session_summary']['context']['watch_next_context_tokens'])
                if outputs:
                    self.assertEqual(100_000, row['prompt']['incoming_context_tokens'])
                else:
                    self.assertIn('waiting', row['live_context']['watch_context_detail'])

    def test_historical_cost_and_help_export_the_same_representative_prompt(self):
        latest = replace(self.second, in_progress=False, watch_model="Historical model",
            watch_effort="high", calls=17, linked_agent_count=2, has_additional_model=True,
            unresolved_cost=True, aborted=True, abort_reason="quota_limit")
        history = replace(self.cards[0], focal_id="", rows=(WatchRow("same-session", "Concurrent", latest),))

        wire = project_live(replace(self.frame, history_cards=(history,))).to_json()
        card = wire["history_cards"][0]
        item = card["rows"][0]

        self.assertEqual("2.75", item["prompt"]["ccost"])
        self.assertEqual(24, item["prompt"]["prompt_number"])
        self.assertEqual(("Historical model", "high", 1_200_000),
            (item["model"], item["effort"], item["watch_duration_ms"]))
        self.assertEqual((17, 2, True, "quota_limit"), (item["prompt"]["calls"],
            item["prompt"]["linked_agent_count"], item["prompt"]["has_additional_model"], item["prompt"]["abort_reason"]))
        self.assertEqual("4582.125", card["session_summary"]["cost"]["known_ccost"])

    def test_handoff_requires_active_comparable_source_predecessor_and_no_current_estimate(self):
        capture = handoff_capture(handoff_snapshot())
        self.assertEqual((('next', ('u', 230_000)),), capture.context_handoffs)
        self.assertIsNone(capture.rows[-1].watch_next_context_tokens)
        self.assertIsNone(capture.rows[-1].watch_delta_context_tokens)
        wire = project_live(handoff_frame(self.frame, 'pending')).to_json()
        self.assertEqual({'previous_id': 'u', 'previous_tokens': 230_000},
            wire['active_cards'][0]['context_handoff'])
        self.assertEqual('N/A', wire['active_cards'][0]['rows'][0]['live_context']['display']['watch_next_context_tokens'])
        fresh = handoff_capture(handoff_snapshot('fresh')).rows[-1]
        self.assertEqual(235_000, fresh.watch_next_context_tokens)
        self.assertTrue(fresh.in_progress)
        unverified = handoff_capture(handoff_snapshot('unverified')).rows[-1]
        self.assertTrue(unverified.execution_unverified)
        self.assertIsNone(unverified.watch_next_context_tokens)
        for phase in ('fresh', 'tools', 'model', 'model-selection', 'reset', 'move',
                      'inactive', 'unverified', 'partial-usage', 'incomplete'):
            with self.subTest(phase=phase):
                self.assertEqual((), handoff_capture(handoff_snapshot(phase)).context_handoffs)
        snapshot = handoff_snapshot()
        compacted = replace(snapshot.messages[-2], message_id='compact', created_at_ms=1800,
            parts=(replace(snapshot.messages[-2].parts[0], kind='compaction', data={}),))
        snapshot = replace(snapshot, messages=snapshot.messages + (compacted,),
            parts=snapshot.parts + compacted.parts,
            events=snapshot.events + (NormalizedEvent('compact', 'root', EventKind.COMPACTION,
                1800, compacted.provenance, ''),))
        self.assertEqual((), handoff_capture(snapshot).context_handoffs)

    def test_pending_unknown_partial_estimate_and_genuine_empty_are_distinct(self):
        for state in ("loading", "partial", "unavailable"):
            pending = running_prompts((), state)
            self.assertEqual((None, None, None, False),
                (pending.count, pending.ccost, pending.duration_ms, pending.complete))
            known = running_prompts(self.cards, state)
            self.assertEqual((2, D(4)), (known.count, known.ccost))
            self.assertFalse(known.complete)
            self.assertTrue(known.unresolved_cost)
        row = replace(self.first, ccost=D(0), unresolved_cost=True, cost_estimated=True)
        card = replace(self.cards[0], rows=(WatchRow("same-session", "Concurrent", row),))
        partial = running_prompts((card,), "observed")
        wire = project_live(replace(self.frame, running=partial)).to_json()["running"]
        self.assertEqual("N/A", wire["display"]["ccost"])
        self.assertTrue(wire["cost_estimated"])
        zero = running_prompts((), "observed")
        self.assertEqual((0, D(0), None, True, False),
            (zero.count, zero.ccost, zero.duration_ms, zero.complete, zero.unresolved_cost))
        self.assertEqual("$0.00", project_live(replace(self.frame, running=zero),
            ccost_display_unit="usd").to_json()["running"]["display"]["ccost"])

    @unittest.skipUnless(shutil.which("node"), "optional JS VM unavailable")
    def test_opening_reserve_measures_real_and_reference_header(self):
        result = subprocess.run([shutil.which("node"), "development/tests/fixtures/mini_opening.cjs"],
            cwd=ROOT, text=True, encoding="utf-8", capture_output=True, timeout=15)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "optional JS VM unavailable")
    def test_app_owned_window_races_health_settings_and_independent_dom(self):
        payload = {"state": "running", "view": project_live(replace(self.frame,
            active_cards=tuple(replace(card, session_id=f"session-{index}") for index, card in enumerate(self.cards)),
            history_cards=(), running=running_prompts(self.cards, "observed"))).to_json()}
        result = subprocess.run([shutil.which("node"), "development/tests/integration/mini_watch.cjs"],
            cwd=ROOT, input=json.dumps(payload), text=True, encoding="utf-8", capture_output=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_finish_export_uses_terminal_evidence_local_date_and_dst_offset(self):
        for when, clock, full in (
                ((2026, 11, 5, 22, 47), '23:47', '2026-11-05 23:47 +0100'),
                ((2026, 11, 5, 23, 8), '00:08', '2026-11-06 00:08 +0100'),
                ((2026, 10, 25, 0, 30), '02:30', '2026-10-25 02:30 +0200'),
                ((2026, 10, 25, 1, 30), '02:30', '2026-10-25 02:30 +0100')):
            finished = int(datetime(*when, tzinfo=timezone.utc).timestamp() * 1000)
            row = replace(self.first, completed_at_ms=finished, in_progress=False,
                aborted=True, abort_reason='quota_limit', completed_successfully=False)
            card = replace(self.cards[0], rows=(WatchRow('same-session', 'Concurrent', row),))

            wire = project_live(replace(self.frame, history_cards=(card,)), 'Europe/Stockholm').to_json()
            prompt = wire['history_cards'][0]['rows'][0]['prompt']

            with self.subTest(when=when):
                self.assertEqual((finished, clock, full), (prompt['completed_at_ms'],
                    prompt['display']['finished_clock'], prompt['display']['finished_date_time']))
                self.assertEqual(600_000, prompt['duration_ms'])
                self.assertFalse(prompt['completed_successfully'])
                started = project_live(replace(self.frame, active_cards=(replace(card,
                    rows=(WatchRow('same-session', 'Concurrent', replace(row, at_ms=finished, in_progress=True)),)),)),
                    'Europe/Stockholm').to_json()['active_cards'][0]['rows'][0]['prompt']
                self.assertEqual(full, started['display']['start_date_time'])
        unknown = replace(row, completed_at_ms=None)
        card = replace(card, rows=(WatchRow('same-session', 'Concurrent', unknown),))
        prompt = project_live(replace(self.frame, history_cards=(card,))).to_json()['history_cards'][0]['rows'][0]['prompt']
        self.assertEqual(('—', 'Unknown finish time'),
            (prompt['display']['finished_clock'], prompt['display']['finished_date_time']))

    def test_daily_presentation_expiry_uses_configured_day_including_dst(self):
        for day, start_hour, hours in (((2026, 3, 29), 23, 23), ((2026, 10, 25), 22, 25)):
            # UTC instants of Stockholm midnight, deliberately not browser local time.
            midnight = datetime(*day, tzinfo=timezone.utc).timestamp() * 1000 - (24 - start_hour) * 3600000
            frame = replace(self.frame, daily_usage=replace(self.frame.daily_usage, day_start_ms=int(midnight)))

            daily = project_live(frame, 'Europe/Stockholm').to_json()['daily_usage']

            self.assertEqual(hours * 3600000, daily['day_end_ms'] - daily['day_start_ms'])
            self.assertEqual(self.frame.daily_usage.observed_at_ms, daily['observed_at_ms'])

        frame = replace(self.frame, daily_usage=replace(self.frame.daily_usage, day_start_ms=0))
        self.assertEqual(86400000, project_live(frame, 'UTC').to_json()['daily_usage']['day_end_ms'])
        frame = replace(frame, daily_usage=replace(frame.daily_usage, day_start_ms=-3600000))
        self.assertEqual(82800000, project_live(frame, 'Europe/Stockholm').to_json()['daily_usage']['day_end_ms'])

    def test_windows_timezone_fallback_preserves_repeated_hour_identity(self):
        with patch('src.analysis.timezones.ZoneInfo', side_effect=ZoneInfoNotFoundError):
            zone = resolve_timezone('Europe/Stockholm')
        for hour, fold, expected in ((0, 0, '+0200'), (1, 1, '+0100')):
            utc = datetime(2026, 10, 25, hour, 30, tzinfo=timezone.utc)
            local = utc.astimezone(zone)
            self.assertEqual(('02:30', expected, fold), (local.strftime('%H:%M'), local.strftime('%z'), local.fold))
            self.assertEqual(utc.timestamp(), local.timestamp())


if __name__ == "__main__":
    unittest.main()
