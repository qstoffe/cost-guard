"""Synthetic historical calls shared by canonical and rendered detail checks."""
from dataclasses import replace

from .session_snapshots import make_snapshot, part


def activity_snapshot(failures=4):
    snapshot = make_snapshot()
    additions = {}
    owners = (("a_sub", 1160), ("a_next", 2150), ("a_comp", 3150))
    for index in range(failures):
        mid, start = owners[index % 3]
        value = part(f"failure-{index:04}", mid, "root", "tool", {
            "tool": "read", "callID": f"physical-{index:04}",
            "state": {"status": "error", "input": {"filePath": "src/same.py"},
                      "error": {"code": "ENOENT"} if index != 1 else "private arbitrary error",
                      "output": "private file contents"},
        }, start + index)
        additions.setdefault(mid, []).append(value)
    additions.setdefault("a_next", []).extend((
        part("cancel", "a_next", "root", "tool", {"tool": "shell", "state": {
            "status": "error", "error": {"code": "CANCELLED"},
            "input": {"command": "python task.py --token synthetic-secret --check", "workdir": "src"},
            "output": "synthetic-secret"}}, 2170),
        part("good", "a_next", "root", "tool", {"tool": "grep", "state": {"status": "completed"}}, 2180),
        part("skill-one", "a_next", "root", "tool", {"tool": "skill", "state": {
            "status": "completed", "input": {"id": "auto-github-api"}}}, 2190),
    ))
    additions.setdefault("a_comp", []).append(part("skill-again", "a_comp", "root", "tool",
        {"tool": "skill", "state": {"status": "completed", "input": {"id": "auto-github-api"}}}, 3160))
    # A repeated native snapshot/part is the same physical call, not another read.
    if failures:
        additions["a_sub"].append(replace(additions["a_sub"][0], part_id="duplicate-copy"))
    messages = tuple(replace(message, parts=message.parts + tuple(additions.get(message.message_id, ())))
                     for message in snapshot.messages)
    return replace(snapshot, messages=messages, parts=tuple(p for m in messages for p in m.parts))
