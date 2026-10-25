"""Recent-marker lifecycle regression coverage for Watch activity rows."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import io
import json
import os
import re
import unittest
from unittest.mock import patch

from development.tests.fixtures.session_snapshots import make_snapshot, part, prov
from src.domain import EventKind, NormalizedEvent
from src.presentation import WatchRenderer
from src.presentation.watch_activity import BASE_ROLE, FAILED_ROLE
from src.reports.models import PromptProjection, SessionPromptBlock
from src.watch.models import SkillObservation, WatchProjection
from src.watch.tools import observe_tools
from src.watch.tracker import WatchRowTracker

BROWSER = 'auto-agent-browser'
GITHUB = 'auto-github-api'
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


class ActiveActivityLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tracker = WatchRowTracker(started_at_ms=0, recent_seconds=0, max_rows=20)
        self.parts = (skill('load', BROWSER, start=2100),
                      tool('fail', 'shell', inputs={'command': COMMAND}, output=result()))

    def project(self, rows, snap, now=60_000, *, tracker=None):
        target = tracker or self.tracker
        return target.project(
            {'root': block(rows)}, {'root': snap}, now_ms=now,
            skill_origins_by_root={'root': _test_origins(snap.parts)},
        )

    def test_terminal_updates_retain_final_stats_but_remove_live_status(self):
        parts = self.parts + (tool('running', 'shell', status='running', start=2200),
                              tool('todo', 'todo', inputs={'todos': [{'content': 'unfinished', 'status': 'in_progress'}]}))
        terminal_prompts = (
            prompt(in_progress=False, completed_successfully=True, calls=9, ccost=Decimal('2.5'), duration_ms=12_000,
                   incoming_context_tokens=128, incoming_context_ccost=Decimal('0.5')),
            prompt(in_progress=False, aborted=True, abort_reason='user', calls=9,
                   ccost=Decimal('2.5'), duration_ms=12_000, incoming_context_tokens=128,
                   incoming_context_ccost=Decimal('0.5')),
            prompt(in_progress=False, watch_error=True, calls=9,
                   ccost=Decimal('2.5'), duration_ms=12_000, incoming_context_tokens=128,
                   incoming_context_ccost=Decimal('0.5')),
        )
        for terminal in terminal_prompts:
            with self.subTest(aborted=terminal.aborted, error=terminal.watch_error):
                tracker = WatchRowTracker(started_at_ms=0, recent_seconds=30, max_rows=20)
                active = prompt(in_progress=True, background_kinds=('shell',), background_started_ms=2000)
                active_snapshot = snapshot(parts)
                live = self.project((active,), active_snapshot, tracker=tracker)
                self.assertIsNotNone(live[0].tool)
                live_output = render(live)
                for label in ('tool calls', 'Skills (', 'running:', 'background:', 'TODO'):
                    self.assertIn(label, live_output)

                terminal_snapshot = snapshot(parts, running=False)
                rows = self.project((terminal,), terminal_snapshot, now=61_000, tracker=tracker)
                row = next(item for item in rows if item.prompt.event_id == terminal.event_id)
                self.assertEqual('!' if terminal.aborted or terminal.watch_error else '\u2713', row.marker)
                self.assertIsNotNone(row.tool)
                self.assertEqual(4, row.tool.tool_count)
                self.assertEqual(1, row.tool.failed_count)
                self.assertEqual((('shell', 2), ('custom skill', 1), ('todo', 1)), row.tool.tool_counts)
                self.assertEqual((SkillObservation(BROWSER, 1),), row.tool.skills)
                self.assertFalse(row.tool.has_status_row)
                self.assertEqual((), row.tool.background_kinds)
                self.assertEqual(Decimal('2.5'), row.prompt.ccost)
                self.assertEqual(9, row.prompt.calls)
                self.assertEqual(12_000, row.prompt.duration_ms)
                self.assertEqual(128, row.prompt.incoming_context_tokens)
                self.assertEqual(Decimal('0.5'), row.prompt.incoming_context_ccost)
                output = render(rows)
                for label in ('4 tool calls', 'Skills (1)', BROWSER, '1 failed'):
                    self.assertIn(label, output)
                for label in ('running:', 'background:', 'TODO', 'unfinished'):
                    self.assertNotIn(label, output)

    def test_zero_window_keeps_neutral_error_outcome_without_terminal_activity(self):
        terminal = prompt(in_progress=False, watch_error=True)
        self.project((prompt(in_progress=True),), snapshot(self.parts))
        rows = self.project((terminal,), snapshot(self.parts, running=False))
        row = rows[0]
        self.assertEqual('', row.marker)
        self.assertIsNone(row.tool)
        renderer = WatchRenderer({}, stream=io.StringIO(), interactive=True)
        self.assertIsNone(renderer._row_style(row))
        self.assertIn('#1 [ERROR] work', render(rows))
        long_row = replace(row, prompt=replace(terminal, preview='x' * 500))
        self.assertIn('#1 [ERROR]', renderer._row_label(long_row))
        self.assertLessEqual(len(renderer._row_label(long_row)), 35)

    def test_running_play_marker_outlives_recent_window_then_transitions_to_completion(self):
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=1, max_rows=20)
        active = prompt(in_progress=True)
        active_snapshot = snapshot(self.parts)
        first = self.project((active,), active_snapshot, now=60_000, tracker=tracker)
        self.assertEqual("▶", first[0].marker)

        later = self.project((active,), active_snapshot, now=600_000, tracker=tracker)
        self.assertEqual("▶", later[0].marker)
        self.assertIn("▶ #1 work", render(later))

        completed = prompt(in_progress=False, completed_successfully=True)
        terminal = self.project((completed,), snapshot(self.parts, running=False), now=600_001, tracker=tracker)
        self.assertEqual("✓", terminal[0].marker)
        self.assertNotIn("▶ #1", render(terminal))
        self.assertIn("✓ #1 work", render(terminal))

    def test_recent_green_and_red_markers_expire_with_their_activity_rows(self):
        for terminal in (prompt(in_progress=False, completed_successfully=True),
                         prompt(in_progress=False, aborted=True),
                         prompt(in_progress=False, watch_error=True)):
            with self.subTest(aborted=terminal.aborted, error=terminal.watch_error):
                tracker = WatchRowTracker(started_at_ms=0, recent_seconds=30, max_rows=20)
                active = prompt(in_progress=True)
                terminal_snapshot = snapshot(self.parts, running=False)
                self.project((active,), terminal_snapshot, tracker=tracker)
                recent = self.project((terminal,), terminal_snapshot, now=61_000, tracker=tracker)
                self.assertIsNotNone(recent[0].tool)
                self.assertTrue(recent[0].marker)

                expired = self.project((terminal,), terminal_snapshot, now=91_000, tracker=tracker)
                self.assertEqual('', expired[0].marker)
                self.assertIsNone(expired[0].tool)
                self.assertNotIn('tool calls', render(expired))
                for now in (91_001, 120_000, 600_000):
                    snap = terminal_snapshot if now == 91_001 else replace(
                        terminal_snapshot, source_revision=f'resynced-{now}')
                    again = self.project((terminal,), snap, now=now, tracker=tracker)
                    self.assertEqual(expired, again)

    def test_historical_aborted_flag_does_not_recreate_a_recent_marker_or_activity(self):
        tracker = WatchRowTracker(started_at_ms=60_000, recent_seconds=30, max_rows=20, session_scope=True)
        historical = prompt(in_progress=False, aborted=True, at_ms=2_000)
        rows = self.project((historical,), snapshot(self.parts, running=False), now=61_000, tracker=tracker)
        self.assertEqual('', rows[0].marker)
        self.assertIsNone(rows[0].tool)
        self.assertNotIn('tool calls', render(rows))

    def test_terminal_final_observation_is_stable_until_source_revision_changes(self):
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=30, max_rows=20)
        active = prompt(in_progress=True)
        active_snapshot = snapshot(self.parts)
        terminal_snapshot = snapshot(self.parts, running=False)
        with patch('src.watch.tracker.observe_tools', wraps=observe_tools) as observer:
            live = self.project((active,), active_snapshot, tracker=tracker)
            self.assertIsNotNone(live[0].tool)
            self.assertEqual(1, observer.call_count)

            terminal = self.project((prompt(completed_successfully=True),), terminal_snapshot,
                                    now=61_000, tracker=tracker)
            refreshed = self.project((prompt(completed_successfully=True),), terminal_snapshot,
                                     now=62_000, tracker=tracker)
            self.assertEqual(terminal[0].tool, refreshed[0].tool)
            self.assertEqual(1, observer.call_count)

            more_parts = self.parts + (tool('new-evidence', 'read', start=2300),)
            revised = replace(
                snapshot(more_parts, running=False),
                source_revision=terminal_snapshot.source_revision + '-new',
            )
            updated = self.project((prompt(completed_successfully=True),), revised,
                                   now=63_000, tracker=tracker)
            self.assertEqual(2, observer.call_count)
            self.assertEqual(3, updated[0].tool.tool_count)

    def test_new_prompt_immediately_supersedes_recent_activity_without_inheriting_it(self):
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=30, max_rows=20)
        old = prompt(in_progress=False, watch_error=True)
        snap = snapshot(self.parts, running=False)
        previous = self.project((old,), snap, tracker=tracker)
        self.assertIsNotNone(previous[0].tool)
        self.assertEqual(2, previous[0].tool.tool_count)

        new = prompt('u_new', 2, 5000, in_progress=True)
        event = NormalizedEvent('u_new', 'root', EventKind.USER_PROMPT, 5000, prov('root', 'u_new'))
        new_snapshot = replace(snap, events=snap.events + (event,))
        rows = self.project((old, new), new_snapshot, tracker=tracker)
        self.assertIsNone(rows[0].tool)
        self.assertTrue(rows[0].prompt.watch_error)
        self.assertIn('[ERROR]', render(rows))
        self.assertEqual(0, rows[1].tool.tool_count)
        self.assertEqual((), rows[1].tool.skills)
        self.assertNotIn(BROWSER, render(rows))
        self.assertNotIn('Skills (1)', render(rows))

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

    def test_missing_post_compaction_parts_retain_final_activity_during_recent_highlight(self):
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=30, max_rows=20)
        snap = snapshot(self.parts)
        self.project((prompt(in_progress=True),), snap, tracker=tracker)
        empty = replace(snap, messages=(), parts=(), source_revision=snap.source_revision + '-compacted')
        retained = self.project((), empty, now=61_000, tracker=tracker)
        self.assertTrue(retained)
        self.assertFalse(retained[0].prompt.in_progress)
        self.assertTrue(retained[0].marker)
        self.assertEqual(2, retained[0].tool.tool_count)
        self.assertEqual((SkillObservation(BROWSER, 1),), retained[0].tool.skills)
        self.assertIn('2 tool calls', render(retained))
        self.assertIn('Skills (1)', render(retained))

    def test_fresh_tracker_does_not_restore_expired_terminal_activity(self):
        tracker = WatchRowTracker(started_at_ms=60_000, recent_seconds=30, max_rows=20, session_scope=True)
        for terminal in (prompt(), prompt(aborted=True), prompt(watch_error=True)):
            with self.subTest(aborted=terminal.aborted, error=terminal.watch_error):
                rows = self.project((terminal,), snapshot(self.parts, running=False),
                                    now=61_000, tracker=tracker)
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
        tracker = WatchRowTracker(started_at_ms=0, recent_seconds=30, max_rows=20)
        rows = tracker.project(blocks, snapshots, now_ms=60_000, skill_origins_by_root=origin_maps)
        observations = {row.session_id: row.tool for row in rows}
        self.assertEqual((SkillObservation(BROWSER, 1),), observations['root'].skills)
        self.assertEqual((SkillObservation(GITHUB),), observations['other'].skills)

        blocks['root'] = block((prompt(in_progress=False, watch_error=True),))
        snapshots['root'] = snapshot(self.parts, running=False)
        rows = tracker.project(blocks, snapshots, now_ms=61_000, skill_origins_by_root=origin_maps)
        observations = {row.session_id: row.tool for row in rows}
        self.assertEqual((SkillObservation(BROWSER, 1),), observations['root'].skills)
        self.assertIsNotNone(observations['other'])
        self.assertEqual((SkillObservation(GITHUB),), observations['other'].skills)

        expired = tracker.project(blocks, snapshots, now_ms=91_000, skill_origins_by_root=origin_maps)
        first_row, = (row for row in expired if row.session_id == 'root')
        other_row, = (row for row in expired if row.session_id == 'other')
        self.assertEqual('', first_row.marker)
        self.assertIsNone(first_row.tool)
        self.assertTrue(first_row.prompt.watch_error)
        self.assertEqual('▶', other_row.marker)
        self.assertIsNotNone(other_row.tool)

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
            _table, _styles, activities, _headers = renderer._table_rows(WatchProjection('Watch', 'V2', rows))
            for kind, marker, obs in activities.values():
                line = renderer._activity_line(kind, marker, obs, max(0, width - 4)) if width >= 4 else '|'
                self.assertLessEqual(len(line), width)
            output = render(rows, width=width)
            for line in output.splitlines():
                if 'tool calls' in line or 'Skills' in line:
                    self.assertLessEqual(len(line), width)

if __name__ == '__main__':
    unittest.main()
