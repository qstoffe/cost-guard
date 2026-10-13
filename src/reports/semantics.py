"""Provider-neutral report semantics shared by projections and presentation.

Keep source/provider payload knowledge out; model notices combine catalog dates
with the shared cache-backed first-sighting timestamp.
"""
from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
import sqlite3

from src.cache.repository import CacheRepository
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


FIRST_SIGHTING_HIGHLIGHT_MS = 12 * 60 * 60 * 1000


def provider_qualified_model_id(model) -> str:
    """Return a stable lower-case provider/model key for shared persistence."""
    provider = str(getattr(model.model, "provider", "") or "").strip().casefold().strip("/")
    model_id = str(getattr(model.model, "model", "") or "").strip().casefold()
    if not provider or not model_id:
        return ""
    return model_id if model_id.startswith(provider + "/") else f"{provider}/{model_id}"


def _utc_timestamp(now_ms: int) -> str:
    seconds, milliseconds = divmod(int(now_ms), 1000)
    value = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(microsecond=milliseconds * 1000)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _timestamp_ms(value: str) -> int | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return None
    delta = parsed.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86_400 + delta.seconds) * 1000 + delta.microseconds // 1000


def model_first_sighting_ms(model, repository: CacheRepository | None, now_ms: int) -> int | None:
    """Atomically create or reuse the model's shared UTC first-sighting timestamp."""
    model_id = provider_qualified_model_id(model)
    if repository is None or not model_id:
        return None
    try:
        value = repository.get_or_create_model_first_seen_at(model_id, _utc_timestamp(now_ms))
    except (OSError, ValueError, sqlite3.Error):
        return None
    return _timestamp_ms(value)


def first_sighting_is_highlighted(first_seen_ms: int | None, now_ms: int) -> bool:
    return first_seen_ms is not None and int(now_ms) < first_seen_ms + FIRST_SIGHTING_HIGHLIGHT_MS


def recent_model_notice_details(
    catalog: PricingCatalog, *, now_ms: int, cache_repository: CacheRepository | None = None,
) -> tuple[str, tuple[tuple[int, int], ...]]:
    """Format the existing seven-day notice and identify only first-sighting name spans."""
    seen: set[tuple[str, str]] = set()
    recent: list[tuple[str, str, bool]] = []
    for model in catalog.models:
        released = str(model.metadata.get("release_date") or "")
        if not model_is_recent(released, now_ms=now_ms):
            continue
        name = (model.model.display_name or model.model.model or "").strip()
        if not name:
            continue
        first_seen = model_first_sighting_ms(model, cache_repository, now_ms)
        key = (name.casefold(), released)
        if key in seen:
            continue
        seen.add(key)
        recent.append((name, released, first_sighting_is_highlighted(first_seen, now_ms)))
    if not recent:
        return "", ()
    recent.sort(key=lambda item: (item[1], item[0].lower()))
    dates = sorted({released for _, released, _ in recent})
    text = "\u2726 New Models: "
    highlighted_spans: list[tuple[int, int]] = []
    for index, (name, released, highlighted) in enumerate(recent):
        if index:
            text += ", "
        start = len(text)
        text += f"\u2726 {name}" if highlighted else name
        if highlighted:
            highlighted_spans.append((start, len(text)))
        if len(dates) != 1:
            text += f" ({released})"
    if len(dates) == 1:
        text += f" \u00b7 released {dates[0]}"
    return text, tuple(highlighted_spans)


def recent_model_notice(
    catalog: PricingCatalog, *, now_ms: int, cache_repository: CacheRepository | None = None,
) -> str:
    return recent_model_notice_details(catalog, now_ms=now_ms, cache_repository=cache_repository)[0]


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
