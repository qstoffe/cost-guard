"""Coalesced local principal proof, independent of provider quota and OpenCode history."""
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Thread

from src.runtime_errors import recoverable, recovered

CHECK_SECONDS = 5
PROOF_MS = 12_000


@dataclass(frozen=True, slots=True)
class IdentityDeadline:
    monotonic: float
    wall_ms: int

    def active(self, monotonic, wall_ms):
        return monotonic < self.monotonic and wall_ms < self.wall_ms


class AccountArchiveIdentity:
    def __init__(self, target, publish, observe):
        self.target = target
        self.publish = publish
        self.observe = observe
        self._results = Queue(maxsize=1)
        self._checking = False
        self._context = None
        self._generation = 0
        self._due = float("-inf")
        self._expires = None

    def tick(self, discovery, now, wall):
        target = self.target()
        adapter = discovery.archive_adapter if discovery.archive_eligible else None
        context = target, adapter
        if context != self._context:
            self._context = context
            self._generation += 1
            self._expires = None
            self._due = now
            if target is not None:
                self.publish(target, None, None)
        try:
            generation, account, expires = self._results.get_nowait()
        except Empty:
            pass
        else:
            self._checking = False
            if generation == self._generation and target is not None and self.target() == target:
                self._expires = expires if account is not None and expires.active(now, wall) else None
                self.observe(adapter[0], account, self._expires)
                self.publish(target, account if self._expires is not None else None, self._expires)
        if self._expires is not None and not self._expires.active(now, wall):
            self._expires = None
            self.publish(target, None, None)
        if target is not None and adapter is not None and not self._checking and now >= self._due:
            self._checking = True
            self._due = now + CHECK_SECONDS
            expires = IdentityDeadline(now + PROOF_MS / 1000, wall + PROOF_MS)
            Thread(target=self._read, args=(adapter[1], self._generation, expires),
                   name="cost-guard-account-identity", daemon=True).start()

    def _read(self, provider, generation, expires):
        try:
            account = provider.archive_identity()
        except (OSError, ValueError):
            account = None
        except Exception as exc:
            recoverable(exc, "account-archive-identity")
            account = None
        else:
            recovered("account-archive-identity")
        self._results.put_nowait((generation, account, expires))
