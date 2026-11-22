"""Route demand and cooperative turn selection for managed display work."""

PROJECTIONS = (
    ("mix", "token-mix"),
    ("stats", "ai-stats"),
    ("models", "models"),
    ("accounts", "accounts"),
)
CATALOG_INTERLEAVE = 3
VISIBLE_BURST = 2


class ProjectionTurns:
    """Admit at executor boundaries, preserving a turn for acquisition and unseen views."""

    def __init__(self):
        self._history = CATALOG_INTERLEAVE
        self._visible_run = 0
        self._general_cursor = 0
        self._visible_cursor = 0

    def choose(self, due, visible, *, history_pending):
        preferred = due.intersection(kind for kind, section in PROJECTIONS if section in visible)
        threshold = 1 if preferred else CATALOG_INTERLEAVE
        if history_pending and (self._history < threshold or not due):
            self._history = min(CATALOG_INTERLEAVE, self._history + 1)
            return None
        if not due:
            return None
        self._history = 0
        if preferred and self._visible_run < VISIBLE_BURST:
            self._visible_run += 1
            kind, self._visible_cursor = self._take(preferred, self._visible_cursor)
        else:
            self._visible_run = 0
            kind, self._general_cursor = self._take(due, self._general_cursor)
        return kind

    @staticmethod
    def _take(due, cursor):
        for offset in range(len(PROJECTIONS)):
            index = (cursor + offset) % len(PROJECTIONS)
            kind = PROJECTIONS[index][0]
            if kind in due:
                return kind, (index + 1) % len(PROJECTIONS)
        raise AssertionError("empty projection turn")
