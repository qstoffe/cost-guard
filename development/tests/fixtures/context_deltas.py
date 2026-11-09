"""Invented complete V2 request evidence, projected through the real context/Live owners."""
from dataclasses import replace

from development.tests.fixtures.session_snapshots import make_uncompacted_snapshot, prov
from src.analysis import analyze_snapshot
from src.domain import ActiveContext, EventKind, NormalizedEvent
from src.reports.prompts import build_prompt_block
from src.sources.opencode_v2_normalization import normalize_invocations, normalize_message_bundle
from src.watch.models import WatchCard, WatchRow
from src.watch.running import running_prompts


def context_bundles(*, incoming=100_000, outputs=(12_000,), running=False):
    raw = [{"info": {"id": "u", "sessionID": "root", "role": "user", "time": {"created": 1000}},
            "parts": [{"id": "text", "type": "text", "text": "Synthetic context example"}]}]
    next_input = incoming
    for index, output in enumerate(outputs):
        at = 1100 + index * 200
        raw.append({"info": {"id": f"a{index}", "sessionID": "root", "parentID": "u",
            "role": "assistant", "providerID": "github-copilot", "modelID": "gpt-test",
            "time": {"created": at, "completed": at + 100},
            "finish": "tool-calls" if running or index < len(outputs) - 1 else "stop",
            "tokens": {"input": next_input, "output": output, "reasoning": 0,
                       "cache": {"read": 0, "write": 0}}}, "parts": []})
        if running:
            raw[-1]['parts'] = [{"id": f"tool{index}", "type": "tool", "tool": "read",
                "time": {"start": at + 101}, "state": {"status": "running" if index == len(outputs) - 1 else "completed",
                    "input": {"path": "synthetic.txt"}, "time": {"start": at + 101}}}]
        next_input += output
    if not outputs:
        raw.append({"info": {"id": "waiting", "sessionID": "root", "parentID": "u", "role": "assistant",
            "providerID": "github-copilot", "modelID": "gpt-test", "time": {"created": 1100}}, "parts": []})
    return raw


def context_snapshot(*, incoming=100_000, outputs=(12_000,), running=False, active=True):
    base = make_uncompacted_snapshot()
    raw = context_bundles(incoming=incoming, outputs=outputs, running=running)
    provenance = lambda session, event=None: prov(session, event, "v2")
    messages = tuple(normalize_message_bundle(bundle, provenance)[0] for bundle in raw)
    return replace(base, sessions=(base.root,), messages=messages,
        parts=tuple(p for m in messages for p in m.parts),
        events=(NormalizedEvent("u", "root", EventKind.USER_PROMPT, 1000, provenance("root", "u"),
            "Synthetic context example"),),
        invocations=tuple(i for m in messages for i in normalize_invocations(m, provenance)),
        active_contexts=(ActiveContext("root", tuple(m.message_id for m in messages) if active else ()),),
        source_revision=f"context-{incoming}-{outputs}-{running}-{active}")


def context_v1_database(path):
    """The same invented wire counters persisted in a real, read-only-acquired V1 DB."""
    import json
    import sqlite3
    from contextlib import closing
    from pathlib import Path

    schema = Path(__file__).parent / 'opencode_v1/schema.sql'
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(schema.read_text(encoding='utf-8'))
        connection.execute('INSERT INTO session(id,project_id,directory,title,time_created,time_updated) VALUES(?,?,?,?,?,?)',
                           ('root', 'synthetic', '/synthetic', 'Context example', 900, 2000))
        for bundle in context_bundles():
            info = bundle['info']
            mid, at = info['id'], info['time']['created']
            connection.execute('INSERT INTO message(id,session_id,time_created,time_updated,data) VALUES(?,?,?,?,?)',
                (mid, 'root', at, info['time'].get('completed', at), json.dumps(info)))
            for part in bundle['parts']:
                connection.execute('INSERT INTO part(id,message_id,session_id,time_created,time_updated,data) VALUES(?,?,?,?,?,?)',
                    (part['id'], mid, 'root', at, at, json.dumps(part)))


def context_block(snapshot, prices):
    bundle = analyze_snapshot(snapshot, now_ms=1600, tracked_provider=None)
    return bundle, build_prompt_block(session_id="root", title="Context example", bundle=bundle,
        snapshot=snapshot, catalog=prices, config={})


def context_frame(frame, snapshot, prices, *, historical=False, session_next=None):
    _, block = context_block(snapshot, prices)
    prompt = block.rows[0]
    context = block.session_context
    if session_next is not None:
        context = replace(context, tokens=session_next)
    card = WatchCard("root", "Context example", "" if historical else prompt.event_id,
        (WatchRow("root", "Context example", prompt),), "observed", session_context=context)
    active, history = ((), (card,)) if historical else ((card,), ())
    return replace(frame, rows=card.rows, active_cards=active, history_cards=history,
        cards_state="observed", history_state="observed", history_epoch=1,
        running=running_prompts(active, "observed"))
