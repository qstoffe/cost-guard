"""Small provider-neutral report semantics shared by projections and presentation.

Keep source/provider payload knowledge out of this module.  These helpers encode
v77-visible report decisions that are derived only from canonical analysis and
pricing metadata.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime, timedelta, timezone

from src.analysis.models import PromptRecord
from src.pricing.catalog import PricingCatalog, canonical_model_name
from src.pricing.promotions import model_promotion


def prompt_has_additional_model(record: PromptRecord) -> bool:
    root = canonical_model_name(record.main_model_id)
    if not root:
        return False
    for entry in record.entries:
        model = canonical_model_name(entry.model.model)
        if model and model != root:
            return True
    return False


def input_context_above_price_threshold(catalog: PricingCatalog, model_id: str, tokens: int) -> bool:
    if tokens <= 0:
        return False
    model = catalog.resolve(model_id)
    if model is None:
        return False
    return any(
        tier.min_input_tokens is not None and tier.min_input_tokens > 0 and tokens >= tier.min_input_tokens
        for tier in model.tiers
    )


def _release_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def model_is_recent(release_date: str | None, *, now_ms: int) -> bool:
    released = _release_date(release_date)
    if released is None:
        return False
    today = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).date()
    age = (today - released).days
    return 0 <= age < 7


def recent_model_notice(catalog: PricingCatalog, *, now_ms: int) -> str:
    seen: set[tuple[str, str]] = set()
    recent: list[tuple[str, str]] = []
    for model in catalog.models:
        released = str(model.metadata.get("release_date") or "")
        if not model_is_recent(released, now_ms=now_ms):
            continue
        name = (model.model.display_name or model.model.model or "").strip()
        if not name:
            continue
        key = (name.lower(), released)
        if key in seen:
            continue
        seen.add(key)
        recent.append((name, released))
    if not recent:
        return ""
    recent.sort(key=lambda item: (item[1], item[0].lower()))
    dates = sorted({released for _, released in recent})
    if len(dates) == 1:
        return f"✦ New Models: {', '.join(name for name, _ in recent)} · released {dates[0]}"
    return "✦ New Models: " + ", ".join(f"{name} ({released})" for name, released in recent)


def active_promotion_notes(
    catalog: PricingCatalog, now_ms: int, *, recent_only: bool = False,
) -> tuple[dict[str, int], tuple[str, ...]]:
    """Assign table markers/notes; Watch selects only proven recently started promotions."""
    groups: dict[tuple[int, str], list[object]] = {}
    for model in catalog.models:
        promotion = model_promotion(model)
        if promotion is None or not promotion.active(now_ms):
            continue
        if recent_only and not promotion.recent(now_ms):
            continue
        groups.setdefault((promotion.expires_ms, promotion.discount_percent), []).append(model)

    markers: dict[str, int] = {}
    notes: list[str] = []
    for marker, ((expires_ms, discount), models) in enumerate(groups.items(), start=1):
        names: list[str] = []
        for model in models:
            name = model.model.display_name or model.model.model
            if name:
                markers[name] = marker
                names.append(name)
        expires = datetime.fromtimestamp(expires_ms / 1000, tz=timezone.utc)
        through = (expires - timedelta(days=1)).strftime("%Y-%m-%d")
        resumes = expires.strftime("%Y-%m-%d")
        description = "temporary GitHub Copilot promotional pricing"
        if discount:
            try:
                discount_text = f"{Decimal(discount):f}"
                if "." in discount_text:
                    discount_text = discount_text.rstrip("0").rstrip(".")
                description = f"{discount_text}% off standard GitHub Copilot rates"
            except (ValueError, ArithmeticError):
                pass
        label = "* Price Promotion:" if recent_only else f"*{marker} Price Promotion:"
        ending = f" through {through}." if recent_only else f" through {through}; standard pricing resumes {resumes}."
        notes.append(f"{label} {', '.join(names)} — {description}{ending}")
    return markers, tuple(notes)


def aggregate_usage_notes(month, comparison) -> tuple[str, ...]:
    notes: list[str] = []
    if month.deduplicated_clone_requests:
        notes.append(
            f"Local calculated excluded {month.deduplicated_clone_requests} cloned provider request(s) "
            f"copied by session forks (${month.deduplicated_clone_dollars:.2f})."
        )
    unpriced = comparison.observed_requests - comparison.priced_requests
    if unpriced:
        notes.append(
            f"WARNING: {unpriced} request(s) could not be assigned CCost because reference pricing was unavailable; CCost totals are incomplete."
        )
    return tuple(notes)
