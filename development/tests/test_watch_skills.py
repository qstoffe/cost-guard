"""Confirmed skill loads, conservative failures and latest-prompt Watch activity."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
import json
import os
import re
import unittest
from unittest.mock import patch

from development.fixtures.session_snapshots import make_snapshot, part, prov
from src.domain import EventKind, NormalizedEvent
from src.presentation import WatchRenderer
from src.presentation.watch_activity import BASE_ROLE, FAILED_ROLE, skill_summary_segments, tool_summary_segments
from src.reports.models import PromptProjection, SessionPromptBlock
from src.sources.opencode_v2_normalization import normalize_message_bundle
from src.sources.opencode_v2_wire import current_union_message_to_legacy_bundle
from src.watch.skill_registry import active_skill_origins
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


def skill(pid, skill_id, *, start=2190, origin='custom', **changes):
    call = tool(pid, 'skill', start=start, inputs={'id': skill_id}, **changes)
    return replace(call, data={**call.data, '_test_skill_origin': origin})


def result(*, status='error', error_class='BROWSER_COMMAND', schema=SCHEMA):
    return json.dumps({'schema': schema, 'status': status, 'error': {'class': error_class}})


def snapshot(parts=(), *, running=True):
    base = make_snapshot(running=running)
    messages = tuple(replace(item, parts=tuple(parts)) if item.message_id == 'a_next' else item
                     for item in base.messages if item.message_id not in {'u_comp', 'a_comp'})
    return replace(base, messages=messages, parts=tuple(p for m in messages for p in m.parts),
                   events=tuple(event for event in base.events if event.event_id != 'u_comp'))


def _test_origins(parts):
    origins = {}
    for item in parts:
        origin = item.data.get('_test_skill_origin')
        state = item.data.get('state')
        inputs = state.get('input') if isinstance(state, dict) else None
        if not isinstance(inputs, dict):
            inputs = item.data.get('input')
        skill_id = inputs.get('id', inputs.get('name')) if isinstance(inputs, dict) else None
        if isinstance(skill_id, str) and origin in {'builtin', 'custom'}:
            origins.setdefault(item.session_id, {})[skill_id] = origin
    return origins


def _snapshot_origins(value):
    return _test_origins(part for item in value.messages for part in item.parts)


def observe_snapshot(value, event_id='u_next', *, now_ms=60_000):
    return observe_tools(value, event_id, now_ms=now_ms,
                         skill_origins_by_session=_snapshot_origins(value))


def observe(parts, *, running=True):
    return observe_snapshot(snapshot(parts, running=running))


def text(segments):
    return ''.join(value for value, _role in segments)


def prompt(event_id='u_next', number=1, at_ms=2000, **changes):
    values = {
        'at_ms': at_ms, 'prompt_number': number, 'event_id': event_id, 'label': f'#{number}',
        'preview': 'work', 'model_effort': 'model', 'ccost': Decimal(0),
        'cost_estimated': False, 'unresolved_cost': False, 'calls': 0,
        'incoming_context_tokens': None, 'incoming_context_ccost': None,
        'extra_ccost': None, 'token_mix_percent': None,
    }
    values.update(changes)
    return PromptProjection(**values)


def block(rows, session_id='root'):
    return SessionPromptBlock(session_id, 'Session', tuple(rows), Decimal(0), 0)


def render(rows, *, width=120, interactive=False):
    output = io.StringIO()
    colors = {BASE_ROLE: {'foreground': 'Green'}, 'watchSkillActivity': {'foreground': 'Yellow'},
              FAILED_ROLE: {'foreground': 'Red'}}
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

    def test_builtin_custom_and_unknown_calls_keep_physical_counts_and_verified_loads(self):
        obs = observe([
            skill('builtin-open', 'opencode', origin='builtin'),
            skill('builtin-report', 'report', origin='builtin'),
            skill('custom-first', BROWSER, start=2100),
            skill('custom-repeat', BROWSER, start=2200),
            skill('unknown', 'unknown-skill', origin=None),
        ])
        self.assertEqual(5, obs.tool_count)
        self.assertEqual((('builtin skill', 2), ('custom skill', 2), ('skill', 1)), obs.tool_counts)
        self.assertEqual(obs.tool_count, sum(count for _name, count in obs.tool_counts))
        self.assertEqual((SkillObservation(BROWSER),), obs.skills)

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
        legacy_call = tool('legacy', 'skill', inputs={'name': GITHUB})
        legacy = replace(legacy_call, data={**legacy_call.data, '_test_skill_origin': 'custom'})
        current_part = part('current', 'a_next', 'root', 'tool', {
            'name': 'skill', 'input': {'id': BROWSER}, 'state': {'status': 'completed'},
        }, 2200)
        current = replace(current_part, data={**current_part.data, '_test_skill_origin': 'custom'})
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
        normalized, _ = normalize_message_bundle(
            bundle, lambda sid, pid: prov(sid, pid, 'v2')
        )
        base = snapshot()
        base = replace(base, messages=tuple(normalized if item.message_id == 'a_next' else item for item in base.messages))
        self.assertEqual((SkillObservation(BROWSER),), observe_tools(
            base, 'u_next', skill_origins_by_session={'root': {BROWSER: 'custom'}}
        ).skills)


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
        obs = observe_snapshot(base, 'u_sub', now_ms=60_000)
        self.assertEqual(3, obs.tool_count)
        self.assertEqual(1, obs.failed_count)
        self.assertEqual((SkillObservation(BROWSER, 1),), obs.skills)
        self.assertEqual((), observe_snapshot(base, 'u_next', now_ms=60_000).skills)

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
                         [value for value, role in segments if role == BASE_ROLE and value.startswith('auto-')])
        self.assertTrue(all(role == BASE_ROLE for value, role in segments if role != FAILED_ROLE))
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


class WatchSkillRegistryTests(unittest.TestCase):
    def test_registry_is_queried_once_per_session_only_for_active_skill_work(self):
        class RegistrySource:
            def __init__(self):
                self.sessions = []

            def skill_origins_for_session(self, session_id):
                self.sessions.append(session_id)
                return {BROWSER: 'custom'}

        source = RegistrySource()
        snap = snapshot((skill('first', BROWSER), skill('repeat', BROWSER, start=2200)))
        origins = active_skill_origins(source, snap, block((prompt(in_progress=True),)))
        self.assertEqual({'root': {BROWSER: 'custom'}}, origins)
        self.assertEqual(['root'], source.sessions)
        self.assertEqual({}, active_skill_origins(source, snap, block((prompt(),))))
        self.assertEqual(['root'], source.sessions)


class ActiveActivityLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tracker = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=20)
        self.parts = (skill('load', BROWSER, start=2100),
                      tool('fail', 'shell', inputs={'command': COMMAND}, output=result()))

    def project(self, rows, snap, now=60_000):
        return self.tracker.project(
            {'root': block(rows)}, {'root': snap}, now_ms=now,
            skill_origins_by_root={'root': _test_origins(snap.parts)},
        )

    def test_terminal_updates_remove_every_activity_row_and_keep_prompt_metrics(self):
        parts = self.parts + (tool('running', 'shell', status='running', start=2200),
                             tool('todo', 'todo', inputs={'todos': [{'content': 'unfinished', 'status': 'in_progress'}]}))
        terminal_prompts = (
            prompt(in_progress=False, calls=9, ccost=Decimal('2.5'), duration_ms=12_000,
                   incoming_context_tokens=128, incoming_context_ccost=Decimal('0.5')),
            prompt(in_progress=False, aborted=True, abort_reason='user', calls=9,
                   ccost=Decimal('2.5'), duration_ms=12_000, incoming_context_tokens=128,
                   incoming_context_ccost=Decimal('0.5')),
            prompt(in_progress=False, watch_error=True, calls=9, ccost=Decimal('2.5'), duration_ms=12_000,
                   incoming_context_tokens=128, incoming_context_ccost=Decimal('0.5')),
        )
        for terminal in terminal_prompts:
            with self.subTest(aborted=terminal.aborted, error=terminal.watch_error):
                tracker = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=20)
                active = prompt(in_progress=True, background_kinds=('shell',), background_started_ms=2000)
                active_snapshot = snapshot(parts)
                origins = {'root': _test_origins(active_snapshot.parts)}
                live = tracker.project({'root': block((active,))}, {'root': active_snapshot},
                                       now_ms=60_000, skill_origins_by_root=origins)
                self.assertIsNotNone(live[0].tool)
                live_output = render(live)
                for label in ('tool calls', 'Skills (', 'running:', 'background:', 'TODO'):
                    self.assertIn(label, live_output)
                terminal_snapshot = snapshot(parts, running=False)
                rows = tracker.project({'root': block((terminal,))}, {'root': terminal_snapshot},
                                       now_ms=61_000, skill_origins_by_root=origins)
                row = next(item for item in rows if item.prompt.event_id == terminal.event_id)
                self.assertIsNone(row.tool)
                self.assertEqual(Decimal('2.5'), row.prompt.ccost)
                self.assertEqual(9, row.prompt.calls)
                self.assertEqual(12_000, row.prompt.duration_ms)
                self.assertEqual(128, row.prompt.incoming_context_tokens)
                self.assertEqual(Decimal('0.5'), row.prompt.incoming_context_ccost)
                output = render(rows)
                self.assertIn('#1', output)
                self.assertIn('work', output)
                for label in ('tool calls', 'Skills (', 'running:', 'background:', 'TODO'):
                    self.assertNotIn(label, output)

    def test_completed_refresh_does_not_recompute_or_retain_final_observations(self):
        active = prompt(in_progress=True)
        with patch('src.watch.tracker.observe_tools', wraps=observe_tools) as observer:
            rows = self.project((active,), snapshot(self.parts))
            self.assertIsNotNone(rows[0].tool)
            self.assertEqual(1, observer.call_count)
            terminal = self.project((prompt(),), snapshot(self.parts, running=False), now=61_000)
            self.assertIsNone(terminal[0].tool)
            self.assertEqual(1, observer.call_count)

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
        self.assertIsNone(self.project((old,), new_snapshot)[0].tool)

    def test_compaction_keeps_activity_on_logical_prompt_not_terminal_checkpoint(self):
        compact = prompt('u_comp', 2, 3000, is_compaction=True)
        snap = snapshot(self.parts)
        event = NormalizedEvent('u_comp', 'root', EventKind.COMPACTION, 3000, prov('root', 'u_comp'))
        snap = replace(snap, events=snap.events + (event,))
        live = self.project((prompt(in_progress=True), compact), snap)
        self.assertIsNone(live[0].tool)
        self.assertEqual('u_next', live[1].prompt.event_id)
        self.assertEqual(2, live[1].tool.tool_count)
        self.assertTrue(all(row.tool is None for row in self.project((compact,), snap)))

    def test_missing_post_compaction_parts_remove_activity_from_retained_prompt(self):
        snap = snapshot(self.parts)
        self.project((prompt(in_progress=True),), snap)
        empty = replace(snap, messages=(), parts=())
        retained = self.project((), empty)
        self.assertTrue(retained)
        self.assertTrue(all(row.tool is None for row in retained))
        self.assertNotIn('tool calls', render(retained))

    def test_terminal_rehydration_never_restores_activity(self):
        for terminal in (prompt(), prompt(aborted=True), prompt(watch_error=True)):
            tracker = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=20)
            rows = tracker.project({'root': block((terminal,))},
                                   {'root': snapshot(self.parts, running=False)}, now_ms=60_000)
            self.assertIsNone(rows[0].tool)
            self.assertNotIn('tool calls', render(rows))
            self.assertIn('#1', render(rows))
            self.assertIn('work', render(rows))

    def test_simultaneous_sessions_have_independent_activity_lifecycles(self):
        first = snapshot(self.parts)
        second_base = snapshot((skill('load', GITHUB),))
        second = replace(second_base, root=replace(second_base.root, session_id='other'),
                         messages=tuple(replace(m, session_id='other', parts=tuple(replace(p, session_id='other') for p in m.parts))
                                        for m in second_base.messages),
                         events=tuple(replace(e, session_id='other') for e in second_base.events))
        blocks = {'root': block((prompt(in_progress=True),)),
                  'other': block((prompt(in_progress=True),), 'other')}
        snapshots = {'root': first, 'other': second}
        origin_maps = {'root': _snapshot_origins(first), 'other': _snapshot_origins(second)}
        rows = self.tracker.project(blocks, snapshots, now_ms=60_000, skill_origins_by_root=origin_maps)
        observations = {row.session_id: row.tool for row in rows}
        self.assertEqual((SkillObservation(BROWSER, 1),), observations['root'].skills)
        self.assertEqual((SkillObservation(GITHUB),), observations['other'].skills)

        blocks['root'] = block((prompt(in_progress=False),))
        snapshots['root'] = snapshot(self.parts, running=False)
        rows = self.tracker.project(blocks, snapshots, now_ms=61_000, skill_origins_by_root=origin_maps)
        observations = {row.session_id: row.tool for row in rows}
        self.assertIsNone(observations['root'])
        self.assertIsNotNone(observations['other'])
        self.assertEqual((SkillObservation(GITHUB),), observations['other'].skills)

    def test_skills_row_uses_tool_activity_color_and_failures_stay_red(self):
        rows = self.project((prompt(in_progress=True),), snapshot(self.parts))
        raw = render(rows, interactive=True)
        clean = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', raw)
        lines = clean.splitlines()
        prompt_line = next(line for line in lines if '#1 work' in line)
        tool_index = next(index for index, line in enumerate(lines) if 'tool calls' in line)
        self.assertIn('Skills (1)', lines[tool_index + 1])
        activity_line = lines[tool_index + 1]
        activity_prefix = next(index for index, char in enumerate(activity_line) if char not in '| ')
        self.assertEqual(prompt_line.index('#'), activity_prefix)
        self.assertIn('\x1b[92m' + BROWSER + '\x1b[0m', raw)
        self.assertNotIn('\x1b[93m' + BROWSER + '\x1b[0m', raw)
        self.assertIn('\x1b[91m [1 tool call failure]\x1b[0m', raw)

    def test_real_tiny_terminal_is_not_clamped_to_forty_columns_for_activity(self):
        class TinyTerminal(io.StringIO):
            def isatty(self):
                return True

            def fileno(self):
                return 1

        rows = self.project((prompt(in_progress=True),), snapshot(self.parts))
        stream = TinyTerminal()
        renderer = WatchRenderer({'colors': {}}, stream=stream, interactive=False)
        with patch('src.presentation.terminal.os.get_terminal_size', return_value=os.terminal_size((25, 10))):
            renderer.render(WatchProjection('Watch', 'V2', rows))
        activities = [line for line in stream.getvalue().splitlines() if line.startswith('|     ->')]
        self.assertEqual(2, len(activities))
        self.assertTrue(all(len(line) <= 24 for line in activities))

    def test_rendered_activity_lines_respect_terminal_width_including_borders(self):
        rows = self.project((prompt(in_progress=True),), snapshot(self.parts))
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
