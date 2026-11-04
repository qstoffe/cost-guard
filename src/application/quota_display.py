"""Web-only native quota orientation variants, independent of CCost and acquisition."""
from decimal import Decimal

from src.display import money, native_amount, quota_usage
from .contracts import record


def percent(fraction):
    if fraction is None:
        return "—"
    if 0 < fraction < Decimal("0.0005"):
        return ">0%"
    if fraction < 1 and fraction * 100 >= Decimal("99.95"):
        return "<100%"
    return f"{fraction * 100:.1f}".removesuffix(".0") + "%"


def quota_displays(values):
    """Consume only normalized quota fields; preserve source precision and overage."""
    numbers = {key: None if values.get(key) is None else Decimal(values[key]) for key in
               ("used", "limit", "remaining", "remaining_fraction", "remaining_money", "limit_money")}
    unlimited = values.get("unlimited", False)
    used_fraction, used, used_money = quota_usage(**numbers, unlimited=unlimited)
    limit, remaining = numbers["limit"], numbers["remaining"]
    finite = not unlimited and (limit is None or limit > 0)
    fraction = None
    if finite and limit is not None and remaining is not None:
        fraction = remaining / limit
    elif finite and numbers["remaining_fraction"] is not None:
        fraction = numbers["remaining_fraction"]
    elif finite and used_fraction is not None:
        fraction = 1 - used_fraction
    if values.get("window_active") is False:
        fraction = None
    if remaining is None and limit is not None and fraction is not None:
        remaining = max(Decimal(0), limit - used) if used is not None else fraction * limit
    remaining_money = numbers["remaining_money"]
    if fraction is not None and remaining_money is None and numbers["limit_money"] is not None:
        remaining_money = fraction * numbers["limit_money"]
    exhausted = fraction <= 0 if fraction is not None else used_fraction == 1
    overage = (f"Native Used {native_amount(used, values.get('unit'), kind='consumed')} exceeds "
               f"limit {native_amount(limit, values.get('unit'))}." if not unlimited and
               used is not None and limit is not None and limit > 0 and used > limit else "")

    def variant(mode, fill, amount, native_money):
        unit = values.get("unit") or "units"
        native = "N/A" if amount is None else native_amount(amount, unit,
            kind="remaining" if mode == "remaining" else "consumed")
        if not unlimited and limit is not None and limit > 0:
            native += "/" + native_amount(limit, unit)
        bounded = None if fill is None else max(Decimal(0), min(Decimal(1), fill))
        used_percent = "—" if bounded is None else ("<100%" if bounded < 1 and bounded * 100 >= Decimal("99.95")
            else f"{bounded * 100:.1f}".removesuffix(".0") + "%")
        return record(mode=mode, fraction=bounded, percent=percent(bounded) if mode == "remaining" else used_percent,
            account_percent="N/A" if bounded is None else f"{bounded * 100:.0f}%",
            native=native + " " + unit, money=money(native_money),
            exhausted=exhausted if mode == "remaining" else used_fraction == 1, note=overage)

    used_view = variant("used", used_fraction, used, used_money)
    return record(used=used_view, remaining=used_view if fraction is None else
                  variant("remaining", fraction, remaining, remaining_money))
