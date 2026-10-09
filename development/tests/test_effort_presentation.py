"""Trustworthy shared effort meaning and request-only compaction regressions."""
from __future__ import annotations

import io
import unittest
from dataclasses import replace

from development.tests.test_analysis_core import make_snapshot
from development.tests.test_step6_context_comparisons import catalog
from development.tests.test_opencode_v2 import source_with_current_service
from src.analysis.core import analyze_snapshot
from src.analysis.effort import EffortKind, interpret_effort, prompt_effort
from src.analysis.comparisons import model_timeline_name, watch_model_timeline_name
from src.domain import ModelRef
from src.presentation import ReportRenderer, WatchRenderer
from src.reports.models import ReportKind, ReportProjection
from src.reports.prompts import build_prompt_block
from src.sources.opencode_v2_wire import interim_flat_message_to_legacy_bundle
from src.watch.models import WatchProjection, WatchRow


def normal_snapshot(selected="default", actual=None):
    snapshot = make_snapshot()
    return replace(
        snapshot,
        events=tuple(replace(event, metadata={**event.metadata, "variant": selected})
                     if event.event_id == "u_next" else event for event in snapshot.events),
        messages=tuple(replace(message, variant=actual) if message.message_id == "a_next"
                       else message for message in snapshot.messages),
        invocations=tuple(replace(invocation, variant=actual) if invocation.message_id == "a_next"
                          else invocation for invocation in snapshot.invocations),
    )


def project(snapshot):
    bundle = analyze_snapshot(snapshot, now_ms=6000, tracked_provider=None)
    block = build_prompt_block(session_id=snapshot.root.session_id, title="Test", bundle=bundle,
                               snapshot=snapshot, catalog=catalog(), config={})
    return bundle, block


class EffortMeaningTests(unittest.TestCase):
    def test_explicit_selected_effort_wins(self):
        for level in ("High", "medium", "xhigh", "low", "minimal", "custom"):
            with self.subTest(level=level):
                result = interpret_effort(level, request_levels=("low",))
                self.assertEqual(EffortKind.EXPLICIT, result.kind)
                self.assertEqual(level, result.level)

    def test_default_needs_unanimous_concrete_request_evidence(self):
        for selected in (None, "", "Default", " default "):
            with self.subTest(selected=selected):
                resolved = interpret_effort(selected, request_levels=("medium", "Medium"))
                self.assertEqual(EffortKind.RESOLVED_DEFAULT, resolved.kind)
                self.assertEqual("medium", resolved.level)
                for levels in ((), (None,), ("default",), ("medium", None), ("medium", "high")):
                    self.assertEqual(EffortKind.DEFAULT, interpret_effort(selected, request_levels=levels).kind)

    def test_no_attributable_effort_has_no_level(self):
        result = interpret_effort("High", attributable=False)
        self.assertEqual(EffortKind.NONE, result.kind)
        self.assertIsNone(result.level)
        self.assertEqual("N/A", model_timeline_name(catalog(), "", "", ""))

    def test_compaction_ignores_default_resolution_and_requires_own_explicit_level(self):
        for selected in (None, "", "Default"):
            result = interpret_effort(selected, request_levels=("High",), compaction=True)
            self.assertEqual(EffortKind.NONE, result.kind)
        self.assertEqual(EffortKind.EXPLICIT, interpret_effort("High", compaction=True).kind)

    def test_no_provider_family_can_manufacture_a_default(self):
        for provider in ("github-copilot", "openai", "anthropic", "claude-code", "new"):
            for model in ("gpt-5", "gpt-5.6", "gpt-6.1-sol", "claude-opus-5-5"):
                with self.subTest(provider=provider, model=model):
                    expected = model + " (Default)"
                    self.assertEqual(expected, model_timeline_name(catalog(), model, provider, "default"))
                    self.assertEqual(expected, watch_model_timeline_name(catalog(), model, provider, ""))


class EffortProjectionTests(unittest.TestCase):
    def test_normal_watch_and_report_labels_are_identical(self):
        for selected, actual, expected in (("high", None, "High"), ("medium", None, "Medium"),
                                           ("default", None, "Default"), ("", None, "Default"),
                                           ("default", "medium", "Medium")):
            with self.subTest(selected=selected, actual=actual):
                _, block = project(normal_snapshot(selected, actual))
                row = next(row for row in block.rows if row.event_id == "u_next")
                self.assertEqual(f"GPT Test ({expected})", row.model_effort)
                self.assertEqual(row.model_effort, row.watch_model_effort)
                self.assertNotIn("->", row.model_effort)

    def test_actual_renderers_keep_default_and_resolved_labels_compact(self):
        for actual, expected in ((None, "Default"), ("medium", "Medium"), ("high", "High")):
            _, block = project(normal_snapshot("default", actual))
            row = next(row for row in block.rows if row.event_id == "u_next")
            block = replace(block, rows=(row,))
            report_out, watch_out = io.StringIO(), io.StringIO()
            ReportRenderer({}, stream=report_out, color_enabled=False).render(
                ReportProjection(ReportKind.SESSION, "Test", "Test", prompt_blocks=(block,)))
            WatchRenderer({}, stream=watch_out, interactive=False).render(
                WatchProjection("Test", "Test", (WatchRow("root", "Test", row),), now_ms=6000))
            for text in (report_out.getvalue(), watch_out.getvalue()):
                self.assertIn(f"GPT Test ({expected})", text)
                self.assertNotIn("Default ->", text)

    def test_other_requests_models_and_summaries_cannot_resolve_default(self):
        snapshot = normal_snapshot()
        for target in ("a_sub", "ca", "a_comp"):
            changed = replace(snapshot, messages=tuple(replace(m, variant="high")
                              if m.message_id == target else m for m in snapshot.messages))
            bundle, _ = project(changed)
            record = next(p for p in bundle.prompts if p.prompt_id == "u_next")
            self.assertEqual(EffortKind.DEFAULT, prompt_effort(record, changed).kind)
        changed = replace(snapshot, messages=tuple(replace(m, variant="high", model=ModelRef("other", "gpt-test"))
                          if m.message_id == "a_next" else m for m in snapshot.messages))
        bundle, _ = project(changed)
        self.assertEqual(EffortKind.DEFAULT, prompt_effort(bundle.prompts[-1], changed).kind)

    def test_conflicting_or_missing_actual_request_levels_stay_default(self):
        snapshot = normal_snapshot("default", "medium")
        assistant = next(m for m in snapshot.messages if m.message_id == "a_next")
        for level in (None, "high", "default"):
            changed = replace(snapshot, messages=(*snapshot.messages,
                replace(assistant, message_id="a_retry", variant=level, created_at_ms=2200)))
            _, block = project(changed)
            row = next(row for row in block.rows if row.event_id == "u_next")
            self.assertEqual("GPT Test (Default)", row.model_effort)

    def test_request_variant_without_tokens_is_still_attributable(self):
        snapshot = normal_snapshot("default", "medium")
        snapshot = replace(snapshot, invocations=tuple(i for i in snapshot.invocations if i.message_id != "a_next"),
            messages=tuple(replace(m, error_name="AbortedError") if m.message_id == "a_next" else m
                           for m in snapshot.messages))
        _, block = project(snapshot)
        row = next(row for row in block.rows if row.event_id == "u_next")
        self.assertEqual("GPT Test (Medium)", row.model_effort)

    def test_compaction_never_inherits_normal_effort(self):
        for normal in ("default", "high"):
            for own, expected in ((None, "GPT Test"), ("default", "GPT Test"), ("high", "GPT Test (High)")):
                snapshot = normal_snapshot(normal, "medium")
                snapshot = replace(snapshot,
                    messages=tuple(replace(m, variant=own) if m.message_id == "a_comp" else m for m in snapshot.messages),
                    invocations=tuple(replace(i, variant=own) if i.message_id == "a_comp" else i for i in snapshot.invocations))
                _, block = project(snapshot)
                row = next(row for row in block.rows if row.is_compaction)
                self.assertEqual(expected, row.model_effort)
                self.assertEqual(expected, row.watch_model_effort)

    def test_compaction_renderers_show_own_model_and_explicit_effort_only(self):
        snapshot = normal_snapshot("high", "high")
        for own, expected in ((None, "GPT Test"), ("high", "GPT Test (High)")):
            changed = replace(snapshot,
                messages=tuple(replace(m, variant=own) if m.message_id == "a_comp" else m for m in snapshot.messages),
                invocations=tuple(replace(i, variant=own) if i.message_id == "a_comp" else i for i in snapshot.invocations))
            _, block = project(changed)
            row = next(row for row in block.rows if row.is_compaction)
            for calls in (row.calls, 0):
                compact = replace(row, calls=calls, ccost=0 if not calls else row.ccost)
                report_out, watch_out = io.StringIO(), io.StringIO()
                ReportRenderer({}, stream=report_out, color_enabled=False).render(
                    ReportProjection(ReportKind.SESSION, "Test", "Test", prompt_blocks=(replace(block, rows=(compact,)),)))
                WatchRenderer({}, stream=watch_out, interactive=False).render(
                    WatchProjection("Test", "Test", (WatchRow("root", "Test", compact),), now_ms=6000))
                for text in (report_out.getvalue(), watch_out.getvalue()):
                    self.assertIn("/compact", text)
                    self.assertIn(expected, text)
                    self.assertNotIn("(Default)", text)
                    if own is None:
                        self.assertNotIn("(High)", text)

    def test_compaction_trigger_can_supply_its_own_explicit_effort(self):
        snapshot = normal_snapshot("default", "medium")
        snapshot = replace(snapshot, events=tuple(replace(event, metadata={**event.metadata, "variant": "high"})
            if event.event_id == "u_comp" else event for event in snapshot.events))
        _, block = project(snapshot)
        compact = next(row for row in block.rows if row.is_compaction)
        self.assertEqual("GPT Test (High)", compact.model_effort)


class EffortSourceTests(unittest.TestCase):
    def test_current_v2_session_selection_is_not_request_effort(self):
        with source_with_current_service() as (source, server, _registration):
            server.sessions[0]["model"]["variant"] = "high"
            server.messages["ses_current"][1]["model"].pop("variant")
            snapshot = source.load_session_snapshot("ses_current")
            self.assertIsNone(next(m for m in snapshot.messages if m.role.value == "user").variant)
            _, block = project(snapshot)
            self.assertEqual("gpt-5.6 (Default)", block.rows[0].model_effort)

    def test_current_v2_persisted_request_variant_wins_over_mutable_selection(self):
        with source_with_current_service() as (source, server, _registration):
            server.sessions[0]["model"]["variant"] = "high"
            snapshot = source.load_session_snapshot("ses_current")
            _, block = project(snapshot)
            self.assertEqual("gpt-5.6 (Medium)", block.rows[0].model_effort)


    def test_current_v2_model_switch_preserves_historical_rows(self):
        with source_with_current_service() as (source, server, _registration):
            server.messages["ses_current"][1]["model"]["variant"] = "xhigh"
            server.messages["ses_current"].extend((
                {"id": "msg_sol_user", "type": "user", "text": "continue", "time": {"created": 5000}},
                {"id": "msg_sol_assistant", "type": "assistant", "agent": "build",
                 "model": {"providerID": "openai", "id": "gpt-6.1-sol", "variant": "medium"},
                 "content": [{"type": "text", "id": "sol_answer", "text": "done"}],
                 "finish": "stop", "tokens": {"input": 150, "cache": {"read": 400, "write": 0}, "output": 30},
                 "cost": 0.1, "time": {"created": 5100, "completed": 5500}},
            ))
            server.sessions[0]["model"] = {"providerID": "openai", "id": "gpt-6.1-sol", "variant": "default"}
            snapshot = source.load_session_snapshot("ses_current")
            self.assertTrue(all(m.model is None for m in snapshot.messages if m.role.value == "user"))
            _, block = project(snapshot)
            self.assertEqual(["gpt-5.6 (XHigh)", "gpt-6.1-sol (Medium)"],
                             [row.model_effort for row in block.rows if not row.is_compaction])
            server.sessions[0]["model"] = {"providerID": "openai", "id": "other", "variant": "low"}
            _, updated = project(source.load_session_snapshot("ses_current"))
            self.assertEqual([(x.model_effort, x.ccost, x.calls) for x in block.rows],
                             [(x.model_effort, x.ccost, x.calls) for x in updated.rows])
            self.assertEqual([x.model_effort for x in updated.rows],
                             [x.watch_model_effort for x in updated.rows])

    def test_current_v2_unanswered_prompt_does_not_inherit_session_model(self):
        with source_with_current_service() as (source, server, _registration):
            server.messages["ses_current"].append(
                {"id": "msg_waiting_user", "type": "user", "text": "waiting", "time": {"created": 5200}})
            server.sessions[0]["model"] = {"providerID": "openai", "id": "gpt-6.1-sol", "variant": "high"}
            snapshot = source.load_session_snapshot("ses_current")
            waiting = next(m for m in snapshot.messages if m.message_id == "msg_waiting_user")
            self.assertIsNone(waiting.model)
            self.assertNotIn("model_id", next(e for e in snapshot.events
                                               if e.event_id == "msg_waiting_user").metadata)

    def test_interim_v2_does_not_copy_session_variant_to_assistant(self):
        item = {"id": "a", "role": "assistant", "parts": [],
                "metadata": {"assistant": {"providerID": "openai", "modelID": "gpt"}}}
        session = {"id": "s", "model": {"id": "gpt", "providerID": "openai", "variant": "high"}}
        bundle = interim_flat_message_to_legacy_bundle(item, session=session, ordinal=0)
        self.assertNotIn("variant", bundle["info"])
        item["metadata"]["assistant"]["variant"] = "low"
        bundle = interim_flat_message_to_legacy_bundle(item, session=session, ordinal=0)
        self.assertEqual("low", bundle["info"]["variant"])

    def test_current_v2_compaction_preserves_only_its_own_variant(self):
        with source_with_current_service() as (source, server, _registration):
            server.messages["ses_current"].append({"id": "compact", "type": "compaction", "status": "completed",
                "reason": "manual", "time": {"created": 5000}, "summary": "summary", "recent": "recent",
                "model": {"id": "gpt-5.6", "providerID": "openai", "variant": "high"}})
            _, block = project(source.load_session_snapshot("ses_current"))
            row = next(row for row in block.rows if row.is_compaction)
            self.assertEqual("gpt-5.6 (High)", row.model_effort)
            server.messages["ses_current"][-1]["model"].pop("variant")
            _, block = project(source.load_session_snapshot("ses_current"))
            row = next(row for row in block.rows if row.is_compaction)
            self.assertEqual("gpt-5.6", row.model_effort)


if __name__ == "__main__":
    unittest.main()
