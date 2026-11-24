"""Web Watch owns these samples; archive reads and writes use its history lane."""
from collections import Counter
from decimal import Decimal, InvalidOperation
import logging
import sqlite3

from src.application.projection import identity
from src.application.quota_capacity import CapacitySample, capacity_candidate, capacity_selection, compatibility, quota_capacity_key
from src.cache.web_archive import ArchiveFact


LOG = logging.getLogger(__name__)
DOMAIN = "quota-capacity/1"
PARTITION = "account-capacity"
WRITE_INTERVAL_MS = 60_000


def read_samples(archive):
    try:
        archive.initialize()
        samples = {}
        for key, fact in archive.history_rows(DOMAIN):
            if fact.partition != PARTITION:
                continue
            try:
                value = fact.value
                capacity, fraction = Decimal(value["capacity"]), Decimal(value["fraction_used"])
                reset, match, pricing = value["reset_ms"], value["compatibility"], value["pricing"]
                if (not capacity.is_finite() or capacity <= 0 or abs(capacity.adjusted()) > 100
                        or not fraction.is_finite() or not 0 < fraction <= 1
                        or type(reset) is not int or not 0 < fact.observed_ms < reset
                        or not isinstance(match, str) or not isinstance(pricing, str)):
                    continue
            except (KeyError, InvalidOperation, TypeError, ValueError):
                continue
            previous = samples.get(key)
            if previous is None or previous.observed_ms < fact.observed_ms:
                samples[key] = CapacitySample(capacity, match, reset, fact.observed_ms, pricing, fraction)
        return samples
    except (sqlite3.Error, OSError):
        LOG.warning("quota_capacity_archive_read_unavailable")
        return None


def write_samples(archive, samples):
    written = {}
    for key, sample in samples.items():
        value = dict(capacity=str(sample.capacity), compatibility=sample.compatibility,
                     reset_ms=sample.reset_ms, pricing=sample.pricing, fraction_used=str(sample.fraction_used))
        fact = ArchiveFact(identity(value), sample.observed_ms, value)
        try:
            if archive.publish(PARTITION, DOMAIN, {key: fact}):
                written[key] = sample
        except (sqlite3.Error, OSError):
            LOG.warning("quota_capacity_archive_write_unavailable")
    return written


class QuotaCapacityHistory:
    """Keep one accepted sample per quota, with bounded, coalesced archive work."""

    def __init__(self, archive, pool):
        self.archive, self.pool = archive, pool
        self.samples = self.written = None
        self.pending = None
        self.retry_ms = 0
        self.job = pool.submit(read_samples, archive)

    def _collect(self, now_ms):
        if self.job is None or not self.job.done():
            return
        result = self.job.result()
        self.job = None
        if self.samples is None:
            if result is None:
                self.retry_ms = now_ms + WRITE_INTERVAL_MS
            else:
                self.samples, self.written = result, dict(result)
        else:
            self.written.update(result)
            if len(result) != self.pending:
                self.retry_ms = now_ms + WRITE_INTERVAL_MS
            self.pending = None

    def _write_due(self, *, flush=False):
        due = {}
        for key, sample in self.samples.items():
            previous = self.written.get(key)
            if (previous is None or previous != sample and
                    (flush or previous.compatibility != sample.compatibility or previous.reset_ms != sample.reset_ms
                     or sample.observed_ms - previous.observed_ms >= WRITE_INTERVAL_MS)):
                due[key] = sample
        return due

    def project(self, accounts, histories, now_ms):
        self._collect(now_ms)
        if self.samples is None:
            if self.job is None and now_ms >= self.retry_ms:
                self.job = self.pool.submit(read_samples, self.archive)
            return {}
        quotas = [(key, item.account, quota) for item in accounts for quota in item.account.quotas
                  if (key := quota_capacity_key(item.account, quota)) is not None]
        counts = Counter(key for key, _, _ in quotas)
        offers = {}
        for key, account, quota in quotas:
            if counts[key] != 1:
                continue
            match = compatibility(account, quota)
            saved = self.samples.get(key)
            candidate = (capacity_candidate(account, quota, histories, match, now_ms)
                         if saved is None or account.fetched_at_ms > saved.observed_ms else None)
            offer, updated = capacity_selection(saved, candidate, match, quota, account.fetched_at_ms, now_ms)
            if offer is not None:
                offers[key] = offer
            if updated is not None:
                self.samples[key] = updated
        if self.job is None and now_ms >= self.retry_ms and (due := self._write_due()):
            self.pending = len(due)
            self.job = self.pool.submit(write_samples, self.archive, due)
        return offers

    def flush(self):
        if self.samples is None:
            return
        # The same pool orders final writes after any in-flight publication.
        if due := self._write_due(flush=True):
            self.pool.submit(write_samples, self.archive, due)
