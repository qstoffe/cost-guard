"""Cache-only Sessions query model; cannot admit work or read OpenCode."""
from dataclasses import asdict, dataclass
import re
import time

from src.cache.display_history import DisplayHistory, EMPTY_HISTORY_EVIDENCE, FIELD_EVIDENCE_BITS, SORT_COLUMNS

from .contracts import record
from .display import with_display
from .session_catalog_scope import PAGE_SIZE, PERIODS, catalog_window


_SCALAR_FIELDS = dict(activity="activity_ms", model="model", ccost="ccost", prompts="prompts",
                      duration="duration_ms", ctx="context_tokens")
_SESSION_ID = re.compile(r"[A-Za-z0-9_-]{1,200}")


def field_states(row, values):
    def state(name, value):
        evidence = row.field_evidence
        examined = evidence & FIELD_EVIDENCE_BITS[_SCALAR_FIELDS[name]]
        if value is not None:
            return "as-of" if examined or not row.source_present or row.running else "retained"
        if examined and name in ("activity", "model", "ctx") and evidence & EMPTY_HISTORY_EVIDENCE:
            return "complete_empty_history"
        if not row.source_present:
            return "source-history-missing"
        if examined and name in ("model", "ctx", "duration"):
            return "source-field-unavailable"
        return "pending"

    return {name: state(name, value) for name, value in values.items()}


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
    coverage_supported: bool = False

    def detail(self, *, session_id, offset=0):
        if (not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id)
                or type(offset) is not int or not 0 <= offset <= 1_000_000 or offset % PAGE_SIZE):
            raise ValueError("invalid_session_detail_query")
        generation, header, count, rows = self.history.session_detail_page(
            self.source, session_id, limit=PAGE_SIZE, offset=offset)
        summary = None
        status = "pending"
        if header is not None:
            title, ccost, prompts, context, context_detail, present, known, current = header
            summary = with_display(record(title=title, ccost=ccost, prompts=prompts, context_tokens=context,
                context_detail=context_detail, source_present=bool(present)), self.timezone_id).to_json()
            status = "as-of" if known and present and current else "retained" if known else (
                "source-history-missing" if not present else "pending")
        displayed = [with_display(record(**asdict(row), at_ms=row.start_ms, ccost=row.observed_cost,
            unresolved_cost=not row.cost_complete, incoming_context_tokens=row.context_tokens,
            incoming_context_ccost=row.incoming_cost, extra_ccost=row.extra_cost,
            token_mix_percent=tuple(map(int, row.mix.split(","))) if row.mix else None), self.timezone_id).to_json()
            for row in rows]
        return dict(binding=self.binding, generation=generation, session_id=session_id, offset=offset,
                    size=PAGE_SIZE, cached_total=count, summary=summary, history_coverage=status, rows=displayed)

    def page(self, *, period="today", sort="activity", direction=-1, offset=0, known=None, now_ms=None):
        if (period not in PERIODS or sort not in SORT_COLUMNS or type(direction) is not int
                or direction not in (-1, 1) or type(offset) is not int
                or not 0 <= offset <= 1_000_000 or offset % PAGE_SIZE):
            raise ValueError("invalid_sessions_query")
        now_ms = wall_ms() if now_ms is None else now_ms
        window = catalog_window(period, self.timezone_id, now_ms)
        # All-time includes unknown clocks; constrained periods use qualified
        # event clocks and never admit a source report to answer the query.
        end = None if window.start_ms is None else window.end_ms
        scope = dict(period=period, sort=sort, direction=direction, offset=offset,
                     size=PAGE_SIZE, binding=self.binding, timezone_id=window.timezone_id,
                     start_ms=window.start_ms, end_ms=end)
        if known is not None and self._same_query(known, scope):
            changes = self.history.session_changes(self.source, known["generation"])
            # Time advances even when no rows have been written. If a known
            # future clock has crossed the upper bound, issue a new page read.
            if (not self.history.has_running_snapshot(self.source, self.binding)
                    and not changes.affects(known["generation"], start_ms=window.start_ms, end_ms=end)
                    and (end == known["end_ms"] or window.start_ms is not None
                         and end > known["end_ms"]
                         and not self.history.has_session_clock(self.source, known["end_ms"], end))):
                return dict(**scope, generation=changes.generation, unchanged=True)
        result = self.history.session_page(self.source, sort=sort, direction=direction, limit=PAGE_SIZE,
                                           offset=offset, start_ms=window.start_ms, end_ms=end,
                                           live_binding=self.binding, now_ms=now_ms)
        rows = []
        for row in result.rows:
            values = {"model": row.model, "ccost": row.ccost, "prompts": row.prompts,
                      "duration": row.duration_ms, "ctx": row.context_tokens,
                      "activity": row.activity_ms if row.activity_ms is not None else row.prompt_started_ms}
            states = field_states(row, values)
            tokens = with_display(record(ccost=row.ccost, duration_ms=row.duration_ms, context_tokens=row.context_tokens),
                                  window.timezone_id, now_ms).to_json()
            rows.append(dict(session_id=row.session_id, title=row.title, activity_ms=row.activity_ms, model=row.model,
                               model_help=row.model_help, has_model_details=bool(row.has_model_details),
                               running=row.running,
                               activity_origin=row.activity_origin, prompt_started_ms=row.prompt_started_ms,
                               catalog_activity_ms=(row.catalog_activity_ms if row.source_present
                                   and row.activity_origin is None and row.activity_ms is None else None),
                              ccost=row.ccost, prompts=row.prompts, duration_ms=row.duration_ms,
                               context_tokens=row.context_tokens, context_detail=row.context_detail,
                               source_present=row.source_present, fields=states,
                              display=tokens["display"], display_units=tokens.get("display_units")))
        # Cached membership/count is not historical source completeness.
        if result.coverage is not None:
            coverage = "as-of" if result.coverage.covers(window.start_ms) else "pending"
        else:
            coverage = "pending" if self.coverage_supported else "unknown"
        return dict(**scope, generation=result.generation, cached_total=result.total, rows=rows,
                    history_coverage=coverage,
                    running_refresh_ms=(result.running_expires_ms - now_ms if result.running_expires_ms else None))

    @staticmethod
    def _same_query(known, scope):
        keys = {"binding", "generation", "start_ms", "end_ms", "period", "sort", "direction", "offset"}
        if (not isinstance(known, dict) or set(known) != keys or type(known["generation"]) is not int
                or known["generation"] < 0 or any(known[key] is not None and type(known[key]) is not int
                                                     for key in ("start_ms", "end_ms"))
                or type(known["direction"]) is not int or type(known["offset"]) is not int):
            raise ValueError("invalid_sessions_cursor")
        return ((scope["end_ms"] is None) == (known["end_ms"] is None)
                and all(known[key] == scope[key] for key in ("binding", "start_ms", "period", "sort", "direction", "offset")))
