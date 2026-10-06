"""Shared semantic numeric presentation; never used to round analysis values.

Standard-library-only so report projections and terminal renderers share the
same amount/rate rules without depending on each other's layers.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from typing import Sequence


def exact_number(value: Decimal | int) -> str:
    """Locale-neutral exact rate/limit/ordinary number, without grouping."""
    text = str(value) if isinstance(value, int) else format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _capacity_amount(value: Decimal, *, rounding: str) -> str:
    if value == 0:
        return "0"
    if Decimal(0) < value < Decimal("0.1"):
        return "<0.1"
    if value < 1:
        return format(value.quantize(Decimal("0.1"), rounding=rounding), ".1f")
    return format(value.to_integral_value(rounding=rounding), "f")


def ccost_amount(value: Decimal | None, *, unresolved: bool = False) -> str:
    """Naked consumed/reference amount, conservative upward display only."""
    if value is None or (unresolved and value == 0):
        return "N/A"
    return ("?" if unresolved else "") + _capacity_amount(value, rounding=ROUND_CEILING)


def consumed_capacity(value: Decimal) -> str:
    return _capacity_amount(value, rounding=ROUND_CEILING)


def remaining_capacity(value: Decimal) -> str:
    return _capacity_amount(value, rounding=ROUND_FLOOR)


def balanced_share_percents(totals: Sequence[int]) -> tuple[str, ...]:
    """Largest-remainder display at 0.1 percentage points; exact integer math.

    Correct the categories with the largest fractional tenths (stable ties), not
    a fixed remainder bucket. Expects known nonnegative counts with a positive
    total; underlying token proportions are never changed.
    """
    total = sum(totals)
    tenths = [1000 * value // total for value in totals]
    order = sorted(range(len(totals)), key=lambda i: (-(1000 * totals[i] % total), i))
    for index in order[:1000 - sum(tenths)]:
        tenths[index] += 1
    return tuple(exact_number(Decimal(value) / 10) + "%" for value in tenths)


def reference_rate(value: Decimal | None) -> str:
    """Quoted rates retain meaningful source precision, never amount rounding."""
    return "-" if value is None else exact_number(value)


def ccost_range(cached: Decimal | None, fresh: Decimal | None) -> str:
    if cached is None and fresh is None:
        return "N/A"
    if cached is None or fresh is None or cached == fresh:
        return ccost_amount(fresh if cached is None else cached)
    low, high = sorted((cached, fresh))
    return ccost_amount(low) + "–" + ccost_amount(high)
