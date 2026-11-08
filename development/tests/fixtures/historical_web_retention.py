"""Consistent disposable cache seeds and numeric persistent-fixture observations.

Only the explicitly supplied synthetic product cache is replaced. Registration,
configuration, source process and evidence directories are never seed contents.
"""
import hashlib
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3


def counter_delta(before, after):
    requests = {key: after['requests'].get(key, 0) - before['requests'].get(key, 0)
        for key in before['requests'].keys() | after['requests'].keys()}
    result = dict(requests=requests, bytes=after['bytes'] - before['bytes'],
        cpu_seconds=after['cpu_seconds'] - before['cpu_seconds'])
    if any(value < 0 for value in requests.values()) or result['bytes'] < 0 or result['cpu_seconds'] < 0:
        raise RuntimeError('fixture_counter_reset')
    return result


class CacheSeed:
    def __init__(self, product_data, seed):
        self.cache = (Path(product_data) / 'cache').resolve()
        self.seed = Path(seed).resolve()
        self.fingerprint = None
        if self.seed == self.cache or self.seed.is_relative_to(self.cache) or self.cache.is_relative_to(self.seed):
            raise ValueError('fixture_seed_overlaps_cache')

    def capture(self):
        """Call after normal host/child closure; SQLite backup includes committed WAL."""
        databases = tuple(self.cache.rglob('*.sqlite3'))
        if not databases:
            raise RuntimeError('fixture_seed_has_no_database')
        shutil.copytree(self.cache, self.seed, ignore=shutil.ignore_patterns('*.sqlite3', '*-wal', '*-shm'))
        entries = {}
        for database in databases:
            target = self.seed / database.relative_to(self.cache)
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(target)) as destination:
                    source.backup(destination)
                    if destination.execute('PRAGMA quick_check').fetchone() != ('ok',):
                        raise RuntimeError('fixture_seed_integrity_failed')
                    if destination.execute("SELECT 1 FROM sqlite_master WHERE name='cache_entries'").fetchone():
                        for namespace, count in destination.execute('SELECT namespace, COUNT(*) FROM cache_entries GROUP BY namespace'):
                            entries[namespace] = entries.get(namespace, 0) + count
        self.fingerprint = self._fingerprint(self.seed)
        return dict(**self.fingerprint, entries_by_namespace=entries)

    def restore(self):
        if self.fingerprint is None:
            raise RuntimeError('fixture_seed_not_captured')
        # This is only the owned disposable fixture cache, not the product tree,
        # registration, arbitrary run root or another worker's state.
        if self.cache.exists():
            shutil.rmtree(self.cache)
        shutil.copytree(self.seed, self.cache)
        actual = self._fingerprint(self.cache)
        if actual != self.fingerprint:
            raise RuntimeError('fixture_seed_restore_mismatch')
        return actual

    @staticmethod
    def _fingerprint(root):
        digest, total, count = hashlib.sha256(), 0, 0
        for path in sorted(root.rglob('*')):
            if path.is_file():
                value = path.read_bytes()
                digest.update(path.relative_to(root).as_posix().encode())
                digest.update(value)
                total += len(value)
                count += 1
        return dict(sha256=digest.hexdigest(), bytes=total, files=count)
