"""Aligned subfields inside the model table's relative and exact price cells.

Widths are measured on plain visible fields, before ANSI styling. Numeric
columns are never terminal-shrunk; only Publisher/Model are flexible.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Iterable, Sequence

from src.reports.models import ModelComparisonProjection

from .terminal import visible_len


def compact_threshold(value: int) -> str:
    divisor, suffix = (1_000_000, "M") if value >= 1_000_000 else (1000, "K") if value >= 1000 else (1, "")
    text = format(Decimal(value) / divisor, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text + suffix


def aligned_relative_costs(items: Sequence[ModelComparisonProjection]) -> list[str]:
    markers = [f"*{item.promotion_marker}" if item.promotion_marker is not None else "" for item in items]
    marker_width = max(map(visible_len, markers), default=0)
    fields = []
    for item in items:
        values = []
        if item.relative_cost is not None:
            values.append(f"{item.relative_cost:.1f}x")
            for level in item.relative_levels[1:]:
                values.extend(("→", "N/A" if level.relative_cost is None else f"{level.relative_cost:.1f}x",
                               f"({level.threshold_operator}{compact_threshold(level.threshold_tokens)})"
                               if level.threshold_tokens is not None else ""))
        fields.append(values)
    count = max(map(len, fields), default=0)
    widths = [max((visible_len(row[index]) for row in fields if index < len(row)), default=0)
              for index in range(count)]
    result = []
    for marker, values in zip(markers, fields):
        parts = []
        for index, width in enumerate(widths):
            value = values[index] if index < len(values) else ""
            # Base and each subsequent multiplier end at a shared position.
            parts.append(value.rjust(width) if index == 0 or index % 3 == 2 else value.ljust(width))
        prefix = marker.ljust(marker_width) + " " if marker_width else ""
        result.append(prefix + " ".join(parts))
    return result


def aligned_price_summaries(values: Iterable[str]) -> list[str]:
    """Align all four native USD categories and every tier boundary exactly."""
    raw = [str(value or "N/A") for value in values]
    parsed = []
    for value in raw:
        tiers = []
        for part in value.replace(" -> ", "→").split("→"):
            rates, _, threshold = part.strip().partition(" ")
            match = re.fullmatch(r"\(([>≥])(\d+)\)", threshold)
            if match:
                threshold = f"({match[1]}{compact_threshold(int(match[2]))})"
            tiers.append((rates.split("/"), threshold))
        parsed.append(tiers)
    depth = max(map(len, parsed), default=0)
    widths = [[0] * 4 for _ in range(depth)]
    threshold_widths = [0] * depth
    for tiers in parsed:
        for index, (rates, _threshold) in enumerate(tiers):
            threshold_widths[index] = max(threshold_widths[index], visible_len(_threshold))
            if len(rates) == 4:
                for category, rate in enumerate(rates):
                    widths[index][category] = max(widths[index][category], visible_len(rate))
    result = []
    for tiers in parsed:
        parts = []
        for index, (rates, threshold) in enumerate(tiers):
            text = "/".join(rate.rjust(widths[index][category]) for category, rate in enumerate(rates)) \
                if len(rates) == 4 else "/".join(rates)
            parts.append(text + (" " + threshold.ljust(threshold_widths[index]) if threshold_widths[index] else ""))
        result.append("→".join(parts))
    return result
