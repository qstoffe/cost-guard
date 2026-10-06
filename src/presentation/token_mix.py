"""Compact rendering of already-derived token shares and CCost; no acquisition."""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from src.analysis.token_mix import TokenMix
from src.numbers import balanced_share_percents, ccost_amount

MIX_LABELS = ("Input", "Cache", "Write", "Output")
MIX_TERM = "Token Mix %"


def compact_tokens(value: int) -> str:
    for size, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= size:
            text = f"{Decimal(value) / size:.1f}".removesuffix(".0")
            return text + suffix
    return str(value)


def mix_cost_text(mix: TokenMix, value: Decimal) -> str:
    """`?` marks known CCost that excludes unpriceable requests (partial)."""
    return ("" if mix.cost_complete else "?") + ccost_amount(value)


def total_cost_text(mix: TokenMix) -> str:
    if mix.costs is None or (mix.request_count and not mix.priced_requests):
        return "N/A"
    return mix_cost_text(mix, sum(mix.costs, Decimal(0)))


def _share_parts(mix: TokenMix) -> list[tuple[str, str | None]]:
    parts = []
    shares = (("--",) * 4 if any(share is None for share in mix.shares)
              else balanced_share_percents(mix.totals))
    for index, share in enumerate(shares):
        cost = None
        if mix.costs is not None:
            cost = "N/A" if mix.request_count and not mix.priced_requests else mix_cost_text(mix, mix.costs[index])
        parts.append((share, cost))
    return parts


def mix_cells(mix: TokenMix, *, labels: bool = True) -> tuple[str, ...]:
    return tuple((label + ": " if labels else "") + share + ("" if cost is None else f" ({cost})")
                 for label, (share, cost) in zip(MIX_LABELS, _share_parts(mix)))


def packed_cells(cells: Sequence[str], width: int, *, indent: str = "") -> list[str]:
    """Greedily pack whole cells into lines; a cell is never split."""
    lines: list[str] = []
    current = ""
    for cell in cells:
        candidate = current + "   " + cell if current else cell
        if current and len(indent) + len(candidate) > width:
            lines.append(indent + current)
            candidate = cell
        current = candidate
    return lines + ([indent + current] if current else [])


def aligned_mix_cells(mixes: Sequence[TokenMix]) -> list[tuple[str, ...]]:
    """Table cells whose share and parenthesized CCost align independently per category."""
    parts = [_share_parts(mix) for mix in mixes]
    rows: list[list[str]] = [[] for _ in parts]
    for index in range(len(MIX_LABELS)):
        column = [row[index] for row in parts]
        share_width = max((len(share) for share, _cost in column), default=0)
        cost_width = max((len(cost) for _share, cost in column if cost is not None), default=0)
        for row, (share, cost) in zip(rows, column):
            text = share.rjust(share_width)
            if cost is not None:
                text += f" ({cost.rjust(cost_width)})"
            elif cost_width:
                text += " " * (cost_width + 3)
            row.append(text)
    return [tuple(row) for row in rows]


def prompt_scope(count: int) -> str:
    return "1 prompt" if count == 1 else f"{count} prompts"


def token_mix_lines(scope: str, mix: TokenMix, *, width: int | None = None) -> list[str]:
    """One line when it fits; otherwise wrap cells under the heading."""
    heading = MIX_TERM + " · " + scope
    if not mix.request_count:
        return [heading + " · no token data yet"]
    cells = mix_cells(mix)
    line = heading + " · " + "   ".join(cells)
    if width is None or len(line) <= width:
        return [line]
    body = "  " + "   ".join(cells)
    return [heading, body] if len(body) <= width else [heading, *("  " + cell for cell in cells)]


def watch_total_line(mix: TokenMix) -> str:
    """CCost added during this Watch run: the run mix's deduplicated requests."""
    return "Watch total CCost: " + ("0" if not mix.request_count else total_cost_text(mix))


def session_subtotal_text(mix: TokenMix | None) -> str:
    """`Σ <value>` for CCost newly observed in this session during the Watch run."""
    return "Σ " + ("0" if mix is None or not mix.request_count else total_cost_text(mix))


def token_mix_line(scope: str, mix: TokenMix) -> str:
    return token_mix_lines(scope, mix)[0]
