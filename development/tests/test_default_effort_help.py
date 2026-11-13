"""Tooltip-only effort provenance, route isolation and compact round trips."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import json
import unittest

from development.tests.fixtures.session_snapshots import make_snapshot
from development.tests.fixtures.pricing_catalog import catalog
from src.analysis import analyze_snapshot
from src.analysis.ai_stats_responses import ResponseCall, podium
from src.analysis.effort_defaults import DEFAULTS, request_effort
from src.analysis.model_identity import encode_model, decode_model, dependencies
from src.application.ai_stats import response_tokens
from src.application.display import with_display
from src.application.effort_help import effort_help
from src.application.projection import prompt
from src.domain import ModelRef
from src.domain.effort import EffortEvidence, bounded_evidence
from src.reports.matched_runs import project_run, encode_run, decode_run
from src.reports.prompt_rows import PromptRowProjector
from src.sources.opencode_v2_effort import observation
from src.sources.opencode_v2_model_identity import DesktopModelCatalog


def projected_snapshot(selected="default", actual=None, model=None):
    saved = make_snapshot()
    saved = replace(saved,
        events=tuple(replace(e, metadata={**e.metadata, "variant": selected})
                     if e.event_id == "u_next" else e for e in saved.events),
        messages=tuple(replace(m, variant=actual, model=model or m.model)
                       if m.message_id == "a_next" else m for m in saved.messages),
        invocations=tuple(replace(i, variant=actual, model=model or i.model)
                          if i.message_id == "a_next" else i for i in saved.invocations))
    bundle = analyze_snapshot(saved, tracked_provider=None)
    record = next(p for p in bundle.prompts if p.prompt_id == "u_next")
    row = PromptRowProjector(snapshot=saved, bundle=bundle, catalog=catalog(), config={}).prompt(record)
    return saved, bundle, row, with_display(prompt(row, details=True)).to_json()


class DefaultEffortHelpTests(unittest.TestCase):
    def test_exact_vendor_examples_and_unknown_do_not_change_selected_variants(self):
        base = analyze_snapshot(make_snapshot(), tracked_provider=None).trace_entries[0]
        for provider, model, expected in (
            ("anthropic", "claude-opus-5-5", "medium"),
            ("anthropic", "claude-haiku-5-5", "medium"),
            ("openai", "gpt-6.1-sol", "medium"),
            ("google", "gemini-4-carbon", "medium"),
            ("anthropic", "claude-sonnet-5-5", "high"),
            ("xai", "grok-4.7", "high"),
            ("moonshotai", "kimi-k3", "max"),
            ("openai", "gpt-5.4-nano", "none"),
            ("unknown", "gpt-6.1-sol", "unknown"),
        ):
            with self.subTest(provider=provider, model=model):
                entry = replace(base, model=ModelRef(provider, model), variant="default", selected_effort=None)
                value = request_effort(entry)
                self.assertEqual(f"default ({expected})", effort_help(value))
                self.assertEqual("default", entry.variant)
                self.assertNotIn("*", effort_help(value))
                self.assertTrue(effort_help(value, value_cell=True).startswith(f"default ({expected})*\n* "))

    def test_all_31_reviewed_entries_include_conditional_and_unknown_not_fake_coverage(self):
        self.assertEqual(31, sum(map(len, DEFAULTS.values())))
        self.assertEqual(6, len(DEFAULTS))
        self.assertEqual("", DEFAULTS["anthropic"]["claude-haiku-4-5"])
        self.assertEqual("", DEFAULTS["anthropic"]["claude-sonnet-4"])
        self.assertEqual("", DEFAULTS["microsoft"]["mai-code-1.1-flash"])
        self.assertEqual("", DEFAULTS["openai"]["gpt-6-astra"])
        self.assertEqual("", DEFAULTS["anthropic"]["claude-opus-4-8-fast"])
        attachment = next(Path(__file__).parents[1].glob(
            "backlog/*/*-000694-*/MODEL-DEFAULT-EFFORT-RESEARCH.json"))
        research = json.loads(attachment.read_text(encoding="utf-8"))
        self.assertEqual(31, len(research["rows"]))
        self.assertEqual(6, len({row["publisher"] for row in research["rows"]}))
        for row in research["rows"]:
            for source in row["evidence"]:
                self.assertTrue(research["sources"][source].startswith("https://"))
        expected = {row["model"] for row in research["rows"] if row["confidence"] == "unresolved"}
        self.assertEqual({"Claude Haiku 4.5", "Claude Sonnet 4", "MAI-Code-1.1-Flash"}, expected)

    def test_config_alias_and_package_precedence_and_codec_are_source_qualified(self):
        base = analyze_snapshot(make_snapshot(), tracked_provider=None).trace_entries[0]
        observed = observation("/same-project", "alias",
            {"settings": {"reasoningEffort": "high"}},
            {"modelID": "gpt-6.1-sol", "package": "@opencode/ai/providers/openai/responses",
             "settings": {"reasoningEffort": "low"}})
        model = ModelRef("openai", "alias", effort_default=observed)
        self.assertEqual(model.effort_default, decode_model(encode_model(model)).effort_default)
        entry = replace(base, model=model, variant="default", selected_effort=None)
        evidence = request_effort(entry)
        self.assertEqual("default (low)", effort_help(evidence))
        self.assertIn("current OpenCode", effort_help(evidence, value_cell=True))
        self.assertIn("historical settings may differ", effort_help(evidence, value_cell=True))
        exact = replace(entry, selected_effort="default", variant="high")
        self.assertEqual("default (high)", effort_help(request_effort(exact)))
        self.assertIn("Observed", effort_help(request_effort(exact), value_cell=True))
        explicit = replace(exact, selected_effort="medium")
        self.assertEqual("Medium", effort_help(request_effort(explicit), value_cell=True, explicit="Medium"))
        native = observation("/same-project", "gpt-5.4-nano", {},
            {"modelID": "gpt-5.4-nano", "package": "@opencode/ai/providers/openai/responses"})
        self.assertEqual(("medium", "current-package"), (native.level, native.source))
        proxy = replace(model, effort_default=replace(observed, level="", package="unknown-adapter"))
        self.assertEqual("default (unknown)", effort_help(request_effort(replace(entry, model=proxy))))

    def test_each_supported_option_spelling_and_conflicting_options(self):
        for package, settings in (
            ("openai", {"reasoningEffort": "low"}), ("openai", {"reasoning": {"effort": "low"}}),
            ("anthropic", {"effort": "low"}), ("google", {"thinkingLevel": "LOW"}),
            ("google", {"thinkingConfig": {"thinkingLevel": "LOW"}}),
        ):
            self.assertEqual("low", observation("/p", "m", {},
                {"package": "@opencode/ai/providers/" + package, "settings": settings}).level)
        self.assertEqual("unknown", observation("/p", "m", {},
            {"package": "@opencode/ai/providers/openai",
             "settings": {"reasoningEffort": "low", "reasoning": {"effort": "high"}}}).level)
        self.assertEqual("unknown", observation("/p", "m", {},
            {"package": "custom-adapter", "settings": {"effort": "low"}}).level)
        self.assertEqual("unknown", observation("/p", "m", {},
            {"package": "@opencode/ai/providers/anthropic", "settings": {"reasoningEffort": "low"}}).level)

    def test_equal_accounting_models_keep_both_location_qualified_dependencies(self):
        base = analyze_snapshot(make_snapshot(), tracked_provider=None).trace_entries[0]
        first = ModelRef("openai", "alias", effort_default=observation("/one", "alias", {},
            {"package": "@opencode/ai/providers/openai", "settings": {"reasoningEffort": "low"}}))
        second = replace(first, effort_default=replace(first.effort_default, scope="/two", signature="different"))
        self.assertEqual(first, second, "effort evidence must not change billing/group identity")
        models = dependencies((replace(base, model=first), replace(base, model=second)))
        self.assertEqual(["/one", "/two"], [value["effort_default"]["scope"] for value in models])

    def test_match_cache_real_json_roundtrip_and_corrupt_effort_groups(self):
        from development.tests.fixtures.claude_alias import snapshot
        saved = snapshot(0, "claude-sonnet-5-5", "anthropic")
        bundle = analyze_snapshot(saved, tracked_provider=None)
        original = project_run(saved, bundle, catalog(), {})
        self.assertIsNotNone(original)
        payload = json.loads(json.dumps(encode_run(original)))
        self.assertEqual(original, decode_run(payload))
        for bad in ([], [["wrong", "model", "default", []]],
                    [[*payload["effort_evidence"][0][:3], [{"selected": "default"}]]]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                decode_run({**payload, "effort_evidence": bad})

    def test_bounded_distinct_evidence_reports_overflow_without_inventing_default(self):
        values = bounded_evidence(EffortEvidence(str(index)) for index in range(1000))
        self.assertEqual(24, len(values))
        self.assertEqual("omitted", values[-1].source)
        self.assertNotIn("default", effort_help(values[-1]))

    def test_same_prompt_selection_never_resolves_another_provider_or_a_summary(self):
        saved, _, _, _ = projected_snapshot("default", "high")
        changed = replace(saved, invocations=tuple(replace(item,
            model=replace(item.model, provider="other-provider")) for item in saved.invocations))
        entries = analyze_snapshot(changed, tracked_provider=None).trace_entries
        entry = next(item for item in entries if item.message_id == "a_next")
        self.assertIsNone(entry.selected_effort)
        self.assertEqual("high", effort_help(request_effort(entry)))

    def test_current_catalog_reuses_two_reads_and_rejects_location_and_config_turnover(self):
        class Client:
            def __init__(self):
                self.reads, self.level, self.directory = 0, "low", "/p"
            def json(self, route, **kwargs):
                self.reads += 1
                return {"location": {"directory": self.directory}, "data":
                    [{"id": "openai", "settings": {"reasoningEffort": "high"}}] if route == "/api/provider" else
                    [{"providerID": "openai", "id": "alias", "modelID": "gpt-6.1-sol",
                      "package": "@opencode/ai/providers/openai/responses",
                      "settings": {"reasoningEffort": self.level}}]}
        client, clock = Client(), [0]
        resolver = DesktopModelCatalog(lambda: client, clock=lambda: clock[0])
        model = resolver.resolve(ModelRef("openai", "alias"), "/p")
        for _ in range(30):
            self.assertTrue(resolver.current((model,)))
        self.assertEqual(2, client.reads)
        client.level, clock[0] = "high", 31
        self.assertFalse(resolver.current((model,)))
        client.directory = "/wrong"
        other = resolver.resolve(ModelRef("openai", "alias"), "/relocated")
        self.assertEqual("", other.effort_default.level)
        self.assertEqual("default (unknown)", effort_help(request_effort(replace(
            analyze_snapshot(make_snapshot(), tracked_provider=None).trace_entries[0],
             model=other, variant="default"))))

    def test_malformed_catalog_observations_are_negative_and_cannot_inflate_evidence(self):
        class Client:
            def json(self, route, **kwargs):
                return {"location": {"directory": "/p"}, "data":
                    [{"id": []}] if route == "/api/provider" else
                    [{"providerID": "openai", "id": "m", "modelID": "x" * 10000, "package": "custom"}]}
        resolver = DesktopModelCatalog(lambda: Client())
        model = resolver.resolve(ModelRef("openai", "m"), "/p")
        self.assertEqual(("m", ""), (model.effort_default.model_id, model.effort_default.package))
        self.assertTrue(resolver.current((model,)))

    def test_request_bound_default_keeps_visible_values_costs_and_ordinary_help_terse(self):
        _, bundle, row, wire = projected_snapshot(actual="medium")
        help_values = wire["display"]
        self.assertEqual("Medium", row.watch_effort)
        self.assertEqual("medium", next(e for e in bundle.trace_entries if e.message_id == "a_next").variant)
        for name in ("model_detail_help", "cost_detail_help", "calls_help", "main_model_help", "effort_tooltip"):
            self.assertIn("default (medium)", help_values[name])
            self.assertNotIn("default (medium)*", help_values[name])
            self.assertNotIn("Defaults may change", help_values[name])
        self.assertIn("default (medium)*", help_values["effort_help"])
        self.assertIn("Observed in the recorded request", help_values["effort_help"])
        self.assertEqual(row.ccost, sum((part.known_ccost for part in row.cost_parts), Decimal(0)))
        self.assertEqual(row.calls, sum(part.calls for part in row.cost_parts))
        _, _, explicit, explicit_wire = projected_snapshot("high", "high")
        self.assertEqual("High", explicit.watch_effort)
        self.assertEqual("High", explicit_wire["display"]["effort_help"])
        self.assertNotIn("default (", explicit_wire["display"]["model_detail_help"])

    def test_podium_keeps_label_and_sample_math_but_adds_default_to_help(self):
        _, bundle, _, _ = projected_snapshot()
        entry = replace(bundle.trace_entries[0], model=ModelRef("anthropic", "claude-opus-5-5"),
                        variant="default", selected_effort=None)
        rows = podium((SimpleNamespace(responses=(ResponseCall(entry, 1000),)),), (entry,), None, entry.completed_at_ms)
        tokens = response_tokens(rows[0])
        self.assertTrue(tokens["label"].endswith(" · default"))
        self.assertIn("default (medium)", tokens["model_help"])
        self.assertNotIn("*", tokens["model_help"])
        self.assertEqual(entry.tokens.output + entry.tokens.reasoning, rows[0].tokens_per_second)

    def test_unattributable_summary_has_no_default_and_explicit_summary_is_unchanged(self):
        base = analyze_snapshot(make_snapshot(), tracked_provider=None).trace_entries[0]
        summary = replace(base, summary=True, variant=None, selected_effort=None)
        self.assertEqual("N/A", effort_help(request_effort(summary)))
        self.assertEqual("High", effort_help(request_effort(replace(summary, variant="high")), explicit="High"))

    def test_footnote_source_wording_does_not_call_documentation_or_config_observed(self):
        for source, expected in (("documentation", "Likely"), ("current-configuration", "Inferred"),
                                 ("request", "Observed"), ("unknown", "No supported")):
            value = EffortEvidence("default", "unknown" if source == "unknown" else "high", source)
            self.assertEqual("default (" + value.effective + ")", effort_help(value))
            self.assertIn(expected, effort_help(value, value_cell=True))

    def test_live_probe_oracle_matches_physical_request_and_rejects_note_leakage(self):
        from development.tests.integration.effort_live_observations import check_row
        saved, _, row, wire = projected_snapshot(actual="medium")
        wire["display"]["model_detail_help"] += "\nLinked subagents*"
        observed = dict(prompt=wire, model=row.watch_model, effort=row.watch_effort)

        counts = check_row(saved.root.session_id, row, observed, saved)

        self.assertGreater(counts["default_requests"], 0)
        self.assertGreater(counts["source_request"], 0)
        wire["display"]["model_detail_help"] += "\ndefault (medium)*"
        with self.assertRaisesRegex(AssertionError, "default marker leaked"):
            check_row(saved.root.session_id, row, observed, saved)

    def test_live_probe_current_v2_without_user_model_keeps_assistant_default_and_explicit(self):
        from development.tests.integration.effort_live_observations import check_row
        for variant, expected in ((None, "default_requests"), ("high", "explicit_requests")):
            saved, _, row, wire = projected_snapshot(actual=variant,
                model=ModelRef("anthropic", "claude-sonnet-5-5"))
            saved = replace(saved, events=tuple(replace(event, metadata={}) for event in saved.events))
            observed = dict(prompt=wire, model=row.watch_model, effort=row.watch_effort)

            counts = check_row(saved.root.session_id, row, observed, saved)

            self.assertGreater(counts[expected], 0)
            self.assertGreater(counts["absent_event_metadata"], 0)
            if variant is not None:
                self.assertEqual(0, counts["default_requests"])


if __name__ == "__main__":
    unittest.main()
