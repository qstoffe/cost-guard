"""Cache-only Sessions query model; cannot admit work or read OpenCode."""
from dataclasses import dataclass
import time

from src.cache.display_history import DisplayHistory, SORT_COLUMNS

from .session_catalog_scope import PAGE_SIZE, PERIODS, catalog_window


def wall_ms():
    return int(time.time() * 1000)


@dataclass(frozen=True, slots=True)
class CachedSessionViews:
    # The Web composition root supplies the authenticated source binding.
    # Browser-controlled values never select the archive identity.
    history: DisplayHistory
    source: str
    timezone_id: str
    binding: str = ""

    def page(self, *, period="today", sort="activity", direction=-1, offset=0, now_ms=None):
        if (period not in PERIODS or sort not in SORT_COLUMNS or type(direction) is not int
                or direction not in (-1, 1) or type(offset) is not int
                or not 0 <= offset <= 1_000_000 or offset % PAGE_SIZE):
            raise ValueError("invalid_sessions_query")
        window = catalog_window(period, self.timezone_id, wall_ms() if now_ms is None else now_ms)
        # All-time includes unknown clocks; constrained periods use qualified
        # event clocks and never admit a source report to answer the query.
        end = None if window.start_ms is None else window.end_ms
        result = self.history.session_page(self.source, sort=sort, direction=direction, limit=PAGE_SIZE,
                                           offset=offset, start_ms=window.start_ms, end_ms=end)
        rows = []
        for row in result.rows:
            values = {"model": row.model, "ccost": row.ccost, "prompts": row.prompts,
                      "duration": row.duration_ms, "ctx": row.context_tokens, "activity": row.activity_ms}
            states = {name: "as-of" if value is not None else "pending" if row.source_present else "source-history-missing"
                      for name, value in values.items()}
            rows.append(dict(session_id=row.session_id, title=row.title, activity_ms=row.activity_ms, model=row.model,
                             ccost=row.ccost, prompts=row.prompts, duration_ms=row.duration_ms,
                             context_tokens=row.context_tokens, source_present=row.source_present, fields=states))
        # Cached membership/count is not historical source completeness.
        return dict(period=period, sort=sort, direction=direction, offset=offset, size=PAGE_SIZE, binding=self.binding,
                    generation=result.generation, cached_total=result.total, rows=rows,
                    timezone_id=window.timezone_id)
