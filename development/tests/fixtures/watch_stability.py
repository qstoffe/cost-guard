"""Source-shaped benign omissions; synthetic commands, never saved owner sessions."""
from dataclasses import replace

from .session_snapshots import make_uncompacted_snapshot, part
from .watch_runtime import MutableSource, make_service
from src.application.live_projection import project_live
from src.reports.watch_capture import capture_rows
from src.watch.card_workers import CardResult, current_tool_details
from src.watch.cards import CardSession, WatchCards
from src.watch.models import WatchProjection
from src.domain import BackgroundActivity


def refresh_publications(directory):
    source = MutableSource(make_uncompacted_snapshot(running=True))
    _, _, service, _ = make_service(directory, source, now_ms=20000)
    original = source.snapshot
    old = part("old-note", "a_sub", "root", "text", {"text": "old note"}, 1100)
    running = part("stable-tool", "a_next", "root", "tool", {"tool": "shell", "callID": "stable-call",
        "state": {"status": "running", "input": {
             "command": "python safe.py", "workdir": "src", "background": False}}}, 2100)
    background = part("background-tool", "a_next", "root", "tool", {"tool": "shell", "callID": "background-call",
        "state": {"status": "completed", "input": {
            "command": "python background.py", "workdir": "src", "background": True}}}, 2150)
    failure = part("failed-tool", "a_next", "root", "tool", {"tool": "read", "callID": "failed-call",
        "state": {"status": "error", "input": {"path": "src/missing.py"}, "error": {"code": "ENOENT"}}}, 2200)
    cards = WatchCards(None)
    entry = CardSession(original.root, original.source_revision, 1)
    cards.sessions["root"] = entry
    frames = []
    for tick in range(6):
        messages = tuple(replace(message, parts=message.parts +
            ((running, background, failure) if message.message_id == "a_next" else
             (old,) if message.message_id == "a_sub" and tick % 2 == 0 else ()))
            for message in original.messages)
        source.snapshot = replace(original, messages=messages,
            background=(BackgroundActivity("stable-job", "root", "shell", 2150, "a_next",
                tool_call_id="background-call"),),
            parts=tuple(item for message in messages for item in message.parts))
        service.now_ms = 20000 + tick * 1000
        capture, item = capture_rows(service, source.snapshot.root, entry.snapshot)
        tools = tuple((row.event_id, current_tool_details(item.snapshot, capture, row, service.now_ms, {}))
            for row in capture.rows)
        cards.accept(CardResult("root", 1, "rows", (capture, tools, item.snapshot)), service.now_ms)
        focal = next(row for row in entry.capture.rows if row.event_id == "u_next")
        card = cards._card(entry, focal, service.now_ms)
        frames.append(project_live(WatchProjection("Watch", "fixture", (),
            active_cards=(card,), cards_state="observed", now_ms=service.now_ms)).to_json())
    return frames
