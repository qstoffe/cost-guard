"""Select a small Live preview cohort without walking the historical roster each tick."""
from bisect import bisect_left
from heapq import merge, nsmallest
from itertools import islice


def _dated(index, now_ms):
    end = bisect_left(index, (now_ms + 1,))
    while end:
        clock = index[end - 1][0]
        start = bisect_left(index, (clock,), 0, end)
        for position in range(start, end):
            yield -clock, index[position][1]
        end = start


def preview_keys(catalog, excluded, now_ms, limit):
    def available(key):
        return key not in excluded and not catalog._running(key)

    def scalar():
        for key, row in catalog.rows.items():
            if available(key) and catalog._activity_current(key):
                clock = row.last_activity_ms
                yield -(clock if type(clock) is int and 0 < clock <= now_ms else 0), key

    def metadata():
        for rank, key in _dated(catalog.activity_index, now_ms):
            if available(key) and not catalog._activity_current(key):
                yield rank, key
        for key in catalog.preview_roots:
            clock = catalog.activity.get(key)
            if (not (type(clock) is int and 0 < clock <= now_ms)
                    and available(key) and not catalog._activity_current(key)):
                yield 0, key

    best = nsmallest(limit, scalar())
    if not best:
        return tuple(key for _, key in islice(metadata(), limit))
    return tuple(key for _, key in islice(merge(best, metadata()), limit))
