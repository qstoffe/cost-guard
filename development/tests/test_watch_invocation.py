"""Invocation scope, privacy, source links and bounded immutable Web publication."""
from dataclasses import asdict, replace
import json
import unittest
from unittest.mock import patch

from development.tests.fixtures.session_snapshots import make_snapshot, part
from development.tests.fixtures.watch_summary import summary_watch
from src.application.live_projection import project_live
from src.domain import BackgroundActivity
from src.sources.opencode_v2_background import background_activities
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

    def test_dto_retained_unverified_terminal_and_100_card_replay_budget(self):
        frame = summary_watch()
        detail = invocation(tool(inputs={"command": "x" * 3500 + ' --api-key=synthetic-private --mode=fast'}))
        observation = replace(observe_tools(snapshot_with(tool()), "u_next", now_ms=20_000),
            running_invocation=detail, background_invocation=detail, background_kinds=("shell",))
        card = frame.active_cards[0]
        row = replace(card.rows[0], tool=observation, prompt=replace(card.rows[0].prompt, in_progress=True))
        card = replace(card, rows=(row,), state="observed")
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
