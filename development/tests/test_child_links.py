"""Only native tool results with real ancestry and possible timing establish links."""
from copy import deepcopy
from dataclasses import replace
import unittest

from development.tests.fixtures.subagent_sessions import incident_source
from src.analysis import analyze_snapshot
from src.analysis.child_links import child_session_id
from src.domain import MessageRole
from src.watch.tools import observe_tools


class ChildLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with incident_source() as (source, _server):
            cls.snapshot = source.load_session_snapshot("ses_current")
        cls.tool = next(part for part in cls.snapshot.parts if part.kind == "tool")

    def changed(self, tool, *, role=None, child_parent="ses_current"):
        messages = tuple(replace(message, parts=(tool,), **({"role": role} if role else {}))
            if message.message_id == "a1" else message for message in self.snapshot.messages)
        sessions = tuple(replace(session, parent_session_id=child_parent)
            if session.session_id == "ses_current_child" else session for session in self.snapshot.sessions)
        return replace(self.snapshot, messages=messages, sessions=sessions)

    def assert_link(self, snapshot, expected):
        record = analyze_snapshot(snapshot, now_ms=20_000).prompts[0]
        self.assertEqual(3 if expected else 2, record.model_calls)
        self.assertEqual(("ses_current_child",) if expected else (), record.linked_session_ids)
        # Child activity follows the same interpretation, not an independent parser.
        child_message = next(m for m in snapshot.messages if m.message_id == "ca")
        activity = replace(self.tool, part_id="child-read", message_id="ca", session_id="ses_current_child",
            created_at_ms=3500, updated_at_ms=3600, data={"tool": "child-proof", "state": {"status": "completed"}})
        snapshot = replace(snapshot, messages=tuple(replace(m, parts=(activity,)) if m == child_message else m
            for m in snapshot.messages))
        self.assertEqual(expected, "child-proof" in dict(observe_tools(snapshot, "u1").tool_counts))

    def test_both_tool_names_and_metadata_spellings_at_each_supported_level(self):
        for name in ("task", "subagent"):
            for key in ("sessionID", "sessionId"):
                for level in ("state", "top"):
                    with self.subTest(name=name, key=key, level=level):
                        data = deepcopy(self.tool.data)
                        data["tool"] = name
                        data["state"]["metadata"] = {}
                        target = data["state"] if level == "state" else data
                        target["metadata"] = {key: "ses_current_child"}
                        data["state"]["output"] = '<subagent sessionID="unrelated">copied</subagent>'
                        self.assert_link(self.changed(replace(self.tool, data=data)), True)

    def test_only_exact_native_output_envelopes_are_supported_as_fallbacks(self):
        for name, wrapper in (("subagent", '<subagent sessionID="ses_current_child">done</subagent>'),
                              ("task", '<task id="ses_current_child">done</task>')):
            for prefix, expected in (("", True), ("copied text: ", False), ("```\n", False)):
                with self.subTest(name=name, prefix=prefix):
                    data = deepcopy(self.tool.data)
                    data["tool"] = name
                    data["state"]["metadata"] = {}
                    data["state"]["output"] = prefix + wrapper
                    self.assert_link(self.changed(replace(self.tool, data=data)), expected)

    def test_malformed_structured_identity_is_not_replaced_by_valid_copied_output(self):
        for value in (None, 4, {}, [], "", "ses bad", "../child", "ses_<bad>", "x" * 257):
            with self.subTest(value=value):
                data = deepcopy(self.tool.data)
                data["state"]["metadata"] = {"sessionID": value}
                self.assertEqual("", child_session_id(replace(self.tool, data=data)))
                self.assert_link(self.changed(replace(self.tool, data=data)), False)

    def test_unrelated_tools_user_text_wrong_parent_and_impossible_intervals(self):
        data = deepcopy(self.tool.data)
        data["tool"] = "read"
        self.assert_link(self.changed(replace(self.tool, data=data)), False)
        self.assert_link(self.changed(replace(self.tool, kind="text")), False)
        self.assert_link(self.changed(self.tool, role=MessageRole.USER), False)
        self.assert_link(self.changed(self.tool, child_parent="different-parent"), False)
        for start, end in ((3900, 3200), (3200, 3200), (3000, 3900)):
            with self.subTest(start=start, end=end):
                data = deepcopy(self.tool.data)
                data["state"]["time"] = {"start": start, "end": end}
                self.assert_link(self.changed(replace(self.tool, data=data)), False)

    def test_latest_physical_call_correction_invalidates_an_older_link(self):
        invalid = replace(self.tool, part_id="corrected", updated_at_ms=4600,
            data={"tool": "subagent", "callID": "call-link", "state": {
                "metadata": {"sessionID": "unrelated"}, "time": {"start": 3200, "end": 3900}}})
        messages = tuple(replace(m, parts=(*m.parts, invalid, self.tool)) if m.message_id == "a1" else m
            for m in self.snapshot.messages)
        self.assert_link(replace(self.snapshot, messages=messages), False)


if __name__ == "__main__":
    unittest.main()
