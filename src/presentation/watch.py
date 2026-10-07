"""Full-screen/redirect-safe rendering for Watch projections."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import os
import sys
from typing import Mapping, TextIO

from src.version import mode_heading
from src.numbers import ccost_amount
from src.watch.models import ToolObservation, WatchProjection, WatchRow, WatchSessionSubtotal

from .terminal import AnsiStyler, Column, StyledText, fit, render_table
from .terminal import terminal_content_width
from .accounts import account_capacity_parts, capacity_lines, quota_label
from .token_mix import prompt_scope, token_mix_line, token_mix_lines, watch_total_line
from src.analysis.token_mix import TokenMix
from src.analysis.context import PriceWarningSeverity
from .context_warnings import WARNING_ROLE, next_ictx_ccost, warning_explanation_lines
from .pricing_notices import pricing_notice_lines
from .watch_activity import BASE_ROLE, status_segments, tool_summary_segments

_WATCH_COLUMNS = (
    Column("Session / prompt", fixed_width=35),
    Column("Model / effort", fixed_width=25),
    Column("CCost", True, fixed_width=7),
    Column("Calls", True, fixed_width=5),
    Column("Duration", True, fixed_width=8),
    Column("Δctx → Next Ictx", True, fixed_width=20),
)


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




def _duration(ms: int | None) -> str:
    if ms is None:
        return "N/A"
    seconds = max(0, int((Decimal(ms) / Decimal(1000)).to_integral_value(rounding=ROUND_HALF_UP)))
    if seconds < 60:
        return f"{seconds}s"
    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m" if remaining_seconds == 0 else f"{minutes}m{remaining_seconds}s"
    hours, remaining_minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h" if remaining_minutes == 0 else f"{hours}h{remaining_minutes}m"
    days, remaining_hours = divmod(hours, 24)
    return f"{days}d" if remaining_hours == 0 else f"{days}d{remaining_hours}h"


def _context_cell(row: WatchRow, row_role: str | None) -> StyledText:
    prompt = row.prompt
    warning_role = row_role
    if row.next_context_warning_severity != PriceWarningSeverity.NONE:
        warning_role = WARNING_ROLE
    delta = prompt.watch_delta_context_tokens
    next_tokens = prompt.watch_next_context_tokens
    return StyledText((
        (f"{_tokens(delta, signed=True):>7}", row_role),
        (" → ", row_role),
        (f"{_tokens(next_tokens, approximate=True):>8}", warning_role),
    ))


def _empty_row(text: str) -> tuple[str, ...]:
    """A single placeholder row keeps the table from ending in a double rule."""
    return ("  " + text, "", "", "", "", "")


def _session_subtotal_text(subtotal: WatchSessionSubtotal | None) -> str:
    """Format the projected row subtotal, including unresolved provenance."""
    return "Σ " + ("N/A" if subtotal is None else ccost_amount(subtotal.ccost, unresolved=subtotal.unresolved_cost))


class WatchRenderer:
    def __init__(self, config: Mapping[str, object], *, stream: TextIO | None = None, interactive: bool | None = None,
                 terminal_width: int | None = None) -> None:
        self.config = config
        self.stream = stream or sys.stdout
        if interactive is None:
            interactive = bool(getattr(self.stream, "isatty", lambda: False)()) and not os.environ.get("TERM") == "dumb"
        self.interactive = bool(interactive)
        colors = config.get("colors") if isinstance(config.get("colors"), Mapping) else {}
        self.styler = AnsiStyler(colors, enabled=self.interactive)
        self.timezone_id = str(config.get("timezone") or "Europe/Stockholm")
        self._status_visible = False
        self.terminal_width = terminal_width

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

    @staticmethod
    def _watch_title(source_label: str, title: str = "Cost Guard Watch") -> str:
        suffix = ""
        prefix = "Cost Guard Watch - "
        if title.startswith(prefix):
            suffix = " — " + title[len(prefix):]
        return mode_heading("Prompt watch") + f"{suffix} — Source: OpenCode {source_label}"

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
        prefix = "[ABORTED] " if prompt.aborted else ""
        return f"  {marker}#{prompt.prompt_number} {prefix}{prompt.preview}"

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

    def _table_rows(self, projection: WatchProjection) -> tuple[
        list[tuple[object, ...]], list[tuple[str | None, ...]], dict[int, tuple[str, str, ToolObservation]]
    ]:
        rows: list[tuple[object, ...]] = []
        styles: list[tuple[str | None, ...]] = []
        activities: dict[int, tuple[str, str, ToolObservation]] = {}
        previous_session = None
        warnings = projection.session_warnings or {}
        warning_numbers = {session_id: index + 1 for index, session_id in enumerate(warnings)}
        for row in projection.rows:
            if row.session_id != previous_session:
                if row.session_id in warning_numbers:
                    number = warning_numbers[row.session_id]
                    marker = f"*{number}"
                    name = fit(row.session_title, _WATCH_COLUMNS[0].fixed_width - len(marker) - 1).rstrip()
                    title = StyledText(((marker, WARNING_ROLE), (" " + name, "watchSessionHeader")))
                else:
                    title = row.session_title
                subtotal = _session_subtotal_text(projection.session_subtotals.get(row.session_id))
                rows.append((title, "", subtotal, "", "", ""))
                styles.append(("watchSessionHeader", None, None, None, None, None))
                previous_session = row.session_id
            prompt = row.prompt
            role = self._row_style(row)
            native_compaction_without_billing = prompt.is_compaction and prompt.calls == 0 and prompt.ccost == 0
            model_label = prompt.watch_model_effort or prompt.model_effort or "N/A"
            rows.append((
                self._row_label(row),
                "" if native_compaction_without_billing and model_label == "N/A" else model_label,
                "" if native_compaction_without_billing else ccost_amount(prompt.ccost, unresolved=prompt.unresolved_cost),
                "" if native_compaction_without_billing else prompt.calls,
                "" if native_compaction_without_billing and not prompt.in_progress else _duration(self._duration_for(row, projection.now_ms)),
                _context_cell(row, role),
            ))
            styles.append((role, role, role, role, role, None))
            if prompt.in_progress and row.tool is not None:
                arrow = "↳" if self._supports_arrow() and self.interactive else "->"
                marker = " " * self._row_label(row).index("#") + arrow
                for kind in ("tools", "status") if row.tool.has_status_row else ("tools",):
                    activities[len(rows)] = (kind, marker, row.tool)
                    rows.append((marker, "", "", "", "", ""))
                    styles.append(("watchToolActivity", None, None, None, None, None))
        return rows, styles, activities

    def _activity_line(self, kind: str, marker: str, tool: ToolObservation, span_width: int) -> str:
        prefix = f"{marker} "
        width = max(1, span_width - len(prefix))
        if kind == "tools":
            segments = tool_summary_segments(tool, width)
        else:
            segments = status_segments(tool, width, _duration(tool.running_ms), _duration(tool.background_ms))
        segments = [(prefix, BASE_ROLE)] + segments
        padding = max(0, span_width - sum(len(text) for text, _role in segments))
        body = "".join(self.styler.apply(text, role) for text, role in segments)
        return "| " + body + " " * padding + " |"

    def _render_table(self, projection: WatchProjection) -> None:
        rows, styles, activities = self._table_rows(projection)
        if not rows:
            rows, styles = [_empty_row("No prompts yet")], [("watchToolActivity",) + (None,) * 5]
        lines = render_table(_WATCH_COLUMNS, rows, styles=styles, styler=self.styler)
        if lines and activities:
            span_width = max(1, len(lines[0]) - 4)
            for row_index, (kind, marker, tool) in activities.items():
                lines[3 + row_index] = self._activity_line(kind, marker, tool, span_width)
        for line in lines:
            self._write(line)
        warnings = projection.session_warnings or {}
        for number, (session_id, warning) in enumerate(warnings.items(), start=1):
            clean = warning[1:-1] if warning.startswith("[") and warning.endswith("]") else warning
            warning_row = next((item for item in reversed(projection.rows) if item.session_id == session_id and item.next_context_warning), None)
            severity = warning_row.next_context_warning_severity if warning_row else PriceWarningSeverity.NONE
            suffix = ""
            if warning_row is not None:
                prompt = warning_row.prompt
                low = prompt.watch_next_context_cached_ccost
                high = prompt.watch_next_context_fresh_ccost
                if low is None and high is None:
                    low, high = prompt.next_context_cached_ccost, prompt.next_context_fresh_ccost
                if low is not None and high is not None:
                    suffix = " " + next_ictx_ccost(low, high)
            for line in warning_explanation_lines(f"*{number}", f"Next Ictx: {clean}{suffix}", severity, self.styler):
                self._write(line)

    def _render_quota(self, projection: WatchProjection) -> None:
        width = self.terminal_width if self.terminal_width is not None else terminal_content_width(self.stream)
        mix = projection.token_mix
        for line in token_mix_lines(prompt_scope(mix.sample_size), mix, width=width):
            self._write(line)
        self._write(watch_total_line(mix))
        quota = projection.quota
        if quota is None:
            return
        if not quota.accounts:
            return
        primary_width = max([4] + [len(quota_label(account.account.quotas[0].label))
                                  for account in quota.accounts if account.account.quotas])
        # Only accounts that can fit at all participate in compact label padding;
        # an oversized account keeps its own vertical fallback, not everyone else's.
        compact_labels = []
        for account in quota.accounts:
            components = account_capacity_parts(
                account, self.timezone_id, now_ms=projection.now_ms, compact=True, watch=True,
                primary_label_width=primary_width,
                recovering=account.account.key in projection.quota_recovering_accounts)
            if len(account.label) + 3 + len(" | ".join(str(item) for item in components)) <= width:
                compact_labels.append(len(account.label))
        label_width = max(compact_labels, default=0)
        previous_vertical = False
        first = True
        for account in quota.accounts:
            lines = capacity_lines(account, self.styler, self.timezone_id, width=width,
                                    now_ms=projection.now_ms, watch=True,
                                    account_label_width=label_width, primary_label_width=primary_width,
                                    recovering=account.account.key in projection.quota_recovering_accounts)
            is_vertical = len(lines) > 1
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
        self._write(mode_heading("Watch"))
        self._write_status("Initializing...", active=True, newline=False)

    def render_startup_status(self, line: str) -> None:
        if not self.interactive:
            return
        self.stream.write("\r\x1b[2K" + self.styler.apply(line, "activeRunning"))
        self.stream.flush()
        self._status_visible = True

    def render(self, projection: WatchProjection) -> None:
        self._clear()
        self._write(self._watch_title(projection.source_label, projection.title))
        for warning in projection.source_warnings:
            self._write(self.styler.apply("WARNING: " + warning, "costQuotaWarning"))
        width = self.terminal_width if self.terminal_width is not None else terminal_content_width(self.stream)
        if projection.recent_model_notice:
            for line in pricing_notice_lines(projection.recent_model_notice, width, self.styler, "modelComparisonNew"):
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
