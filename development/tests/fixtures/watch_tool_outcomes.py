"""Synthetic full-Watch outcome subsets for projection and real browser checks."""
from dataclasses import replace

from development.tests.fixtures.watch_summary import summary_watch
from src.watch.models import SkillObservation, ToolFailure, ToolObservation, ToolOutcome
from src.watch.invocation import invocation
from development.tests.fixtures.session_snapshots import make_snapshot, part
from src.domain import BackgroundActivity
from src.watch.tools import observe_tools


def outcome_watch():
    frame = summary_watch()
    card = frame.active_cards[0]
    tool = ToolObservation(tool_count=12,
        tool_counts=(("grep", 4), ("execute", 3), ("a", 1), ("b", 1), ("c", 1), ("d", 1), ("<custom-tool>", 1)),
        failed_count=2, tool_outcomes=(ToolOutcome("grep", "failed", 2), ToolOutcome("execute", "cancelled", 1)),
        skills=(SkillObservation("custom-skill", 1),), running_tool="execute", running_ms=12000,
        background_kinds=("subagent",), background_ms=20000)
    detail = invocation(part("call-part", "assistant", "root", "tool", {"tool": "shell", "callID": "call", "state": {
        "input": {"command": '"C:\\Python313\\python.exe" "D:\\dev\\scripts\\tokenizer.py" --mode=fast --limit=25\n'
                             'Write-Output \'<script>throw 1</script>\'',
                  "workdir": "C:/synthetic/source", "background": False, "timeout": 120000}}}, 1000))
    tool = replace(tool, running_invocation=detail,
        background_invocation=replace(detail, identity="background-call"),
        failed_invocations=tuple(ToolFailure("grep", invocation(part(f"failed-{i}", "assistant", "root", "tool",
            {"tool": "grep", "callID": f"failed-{i}", "state": {"status": "error",
             "input": {"pattern": "<img src=x>", "path": f"src/example-{i}.py"}}}, 1000 + i)),
            "File not found" if i == 1 else "Failure reason unavailable") for i in (1, 2)))
    row = replace(card.rows[0], tool=tool)
    return replace(frame, rows=(row,), active_cards=(replace(card, rows=(row,)),))


def revision_observations(mode="foreground", count=1):
    """Authoritative source-shaped same-call revisions, not an owner-incident replay."""
    snapshot = make_snapshot(running=True)
    observations = []
    for revision, now in ((1000, 20_000), (2000, 30_000)):
        parts = tuple(replace(part(f"p-{i}", "a_next", "root", "tool", {
            "tool": "shell", "callID": f"call-{i}", "state": {
                "status": "completed" if mode == "background" else "running",
                "input": {"command": f"python task{i}.py --limit={revision}", "workdir": "src"}}}, 1000 + i),
            updated_at_ms=revision) for i in range(count))
        messages = tuple(replace(message, parts=parts) if message.message_id == "a_next" else message
                         for message in snapshot.messages)
        jobs = tuple(BackgroundActivity(f"job-{i}", "root", "shell", 1000 + i, "a_next",
                     tool_call_id=f"call-{i}") for i in range(count)) if mode == "background" else ()
        observed = observe_tools(replace(snapshot, messages=messages,
            parts=tuple(p for m in messages for p in m.parts), background=jobs, complete=True),
            "u_next", now_ms=now, include_invocations=True)
        observations.append(replace(observed, background_kinds=("shell",) * len(jobs),
                                    background_ms=now - 1000 if jobs else 0))
    return tuple(observations)


def two_shell_tools(scope):
    """Two bounded synthetic commands for the authenticated shipped-host probe."""
    details = tuple(replace(invocation(part(f'p-{i}', 'assistant', 'root', 'tool', {
        'tool': 'shell', 'callID': f'{scope}-{i}', 'state': {'input': {
            'command': f'python task{i}.py --check\nWrite-Output "synthetic {i}"',
            'background': True, 'workdir': 'C:/fixture', 'timeout': 120000}}}, 1000)),
        mode='background') for i in (1, 2))
    return ToolObservation(tool_count=2, tool_counts=(('shell', 2),), background_kinds=('shell', 'shell'),
        background_ms=20_000, background_invocations=details, background_invocation_count=2)


def disclosure_publications():
    """Actual immutable DTOs over synthetic canonical calls and a partial capture."""
    from src.application.live_projection import project_live
    snapshot = make_snapshot(running=True)
    frames = []
    for tick in range(48):
        # Four failures, then a fifth; the existing physical identities do not move.
        count = 4 if tick < 12 else 5
        parts = tuple(part(f"failure-{i}", "a_next", "root", "tool", {
            "tool": "read", "callID": f"failure-{i}", "state": {"status": "error",
                "input": {"path": f"src/synthetic-{i}.py"},
                "error": {"code": "EACCES" if i == 1 and tick > 20 else "ENOENT"}}}, 1000 + i)
            for i in range(count))
        running = tuple(part(f"running-{i}", "a_next", "root", "tool", {
            "tool": "shell", "callID": f"running-{i}", "state": {"status": "running",
                "input": {"command": f"python task{i}.py --limit={tick}"}}}, 1000 + i)
            for i in range(1 if tick < 8 or tick > 30 else 2))
        successes = tuple(part(f"success-{i}", "a_next", "root", "tool", {
            "tool": "grep", "callID": f"success-{i}", "state": {"status": "completed"}}, 1500 + i)
            for i in range(tick // 12))
        messages = tuple(replace(message, parts=(*parts, *running, *successes)) if message.message_id == "a_next"
                         else message for message in snapshot.messages)
        observation = observe_tools(replace(snapshot, messages=messages,
            parts=tuple(p for m in messages for p in m.parts), complete=True),
            "u_next", now_ms=20_000 + tick * 1000, include_invocations=True)
        background = two_shell_tools("disclosure")
        observation = replace(observation, background_kinds=background.background_kinds,
            background_invocations=background.background_invocations, background_invocation_count=2,
            skills=(SkillObservation("stable-skill", tick % 3), SkillObservation("other-skill")))
        frame = summary_watch()
        card = frame.active_cards[0]
        row = replace(card.rows[0], tool=observation)
        # Production projection must clear sensitive details, without calling this
        # an authoritative empty membership. No owner's private trace is involved.
        card = replace(card, rows=(row,), state="partial" if tick in (6, 17, 28, 39) else "observed")
        frames.append(project_live(replace(frame, active_cards=(card,))).to_json())
    return frames
