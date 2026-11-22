"""Replaceable, bounded browser hints; every caller holds the catalog lock."""
from dataclasses import dataclass


VISIBLE_HINT_LIMIT = 8
MAX_TAB_LEASES = 16
LEASE_SECONDS = 30
RECENT_SECONDS = 15


@dataclass(slots=True)
class _Lease:
    sequence: int
    expires: float
    keys: tuple[str, ...]
    pending: tuple[str, ...]


class SessionDemand:
    def __init__(self):
        self._scope = None
        self._leases = {}
        self._recent = {}

    def _current(self, now):
        for tab, lease in tuple(self._leases.items()):
            if now >= lease.expires:
                del self._leases[tab]
        for key, deadline in tuple(self._recent.items()):
            if now >= deadline:
                del self._recent[key]
        return self._leases

    def replace(self, scope, tab, sequence, keys, now, *, remember=False, joined=None):
        if scope != self._scope:
            self._scope = scope
            self._leases.clear()
            self._recent.clear()
        leases = self._current(now)
        prior = leases.get(tab)
        if (prior is None and len(leases) >= MAX_TAB_LEASES
                or prior is not None and sequence <= prior.sequence):
            return 0
        # Renewing the same viewport must not re-admit already consumed work.
        pending = keys if prior is None or prior.keys != keys else prior.pending
        if joined is not None:
            pending = tuple(key for key in pending if key != joined)
        if prior is not None and remember:
            # Formerly visible is lower priority, not queue cancellation or
            # a reason to reacquire an already consumed foreground root.
            self._recent.update((key, now + RECENT_SECONDS) for key in prior.pending if key not in keys)
            while len(self._recent) > VISIBLE_HINT_LIMIT:
                del self._recent[next(iter(self._recent))]
        for key in keys:
            self._recent.pop(key, None)
        leases[tab] = _Lease(sequence, now + LEASE_SECONDS, keys, pending)
        return len(pending)

    def ready(self, scope, now):
        return scope == self._scope and any(lease.pending for lease in self._current(now).values())

    def take(self, scope, now):
        if scope != self._scope:
            return None
        leases = self._current(now)
        for tab, lease in tuple(leases.items()):
            if lease.pending:
                key = lease.pending[0]
                # Give the next visible document a turn; shared demand is one job.
                leases[tab] = leases.pop(tab)
                self.consume(scope, key, now)
                return key
        return None

    def consume(self, scope, key, now):
        if scope == self._scope:
            for lease in self._current(now).values():
                if key in lease.pending:
                    lease.pending = tuple(item for item in lease.pending if item != key)
            self._recent.pop(key, None)

    def nearby(self, scope, now):
        if scope != self._scope:
            return False
        self._current(now)
        return bool(self._recent)

    def take_nearby(self, scope, now):
        if self.nearby(scope, now):
            key = next(reversed(self._recent))
            del self._recent[key]
            return key
        return None
