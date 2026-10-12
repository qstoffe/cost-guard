"""Confirmed skill loads, conservative failures and latest-prompt Watch activity."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from development.fixtures.session_snapshots import make_snapshot, message, part, prov
from src.config import merge_config, normalize_legacy_settings, read_jsonc, validate_configuration
from src.domain import EventKind, MessageRole, NormalizedEvent
from src.presentation import WatchRenderer
from src.presentation.watch_activity import FAILED_ROLE, SKILL_ROLE, skill_summary_segments, tool_summary_segments
from src.reports.models import PromptProjection, SessionPromptBlock
from src.sources.opencode_v2_normalization import normalize_message_bundle
from src.sources.opencode_v2_wire import current_union_message_to_legacy_bundle
from src.watch.models import SkillObservation, ToolObservation, WatchProjection
from src.watch.tools import observe_tools
from src.watch.tracker import WatchRowTracker

BROWSER = 'auto-agent-browser'
GITHUB = 'auto-github-api'
CHECKPOINT = 'shared-checkpoint-memory-contract'
SCHEMA = 'opencode-toolkit/agent-browser-wrapper/v1'
COMMAND = r'py -3 "C:\home\.config\opencode\skills\auto-agent-browser\scripts\browser_cli.py" run --service fixture'


def tool(pid, name, *, start=2190, status='completed', inputs=None, **state):
    return part(pid, 'a_next', 'root', 'tool', {
        'tool': name, 'state': {'status': status, 'input': inputs or {}, **state},
    }, start)


def skill(pid, skill_id, *, start=2190, **changes):
    return tool(pid, 'skill', start=start, inputs={'id': skill_id}, **changes)


def result(*, status='error', error_class='BROWSER_COMMAND', schema=SCHEMA):
    return json.dumps({'schema': schema, 'status': status, 'error': {'class': error_class}})


def snapshot(parts=(), *, running=True):
    base = make_snapshot(running=running)
    messages = tuple(replace(item, parts=tuple(parts)) if item.message_id == 'a_next' else item
                     for item in base.messages if item.message_id not in {'u_comp', 'a_comp'})
    return replace(base, messages=messages, parts=tuple(p for m in messages for p in m.parts),
                   events=tuple(event for event in base.events if event.event_id != 'u_comp'))


def observe(parts, *, running=True):
    return observe_tools(snapshot(parts, running=running), 'u_next', now_ms=60_000)


def text(segments):
    return ''.join(value for value, _role in segments)


def prompt(event_id='u_next', number=1, at_ms=2000, **changes):
    return PromptProjection(
        at_ms=at_ms, prompt_number=number, event_id=event_id, label=f'#{number}', preview='work',
        model_effort='model', ccost=Decimal(0), cost_estimated=False, unresolved_cost=False,
        calls=0, incoming_context_tokens=None, incoming_context_ccost=None,
        extra_ccost=None, token_mix_percent=None, **changes,
    )


def block(rows, session_id='root'):
    return SessionPromptBlock(session_id, 'Session', tuple(rows), Decimal(0), 0)


def render(rows, *, width=120, interactive=False):
    output = io.StringIO()
    colors = {SKILL_ROLE: {'foreground': 'Yellow'}, FAILED_ROLE: {'foreground': 'Red'}}
    WatchRenderer({'colors': colors}, stream=output, interactive=interactive, terminal_width=width).render(
        WatchProjection('Watch', 'V2', tuple(rows), now_ms=60_000))
    return output.getvalue()


class SkillLoadTests(unittest.TestCase):
    def test_one_and_multiple_confirmed_ids_and_most_recent_first(self):
        obs = observe([skill('a', BROWSER, start=2100), skill('b', GITHUB, start=2120)])
        self.assertEqual((SkillObservation(GITHUB), SkillObservation(BROWSER)), obs.skills)
        self.assertEqual(2, obs.tool_count)
        self.assertEqual((SkillObservation(BROWSER),), observe([skill('a', BROWSER)]).skills)

    def test_repeated_loads_update_order_without_inflating_distinct_count(self):
        obs = observe([skill('a', BROWSER, start=2100), skill('b', GITHUB, start=2120),
                       skill('c', BROWSER, start=2140)])
        self.assertEqual((SkillObservation(BROWSER), SkillObservation(GITHUB)), obs.skills)
        self.assertEqual(3, obs.tool_count)

    def test_order_uses_load_time_not_message_iteration_order(self):
        obs = observe([skill('new', GITHUB, start=2140), skill('old', BROWSER, start=2100)])
        self.assertEqual([GITHUB, BROWSER], [item.skill_id for item in obs.skills])

    def test_prose_inputs_and_unconfirmed_calls_do_not_prove_load(self):
        obs = observe([
            part('text', 'a_next', 'root', 'text', {'text': f'loaded {BROWSER}'}, 2100),
            tool('read', 'read', inputs={'id': BROWSER}),
            skill('pending', BROWSER, status='running'),
            skill('failed', GITHUB, status='error', error='not available'),
        ])
        self.assertEqual((), obs.skills)
        self.assertEqual(3, obs.tool_count)
        self.assertEqual(1, obs.failed_count)

    def test_legacy_name_and_current_top_level_input_are_canonical(self):
        legacy = tool('legacy', 'skill', inputs={'name': GITHUB})
        current = part('current', 'a_next', 'root', 'tool', {
            'name': 'skill', 'input': {'id': BROWSER}, 'state': {'status': 'completed'},
        }, 2200)
        self.assertEqual([BROWSER, GITHUB], [item.skill_id for item in observe([legacy, current]).skills])

    def test_control_characters_and_path_inputs_cannot_inject_skill_rows(self):
        for value in ('../skill', 'skill\nnext', '\x1b[31mevil', '', {}, '..'):
            with self.subTest(value=value):
                self.assertEqual((), observe([skill('bad', value)]).skills)

    def test_current_wire_normalization_preserves_skill_input(self):
        bundle = current_union_message_to_legacy_bundle({
            'id': 'a_next', 'type': 'assistant', 'parentID': 'u_next', 'time': {'created': 2100},
            'content': [{'type': 'tool', 'name': 'skill', 'input': {'id': BROWSER},
                         'time': {'ran': 2190}, 'state': {'status': 'completed'}}],
        }, session={'id': 'root'}, ordinal=0)
        bundle['info']['parentID'] = 'u_next'
        normalized, _ = normalize_message_bundle(bundle, lambda sid, pid: prov(sid, pid, 'v2'))
        base = snapshot()
        base = replace(base, messages=tuple(normalized if item.message_id == 'a_next' else item for item in base.messages))
        self.assertEqual((SkillObservation(BROWSER),), observe_tools(base, 'u_next').skills)


class FailureAttributionTests(unittest.TestCase):
    def test_malformed_native_status_is_neutral_not_a_watch_crash(self):
        obs = observe([tool('unknown', 'shell', status=[], inputs={'command': COMMAND}, output=result())])
        self.assertEqual(1, obs.tool_count)
        self.assertEqual(0, obs.failed_count)

    def test_task_child_skill_and_failures_follow_existing_canonical_prompt_scope(self):
        base = make_snapshot()
        child_parts = tuple(replace(p, session_id='child', message_id='ca') for p in (
            skill('load', BROWSER), tool('fail', 'shell', inputs={'command': COMMAND}, output=result())))
        base = replace(base, messages=tuple(replace(m, parts=child_parts) if m.message_id == 'ca' else m
                                           for m in base.messages))
        obs = observe_tools(base, 'u_sub', now_ms=60_000)
        self.assertEqual(3, obs.tool_count)
        self.assertEqual(1, obs.failed_count)
        self.assertEqual((SkillObservation(BROWSER, 1),), obs.skills)
        self.assertEqual((), observe_tools(base, 'u_next', now_ms=60_000).skills)

    def test_native_and_structured_failures_count_each_physical_call_once(self):
        failed = tool('failed', 'shell', status='error', inputs={'command': COMMAND},
                      output=result(), error='command failed')
        obs = observe([skill('load', BROWSER), failed, failed])
        self.assertEqual(2, obs.tool_count)
        self.assertEqual(1, obs.failed_count)
        self.assertEqual((SkillObservation(BROWSER, 1),), obs.skills)

    def test_call_id_copies_count_only_latest_physical_tool_state(self):
        running = tool('early', 'shell', status='running', inputs={'command': COMMAND})
        final = tool('late', 'shell', inputs={'command': COMMAND}, output=result())
        running = replace(running, data={**running.data, 'callID': 'same-call'})
        final = replace(final, data={**final.data, 'callID': 'same-call'}, updated_at_ms=2200)
        obs = observe([skill('load', BROWSER), running, final])
        self.assertEqual(2, obs.tool_count)
        self.assertEqual(1, obs.failed_count)
        self.assertEqual('', obs.running_tool)
        self.assertEqual((SkillObservation(BROWSER, 1),), obs.skills)

    def test_completed_shell_with_verified_toolkit_error_counts(self):
        calls = [skill('load', BROWSER),
                 tool('a', 'shell', inputs={'command': COMMAND}, output=result()),
                 tool('b', 'bash', inputs={'command': COMMAND.replace('\\', '/')},
                      output=result() + '\nExited with code 21')]
        obs = observe(calls)
        self.assertEqual(2, obs.failed_count)
        self.assertEqual((SkillObservation(BROWSER, 2),), obs.skills)

    def test_explicit_metadata_is_direct_evidence_not_recent_skill(self):
        obs = observe([skill('a', BROWSER), skill('b', GITHUB, start=2195),
                       tool('fail', 'read', status='error', error='not found', metadata={'skill_id': BROWSER})])
        self.assertEqual((SkillObservation(GITHUB), SkillObservation(BROWSER, 1)), obs.skills)
        self.assertEqual(1, obs.failed_count)

    def test_generic_reads_and_shells_stay_unattributed(self):
        obs = observe([skill('load', CHECKPOINT),
                       tool('read', 'read', status='error', error='missing', inputs={'path': 'skills/shared-checkpoint-memory-contract/scripts/lineage.py'}),
                       tool('shell', 'shell', status='error', error='command failed', inputs={'command': 'python unrelated.py'})])
        self.assertEqual(2, obs.failed_count)
        self.assertEqual((SkillObservation(CHECKPOINT),), obs.skills)

    def test_exact_execution_of_non_toolkit_skill_script_can_attribute_native_error(self):
        obs = observe([skill('load', 'custom-skill'), tool('fail', 'shell', status='error', error='command failed',
                       inputs={'command': 'python /home/skills/custom-skill/scripts/check.py'})])
        self.assertEqual((SkillObservation('custom-skill', 1),), obs.skills)

    def test_script_identity_without_confirmed_load_does_not_invent_loaded_skill(self):
        obs = observe([tool('fail', 'shell', inputs={'command': COMMAND}, output=result())])
        self.assertEqual(1, obs.failed_count)
        self.assertEqual((), obs.skills)

    def test_conflicting_skill_identities_fail_closed(self):
        obs = observe([skill('a', BROWSER), skill('b', GITHUB),
                       tool('fail', 'shell', inputs={'command': COMMAND}, output=result(), metadata={'skillID': GITHUB})])
        self.assertEqual(1, obs.failed_count)
        self.assertEqual([0, 0], [item.failed_count for item in obs.skills])

    def test_failure_total_includes_attributed_and_unattributed_errors(self):
        obs = observe([skill('a', BROWSER),
                       tool('browser', 'shell', inputs={'command': COMMAND}, output=result()),
                       tool('read', 'read', status='error', error='missing'),
                       tool('grep', 'grep', status='error', error='bad regex')])
        self.assertEqual(3, obs.failed_count)
        self.assertEqual((SkillObservation(BROWSER, 1),), obs.skills)

    def test_ordinary_shell_programs_do_not_pay_for_skill_command_parsing(self):
        with patch('src.watch.tool_contracts._command_tokens', side_effect=AssertionError('unnecessary program parse')):
            obs = observe([tool('shell', 'shell', inputs={'command': 'python -c "print(1)"'})])
        self.assertEqual(1, obs.tool_count)
        self.assertEqual((), obs.skills)

    def test_output_decoding_is_not_attempted_for_arbitrary_tools(self):
        with patch('src.watch.tool_contracts._result', side_effect=AssertionError('unnecessary output access')):
            obs = observe([tool('read', 'read', output=result()),
                           tool('shell', 'shell', inputs={'command': 'python unrelated.py'}, output=result())])
        self.assertEqual(0, obs.failed_count)

    def test_unknown_outputs_schemas_exit_codes_and_expected_nonzero_are_not_failures(self):
        outputs = ('error failed', result(status='ok'), result(schema='other/v1'),
                   '{"status":"error","error":{"class":"BROWSER_COMMAND"}}',
                   result() + '\nadditional output', '["error"]', '{invalid',
                   result(error_class=''), 'x' * 65_537)
        for output in outputs:
            with self.subTest(output=output[:80]):
                obs = observe([tool('a', 'shell', inputs={'command': COMMAND}, output=output, metadata={'exit': 21})])
                self.assertEqual(0, obs.failed_count)
        self.assertEqual(0, observe([tool('exit', 'shell', metadata={'exit': 1})]).failed_count)

    def test_mentions_compound_commands_and_interpreted_programs_are_not_execution_proof(self):
        commands = (f'echo {COMMAND}', f'Get-Content {COMMAND}', f'{COMMAND}; echo done',
                    f'python -c "print(\'{COMMAND}\')"', COMMAND.replace('\\', '/').replace('scripts/', 'scripts/../scripts/'),
                    COMMAND.replace('\\scripts\\', '\\scripts\\..\\scripts\\'), f'{COMMAND} | cat', COMMAND.replace('"', '', 1))
        for command in commands:
            with self.subTest(command=command):
                obs = observe([skill('load', BROWSER), tool('failed', 'shell', inputs={'command': command}, output=result())])
                self.assertEqual(0, obs.failed_count)

    def test_cancellations_and_interruptions_do_not_count_as_failures(self):
        calls = [skill('load', BROWSER),
                 tool('a', 'shell', status='error', inputs={'command': COMMAND}, error={'name': 'AbortedError'}, output=result()),
                 tool('b', 'shell', inputs={'command': COMMAND}, metadata={'interrupted': True}, output=result()),
                 tool('c', 'shell', inputs={'command': COMMAND}, output=result(error_class='CANCELLED')),
                 tool('d', 'shell', status='error', error='command failed', inputs={'command': COMMAND}, output=result(error_class='INTERRUPTED'))]
        obs = observe(calls)
        self.assertEqual(0, obs.failed_count)
        self.assertEqual((SkillObservation(BROWSER),), obs.skills)


class SkillWidthTests(unittest.TestCase):
    def observation(self):
        return ToolObservation(tool_count=54, failed_count=3,
                               skills=(SkillObservation(BROWSER, 1), SkillObservation(GITHUB),
                                       SkillObservation('auto-jira-api'), SkillObservation('auto-log-debugging', 2)))

    def test_large_skill_inventory_builds_only_the_selected_candidate(self):
        obs = ToolObservation(skills=tuple(SkillObservation(f'skill-{index}') for index in range(1000)))
        from src.presentation.watch_activity import _skill_candidate
        with patch('src.presentation.watch_activity._skill_candidate', wraps=_skill_candidate) as candidate:
            line = text(skill_summary_segments(obs, 80))
        self.assertLessEqual(len(line), 80)
        self.assertEqual(1, candidate.call_count)
        self.assertIn('+', line)

    def test_empty_skills_never_produce_row(self):
        self.assertEqual([], skill_summary_segments(ToolObservation(), 100))

    def test_exact_terminology_and_independent_colors(self):
        segments = skill_summary_segments(self.observation(), 300)
        self.assertEqual([' [1 tool call failure]', ' [2 tool call failures]'],
                         [value for value, role in segments if role == FAILED_ROLE])
        self.assertEqual([BROWSER, GITHUB, 'auto-jira-api', 'auto-log-debugging'],
                         [value for value, role in segments if role == SKILL_ROLE and value.startswith('auto-')])
        self.assertNotIn('[0', text(segments))

    def test_all_widths_fit_and_omitted_count_matches_whole_names(self):
        obs = self.observation()
        for width in range(0, 301):
            with self.subTest(width=width):
                line = text(skill_summary_segments(obs, width))
                self.assertLessEqual(len(line), width)
                shown = sum(skill.skill_id in line for skill in obs.skills)
                omitted = re.search(r'\+(\d+) more', line)
                if omitted:
                    self.assertEqual(len(obs.skills) - shown, int(omitted[1]))
                for skill in obs.skills:
                    if skill.skill_id in line:
                        self.assertNotIn(skill.skill_id + '...', line)
                if shown:
                    self.assertIn(BROWSER, line)

    def test_narrow_row_prioritizes_latest_complete_name_and_failure_indicator(self):
        expected = f'Skills (4): {BROWSER} [1 tool call failure] · +3 more'
        self.assertEqual(expected, text(skill_summary_segments(self.observation(), len(expected))))
        names_only = f'Skills (4): {BROWSER} · +3 more'
        self.assertEqual(names_only, text(skill_summary_segments(self.observation(), len(names_only))))
        self.assertEqual('Skills (4)', text(skill_summary_segments(self.observation(), 10)))

    def test_tool_total_and_nonzero_failure_survive_compact_widths(self):
        obs = self.observation()
        self.assertEqual('54 · 3 failed', text(tool_summary_segments(obs, 13)))
        self.assertEqual('54 · 3!', text(tool_summary_segments(obs, 7)))
        for width in range(0, 150):
            self.assertLessEqual(len(text(tool_summary_segments(obs, width))), width)


class SkillColorCompatibilityTests(unittest.TestCase):
    def test_complete_older_custom_palette_inherits_existing_yellow_role(self):
        defaults = read_jsonc(Path(__file__).resolve().parents[2] / 'config/default-config.jsonc')
        palette = dict(defaults['colorSchemes']['classic'])
        palette.pop('watchSkillActivity')
        original = {'colorScheme': 'custom', 'colorSchemes': {'custom': palette}}
        overrides = normalize_legacy_settings(original)
        self.assertEqual(palette['watchRunningWarning'], overrides['colorSchemes']['custom']['watchSkillActivity'])
        self.assertNotIn('watchSkillActivity', original['colorSchemes']['custom'])
        validate_configuration(merge_config(defaults, overrides), defaults, overrides)

    def test_explicit_skill_style_or_disable_remains_an_override(self):
        for value in (None, {'foreground': 'Yellow'}):
            palette = {'watchRunningWarning': {'foreground': 'Red'}, 'watchSkillActivity': value}
            normalized = normalize_legacy_settings({'colorSchemes': {'custom': palette}})
            self.assertEqual(value, normalized['colorSchemes']['custom']['watchSkillActivity'])


class PersistentActivityTests(unittest.TestCase):
    def setUp(self):
        self.tracker = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=20)
        self.parts = (skill('load', BROWSER, start=2100),
                      tool('fail', 'shell', inputs={'command': COMMAND}, output=result()))

    def project(self, rows, snap, now=60_000):
        return self.tracker.project({'root': block(rows)}, {'root': snap}, now_ms=now)

    def test_completion_retains_final_counts_and_skills_clears_active_todo_and_running(self):
        parts = self.parts + (tool('running', 'shell', status='running', start=2200),
                             tool('todo', 'todo', inputs={'todos': [{'content': 'unfinished', 'status': 'in_progress'}]}))
        live = self.project((prompt(in_progress=True),), snapshot(parts))
        self.assertTrue(live[0].tool.has_status_row)
        final = self.project((prompt(in_progress=False),), snapshot(parts, running=False), now=61_000)
        self.assertEqual(4, final[0].tool.tool_count)
        self.assertEqual(1, final[0].tool.failed_count)
        self.assertEqual((SkillObservation(BROWSER, 1),), final[0].tool.skills)
        self.assertFalse(final[0].tool.has_status_row)
        output = render(final)
        self.assertIn('4 tool calls', output)
        self.assertIn(f'Skills (1): {BROWSER} [1 tool call failure]', output)
        self.assertNotIn('running:', output)
        self.assertNotIn('TODO', output)

    def test_new_prompt_replaces_old_activity_even_before_it_has_tools(self):
        old = prompt(in_progress=False)
        snap = snapshot(self.parts, running=False)
        self.project((old,), snap)
        new = prompt('u_new', 2, 5000, in_progress=True)
        event = NormalizedEvent('u_new', 'root', EventKind.USER_PROMPT, 5000, prov('root', 'u_new'))
        new_snapshot = replace(snap, events=snap.events + (event,))
        rows = self.project((old, new), new_snapshot)
        self.assertIsNone(rows[0].tool)
        self.assertEqual(0, rows[1].tool.tool_count)
        self.assertEqual((), rows[1].tool.skills)
        self.assertNotIn('Skills (1)', render(rows))
        missing_projection = self.project((old,), new_snapshot)
        self.assertIsNone(missing_projection[0].tool)

    def test_compaction_keeps_activity_on_logical_prompt_not_checkpoint(self):
        compact = prompt('u_comp', 2, 3000, is_compaction=True)
        snap = snapshot(self.parts)
        event = NormalizedEvent('u_comp', 'root', EventKind.COMPACTION, 3000, prov('root', 'u_comp'))
        snap = replace(snap, events=snap.events + (event,))
        live = self.project((prompt(in_progress=True), compact), snap)
        self.assertIsNone(live[0].tool)
        self.assertEqual('u_next', live[1].prompt.event_id)
        retained = self.project((compact,), snap)
        self.assertEqual('u_next', retained[1].prompt.event_id)
        self.assertEqual(2, retained[1].tool.tool_count)
        self.assertFalse(retained[1].tool.has_status_row)

    def test_missing_post_compaction_parts_retain_last_counts_without_running_flags(self):
        snap = snapshot(self.parts)
        self.project((prompt(in_progress=True),), snap)
        empty = replace(snap, messages=(), parts=())
        retained = self.project((), empty)
        self.assertEqual(2, retained[0].tool.tool_count)
        self.assertEqual((SkillObservation(BROWSER, 1),), retained[0].tool.skills)
        self.assertFalse(retained[0].tool.has_status_row)

    def test_stable_completed_refresh_reuses_observation_but_new_snapshot_recomputes(self):
        snap = snapshot(self.parts, running=False)
        with patch('src.watch.tracker.observe_tools', wraps=observe_tools) as observer:
            for index in range(3):
                self.project((prompt(),), snap, now=60_000 + index)
            self.assertEqual(1, observer.call_count)
            self.project((prompt(),), replace(snap, source_revision='reconnected'))
            self.assertEqual(2, observer.call_count)

    def test_refresh_reconstruction_and_abort_do_not_duplicate_activity(self):
        snap = snapshot(self.parts, running=False)
        for aborted in (False, True):
            row_prompt = prompt(aborted=aborted)
            for index in range(3):
                rows = self.project((row_prompt,), snap, now=60_000 + index)
                self.assertEqual(1, len(rows))
                self.assertEqual(2, rows[0].tool.tool_count)
                self.assertEqual(1, render(rows).count('Skills (1)'))
                self.assertEqual(1, render(rows).count('2 tool calls'))
            rebuilt = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=20).project(
                {'root': block((row_prompt,))}, {'root': snap}, now_ms=60_010)
            self.assertEqual(rows[0].tool, rebuilt[0].tool)

    def test_simultaneous_sessions_have_independent_latest_activity(self):
        first = snapshot(self.parts, running=False)
        second_base = snapshot((skill('load', GITHUB),), running=False)
        second = replace(second_base, root=replace(second_base.root, session_id='other'),
                         messages=tuple(replace(m, session_id='other', parts=tuple(replace(p, session_id='other') for p in m.parts))
                                        for m in second_base.messages),
                         events=tuple(replace(e, session_id='other') for e in second_base.events))
        blocks = {'root': block((prompt(),)), 'other': block((prompt(),), 'other')}
        snapshots = {'root': first, 'other': second}
        rows = self.tracker.project(blocks, snapshots, now_ms=60_000)
        observations = {row.session_id: row.tool for row in rows}
        self.assertEqual((SkillObservation(BROWSER, 1),), observations['root'].skills)
        self.assertEqual((SkillObservation(GITHUB),), observations['other'].skills)
        new = prompt('u_new', 2, 5000, in_progress=True)
        event = NormalizedEvent('u_new', 'root', EventKind.USER_PROMPT, 5000, prov('root', 'u_new'))
        snapshots['root'] = replace(first, events=first.events + (event,))
        blocks['root'] = block((prompt(), new))
        rows = self.tracker.project(blocks, snapshots, now_ms=61_000)
        self.assertEqual(observations['other'], next(row.tool for row in rows if row.session_id == 'other'))
        self.assertIsNone(next(row.tool for row in rows if row.session_id == 'root' and row.prompt.event_id == 'u_next'))

    def test_skills_directly_follow_tool_row_and_colors_and_arrows_align(self):
        rows = self.project((prompt(),), snapshot(self.parts, running=False))
        raw = render(rows, interactive=True)
        clean = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', raw)
        lines = clean.splitlines()
        prompt_line = next(line for line in lines if '#1 work' in line)
        tool_index = next(index for index, line in enumerate(lines) if '2 tool calls' in line)
        self.assertIn('Skills (1)', lines[tool_index + 1])
        self.assertEqual(prompt_line.index('#'), lines[tool_index + 1].index('↳'))
        self.assertIn('\x1b[93m' + BROWSER + '\x1b[0m', raw)
        self.assertIn('\x1b[91m [1 tool call failure]\x1b[0m', raw)

    def test_real_tiny_terminal_is_not_clamped_to_forty_columns_for_activity(self):
        class TinyTerminal(io.StringIO):
            def isatty(self):
                return True

            def fileno(self):
                return 1

        rows = self.project((prompt(),), snapshot(self.parts, running=False))
        stream = TinyTerminal()
        renderer = WatchRenderer({'colors': {}}, stream=stream, interactive=False)
        with patch('src.presentation.terminal.os.get_terminal_size', return_value=os.terminal_size((25, 10))):
            renderer.render(WatchProjection('Watch', 'V2', rows))
        activities = [line for line in stream.getvalue().splitlines() if line.startswith('|     ->')]
        self.assertEqual(2, len(activities))
        self.assertTrue(all(len(line) <= 24 for line in activities))

    def test_rendered_activity_lines_respect_terminal_width_including_borders(self):
        rows = self.project((prompt(),), snapshot(self.parts, running=False))
        for width in range(1, 161):
            renderer = WatchRenderer({'colors': {}}, stream=io.StringIO(), interactive=False, terminal_width=width)
            _table, _styles, activities = renderer._table_rows(WatchProjection('Watch', 'V2', rows))
            for kind, marker, obs in activities.values():
                line = renderer._activity_line(kind, marker, obs, max(0, width - 4)) if width >= 4 else '|'
                self.assertLessEqual(len(line), width)
            output = render(rows, width=width)
            for line in output.splitlines():
                if 'tool calls' in line or 'Skills' in line:
                    self.assertLessEqual(len(line), width)


if __name__ == '__main__':
    unittest.main()
