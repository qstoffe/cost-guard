"""Presentation-only quota precision; canonical reference Credits remain unrounded."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

from src.numbers import ccost_amount, ccost_unit, exact_number


def within_tolerance(raw, candidate):
    with localcontext() as context:
        context.prec = max(context.prec, len(raw.as_tuple().digits) + 3, len(candidate.as_tuple().digits) + 3)
        return abs(candidate - raw) * 20 <= raw


def rounded_estimate(value):
    """Coarsest nearest half-up 1/2-significant-digit value within five percent."""
    try:
        raw = Decimal(value) if value is not None and not isinstance(value, bool) else None
    except (InvalidOperation, TypeError, ValueError):
        return None
    if raw is None or not raw.is_finite() or raw < 0:
        return None
    if not raw:
        return Decimal(0)
    with localcontext() as context:
        context.prec = max(context.prec, len(raw.as_tuple().digits) + 3)
        for digits in (1, 2):
            quantum = Decimal((0, (1,), raw.adjusted() - digits + 1))
            candidate = raw.quantize(quantum, rounding=ROUND_HALF_UP)
            # Multiplication avoids division/repeating-decimal boundary errors.
            if candidate > 0 and within_tolerance(raw, candidate):
                return candidate
    return raw


def estimate_amount(raw):
    rounded = rounded_estimate(raw)
    if rounded is None:
        return "?"
    if ccost_unit() == "credits":
        return exact_number(rounded)
    value = ccost_amount(rounded)
    return "<$0.01" if rounded > 0 and value == "$0.00" else value


def reference_help_amount(value, *, inferred=False):
    """Ordinary unit precision from raw Credits, never the visible estimate."""
    try:
        raw = Decimal(value) if value is not None and not isinstance(value, bool) else None
    except (InvalidOperation, TypeError, ValueError):
        return "?"
    if raw is None or not raw.is_finite() or raw < 0:
        return "?"
    if ccost_unit() == "credits":
        amount = ("<1" if 0 < raw < 1 else ccost_amount(raw)) + " Credits"
    else:
        amount = ccost_amount(raw)
        if raw > 0 and amount == "$0.00":
            amount = "<$0.01"
    return ("~" if inferred else "") + amount


def estimate_help(raw):
    amount = reference_help_amount(raw, inferred=True)
    return "" if amount == "?" else amount
