"""Full-screen/redirect-safe rendering for Watch projections."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import os
import sys
from typing import Mapping, TextIO

from src.version import DISPLAY_VERSION, PRODUCT_NAME
from src.numbers import ccost_amount
from src.analysis.timezones import format_local_timestamp, resolve_timezone
from src.watch.models import ToolObservation, WatchProjection, WatchRow, WatchSessionSubtotal

from .terminal import AnsiStyler, Column, StyledText, fit, render_table, single_line, wrap_prose
from .terminal import terminal_content_width
from .accounts import capacity_block, compact_label_fits, quota_label
from .token_mix import prompt_scope, token_mix_lines, watch_total_lines
from src.analysis.context import PriceWarningSeverity
from .context_warnings import WARNING_ROLE, context_warning_text, warning_cost_suffix, warning_explanation_lines
from .pricing_notices import pricing_notice_lines
from .watch_activity import BASE_ROLE, skill_summary_segments, status_segments, tool_summary_segments
from .duration import duration_text as _duration

_WATCH_COLUMNS = (
    Column("Session / prompt", fixed_width=35),
    Column("Model / effort", fixed_width=25),
    Column("CCost", True, fixed_width=7),
    Column("Calls", True, fixed_width=5),
    Column("Duration", True, fixed_width=8),
    Column("Δctx → Next Ictx    ", fixed_width=20),
)
_CONTEXT_DELTA_WIDTH = 5
_CONTEXT_NEXT_WIDTH = 9
# Session headers span Session/prompt and Model/effort, including their divider.
_HEADER_WIDTH = _WATCH_COLUMNS[0].fixed_width + 3 + _WATCH_COLUMNS[1].fixed_width
EARLIER_LABEL = "[Earlier]"
EARLIER_EXPLANATION = "Session activity before Watch started; excluded from Token Mix and Watch total CCost."


def _current_local_date(timezone_id: str) -> date:
    """Read the render-time date in Watch's configured timezone."""
    return datetime.now(timezone.utc).astimezone(resolve_timezone(timezone_id)).date()


def _truncate_label(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    return text[:width] if width <= 3 else text[:width - 3] + "..."


def _fit_effort(effort: str, width: int) -> str:
    if len(effort) <= width:
        return effort
    if width == 5:
        return "(...)"
    if width > 5:
        return "(" + effort[1:-1][:width - 5] + "...)"
    return _truncate_label(effort, width)


def _fit_model_effort(label: str, width: int) -> str:
    """Fit model and trailing effort independently, preserving their identity cues."""
    if len(label) <= width:
        return label
    opening = label.rfind(" (")
    if opening <= 0 or not label.endswith(")"):
        return _truncate_label(label, width)
    model, effort = label[:opening], label[opening + 1:]
    if "(" in effort[1:-1] or ")" in effort[1:-1] or width < 3:
        return _truncate_label(label, width)

    component_width = width - 1
    minimum_model = min(len(model), 4)
    minimum_effort = min(len(effort), 5)
    if component_width >= minimum_model + minimum_effort:
        model_width = min(len(model), max(minimum_model, component_width * 2 // 3))
        effort_width = min(len(effort), component_width - model_width)
        if effort_width < minimum_effort:
            effort_width = minimum_effort
            model_width = component_width - effort_width
    else:
        model_width = max(1, component_width * 2 // 3)
        effort_width = component_width - model_width

    model_width = min(len(model), model_width)
    effort_width = min(len(effort), effort_width)
    remaining = component_width - model_width - effort_width
    model_extra = min(remaining, len(model) - model_width)
    model_width += model_extra
    effort_width += min(remaining - model_extra, len(effort) - effort_width)
    return _truncate_label(model, model_width) + " " + _fit_effort(effort, effort_width)


def _model_effort_cell(label: str) -> str:
    width = _WATCH_COLUMNS[1].fixed_width or 0
    return _fit_model_effort(label, width)


def _tokens(value: int | None, *, signed: bool = False, approximate: bool = False) -> str:
    """Retain the v77 Watch whole-k context display contract."""
    if value is None:
        return "N/A"
    if signed and abs(value) < 500:
        text = "0k"
    else:
        magnitude = abs(value)
        thousands = int((Decimal(magnitude) / Decimal(1000)).to_integral_value(rounding=ROUND_HALF_UP))
        if magnitude > 0 and thousands < 1:
            thousands = 1
        text = f"{thousands}k"
        if value < 0:
            text = "-" + text
        elif signed and value > 0:
            text = "+" + text
    return ("~" if approximate and text != "N/A" else "") + text


def _fit_context_tokens(value: int | None, width: int, *, signed: bool = False,
                        approximate: bool = False) -> str:
    """Bound context diagnostics without losing their sign or unit."""
    text = _tokens(value, signed=signed, approximate=approximate)
    if len(text) <= width or value is None:
        return text
    sign = "-" if value < 0 else "+" if signed else ""
    prefix = "~" if approximate else ""
    for scale, suffix in ((1_000_000, "M"), (1_000_000_000, "B"), (1_000_000_000_000, "T"),
                          (1_000_000_000_000_000, "P")):
        scaled = Decimal(abs(value)) / Decimal(scale)
        places = 1 if scaled < 10 else 0
        rounded = scaled.quantize(Decimal("0.1") if places else Decimal("1"), rounding=ROUND_HALF_UP)
        number = format(rounded, ".1f" if places else ".0f")
        candidate = f"{prefix}{sign}{number}{suffix}"
        if len(candidate) <= width:
            return candidate
    magnitude = abs(value)
    exponent = len(str(magnitude)) - 1
    for places in (1, 0):
        scaled = Decimal(magnitude) / (Decimal(10) ** exponent)
        rounded = scaled.quantize(Decimal("0.1") if places else Decimal("1"), rounding=ROUND_HALF_UP)
        if rounded >= 10:
            exponent += 1
            rounded /= 10
        number = format(rounded, ".1f" if places else ".0f")
        candidate = f"{prefix}{sign}{number}e{exponent}"
        if len(candidate) <= width:
            return candidate
    return f"{sign}1e{exponent}"


def _context_cell(row: WatchRow, row_role: str | None, warning_number: int | None = None) -> StyledText:
    prompt = row.prompt
    warning_role = row_role
    if row.next_context_warning_severity != PriceWarningSeverity.NONE:
        warning_role = WARNING_ROLE
    delta = prompt.watch_delta_context_tokens
    next_tokens = prompt.watch_next_context_tokens
    delta_text = _fit_context_tokens(delta, _CONTEXT_DELTA_WIDTH, signed=True)
    next_text = _fit_context_tokens(next_tokens, _CONTEXT_NEXT_WIDTH, approximate=True)
    parts: list[tuple[str, str | None]] = [
        (delta_text.ljust(_CONTEXT_DELTA_WIDTH), row_role),
        ("→ ", row_role),
        (next_text.rjust(_CONTEXT_NEXT_WIDTH), warning_role),
    ]
    if warning_number is not None:
        marker = f"*{warning_number}"
        marker = f" {marker}" if len(marker) <= 3 else marker
        if len(marker) > 4:
            marker = "*99+"
        parts.append((marker, WARNING_ROLE))
    return StyledText(tuple(parts))


def _empty_row(text: str) -> tuple[str, ...]:
    """A single placeholder row keeps the table from ending in a double rule."""
    return ("  " + text, "", "", "", "", "")


def _session_subtotal_text(subtotal: WatchSessionSubtotal | None) -> str:
    """Format the projected row subtotal, including unresolved provenance."""
    return "Σ " + ("N/A" if subtotal is None else ccost_amount(subtotal.ccost, unresolved=subtotal.unresolved_cost))


def _warning_explanation(session_id: str, warning: str, rows: tuple[WatchRow, ...]) -> tuple[str, PriceWarningSeverity]:
    """Displayed explanation (with multiplier or Next Ictx CCost range) and severity."""
    warning_row = next((item for item in reversed(rows) if item.session_id == session_id and item.next_context_warning), None)
    if warning_row is None:
        return context_warning_text(warning), PriceWarningSeverity.NONE
    prompt = warning_row.prompt
    low = prompt.watch_next_context_cached_ccost
    high = prompt.watch_next_context_fresh_ccost
    multiplier = prompt.watch_next_context_cost_multiplier
    if low is None and high is None:
        low, high = prompt.next_context_cached_ccost, prompt.next_context_fresh_ccost
    if multiplier is None and not prompt.watch_next_context_warning:
        multiplier = prompt.next_context_cost_multiplier
    suffix = (" " + text) if (text := warning_cost_suffix(multiplier, low, high)) else ""
    return context_warning_text(warning) + suffix, warning_row.next_context_warning_severity


def _warning_groups(projection: WatchProjection) -> list[tuple[list[int], str, PriceWarningSeverity]]:
    """One explanation per identical displayed warning; session markers keep their numbers.

    Identity is the complete displayed text (threshold, explanation and cost
    detail) plus severity, so any meaningful difference stays separate.
    """
    groups: dict[tuple[str, PriceWarningSeverity], list[int]] = {}
    for number, (_row_index, session_id, warning) in enumerate(_active_warning_rows(projection), start=1):
        groups.setdefault(_warning_explanation(session_id, warning, projection.rows), []).append(number)
    return [(numbers, text, severity) for (text, severity), numbers in groups.items()]


def _active_warning_rows(projection: WatchProjection) -> tuple[tuple[int, str, str], ...]:
    """Choose only each displayed session's latest row with a live warning."""
    latest: dict[str, tuple[int, str]] = {}
    for index, row in enumerate(projection.rows):
        if row.next_context_warning:
            latest[row.session_id] = (index, row.next_context_warning)
    return tuple((index, session_id, warning) for session_id, (index, warning) in
                 sorted(latest.items(), key=lambda item: item[1][0]))


class WatchRenderer:
    def __init__(self, config: Mapping[str, object], *, stream: TextIO | None = None, interactive: bool | None = None,
                 terminal_width: int | None = None, started_at_ms: int | None = None) -> None:
        self.config = config
        self.stream = stream or sys.stdout
        if interactive is None:
            interactive = bool(getattr(self.stream, "isatty", lambda: False)()) and not os.environ.get("TERM") == "dumb"
        self.interactive = bool(interactive)
        colors = config.get("colors") if isinstance(config.get("colors"), Mapping) else {}
        self.styler = AnsiStyler(colors, enabled=self.interactive)
        self.timezone_id = str(config.get("timezone") or "Europe/Stockholm")
        self.started_at_ms = int(started_at_ms if started_at_ms is not None else
                                  datetime.now(timezone.utc).timestamp() * 1000)
        self._status_visible = False
        self.terminal_width = terminal_width

    def _content_width(self, *, minimum: int = 40) -> int:
        """Configured test width, otherwise the live terminal's content width."""
        if self.terminal_width is not None:
            return self.terminal_width
        return terminal_content_width(self.stream, minimum=minimum)

    def _write(self, text: str = "") -> None:
        self.stream.write(text + "\n")

    def _supports_arrow(self) -> bool:
        encoding = getattr(self.stream, "encoding", None) or "utf-8"
        try:
            "↳".encode(encoding)
            return True
        except (UnicodeEncodeError, LookupError):
            return False

    def _clear(self) -> None:
        if self.interactive:
            self.stream.write("\x1b[2J\x1b[3J\x1b[H")

    def _watch_heading(self, mode: str, started_at_ms: int) -> str:
        timestamp = format_local_timestamp(started_at_ms, self.timezone_id, "%Y-%m-%d %H:%M:%S")
        return f"{PRODUCT_NAME} {DISPLAY_VERSION} (Watch started: {timestamp}) — {mode}"

    def _watch_title(self, source_label: str, title: str = "Cost Guard Watch", started_at_ms: int = 0) -> str:
        suffix = ""
        prefix = "Cost Guard Watch - "
        if title.startswith(prefix):
            suffix = " — " + title[len(prefix):]
        heading = self._watch_heading("Prompt watch", started_at_ms or self.started_at_ms) + suffix
        source = f"Source: OpenCode {source_label}"
        width = self._content_width()
        complete = heading + " — " + source
        if len(complete) <= width:
            return complete
        return "\n".join(wrap_prose(heading, width) + wrap_prose(source, width))

    @staticmethod
    def _status_text(text: str) -> str:
        value = text or "Watching"
        return value if value.startswith("Watch:") else "Watch: " + value

    def _write_status(self, text: str, *, active: bool, newline: bool) -> None:
        rendered = self.styler.apply(self._status_text(text), "activeRunning" if active else None)
        if newline:
            self._write(rendered)
        else:
            # Full frames end here: erase any old rows below the status cursor.
            self.stream.write(rendered + "\x1b[0J")
        self.stream.flush()
        self._status_visible = True

    def _row_label(self, row: WatchRow) -> str:
        prompt = row.prompt
        marker = (row.marker + " ") if row.marker else "  "
        if prompt.is_compaction:
            return f"  {marker}#{prompt.prompt_number} /compact"
        reason = {"user": "user", "quota_limit": "quota limit", "tool_call_limit": "tool call limit",
                  "step_limit": "step limit", "rate_limit": "rate limit"}.get(prompt.abort_reason)
        prefix = (f"[ABORTED by {reason}] " if reason else "[ABORTED] ") if prompt.aborted else (
            "[ENDED after tool calls] " if prompt.ended_after_tool_calls else "")
        lead = f"  {marker}#{prompt.prompt_number} "
        if prefix:
            # Reserve the full stop label before shortening the expendable preview.
            width = _WATCH_COLUMNS[0].fixed_width
            if len(lead + prefix.rstrip()) > width:
                lead = f"{row.marker + ' ' if row.marker else ''}#{prompt.prompt_number} "
            preview_width = max(0, width - len(lead + prefix))
            return (lead + prefix + fit(single_line(prompt.preview), preview_width)).rstrip()
        return lead + single_line(prompt.preview)

    def _row_style(self, row: WatchRow) -> str | None:
        if row.prompt.aborted:
            return "costQuotaCritical" if row.marker else None
        if row.prompt.watch_error:
            return "costQuotaCritical"
        if row.prompt.in_progress:
            return "watchRunningWarning"
        if row.marker == "✓":
            return "watchRecentCompleted"
        return None

    def _duration_for(self, row: WatchRow, now_ms: int) -> int | None:
        if row.prompt.in_progress:
            return max(row.prompt.duration_ms or 0, now_ms - row.prompt.at_ms)
        return row.prompt.duration_ms

    def _session_header(self, row: WatchRow, *, running: bool, today: date | None) -> StyledText:
        """Merged header with a fixed running prefix and timestamp-first Earlier label."""
        segments: list[tuple[str, str | None]] = (
            [("▶", "watchRunningWarning"), (" ", "watchSessionHeader")]
            if running else [("  ", "watchSessionHeader")]
        )
        if row.session_latest_ms > 0:
            pattern = "%H:%M"
            if row.earlier and today is not None:
                local = datetime.fromtimestamp(row.session_latest_ms / 1000, timezone.utc).astimezone(
                    resolve_timezone(self.timezone_id)
                )
                if local.date() != today:
                    pattern = "%Y-%m-%d %H:%M"
            segments.append((format_local_timestamp(row.session_latest_ms, self.timezone_id, pattern) + " ",
                             "watchSessionHeader"))
        if row.earlier:
            segments.extend(((EARLIER_LABEL, WARNING_ROLE), (" ", "watchSessionHeader")))
        # Checkpoint failures can leave Markdown/CRLF in OpenCode session titles.
        room = _HEADER_WIDTH - sum(len(text) for text, _role in segments)
        title = fit(single_line(row.session_title, "Untitled session"), room).rstrip()
        return StyledText(tuple(segments) + ((title, "watchSessionHeader"),))

    def _table_rows(self, projection: WatchProjection) -> tuple[
        list[tuple[object, ...]], list[tuple[str | None, ...]], dict[int, tuple[str, str, ToolObservation]], list[int]
    ]:
        rows: list[tuple[object, ...]] = []
        styles: list[tuple[str | None, ...]] = []
        activities: dict[int, tuple[str, str, ToolObservation]] = {}
        headers: list[int] = []
        previous_session = None
        running_sessions = {row.session_id for row in projection.rows if row.prompt.in_progress and not row.earlier}
        today = (_current_local_date(self.timezone_id)
                 if any(row.earlier for row in projection.rows) else None)
        warning_numbers = {row_index: number for number, (row_index, _session_id, _warning) in
                           enumerate(_active_warning_rows(projection), start=1)}
        for row_index, row in enumerate(projection.rows):
            if row.session_id != previous_session:
                subtotal = _session_subtotal_text(projection.session_subtotals.get(row.session_id))
                headers.append(len(rows))
                rows.append((self._session_header(row, running=row.session_id in running_sessions, today=today),
                             "", subtotal, "", "", ""))
                styles.append(("watchSessionHeader", None, None, None, None, None))
                previous_session = row.session_id
            prompt = row.prompt
            role = self._row_style(row)
            native_compaction_without_billing = prompt.is_compaction and prompt.calls == 0 and prompt.ccost == 0
            model_label = prompt.watch_model_effort or prompt.model_effort or "N/A"
            warning_number = warning_numbers.get(row_index)
            model_cell = ("" if native_compaction_without_billing and model_label == "N/A" and warning_number is None
                          else _model_effort_cell(model_label))
            rows.append((
                self._row_label(row),
                model_cell,
                "" if native_compaction_without_billing else ccost_amount(prompt.ccost, unresolved=prompt.unresolved_cost),
                "" if native_compaction_without_billing else prompt.calls,
                "" if native_compaction_without_billing and not prompt.in_progress else _duration(self._duration_for(row, projection.now_ms)),
                _context_cell(row, role, warning_number),
            ))
            styles.append((role, role, role, role, role, None))
            if row.tool is not None:
                arrow = "↳" if self._supports_arrow() and self.interactive else "->"
                marker = " " * self._row_label(row).index("#") + arrow
                kinds = ["tools"] + (["skills"] if row.tool.skills else [])
                # Terminal rows keep final statistics only; live status never survives.
                if prompt.in_progress and row.tool.has_status_row:
                    kinds.append("status")
                for kind in kinds:
                    activities[len(rows)] = (kind, marker, row.tool)
                    rows.append((marker, "", "", "", "", ""))
                    styles.append(("watchToolActivity", None, None, None, None, None))
        return rows, styles, activities, headers

    def _activity_line(self, kind: str, marker: str, tool: ToolObservation, span_width: int) -> str:
        prefix = f"{marker} " if len(marker) + 1 < span_width else ""
        width = max(0, span_width - len(prefix))
        if kind == "tools":
            segments = tool_summary_segments(tool, width)
        elif kind == "skills":
            segments = skill_summary_segments(tool, width)
        else:
            segments = status_segments(tool, width, _duration(tool.running_ms), _duration(tool.background_ms))
        segments = [(prefix, BASE_ROLE)] + segments
        padding = max(0, span_width - sum(len(text) for text, _role in segments))
        body = "".join(self.styler.apply(text, role) for text, role in segments)
        return "| " + body + " " * padding + " |"

    def _render_table(self, projection: WatchProjection) -> None:
        rows, styles, activities, headers = self._table_rows(projection)
        sessions = list(dict.fromkeys(row.session_id for row in projection.rows))
        active = {row.session_id for row in projection.rows if row.session_active}
        separators = [headers[index] for index, session_id in enumerate(sessions)
                      if index > 0 and session_id in active and sessions[index - 1] not in active]
        if not rows:
            rows, styles = [_empty_row("No prompts since Watch started")], [("watchToolActivity",) + (None,) * 5]
        lines = render_table(_WATCH_COLUMNS, rows,
                             styles=styles, styler=self.styler,
                             separator_before_rows=separators,
                             leading_spans={index: 2 for index in headers})
        if lines and activities:
            terminal_width = self._content_width(minimum=1)
            span_width = max(0, min(len(lines[0]), terminal_width) - 4)
            for row_index, (kind, marker, tool) in activities.items():
                line_index = 3 + row_index + sum(index <= row_index for index in separators)
                lines[line_index] = self._activity_line(kind, marker, tool, span_width) if terminal_width >= 4 else "|"[:max(0, terminal_width)]
        for line in lines:
            self._write(line)
        width = self._content_width()
        if any(row.earlier for row in projection.rows):
            for line in warning_explanation_lines(EARLIER_LABEL, EARLIER_EXPLANATION, PriceWarningSeverity.APPROACHING,
                                                  self.styler, width=width):
                self._write(line)
        for numbers, text, severity in _warning_groups(projection):
            marker = "*" + ",".join(str(number) for number in numbers)
            for line in warning_explanation_lines(marker, text, severity, self.styler, width=width):
                self._write(line)

    def _render_quota(self, projection: WatchProjection) -> None:
        width = self._content_width()
        mix = projection.token_mix
        for line in token_mix_lines(prompt_scope(mix.sample_size), mix, width=width):
            self._write(line)
        for line in watch_total_lines(projection.run_total, projection.today_total, projection.today_label,
                                      width=width):
            self._write(line)
        quota = projection.quota
        if quota is None:
            return
        if not quota.accounts:
            return
        primary_width = max([4] + [len(quota_label(account.account.quotas[0].label))
                                  for account in quota.accounts if account.account.quotas])
        # Only accounts whose label can sit beside compact quotas (one row or split at
        # `|`) participate in label padding; an oversized account keeps its own
        # vertical fallback, not everyone else's.
        label_width = max((len(account.label) for account in quota.accounts if compact_label_fits(
            account, self.timezone_id, width=width, now_ms=projection.now_ms, primary_label_width=primary_width,
            recovering=account.account.key in projection.quota_recovering_accounts)), default=0)
        previous_vertical = False
        first = True
        for account in quota.accounts:
            lines, is_vertical = capacity_block(
                account, self.styler, self.timezone_id, width=width, now_ms=projection.now_ms, watch=True,
                account_label_width=label_width, primary_label_width=primary_width,
                recovering=account.account.key in projection.quota_recovering_accounts)
            if not first and (previous_vertical or is_vertical):
                self._write()
            for line in lines:
                self._write(line)
            first, previous_vertical = False, is_vertical
        self._write()

    def render_initializing(self, source_label: str = "detecting...") -> None:
        """Transient heading/status; steady-state dashboard geometry is unchanged."""
        if not self.interactive:
            return
        self._clear()
        width = self._content_width()
        self._write("\n".join(wrap_prose(self._watch_heading("Watch", self.started_at_ms), width)))
        # Startup loading uses the default foreground like every other mode;
        # activeRunning stays reserved for the steady-state Watch status row.
        self._write_status("Initializing...", active=False, newline=False)

    def render_startup_status(self, line: str, *, active: bool = False) -> None:
        if not self.interactive:
            return
        self.stream.write("\r\x1b[2K" + self.styler.apply(line, "activeRunning" if active else None))
        self.stream.flush()
        self._status_visible = True

    def render(self, projection: WatchProjection) -> None:
        self._clear()
        self._write(self._watch_title(projection.source_label, projection.title, projection.watch_started_at_ms))
        for warning in projection.source_warnings:
            self._write(self.styler.apply("WARNING: " + warning, "costQuotaWarning"))
        width = self._content_width()
        if projection.recent_model_notice:
            for line in pricing_notice_lines(projection.recent_model_notice, width, self.styler, "modelComparisonNew",
                                          highlight_spans=projection.recent_model_notice_highlight_spans):
                self._write(line)
        for notice in projection.recent_promotion_notices:
            for line in pricing_notice_lines(notice, width, self.styler, "modelComparisonPromotion"):
                self._write(line)
        self._render_table(projection)
        self._render_quota(projection)
        if projection.quota_recovering_accounts:
            detail = "showing last known values." if projection.quota_stale else "retrying."
            self._write(self.styler.apply("Quota connection recovering; " + detail, "costQuotaWarning"))
        elif projection.quota_stale:
            self._write(self.styler.apply("Quota refresh unavailable; showing last known account values (up to 5 min old).", "costQuotaWarning"))
        self._write_status(
            projection.status or "Watching",
            active=bool(projection.status_active or projection.active_count),
            newline=not self.interactive,
        )

    def render_status(self, projection: WatchProjection) -> None:
        if not self.interactive:
            return
        text = self.styler.apply(
            self._status_text(projection.status or "Watching"),
            "activeRunning" if (projection.status_active or projection.active_count) else None,
        )
        self.stream.write("\r\x1b[2K" + text)
        self.stream.flush()
        self._status_visible = True

    def finish(self, text: str) -> None:
        if self.interactive and self._status_visible:
            self.stream.write("\r\x1b[2K" + text + "\n")
        else:
            self._write(text)
        self.stream.flush()
