"""Render one-shot report projections to human-readable terminal text."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping, TextIO
import sys

from src.analysis.timezones import format_local_timestamp
from src.analysis.context import PriceWarningSeverity
from src.reports.models import PromptProjection, ReportKind, ReportProjection, SessionPromptBlock
from src.version import DISPLAY_VERSION, PRODUCT_NAME, RELEASE_DATE
from src.numbers import ccost_amount

from .terminal import AnsiStyler, Column, StyledText, fit, render_table, single_line, terminal_content_width, wrap_prose
from .accounts import capacity_lines, money, quota_label
from .token_mix import MIX_TERM, aligned_mix_cells, compact_tokens, mix_cells, packed_cells, total_cost_text
from .definitions import concept_lines
from .context_warnings import WARNING_ROLE, context_warning_text, next_ictx_ccost, threshold_multiplier_text, warning_explanation_lines
from .pricing_notices import pricing_notice_lines
from .model_comparison import aligned_price_summaries as _aligned_price_summaries, aligned_relative_costs
from .model_supersession import superseded_rows


def _context_k(value: int | None) -> str:
    if value is None:
        return "N/A"
    if value <= 0:
        return "0k"
    rounded = int((Decimal(value) / Decimal(1_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{max(1, rounded)}k"


def _context_delta_k(value: int | None) -> str:
    if value is None:
        return "N/A"
    if abs(value) < 500:
        return "0k"
    magnitude = _context_k(abs(value))
    return ("+" if value > 0 else "-") + magnitude


def _duration(ms: int | None) -> str:
    if ms is None:
        return "N/A"
    seconds = max(0, ms // 1000)
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _percentile(values: list[Decimal], percentile: Decimal) -> Decimal:
    ordered = sorted(values)
    if not ordered:
        return Decimal(0)
    if len(ordered) == 1:
        return ordered[0]
    pct = max(Decimal(0), min(Decimal(100), percentile))
    position = pct / Decimal(100) * Decimal(len(ordered) - 1)
    lower = int(position.to_integral_value(rounding="ROUND_FLOOR"))
    upper = int(position.to_integral_value(rounding="ROUND_CEILING"))
    if lower == upper:
        return ordered[lower]
    fraction = position - Decimal(lower)
    return ordered[lower] * (Decimal(1) - fraction) + ordered[upper] * fraction


class _MetricProfile:
    __slots__ = ("enabled", "minimum", "p50", "p75", "p90")

    def __init__(self, values: Iterable[Decimal], thresholds: Mapping[str, object]) -> None:
        numbers = list(values)
        self.minimum = min(numbers) if numbers else Decimal(0)
        minimum_samples = max(1, int(thresholds.get("promptCostMinSamples", 5)))
        self.enabled = bool(len(numbers) >= minimum_samples and numbers and max(numbers) > self.minimum)
        self.p50 = _percentile(numbers, Decimal(str(thresholds.get("promptCostP50", 50)))) if self.enabled else Decimal(0)
        self.p75 = _percentile(numbers, Decimal(str(thresholds.get("promptCostP75", 75)))) if self.enabled else Decimal(0)
        self.p90 = _percentile(numbers, Decimal(str(thresholds.get("promptCostP90", 90)))) if self.enabled else Decimal(0)

    def role(self, value: Decimal | None) -> str | None:
        if value is None or not self.enabled:
            return None
        if value >= self.p90:
            return "promptCostP90"
        if value >= self.p75 and value > self.p50:
            return "promptCostP75"
        if value >= self.p50 and value > self.minimum:
            return "promptCostP50"
        return None


def _breakdown(main: Decimal, subagent: Decimal, *, main_estimated: bool, subagent_estimated: bool, total_text: str) -> str:
    return (
        "  Main: " + ccost_amount(main, unresolved=main_estimated)
        + " | Subagents: " + ccost_amount(subagent, unresolved=subagent_estimated)
        + " | Total: " + total_text
    )


def _prompt_ictx(item: PromptProjection, *, delta_width: int = 0, next_width: int = 0) -> str | StyledText:
    if item.next_context_tokens is not None and item.delta_context_tokens is not None:
        delta = _context_delta_k(item.delta_context_tokens)
        next_value = _context_k(item.next_context_tokens)
        if delta_width > 0:
            delta = delta.rjust(delta_width)
        if next_width > 0:
            next_value = next_value.rjust(next_width)
        if item.next_context_warning_severity != PriceWarningSeverity.NONE:
            return StyledText(((f"{delta} → ", None), (next_value, WARNING_ROLE)))
        return f"{delta} → {next_value}"
    return _context_k(item.incoming_context_tokens)


class ReportRenderer:
    def __init__(
        self, config: Mapping[str, object], *, stream: TextIO | None = None,
        color_enabled: bool | None = None, terminal_width: int | None = None,
    ) -> None:
        self.config = config
        self.stream = stream or sys.stdout
        colors = config.get("colors") if isinstance(config.get("colors"), Mapping) else {}
        self.styler = AnsiStyler(colors, enabled=color_enabled,
                                 light_theme=config.get("colorScheme") == "modus-operandi-tinted")
        self.timezone_id = str(config.get("timezone") or "Europe/Stockholm")
        self.table_width = int(terminal_width) if terminal_width is not None else terminal_content_width(self.stream)

    def _write(self, value: str = "") -> None:
        self.stream.write(value + "\n")

    def _heading(self, value: str) -> None:
        """Own the major-section boundary; section content has no trailing spacer."""
        self._write()
        self._write()
        self._write(value)
        self._write("-" * max(1, self.table_width))
        self._write()

    def _prose(self, value: str, *, prefix: str = "", role: str | None = None) -> None:
        for line in wrap_prose(value, self.table_width, initial_prefix=prefix, continuation_prefix=" " * len(prefix)):
            self._write(self.styler.apply(line, role))

    def _render_model_comparison(self, report: ReportProjection) -> None:
        for line in concept_lines(report.token_mix, report.model_comparison_sample_size, self.table_width, self.styler):
            self._write(line)
        self._write()
        self._prose(f"Pricing/cache metadata: {format_local_timestamp(report.pricing_retrieved_at_ms, self.timezone_id)}")
        rows = []
        styles = []
        aligned_prices = _aligned_price_summaries(item.price_summary for item in report.model_comparison)
        relatives = aligned_relative_costs(report.model_comparison)
        all_models = report.kind == ReportKind.ALL_MODELS
        for item, price_text, relative in zip(report.model_comparison, aligned_prices, relatives):
            rows.append((item.publisher or "N/A", item.model, relative,
                         *((price_text,) if all_models else ()), item.release_date or "N/A"))
            promo = "modelComparisonPromotion" if item.promotional else None
            recent = "modelComparisonNew" if item.recent else None
            styles.append((None, recent, promo, *((promo,) if all_models else ()), recent))
        for line in render_table(
            (
                Column("Publisher", min_width=8, max_width=40, flexible=True),
                Column("Model", min_width=12, max_width=80, flexible=True),
                Column("Relative CCost", fixed_width=max(map(len, relatives), default=0)),
                *((Column("GitHub USD/M I/C/W/O", fixed_width=max(map(len, aligned_prices), default=0)),)
                  if all_models else ()),
                Column("Release date", True, max_width=16),
            ), rows, styles=styles, styler=self.styler, target_width=self.table_width,
            faded_rows=superseded_rows([(item.publisher, item.model) for item in report.model_comparison]),
        ):
            self._write(line)
        for note in report.model_comparison_promotion_notes:
            for line in pricing_notice_lines(note, self.table_width, self.styler, "modelComparisonPromotion"):
                self._write(line)
        if report.recent_model_notice:
            for line in pricing_notice_lines(report.recent_model_notice, self.table_width, self.styler, "modelComparisonNew"):
                self._write(line)

    def _render_sessions(self, report: ReportProjection) -> None:
        rows = [(
            item.session_id, single_line(item.title, item.session_id), item.model + (" *" if item.multiple_models else ""),
            ccost_amount(item.ccost, unresolved=not item.complete), item.prompt_count,
        ) for item in report.session_usage]
        for line in render_table(
            (Column("Session id", max_width=512),
             Column("Name", min_width=12, max_width=100, flexible=True),
             Column("Model", min_width=10, max_width=60, flexible=True),
             Column("CCost", True), Column("#", True)),
            rows, styler=self.styler, target_width=self.table_width,
        ):
            self._write(line)
        self._prose("CCost is whole-session reference token valuation, not billing; ? marks partial pricing.", prefix="* ")
        self._prose("# counts visible prompts; linked child work is included. Only currently available OpenCode data is shown.", prefix="* ")
        if any(item.multiple_models for item in report.session_usage):
            self._prose("A trailing * in Model means more than one model contributed; the dominant model is selected by CCost.", prefix="* ")

    def _render_prompt_block(self, block: SessionPromptBlock, *, warning_number: int | None = None) -> None:
        thresholds = self.config.get("thresholds") if isinstance(self.config.get("thresholds"), Mapping) else {}
        prompt_rows = [row for row in block.rows if not row.is_compaction]
        cost_profile = _MetricProfile((row.ccost for row in prompt_rows), thresholds)
        ictx_cost_profile = _MetricProfile((row.incoming_context_ccost for row in prompt_rows if row.incoming_context_ccost is not None), thresholds)
        extra_cost_profile = _MetricProfile((row.extra_ccost for row in prompt_rows if row.extra_ccost is not None), thresholds)
        mix_profiles = [
            _MetricProfile((Decimal(row.token_mix_percent[index]) for row in prompt_rows if row.token_mix_percent is not None), thresholds)
            for index in range(4)
        ]

        timeline: list[tuple[int, int, str, PromptProjection]] = []
        for item in block.rows:
            timeline.append((item.at_ms, 0 if item.is_compaction else 1, "main", item))
            if item.aborted and item.abort_at_ms > 0:
                timeline.append((max(item.at_ms, item.abort_at_ms), 2, "abort", item))
        timeline.sort(key=lambda value: (value[0], value[1], value[3].prompt_number))
        context_rows = [
            item for _at, _order, kind, item in timeline
            if kind == "main" and item.delta_context_tokens is not None and item.next_context_tokens is not None
        ]
        delta_width = max((len(_context_delta_k(item.delta_context_tokens)) for item in context_rows), default=0)
        next_width = max((len(_context_k(item.next_context_tokens)) for item in context_rows), default=0)

        rows: list[tuple[object, ...]] = []
        styles: list[tuple[str | None, ...]] = []
        last_model: tuple[str, bool] | None = None
        table_has_additional = False
        for _at, _order, kind, item in timeline:
            if kind == "abort":
                clock = format_local_timestamp(item.abort_at_ms or item.at_ms, self.timezone_id, "%H:%M")
                rows.append((f"{clock} #{item.prompt_number} [ABORTED]", "", "", "", "", "", ""))
                styles.append((None,) * 7)
                continue
            clock = format_local_timestamp(item.at_ms, self.timezone_id, "%H:%M")
            if item.is_compaction:
                prompt = f"{clock} #{item.prompt_number} {item.label}{' [RUNNING]' if item.in_progress else ''}"
                if item.model_effort and item.model_effort != "N/A":
                    prompt += "  " + item.model_effort
            else:
                current_model = (item.model_effort, item.has_additional_model)
                if item.model_effort and current_model != last_model:
                    model_text = "Model: " + item.model_effort + (" *" if item.has_additional_model else "")
                    rows.append((model_text, "", "", "", "", "", ""))
                    styles.append((None,) * 7)
                    last_model = current_model
                    table_has_additional = table_has_additional or item.has_additional_model
                prompt = f"{clock} #{item.prompt_number} {single_line(item.preview)}" + (" [RUNNING]" if item.in_progress else "")

            native_compaction_without_billing = item.is_compaction and item.calls == 0
            if item.in_progress:
                mix_text: object = "running - consider ABORT" if item.running_cost_warning else "running"
            elif item.token_mix_percent is not None:
                mix_parts: list[tuple[str, str | None]] = []
                for index, value in enumerate(item.token_mix_percent):
                    if index:
                        mix_parts.append(("/", None))
                    mix_parts.append((str(value), mix_profiles[index].role(Decimal(value))))
                mix_text = StyledText(tuple(mix_parts))
            else:
                mix_text = "" if native_compaction_without_billing else "N/A"
            context_cell = _prompt_ictx(item, delta_width=delta_width, next_width=next_width)
            rows.append((
                prompt,
                "" if native_compaction_without_billing else ccost_amount(item.ccost, unresolved=item.unresolved_cost),
                "" if native_compaction_without_billing else item.calls,
                context_cell,
                "" if native_compaction_without_billing else ccost_amount(item.incoming_context_ccost),
                "" if native_compaction_without_billing else ccost_amount(item.extra_ccost),
                mix_text,
            ))
            active = "activeRunning" if item.in_progress else None
            cost_role = None if native_compaction_without_billing else cost_profile.role(item.ccost)
            ictx_role = "promptIctxPriceThreshold" if item.ictx_price_threshold and not isinstance(context_cell, StyledText) else None
            ictx_cost_role = None if native_compaction_without_billing else ictx_cost_profile.role(item.incoming_context_ccost)
            extra_role = None if native_compaction_without_billing else extra_cost_profile.role(item.extra_ccost)
            styles.append((active, cost_role, None, ictx_role, ictx_cost_role, extra_role, None))
            if item.has_cost_breakdown and item.breakdown_known:
                total_text = ccost_amount(item.ccost, unresolved=item.unresolved_cost)
                rows.append((_breakdown(
                    item.main_ccost, item.subagent_ccost,
                    main_estimated=item.main_estimated, subagent_estimated=item.subagent_estimated,
                    total_text=total_text,
                ), "", "", "", "", "", ""))
                styles.append((None,) * 7)

        total_index = len(rows)
        rows.append((
            "Total", ccost_amount(block.total_ccost, unresolved=not block.comparison_cost_complete), block.total_calls, "",
            block.total_ictx_cost_text, block.total_extra_cost_text, block.total_mix_text,
        ))
        styles.append((None,) * 7)
        if block.total_has_cost_breakdown and block.total_breakdown_known:
            rows.append((_breakdown(
                block.total_main_ccost, block.total_subagent_ccost,
                main_estimated=block.total_main_estimated, subagent_estimated=block.total_subagent_estimated,
                total_text=ccost_amount(block.total_ccost),
            ), "", "", "", "", "", ""))
            styles.append((None,) * 7)

        table_lines = render_table(
            (Column("Prompt", min_width=18, max_width=240, flexible=True), Column("CCost", True), Column("Calls", True), Column("~Ictx", True, max_width=22),
             Column("~Ictx CCost", True), Column("~Extra CCost", True), Column("I/C/W/O %", True, max_width=24)),
            rows, styles=styles, styler=self.styler, target_width=self.table_width, separator_before_rows=(total_index,),
        )
        rendered_width = len(table_lines[0]) if table_lines else max(4, self.table_width)
        content_width = max(0, rendered_width - 4)
        self._write("|" + "-" * max(0, rendered_width - 2) + "|")
        self._write(f"| {fit('Session: ' + block.session_id, content_width)} |")
        title = (f"*{warning_number} " if warning_number else "") + single_line(block.title, block.session_id)
        title_cell = fit(title, content_width)
        if warning_number:
            marker = f"*{warning_number}"
            title_cell = self.styler.apply(marker, WARNING_ROLE) + title_cell[len(marker):]
        self._write(f"| {title_cell} |")
        for line in table_lines:
            self._write(line)
        if table_has_additional:
            self._prose("Additional model(s) were used by linked subagent/child requests; displayed model is the root request model.", prefix="* ")
        warning_role = WARNING_ROLE if block.next_context_warning_severity != PriceWarningSeverity.NONE else None
        if block.next_context_tokens is not None:
            next_line = f"Next Ictx: ~{_context_k(block.next_context_tokens)} " + (
                threshold_multiplier_text(block.next_context_cost_multiplier)
                if warning_role and block.next_context_cost_multiplier is not None
                else next_ictx_ccost(block.next_context_cached_ccost, block.next_context_fresh_ccost))
        else:
            next_line = "Next Ictx: N/A"
        self._prose(next_line, prefix="* ", role=warning_role)
        if warning_number and block.next_context_warning:
            for line in warning_explanation_lines(f"*{warning_number}", context_warning_text(block.next_context_warning),
                                                  block.next_context_warning_severity, self.styler, width=self.table_width):
                self._write(line)

    def _render_prompt_blocks(self, report: ReportProjection, heading: str) -> None:
        self._heading(heading)
        if not report.prompt_blocks:
            self._write("No matching prompt events.")
            return
        warning_numbers = {
            block.session_id: index + 1
            for index, block in enumerate(block for block in report.prompt_blocks if block.next_context_warning)
        }
        for index, block in enumerate(report.prompt_blocks):
            if index:
                self._write()
            self._render_prompt_block(block, warning_number=warning_numbers.get(block.session_id))
        for explanation in (
            "CCost: reference token valuation including linked child work, not actual billing; ? marks partial pricing.",
            "Calls: causal model requests. I/C/W/O %: input/cache-read/cache-write/output (including reasoning) token shares.",
            "~Ictx: approximate incoming context, or context change → next-input context along the session timeline.",
            "~Ictx CCost: current-price reference value of incoming context; not actual billing.",
            "~Extra CCost: current-price reference value of additional causal usage beyond incoming context; not actual billing.",
            "Next Ictx: estimated next-input context and cached–fresh CCost bounds; future cache hits are not predicted.",
        ):
            self._prose(explanation, prefix="* ")

    def _render_accounts_quotas(self, report: ReportProjection) -> None:
        quota = report.accounts_quotas
        if quota is None:
            return
        self._write()
        self._write("Accounts Overview")
        self._write("─" * min(67, self.table_width))
        if not quota.accounts:
            self._write("No configured accounts detected.")
        primary_width = max([4] + [len(quota_label(item.label)) for account in quota.accounts
                                  for item in account.account.quotas] +
                            ([len("Remaining")] if any(account.pace for account in quota.accounts) else []))
        for index, account in enumerate(quota.accounts):
            if index:
                self._write()
            self._write(account.label)
            if account.billed_today is not None:
                self._write("  Billed today: " + money(account.billed_today))
            if account.billed_month is not None:
                self._write("  Billed month: " + money(account.billed_month))
            for line in capacity_lines(account, self.styler, self.timezone_id, width=self.table_width,
                                       force_vertical=True, include_label=False, now_ms=quota.now_ms,
                                       primary_label_width=primary_width):
                self._write(line)
            if account.account.reason:
                self._prose(account.account.reason, prefix="  ")

    def _render_model_token_mix(self, report: ReportProjection) -> None:
        self._write()
        if not report.model_token_mix:
            self._write("No model usage found in available OpenCode history.")
        else:
            total = report.token_mix
            heading = f"Total {MIX_TERM}"
            if total.total_tokens is not None:
                heading += f" · {compact_tokens(total.total_tokens)} tokens"
            self._write(heading)
            for line in packed_cells(mix_cells(total), self.table_width):
                self._write(line)
            self._write()
            cells = aligned_mix_cells([item.mix for item in report.model_token_mix])
            rows = [(item.model, str(item.prompts), str(item.calls), *mix, total_cost_text(item.mix))
                    for item, mix in zip(report.model_token_mix, cells)]
            for line in render_table(
                (Column("Model", min_width=12, max_width=60, flexible=True), Column("Prompts", True),
                 Column("Calls", True), *(Column(name, True, max_width=24) for name in ("Input", "Cache", "Write", "Output")),
                 Column("CCost", True)),
                rows, styler=self.styler, target_width=self.table_width,
            ):
                self._write(line)
        for explanation in (
            "Input/Cache/Write/Output: Token Mix % of the model's token volume (output includes reasoning) and its CCost.",
            "CCost: reference token valuation priced per request, not actual billing; ? marks partial pricing.",
            "Prompts: unique user prompts where the model contributed usage; one prompt can count on several rows.",
            "Calls: model requests attributed to the model, including tool-loop, subagent and compaction requests.",
        ):
            self._prose(explanation, prefix="* ")

    def render(self, report: ReportProjection, *, include_header: bool = True) -> None:
        if include_header:
            self._write(f"# {PRODUCT_NAME} {DISPLAY_VERSION} ({RELEASE_DATE}) — Source: OpenCode {report.source_label}")
        if report.kind in {ReportKind.SESSION, ReportKind.DATE, ReportKind.TOKEN_MIX}:
            self._write(report.title)
        for warning in report.source_warnings:
            self._prose(warning, prefix="" if warning.startswith("⚠") else "WARNING: ", role="costQuotaWarning")
        if report.kind in {ReportKind.NORMAL, ReportKind.ALL_MODELS}:
            self._render_model_comparison(report)
            if report.kind is ReportKind.NORMAL:
                self._render_accounts_quotas(report)
        elif report.kind is ReportKind.SESSIONS:
            self._render_sessions(report)
        elif report.kind is ReportKind.TOKEN_MIX:
            self._render_model_token_mix(report)
        else:
            self._render_prompt_blocks(report, "## User prompts")
        if report.notes:
            self._write()
        for note in report.notes:
            self._prose(note, prefix="* ")
