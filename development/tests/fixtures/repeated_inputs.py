"""Deterministic repeated first inputs with later work, independent root identities."""
from dataclasses import replace

from .synthetic_month import SyntheticMonthSource


def source(groups=11, repeats=3, *, start=1_790_000_000_000):
    result = SyntheticMonthSource(groups * repeats, 2, month_start_ms=start)
    for index, (sid, snapshot) in enumerate(tuple(result.snapshots.items())):
        first = snapshot.messages[0]
        part = replace(first.parts[0], data={'text': f'Exact first input {index // repeats}\n  preserve whitespace'})
        duration = (index % repeats + 1) * 100
        messages = (replace(first, parts=(part,)), replace(snapshot.messages[1], completed_at_ms=first.created_at_ms + duration),
                    *snapshot.messages[2:])
        root = replace(snapshot.root, title=f'Quest <img src=x onerror=alert(1)> {index}',
                       archived_at_ms=start if index % repeats == 0 else None)
        invocations = (replace(snapshot.invocations[0], completed_at_ms=first.created_at_ms + duration),
                       replace(snapshot.invocations[1], tokens=replace(snapshot.invocations[1].tokens, input=999999)))
        result.snapshots[sid] = replace(snapshot, root=root, sessions=(root,), messages=messages,
            parts=tuple(p for message in messages for p in message.parts), invocations=invocations, complete=True)
    return result
