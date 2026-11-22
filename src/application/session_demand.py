"""Replaceable, bounded browser hints; every caller holds the catalog lock."""
from dataclasses import dataclass


VISIBLE_HINT_LIMIT = 8
MAX_TAB_LEASES = 16
LEASE_SECONDS = 30


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

    def _current(self, now):
        for tab, lease in tuple(self._leases.items()):
            if now >= lease.expires:
                del self._leases[tab]
        return self._leases

    def replace(self, scope, tab, sequence, keys, now):
        if scope != self._scope:
            self._scope = scope
            self._leases.clear()
        leases = self._current(now)
        prior = leases.get(tab)
        if (prior is None and len(leases) >= MAX_TAB_LEASES
                or prior is not None and sequence <= prior.sequence):
            return 0
        # Renewing the same viewport must not re-admit already consumed work.
        pending = keys if prior is None or prior.keys != keys else prior.pending
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
                for offered in leases.values():
                    if key in offered.pending:
                        offered.pending = tuple(item for item in offered.pending if item != key)
                return key
        return None
