"""Bounded source-certified post-start overlay, never a global history proof."""
from dataclasses import replace

from src.domain import EventKind


class RecentFinished:
    def __init__(self):
        self.entries = {}

    def observe(self, owner, entry, source_rows, now_ms):
        capture, snapshot = entry.capture, entry.snapshot
        if (not owner.started_at_ms or snapshot is None or not snapshot.complete
                or not capture.authoritative or capture.retained
                or entry.verified_generation != entry.generation):
            return
        events = {event.event_id for event in snapshot.events
            if event.session_id == entry.root.session_id and event.kind is EventKind.USER_PROMPT}
        rows = [row for row in source_rows if row.event_id in events and not row.is_compaction
            and not row.in_progress and not row.execution_unverified
            and (row.completed_successfully or row.aborted or row.watch_error)
            and row.completed_at_ms is not None
            and max(owner.started_at_ms, row.at_ms) <= row.completed_at_ms <= now_ms]
        key = entry.root.session_id
        if not rows:
            self.entries.pop(key, None)
            return
        row = max(rows, key=lambda row: (row.completed_at_ms, row.event_id))
        card = owner._card(entry, None, now_ms, representative=row)
        self.entries[key] = (entry.generation, entry.root.provenance, card)
        ranked = sorted(self.entries, key=lambda key: self.rank(self.entries[key][2]), reverse=True)
        self.entries = {key: self.entries[key] for key in ranked[:5]}

    @staticmethod
    def rank(card):
        return (card.rows[0].prompt.completed_at_ms, card.session_id, card.rows[0].prompt.event_id)

    def project(self, owner, now_ms):
        cards = []
        for key, (generation, provenance, card) in tuple(self.entries.items()):
            entry = owner.sessions.get(key)
            if entry is None or entry.root.provenance != provenance:
                del self.entries[key]
                continue
            if (owner._focals(entry, now_ms) or (key in owner.active_candidates
                    and entry.verified_generation != entry.generation)):
                continue  # Existing running/terminal-grace presentation wins.
            if (entry.generation == generation and entry.verified_generation == generation
                    and entry.capture is not None and entry.capture.authoritative and not entry.capture.retained):
                row = next((row for row in entry.capture.rows if row.event_id == card.rows[0].prompt.event_id), None)
                if row is not None:
                    card = owner._card(entry, None, now_ms, representative=row)
            if (entry.verified_generation != entry.generation or entry.source_status.failed_at is not None
                    or entry.history_status.failed_at is not None):
                card = replace(card, state="refreshing")
            cards.append(card)
        # Keep the small evidence set for a later stale baseline, but hand off
        # atomically to the certified canonical population in this publication.
        return () if owner.history.state == "observed" else tuple(sorted(cards, key=self.rank))
