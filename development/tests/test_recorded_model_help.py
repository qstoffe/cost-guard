"""Raw request provenance survives independent presentation and compact caches."""
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
import unittest

from development.tests.fixtures.claude_alias import DesktopSource, snapshot, catalog
from development.tests.fixtures.session_snapshots import make_snapshot, one_request
from development.tests.fixtures.quick_aborts import quick_aborts
from src.analysis import analyze_snapshot
from src.analysis.ai_stats_responses import ResponseCall, response_rows
from src.application.ai_stats import response_tokens
from src.application.display import with_display
from src.application.model_help import session_model_tokens
from src.application.projection import prompt
from src.domain import ModelRef, TokenUsage
from src.reports.matched_runs import decode_run, encode_run, project_run
from src.reports.prompt_rows import PromptRowProjector
from src.sources.opencode_v2_normalization import normalize_invocations


class RecordedModelHelpTests(unittest.TestCase):
    def test_two_quick_aborts_keep_prompt_bound_selection_and_honest_unknowns(self):
        for generation in ("v1", "v2"):
            for second_model in (False, True):
                for assistant_model in (False, True):
                    with self.subTest(generation=generation, second=second_model, assistant=assistant_model):
                        saved = quick_aborts(generation=generation, second_model=second_model, assistant_model=assistant_model)
                        bundle = analyze_snapshot(saved, tracked_provider=None, now_ms=5000)
                        projector = PromptRowProjector(snapshot=saved, bundle=bundle, catalog=catalog(), config={})

                        rows = tuple(projector.prompt(record) for record in bundle.prompts)
                        wires = tuple(with_display(prompt(row, details=True)).to_json() for row in rows)

                        self.assertEqual(2, len(rows))
                        self.assertEqual(("Claude Sonnet 5.5", "Low"), (rows[0].watch_model, rows[0].watch_effort))
                        self.assertEqual(("Claude Sonnet 5.5", "Low") if second_model else ("N/A", "N/A"),
                            (rows[1].watch_model, rows[1].watch_effort))
                        for index, row in enumerate(rows):
                            self.assertEqual((0, (), Decimal(0), False),
                                (row.calls, row.cost_parts, row.ccost, row.has_model_details))
                            self.assertIsNone(row.incoming_context_tokens)
                            self.assertEqual(100, row.duration_ms)
                            self.assertTrue(row.aborted)
                            self.assertEqual("No model usage recorded", wires[index]["display"]["cost_detail_help"])
                            self.assertEqual(not index or second_model,
                                "Selected model" in wires[index]["display"]["model_detail_help"])
                            self.assertEqual(not index or second_model,
                                "Selected model" in wires[index]["model_display_help"])
                            self.assertNotIn("contribution proof", wires[index]["model_display_help"])
                            self.assertNotIn("Recorded selection:", wires[index]["model_display_help"])

    def test_alias_and_pinned_requests_with_same_effective_price_keep_attributable_groups(self):
        source = DesktopSource((snapshot(),))
        original = source.load_session_snapshot('root-0000')
        request = original.invocations[0]
        pinned = replace(request, invocation_id='pinned', message_id='pinned',
            model=ModelRef('claude-agent', 'claude-sonnet-5-5'))
        mixed = replace(original, invocations=(request, pinned))
        bundle = analyze_snapshot(mixed, tracked_provider=None)
        row = PromptRowProjector(snapshot=mixed, bundle=bundle, catalog=catalog(), config={}).prompt(bundle.prompts[0])

        wire = with_display(prompt(row, details=True)).to_json()

        self.assertEqual([('sonnet',), ('claude-sonnet-5-5',)], [p.selected_models for p in row.cost_parts])
        self.assertEqual(row.ccost, sum((p.known_ccost for p in row.cost_parts), Decimal(0)))
        self.assertEqual(2, wire['cost_detail']['group_count'])
        self.assertIn('claude-agent/sonnet', wire['display']['model_detail_help'])
        self.assertIn('claude-agent/claude-sonnet-5-5', wire['display']['model_detail_help'])
        self.assertEqual(1, wire['display']['model_detail_help'].count('Catalog modelID:'))

    def test_first_prompt_codec_retains_exact_per_effort_raw_models_not_root_wide_dependencies(self):
        source = DesktopSource((snapshot(),))
        original = source.load_session_snapshot('root-0000')
        request = original.invocations[0]
        second = replace(request, invocation_id='copilot', message_id='copilot', variant='high',
            model=ModelRef('github-copilot', 'claude-sonnet-5-5'))
        mixed = replace(original, invocations=(request, second))
        bundle = analyze_snapshot(mixed, tracked_provider=None)

        value = project_run(mixed, bundle, catalog(), {})
        restored = decode_run(encode_run(value))

        self.assertEqual(value, restored)
        recorded = {(provider, effort): models for provider, _model, effort, models in restored.recorded_models}
        self.assertEqual(2, len(recorded))
        self.assertEqual(('claude-sonnet-5-5',), recorded['github-copilot', 'high'])
        self.assertIn(('sonnet',), recorded.values())
        old = encode_run(value)
        old.pop('recorded_models')
        with self.assertRaisesRegex(ValueError, 'invalid_match_fields'):
            decode_run(old)

    def test_stats_keeps_sampled_alias_internally_but_uses_friendly_effort_help(self):
        source = DesktopSource((snapshot(),))
        saved = source.load_session_snapshot('root-0000')
        bundle = analyze_snapshot(saved, tracked_provider=None)
        entry = bundle.trace_entries[0]
        roots = (SimpleNamespace(responses=(ResponseCall(entry, 1000),)),)

        rows = response_rows(roots, (entry,), None, entry.completed_at_ms)
        wire = response_tokens(rows[0])

        self.assertEqual(Decimal(50), rows[0].tokens_per_second)
        self.assertEqual(('sonnet',), rows[0].recorded_models)
        self.assertEqual('claude-agent/Claude Sonnet 5.5\n\nBy Effort:\n• Default — 50 tok/s', wire['model_help'])
        self.assertNotIn('Catalog modelID', wire['model_help'])

    def test_compaction_help_uses_its_own_recorded_model_not_the_main_prompt(self):
        saved = make_snapshot()
        invocations = tuple(replace(i, model=ModelRef('openrouter', 'vendor/future-release'))
            if i.summary else i for i in saved.invocations)
        saved = replace(saved, invocations=invocations)
        bundle = analyze_snapshot(saved, tracked_provider=None)

        row = PromptRowProjector(snapshot=saved, bundle=bundle, catalog=catalog(), config={}).compaction(bundle.compactions[0], 3)
        wire = with_display(prompt(row, details=True)).to_json()

        self.assertIn('openrouter/vendor/future-release', wire['display']['model_detail_help'])
        self.assertNotIn('github-copilot/gpt-test', wire['display']['model_detail_help'])
        self.assertEqual(row.calls, sum(p.calls for p in row.cost_parts))

    def test_failed_saved_selection_without_usage_is_not_a_contributor_or_invented_zero_request(self):
        saved = one_request(running=False)
        messages = tuple(replace(m, model=ModelRef('claude-agent', 'claude-haiku-4-5-20251001'),
            tokens=None, error_name='provider.unknown') if m.role.value == 'assistant' else m for m in saved.messages)
        unrelated = (replace(messages[-1], message_id='other-prompt', parent_message_id='unrelated',
                         model=ModelRef('other-provider', 'wrong-prompt')),
                     replace(messages[-1], message_id='other-session', session_id='child',
                         model=ModelRef('other-provider', 'wrong-session')))
        saved = replace(saved, messages=messages + unrelated,
            invocations=tuple(i for m in messages for i in normalize_invocations(m, lambda sid, eid=None: m.provenance)))
        bundle = analyze_snapshot(saved, tracked_provider=None)

        row = PromptRowProjector(snapshot=saved, bundle=bundle, catalog=catalog(), config={}).prompt(bundle.prompts[0])
        wire = with_display(prompt(row, details=True)).to_json()

        self.assertEqual((0, (), Decimal(0)), (row.calls, row.cost_parts, row.ccost))
        self.assertIn('Recorded selection: claude-agent/claude-haiku-4-5-20251001', wire['display']['model_detail_help'])
        self.assertEqual('No model usage recorded', wire['display']['cost_detail_help'])
        self.assertNotIn('Recorded selection:', wire['display']['cost_detail_help'])
        self.assertNotIn('github-copilot', wire['display']['model_detail_help'])
        self.assertNotIn('other-provider', wire['display']['model_detail_help'])
        zero = replace(messages[-1], tokens=TokenUsage())
        zero_saved = replace(saved, messages=(messages[0], zero),
            invocations=normalize_invocations(zero, lambda sid, eid=None: zero.provenance))
        zero_bundle = analyze_snapshot(zero_saved, tracked_provider=None)
        zero_row = PromptRowProjector(snapshot=zero_saved, bundle=zero_bundle, catalog=catalog(), config={}).prompt(zero_bundle.prompts[0])
        zero_wire = with_display(prompt(zero_row, details=True)).to_json()
        self.assertEqual((1, 1, ()), (zero_row.calls, len(zero_row.cost_parts), zero_row.recorded_selections))
        self.assertNotIn('Usage unavailable', zero_wire['display']['model_detail_help'])

    def test_session_help_stably_lists_raw_ids_and_qualifies_incomplete_coverage(self):
        values = dict(contributor_models=('claude-agent/sonnet', 'github-copilot/claude-sonnet-5-5'),
            contributor_models_complete=False)

        help_text = session_model_tokens(values)['model_help']

        self.assertTrue(help_text.startswith('claude-agent/sonnet\ngithub-copilot/claude-sonnet-5-5'))
        self.assertIn('Observed so far', help_text)
        self.assertNotIn('Observed so far', session_model_tokens(dict(values, contributor_models_complete=True))['model_help'])


if __name__ == '__main__':
    unittest.main()
