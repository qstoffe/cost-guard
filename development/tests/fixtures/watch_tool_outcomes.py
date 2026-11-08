"""Synthetic full-Watch outcome subsets for projection and real browser checks."""
from dataclasses import replace

from development.tests.fixtures.watch_summary import summary_watch
from src.watch.models import SkillObservation, ToolObservation, ToolOutcome
from src.watch.invocation import invocation
from development.tests.fixtures.session_snapshots import part


def outcome_watch():
    frame = summary_watch()
    card = frame.active_cards[0]
    tool = ToolObservation(tool_count=12,
        tool_counts=(("grep", 4), ("execute", 3), ("a", 1), ("b", 1), ("c", 1), ("d", 1), ("<custom-tool>", 1)),
        failed_count=2, tool_outcomes=(ToolOutcome("grep", "failed", 2), ToolOutcome("execute", "cancelled", 1)),
        skills=(SkillObservation("custom-skill", 1),), running_tool="execute", running_ms=12000,
        background_kinds=("subagent",), background_ms=20000)
    detail = invocation(part("call-part", "assistant", "root", "tool", {"callID": "call", "state": {
        "input": {"command": 'git grep "hello world"\nWrite-Output \'<script>throw 1</script>\'',
                  "workdir": "C:/synthetic/source", "timeout": 120000}}}, 1000))
    tool = replace(tool, running_invocation=detail,
        background_invocation=replace(detail, identity="background-call"))
    row = replace(card.rows[0], tool=tool)
    return replace(frame, rows=(row,), active_cards=(replace(card, rows=(row,)),))
