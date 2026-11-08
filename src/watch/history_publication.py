"""Atomic Earlier membership proof over the existing bounded card acquisitions.

The coordinator lifetime pins one selected source. Revision-keyed scalar coverage
survives capture eviction; no metadata timestamp can exclude an unread root.
"""
from uuid import uuid4


class HistoryPublication:
    def __init__(self):
        self.scope = uuid4().hex
        self.epoch = 0
        self.catalog_revision = 0
        self.verified_at_ms = None
        self.cards = ()
        self.signature = None
        self.state = "loading"
        self.checked = self.total = 0
        self.cause = ""

    def project(self, owner, now_ms):
        entries = owner.sessions
        self.total = len(entries)
        self.checked = 0
        failures = []
        for entry in entries.values():
            if entry.source_status.failed_at is None and entry.history_status.failed_at is None:
                self.checked += entry.verified_generation == entry.generation
            elif (entry.source_status.state(retained=self.epoch > 0, confirming_initial=True) == "unavailable"
                    or entry.history_status.state(retained=self.epoch > 0, confirming_initial=True) == "unavailable"):
                failures.append(entry)
        self.cause = failures[0].failure_code if failures else ""
        ids = owner._ranked_ids(now_ms)
        ready = self.checked == self.total and all(entries[key].capture is not None for key in ids)
        if ready:
            cards = tuple(sorted((owner._card(entries[key], None, now_ms) for key in ids),
                key=lambda card: (card.rows[0].prompt.completed_at_ms or 0 if card.rows else 0,
                    card.session_id, card.rows[0].prompt.event_id if card.rows else "")))
            signature = (owner.catalog_revision, owner.evidence_revision, ids)
            if signature != self.signature:
                self.signature = signature
                self.epoch += 1
                self.catalog_revision = owner.catalog_revision
                self.verified_at_ms = now_ms
            # Independent cost enrichment is not a fresh source verification.
            self.cards = cards
            self.state = "observed"
        else:
            # Removal/resumption is terminal invalidation, not a refreshing card.
            self.cards = tuple(card for card in self.cards if card.session_id in entries
                and not owner._focals(entries[card.session_id], now_ms)
                and not (card.session_id in owner.active_candidates
                    and entries[card.session_id].verified_generation != entries[card.session_id].generation))
            self.state = "unavailable" if failures else "refreshing" if self.epoch else "loading"
        return self.cards
