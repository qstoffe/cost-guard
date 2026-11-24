"""Writer-owned newest-first work queue with a separate retry clock."""
from heapq import heappop, heappush


class HistoryQueue:
    def __init__(self):
        self.clear()

    def clear(self):
        self._ready = []
        self._delayed = []
        self._entries = {}
        self._sequence = 0

    def schedule(self, root, activity, due, now):
        self._sequence += 1
        entry = (-activity, root, self._sequence)
        self._entries[root] = entry
        if due <= now:
            heappush(self._ready, entry)
        else:
            heappush(self._delayed, (due, entry))

    def remove(self, root):
        self._entries.pop(root, None)

    def __bool__(self):
        return bool(self._entries)

    def next(self, now, *, take=False):
        while self._delayed and self._delayed[0][0] <= now:
            _, entry = heappop(self._delayed)
            if self._entries.get(entry[1]) == entry:
                heappush(self._ready, entry)
        while self._ready:
            entry = self._ready[0]
            root = entry[1]
            if self._entries.get(root) != entry:
                heappop(self._ready)
                continue
            if take:
                heappop(self._ready)
                self.remove(root)
            return root
        return None
