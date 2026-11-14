"""Invocation scope, privacy, source links and bounded immutable Web publication."""
from dataclasses import asdict, replace
from decimal import Decimal
import json
import unittest
from unittest.mock import Mock, patch

from development.tests.fixtures.session_snapshots import make_snapshot, part
from development.tests.fixtures.watch_summary import summary_watch
from development.tests.fixtures.watch_tool_outcomes import disclosure_publications, revision_observations
from src.application.live_projection import project_live
from src.domain import BackgroundActivity
from src.sources.opencode_v2_background import background_activities, running_jobs
from src.sources.errors import SourceUnavailableError
from src.watch.invocation import invocation, MAX_INPUT_TEXT
from src.watch.tools import observe_tools, without_live_activity
from src.web.events import MAX_EVENT_BYTES, MAX_REPLAY_BYTES, EventHub


def tool(pid="p", inputs=None, *, status="running", call="call", start=1000, updated=1000):
    value = part(pid, "a_next", "root", "tool", {
        "tool": "shell", "callID": call, "state": {"status": status, "input": inputs}}, start)
    return replace(value, updated_at_ms=updated)


def snapshot_with(*parts, background=()):
    snapshot = make_snapshot(running=True)
    messages = tuple(replace(message, parts=message.parts + parts)
                     if message.message_id == "a_next" else message for message in snapshot.messages)
    return replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts),
                   background=background, complete=True)


class InvocationTests(unittest.TestCase):
    def test_partial_publications_separate_aggregate_authority_from_private_detail_availability(self):
        frames = disclosure_publications()
        first = frames[0]["active_cards"][0]["rows"][0]["tool"]
        pending = frames[6]["active_cards"][0]["rows"][0]["tool"]
        recovered = frames[7]["active_cards"][0]["rows"][0]["tool"]

        self.assertEqual("observed", first["detail_state"])
        self.assertEqual(4, len(first["failed_invocations"]))
        self.assertEqual("pending", pending["detail_state"])
        self.assertEqual(first["outcomes"], pending["outcomes"])
        self.assertEqual(first["running_tool"], pending["running_tool"])
        self.assertEqual([], pending["failed_invocations"])
        self.assertEqual([], pending["running_invocations"])
        self.assertEqual([], pending["background_invocations"])
        self.assertIsNone(pending["running_invocation"])
        self.assertIsNone(pending["background_invocation"])
        self.assertEqual([item["identity"] for item in first["failed_invocations"]],
                         [item["identity"] for item in recovered["failed_invocations"]])
        self.assertEqual(first["running_invocations"][0]["identity"],
                         recovered["running_invocations"][0]["identity"])

    def test_explicit_invalidation_is_not_a_pending_detail_projection(self):
        frame = summary_watch()
        card = frame.active_cards[0]
        detail = invocation(tool(inputs={"command": "PRIVATE-MARKER"}))
        row = replace(card.rows[0], tool=replace(
            observe_tools(snapshot_with(tool()), "u_next", now_ms=20_000),
            running_invocation=detail))
        for state, unverified in [("unavailable", False), ("observed", True), ("partial", True)]:
            changed = replace(card, state=state,
                rows=(replace(row, prompt=replace(row.prompt, execution_unverified=unverified)),))
            exported = project_live(replace(frame, active_cards=(changed,))).to_json()
            activity = exported["active_cards"][0]["rows"][0]["tool"]
            self.assertEqual("invalidated", activity["detail_state"])
            self.assertNotIn("PRIVATE-MARKER", json.dumps(activity))

    def test_detail_state_alone_withholds_private_input_even_on_an_observed_card(self):
        frame = summary_watch()
        card = frame.active_cards[0]
        observation = observe_tools(snapshot_with(tool(inputs={"command": "PRIVATE-MARKER"})),
                                    "u_next", now_ms=20_000, include_invocations=True)
        for state in ("pending", "invalidated"):
            row = replace(card.rows[0], tool=replace(observation, detail_state=state))
            exported = project_live(replace(frame, active_cards=(replace(card, rows=(row,)),))).to_json()
            activity = exported["active_cards"][0]["rows"][0]["tool"]
            self.assertEqual(state, activity["detail_state"])
            self.assertEqual([], activity["running_invocations"])
            self.assertNotIn("PRIVATE-MARKER", json.dumps(activity))

    def test_source_revisions_keep_physical_identity_and_elapsed_origin_in_all_running_modes(self):
        for mode in ("foreground", "background"):
            for count in (1, 2):
                before, after = revision_observations(mode, count)
                first = getattr(before, f"{'running' if mode == 'foreground' else mode}_invocations")
                revised = getattr(after, f"{'running' if mode == 'foreground' else mode}_invocations")
                self.assertEqual(count, len(first))
                self.assertEqual([item.identity for item in first], [item.identity for item in revised])
                self.assertEqual([1000 + i for i in range(count)], [item.started_at_ms for item in revised])
                self.assertTrue(all(a.revision != b.revision and a.text != b.text for a, b in zip(first, revised)))
                self.assertEqual(10_000, (after.running_ms - before.running_ms) if mode == "foreground"
                                 else after.background_ms - before.background_ms)

    def test_two_background_shells_retain_separate_commands_and_identities(self):
        first = tool('one', {'command': 'python first.py', 'background': True}, status='completed', call='one')
        second = tool('two', {'command': 'python second.py', 'background': True}, status='completed', call='two')
        jobs = (BackgroundActivity('bg-one', 'root', 'shell', 1000, 'a_next', tool_call_id='one'),
                BackgroundActivity('bg-two', 'root', 'shell', 2000, 'a_next', tool_call_id='two'))

        observed = observe_tools(snapshot_with(first, second, background=jobs), 'u_next',
                                 now_ms=20_000, include_invocations=True)

        details = getattr(observed, 'background_invocations', ())
        self.assertEqual(2, len(details), 'both live jobs need their own disclosure, not one aggregate None')
        self.assertIn('python first.py', details[0].text)
        self.assertIn('python second.py', details[1].text)
        self.assertNotEqual(details[0].identity, details[1].identity)
        self.assertIsNone(observed.running_invocation, 'completed tool calls are not foreground running work')

    def test_registry_recovers_missing_input_only_through_exact_session_job_and_prompt_join(self):
        client = Mock()
        client.json.return_value = {'data': [
            {'id': 'job-one', 'status': 'running', 'command': 'python first.py --token synthetic-private',
             'cwd': 'C:/fixture', 'shell': 'pwsh', 'metadata': {'sessionID': 'root'}},
            {'id': 'job-peer', 'status': 'running', 'command': 'NEVER-EXPOSE-PEER',
             'metadata': {'sessionID': 'peer'}}]}
        items = [{'id': 'a_next', 'type': 'assistant', 'time': {'created': 1000}, 'content': [
            {'id': 'p', 'callID': 'call', 'name': 'shell', 'type': 'tool',
             'state': {'status': 'completed', 'metadata': {'shellID': 'job-one'}}}]}]
        registry = running_jobs(client, 'C:/fixture')
        jobs, _ = background_activities(items, session_id='root', running_jobs=lambda: registry)

        # The canonical part has been lost, but the native start still proves its
        # exact assistant message and shell identity. No call-name/time inference.
        observed = observe_tools(snapshot_with(background=jobs), 'u_next', now_ms=20_000, include_invocations=True)

        self.assertEqual(1, observed.background_invocation_count)
        detail = observed.background_invocations[0]
        self.assertIn('python first.py --token [redacted]', detail.text)
        self.assertIn('cwd:\nC:/fixture', detail.text)
        self.assertIn('shell:\npwsh', detail.text)
        self.assertNotIn('synthetic-private', json.dumps(asdict(detail)))
        self.assertNotIn('NEVER-EXPOSE-PEER', json.dumps(asdict(observed)))
        client.json.assert_called_once_with('/api/shell', query={'location[directory]': 'C:/fixture'})
        unrelated = observe_tools(snapshot_with(background=(replace(jobs[0], owner_message_id='other'),)),
                                  'u_next', now_ms=20_000, include_invocations=True)
        self.assertEqual((), unrelated.background_invocations)

    def test_command_mismatch_keeps_proven_original_only_but_identity_conflict_withholds_everything(self):
        original = tool(inputs={'command': 'python original.py', 'background': True}, status='completed')
        for reason, inputs in [('', (('command', 'REGISTRY-MARKER'), ('cwd', 'REGISTRY-CWD'))),
                               ('Conflicting job ownership; command withheld.', (('command', 'REGISTRY-MARKER'),))]:
            job = BackgroundActivity('bg', 'root', 'shell', 1000, 'a_next', tool_call_id='call',
                                     invocation_input=inputs, invocation_reason=reason)
            observed = observe_tools(snapshot_with(original, background=(job,)), 'u_next', now_ms=20_000,
                                     include_invocations=True)
            detail = observed.background_invocations[0]
            if reason:
                self.assertEqual('', detail.text)
                self.assertIn('Conflicting', detail.qualification)
            else:
                self.assertIn('python original.py', detail.text)
                self.assertIn('executed form not verified', detail.qualification)
            self.assertNotIn('REGISTRY-', json.dumps(asdict(detail)))
        inconsistent = replace(job, invocation_reason='', tool_part_id='contradictory-part')
        observed = observe_tools(snapshot_with(original, background=(inconsistent,)), 'u_next', now_ms=20_000,
                                 include_invocations=True)
        self.assertEqual('', observed.background_invocations[0].text)
        sensitive = tool(inputs={'command': 'curl -u user:synthetic-private', 'background': True}, status='completed')
        observed = observe_tools(snapshot_with(sensitive, background=(replace(job, invocation_reason=''),)),
                                 'u_next', now_ms=20_000, include_invocations=True)
        self.assertNotIn('command:', observed.background_invocations[0].text)
        self.assertNotIn('REGISTRY-', json.dumps(asdict(observed)))
        client = Mock()
        client.json.return_value = {'data': [
            {'id': 'job', 'status': 'running', 'command': 'PEER-COMMAND', 'metadata': {'sessionID': 'peer'}}]}
        items = [{'id': 'a_next', 'type': 'assistant', 'time': {'created': 1000}, 'content': [{
            'id': 'p', 'callID': 'call', 'name': 'shell', 'state': {
                'input': {'background': True}, 'metadata': {'shellID': 'job'}}}]}]
        registry = running_jobs(client, '')
        jobs, _ = background_activities(items, session_id='root', running_jobs=lambda: registry)
        self.assertEqual((), jobs[0].invocation_input)
        self.assertIn('ownership', jobs[0].invocation_reason)
        ambiguous = [*items, {**items[0], 'content': [{**items[0]['content'][0], 'callID': 'other'}]}]
        jobs, _ = background_activities(ambiguous, session_id='root', running_jobs=lambda: registry)
        self.assertEqual(('', '', ()), (jobs[0].tool_part_id, jobs[0].tool_call_id, jobs[0].invocation_input))
        for metadata in ({'jobID': 'job', 'shellID': 'different'},
                         {'jobID': 'job', 'sessionID': 'peer'}):
            items[0]['content'][0]['state']['metadata'] = metadata
            jobs, _ = background_activities(items, session_id='root', running_jobs=lambda: frozenset({'job'}))
            self.assertEqual((), jobs[0].invocation_input)
            self.assertIn('Conflicting', jobs[0].invocation_reason)

    def test_experimental_recovery_is_exact_session_filtered_optional_and_never_guesses_prompt(self):
        client = Mock()
        client.json.side_effect = [{'data': []}, {'data': [
            {'kind': 'shell', 'id': 'daemon-job', 'shellID': 'shell-one', 'sessionID': 'root',
             'status': 'running', 'command': 'python resumed.py'},
            {'kind': 'shell', 'id': 'daemon-two', 'shellID': 'shell-two', 'sessionID': 'root',
             'status': 'running', 'command': 'python second.py'},
            {'kind': 'shell', 'shellID': 'peer', 'sessionID': 'child-unproven',
             'status': 'running', 'command': 'PEER-COMMAND'}]}]
        registry = running_jobs(client, 'C:/fixture', session_id='root', experimental=True)
        items = [{'id': 'a_next', 'type': 'assistant', 'time': {'created': 1000}, 'content': [
            {'id': 'p', 'callID': 'call', 'name': 'shell', 'state': {'status': 'completed',
                'metadata': {'shellID': 'shell-one'}}}]}]

        jobs, _ = background_activities(items, session_id='root', running_jobs=lambda: registry)

        self.assertEqual(1, len(jobs), 'session-level shell-two cannot be assigned to this prompt')
        self.assertEqual((('command', 'python resumed.py'),), jobs[0].invocation_input)
        self.assertNotIn('peer', registry.ids)
        self.assertEqual({'sessionID': 'root', 'kind': 'shell', 'status': 'running', 'descendants': 'false'},
                         client.json.call_args_list[1].kwargs['query'])
        for experimental, expected_reads in [(False, 1), (True, 2)]:
            client.reset_mock()
            client.json.side_effect = [{'data': []}, SourceUnavailableError('absent', http_status=404)]
            registry = running_jobs(client, '', session_id='root', experimental=experimental)
            self.assertEqual(frozenset(), registry.ids)
            self.assertEqual(expected_reads, client.json.call_count)

    def test_foreground_count_is_live_calls_not_tool_totals_and_background_is_independent(self):
        completed = tool('ended', {'command': 'python ended.py'}, status='completed', call='ended')
        active = tool('active', {'command': 'python active.py'}, call='active')
        second = tool('second', {'command': 'python second.py'}, call='second')
        for parts, count in [((completed, active), 1), ((active, second), 2)]:
            observed = observe_tools(snapshot_with(*parts), 'u_next', now_ms=20_000, include_invocations=True)
            self.assertEqual(2, observed.tool_count)
            self.assertEqual(count, observed.running_invocation_count)
            self.assertEqual(count, len(observed.running_invocations))
            self.assertEqual(0, observed.background_invocation_count)
        self.assertEqual((), without_live_activity(observed).running_invocations)

    def test_multi_job_limits_keep_honest_total_stable_order_and_bounded_text(self):
        jobs = tuple(BackgroundActivity(f'bg-{i:02}', 'root', 'shell', 1000 + i, 'a_next',
                    invocation_input=(('command', f'python task{i}.py ' + 'x' * 3000),)) for i in range(12))
        observed = observe_tools(snapshot_with(background=jobs), 'u_next', now_ms=20_000, include_invocations=True)
        reordered = observe_tools(snapshot_with(background=tuple(reversed(jobs))), 'u_next',
                                  now_ms=30_000, include_invocations=True)
        self.assertEqual(12, observed.background_invocation_count)
        self.assertEqual(5, len(observed.background_invocations))
        self.assertEqual(observed.background_invocations, reordered.background_invocations)
        self.assertLessEqual(sum(len(detail.text) for detail in observed.background_invocations), MAX_INPUT_TEXT)
        self.assertTrue(all('budget' in detail.qualification for detail in observed.background_invocations))

    def test_registry_reads_are_one_per_session_capture_not_per_job_or_duration_tick(self):
        for count in (0, 1, 2, 5, 20):
            items = [{'id': 'a_next', 'type': 'assistant', 'time': {'created': 1000}, 'content': [
                {'id': f'p-{i}', 'callID': f'call-{i}', 'name': 'shell', 'state': {'input': {
                    'background': True, 'command': f'python task{i}.py'}, 'metadata': {'shellID': f'job-{i}'}}}
                for i in range(count)]}]
            reader = Mock(return_value=frozenset(f'job-{i}' for i in range(count)))
            jobs, _ = background_activities(items, session_id='root', running_jobs=reader)
            self.assertEqual(count, len(jobs))
            self.assertEqual(int(count > 0), reader.call_count)
        # A returned call lacking a background flag must not become a live job
        # solely because the registry is unavailable.
        items[0]['content'][0]['state']['input'] = {}
        items[0]['content'][0]['state']['status'] = 'completed'
        jobs, _ = background_activities([dict(items[0], content=items[0]['content'][:1])],
                                      session_id='root', running_jobs=lambda: None)
        self.assertEqual((), jobs)

    def test_safe_command_preserves_quotes_newlines_options_and_never_output(self):
        command = 'git grep "hello world"\nWrite-Output \'<script>throw 1</script>\''
        value = tool(inputs={"command": command, "workdir": "C:/source", "background": True, "timeout": 1200})
        detail = invocation(value)
        self.assertIn(command, detail.text)
        self.assertIn("background:\ntrue", detail.text)
        self.assertIn("timeout:\n1200 ms (1.2 s)", detail.text)
        self.assertEqual('', detail.qualification)
        legacy = replace(value, data={"input": {"pattern": "hello", "path": "src"},
                                     "output": "DO NOT EXPOSE", "state": {"status": "running"}})
        self.assertEqual("pattern:\nhello\n\npath:\nsrc", invocation(legacy).text)
        self.assertNotIn("DO NOT EXPOSE", invocation(legacy).text)

    def test_sensitive_values_redacted_without_losing_safe_command_portion(self):
        for command, expected in [
                ('python tokenizer.py --api-key=synthetic-value --mode=fast',
                 'python tokenizer.py --api-key=[redacted] --mode=fast'),
                ('python task.py --token "synthetic value" --limit=25',
                 'python task.py --token [redacted] --limit=25'),
                ("$env:API_KEY='synthetic-value'; python task.py", "$env:API_KEY=[redacted]; python task.py"),
                ('AWS_SECRET_ACCESS_KEY=synthetic-value python task.py',
                 'AWS_SECRET_ACCESS_KEY=[redacted] python task.py'),
                ('curl https://user:synthetic-value@example.com --silent',
                 'curl https://[redacted]@example.com --silent'),
                ('python task.py ghp_synthetic', 'python task.py [redacted]')]:
            with self.subTest(expected=expected):
                detail = invocation(tool(inputs={'command': command}))
                self.assertEqual('command:\n' + expected, detail.text)
                self.assertIn('Sensitive argument/value redacted.', detail.qualification)
                self.assertNotIn('synthetic-value', json.dumps(asdict(detail)))

    def test_ambiguous_credentials_headers_and_private_keys_withheld(self):
        for command in ["curl --token 'synthetic'\"continuation\"", 'curl --token "synthetic\\\"tail"',
                        'python task.py --token=$variable', 'curl -u user:synthetic',
                        "curl -H 'Authorization: Bearer synthetic'", "curl -H 'Cookie: name=synthetic'",
                        'echo -----BEGIN PRIVATE KEY-----\nsynthetic', 'python --token',
                        "curl https://user:'synthetic value'@example.com"]:
            with self.subTest():
                detail = invocation(tool(inputs={"command": command, "workdir": "src", "env": {"X": "private"},
                                                 "password": "private", "content": "private"}))
                self.assertEqual("workdir:\nsrc", detail.text)
                self.assertIn('withheld', detail.qualification)
                self.assertIn('Environment/credential fields omitted.', detail.qualification)
                self.assertIn("Not the complete invocation", detail.qualification)
        detail = invocation(tool(inputs={"pattern": {"nested": "private"}, "code": "private"}))
        self.assertEqual("", detail.text)
        self.assertIn('Structured input omitted.', detail.qualification)
        self.assertIn('Content/script body omitted.', detail.qualification)

    def test_benign_windows_unicode_powershell_and_assignments_preserve_source_exactly(self):
        commands = [r'"C:\Python313\python.exe" "D:\dev\scripts\report.py" --mode=fast --limit=25 --verbose',
                    'NAME=development python tokenizer.py --mode=fast',
                    'FOO=private git status', "$env:FOO='development'; python tokenizer.py",
                    ' & "C:\\Python 313\\python.exe" "D:\\café\\tokenizer.py" --name="hello world"\nWrite-Output \'done\'']
        for command in commands:
            with self.subTest():
                detail = invocation(tool(inputs={'command': command, 'workdir': 'D:\\dev',
                                                 'timeout': 120000, 'background': False}))
                self.assertEqual('command:\n' + command, detail.text.split('\n\n')[0])
                self.assertIn('timeout:\n120000 ms (2 min)', detail.text)
                self.assertIn('background:\nfalse', detail.text)
                self.assertEqual('', detail.qualification)

    def test_missing_empty_oversized_and_unsupported_input_are_honest_and_bounded(self):
        for inputs, reason in [(None, 'No source input'), ({}, 'No source input'),
                               ('invalid', 'No source input'),
                               ({'command': 'x' * 10_000_000}, 'Oversized field omitted'),
                               ({'limit': 1 << 1000}, 'Unsupported numeric'),
                               ({'limit': float('inf')}, 'Unsupported numeric'),
                               ({'unknown': 'private'}, 'Unsupported fields')]:
            detail = invocation(tool(inputs=inputs))
            self.assertEqual("", detail.text)
            self.assertIn(reason, detail.qualification)
        detail = invocation(tool(inputs={"command": "\u2603" * 2000, "path": "src"}))
        self.assertLessEqual(len(detail.text.encode()), MAX_INPUT_TEXT)
        self.assertNotIn("\u2603", detail.text)

    def test_timeout_units_only_for_positive_finite_native_shell_numbers(self):
        for value, text in [(1500, '1500 ms (1.5 s)'), (3600000, '3600000 ms (1 h)'),
                            (1.25, '1.25 ms (0.00125 s)'), (0, '0'), (-1, '-1'),
                            ('120s', '120s'), (True, 'true')]:
            self.assertEqual('command:\npython task.py\n\ntimeout:\n' + text,
                             invocation(tool(inputs={'command': 'python task.py', 'timeout': value})).text)
        for name in ['shell', 'bash', 'functions.shell', 'execute', 'grep']:
            value = tool(inputs={'timeout': 120000})
            value = replace(value, data={**value.data, 'tool': name})
            self.assertEqual(name in {'shell', 'bash', 'functions.shell'}, '120000 ms' in invocation(value).text)
        self.assertNotIn('timeout', invocation(tool(inputs={'command': 'python task.py'})).text)
        for value in [float('inf'), float('-inf'), float('nan')]:
            self.assertEqual('', invocation(tool(inputs={'timeout': value})).text)

    def test_threshold_canonical_copy_longest_and_revision_identity(self):
        first = tool(inputs={"command": "git status"})
        corrected = tool("copy", {"command": "git diff"}, updated=2000)
        snapshot = snapshot_with(first, corrected, tool("other", {"command": "git log"}, call="other", start=2000))
        self.assertIsNone(observe_tools(snapshot, "u_next", now_ms=10_999, include_invocations=True).running_invocation)
        observed = observe_tools(snapshot, "u_next", now_ms=11_000, include_invocations=True)
        self.assertIn("git diff", observed.running_invocation.text)
        self.assertEqual(2, observed.tool_count)
        later = observe_tools(snapshot, "u_next", now_ms=30_000, include_invocations=True)
        self.assertEqual(observed.running_invocation, later.running_invocation)
        self.assertEqual(invocation(first).identity, invocation(corrected).identity)
        self.assertNotEqual(invocation(first).revision, invocation(corrected).revision)
        self.assertNotEqual(invocation(first).identity, invocation(replace(first,
            provenance=replace(first.provenance, source_generation="other"))).identity)
        no_call = replace(first, part_id="call", data={key: value for key, value in first.data.items() if key != "callID"})
        self.assertNotEqual(invocation(first).identity, invocation(no_call).identity, "call/part namespaces stay distinct")
        for status in ["completed", "error"]:
            ended = observe_tools(snapshot_with(tool(inputs={"command": "git status"}, status=status)),
                                  "u_next", now_ms=30_000, include_invocations=True)
            self.assertIsNone(ended.running_invocation)
        self.assertIsNone(without_live_activity(observed).running_invocation)
        self.assertIsNone(observe_tools(snapshot, "u_next", now_ms=30_000).running_invocation, "CLI opt out")

    def test_background_requires_unique_canonical_job_call_link(self):
        original = tool(inputs={"command": "git status", "background": True}, status="completed")
        job = BackgroundActivity("bg", "root", "shell", 1000, "a_next", tool_call_id="call")
        def observed(jobs):
            return observe_tools(snapshot_with(original, background=jobs), "u_next", now_ms=20_000, include_invocations=True)
        self.assertIn("git status", observed((job,)).background_invocation.text)
        self.assertIsNone(observed((job,)).running_invocation)
        for jobs in [(replace(job, tool_call_id=""),), (replace(job, tool_call_id="unrelated"),),
                     (job, replace(job, activity_id="two")), (replace(job, running=False),),
                     (replace(job, owner_message_id="unrelated"),)]:
            self.assertIsNone(observed(jobs).background_invocation)
        items = [{"id": "a_next", "type": "assistant", "time": {"created": 1000}, "content": [{
            "id": "p", "callID": "call", "type": "tool", "name": "shell",
            "state": {"input": {"background": True}, "metadata": {"jobID": "job"}}}]}]
        activities, _ = background_activities(items, session_id="root", running_jobs=lambda: frozenset({"job"}))
        self.assertEqual(("p", "call"), (activities[0].tool_part_id, activities[0].tool_call_id))
        unknown, _ = background_activities(items, session_id="root", running_jobs=lambda: None)
        self.assertEqual(("", ""), (unknown[0].tool_part_id, unknown[0].tool_call_id))
        ambiguous = [*items, {**items[0], "content": [{**items[0]["content"][0], "callID": "other"}]}]
        activities, _ = background_activities(ambiguous, session_id="root", running_jobs=lambda: frozenset({"job"}))
        self.assertEqual(("", ""), (activities[0].tool_part_id, activities[0].tool_call_id))

    def test_linked_child_inputs_stay_inside_canonical_prompt_window(self):
        snapshot = make_snapshot(running=True)
        child_tool = replace(tool(inputs={"pattern": "child-only", "path": "src"}, start=1240, updated=1240),
                             session_id="child", message_id="ca")
        messages = tuple(replace(message, parts=(child_tool,)) if message.message_id == "ca" else message
                         for message in snapshot.messages)
        snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts))
        observed = observe_tools(snapshot, "u_sub", now_ms=30_000, include_invocations=True)
        self.assertIn("child-only", observed.running_invocation.text)
        unrelated = observe_tools(snapshot, "u_next", now_ms=30_000, include_invocations=True)
        self.assertIsNone(unrelated.running_invocation)
        failed_part = replace(child_tool, data={**child_tool.data,
            "state": {**child_tool.data["state"], "status": "error", "error": {"code": "ENOENT"}}})
        messages = tuple(replace(message, parts=(failed_part,)) if message.message_id == "ca" else message
                         for message in snapshot.messages)
        failed_snapshot = replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts))
        failed = observe_tools(failed_snapshot, "u_sub", now_ms=30_000, include_invocations=True)
        self.assertIn("child-only", failed.failed_invocations[0].invocation.text)
        self.assertEqual("File not found", failed.failed_invocations[0].reason)
        self.assertEqual((), observe_tools(failed_snapshot, "u_next", now_ms=30_000,
                                         include_invocations=True).failed_invocations)

    def test_returned_child_background_shell_remains_scoped_to_its_owning_prompt(self):
        snapshot = make_snapshot(running=True)
        job = BackgroundActivity('child-bg', 'child', 'shell', 1240, 'ca', tool_call_id='child-call',
                                 invocation_input=(('command', 'python child.py'),))
        snapshot = replace(snapshot, background=(job,))

        owning = observe_tools(snapshot, 'u_sub', now_ms=30_000, include_invocations=True)
        unrelated = observe_tools(snapshot, 'u_next', now_ms=30_000, include_invocations=True)

        self.assertEqual(1, owning.background_invocation_count)
        self.assertIn('python child.py', owning.background_invocations[0].text)
        self.assertEqual((), unrelated.background_invocations)

    def test_wrong_source_generation_never_discloses_canonical_or_registry_text(self):
        original = tool(inputs={'command': 'ORIGINAL-MARKER'}, status='completed')
        original = replace(original, provenance=replace(original.provenance, source_generation='retired'))
        job = BackgroundActivity('bg', 'root', 'shell', 1000, 'a_next', tool_call_id='call',
                                 invocation_input=(('command', 'REGISTRY-MARKER'),))

        observed = observe_tools(snapshot_with(original, background=(job,)), 'u_next', now_ms=20_000,
                                 include_invocations=True)

        self.assertEqual('', observed.background_invocations[0].text)
        self.assertIn('identity', observed.background_invocations[0].qualification)
        self.assertNotIn('MARKER', json.dumps(asdict(observed)))

    def test_five_foreground_and_background_jobs_fit_100_card_event_and_replay_caps(self):
        frame = summary_watch()
        inputs = {'command': 'python task.py ' + 'x' * 120 + ' --token synthetic-private'}
        parts = tuple(tool(f'p-{i}', inputs, call=f'call-{i}',
                      status='running' if i < 5 else 'completed' if i < 10 else 'error') for i in range(20))
        jobs = tuple(BackgroundActivity(f'bg-{i}', 'root', 'shell', 1000, 'a_next',
                     tool_call_id=f'call-{i}') for i in range(5, 10))
        observed = observe_tools(snapshot_with(*parts, background=jobs), 'u_next', now_ms=30_000,
                                 include_invocations=True)
        self.assertEqual((5, 5, 10), (len(observed.running_invocations), len(observed.background_invocations),
                                    len(observed.failed_invocations)))
        self.assertLessEqual(sum(len(item.text) for item in (
            *observed.running_invocations, *observed.background_invocations,
            *(failure.invocation for failure in observed.failed_invocations))), MAX_INPUT_TEXT)
        card = frame.active_cards[0]
        row = card.rows[0]
        tool_observation = replace(observed, background_kinds=('shell',) * 5)
        card = replace(card, activity_scope="f" * 64, rows=(replace(row, tool=tool_observation,
            prompt=replace(row.prompt, subagent_active=True, parent_outcome="cancellation",
                parent_terminal_time_ms=1_800_000_000_000)),))
        card = replace(card, session_cost=replace(card.session_cost,
            main_ccost=Decimal("4000"), subagent_ccost=Decimal("582.125")))
        frame = replace(frame, active_cards=tuple(replace(card, session_id=f's{i}') for i in range(100)))
        hub = EventHub('multi-invocation-budget')

        for tick in range(8):
            payload = project_live(replace(frame, now_ms=frame.now_ms + tick * 1000)).to_json()
            from development.tests.integration.invocation_observations import observe_invocations
            self.assertEqual(1000, observe_invocations(payload), "live probe inspects both five-call lists, not suppressed singular duplicates")
            encoded = json.dumps(payload).encode()
            self.assertLess(len(encoded), MAX_EVENT_BYTES)
            self.assertNotIn(b'synthetic-private', encoded)
            hub.publish('live', payload)

        self.assertLessEqual(hub.bytes, MAX_REPLAY_BYTES)
        activity = payload["active_cards"][0]["rows"][0]["tool"]
        # Legacy singular fallback does not double-count a duplicate native call.
        fields = ("identity", "revision", "text", "qualification")
        activity["running_invocation"] = {key: activity["running_invocations"][0][key] for key in fields}
        activity["background_invocation"] = activity["running_invocation"]
        activity["running_invocations"] = activity["background_invocations"] = []
        payload["active_cards"] = payload["active_cards"][:1]
        self.assertEqual(1, observe_invocations(payload))

    def test_dto_retained_unverified_terminal_and_100_card_replay_budget(self):
        frame = summary_watch()
        detail = invocation(tool(inputs={"command": "x" * 3500 + ' --api-key=synthetic-private --mode=fast'}))
        observation = replace(observe_tools(snapshot_with(tool()), "u_next", now_ms=20_000),
            running_invocation=detail, background_invocation=detail, background_kinds=("shell",))
        card = frame.active_cards[0]
        row = replace(card.rows[0], tool=observation, prompt=replace(card.rows[0].prompt, in_progress=True))
        card = replace(card, rows=(row,), state="observed", activity_scope="f" * 64)
        for state, prompt in [("unavailable", row.prompt), ("retrying", row.prompt),
                              ("partial", row.prompt), ("observed", replace(row.prompt, in_progress=False)),
                              ("observed", replace(row.prompt, execution_unverified=True))]:
            exported = project_live(replace(frame, active_cards=(replace(card, state=state,
                rows=(replace(row, prompt=prompt),)),))).to_json()
            self.assertIsNone(exported["active_cards"][0]["rows"][0]["tool"]["running_invocation"])
        frame = replace(frame, active_cards=tuple(replace(card, session_id=f"s{i}") for i in range(100)))
        hub = EventHub("invocation-budget")
        with patch("src.watch.invocation.invocation", side_effect=AssertionError("duration tick must not rederive")):
            for tick in range(5):
                payload = project_live(replace(frame, now_ms=frame.now_ms + tick * 1000)).to_json()
                encoded = json.dumps(payload).encode()
                self.assertNotIn(b'synthetic-private', encoded)
                self.assertIn(b'--api-key=[redacted] --mode=fast', encoded)
                self.assertLess(len(encoded), MAX_EVENT_BYTES)
                hub.publish("live", payload)
        self.assertLessEqual(hub.bytes, MAX_REPLAY_BYTES)


if __name__ == "__main__":
    unittest.main()
