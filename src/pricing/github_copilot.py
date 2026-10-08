"""GitHub Copilot pricing provider.

The provider intentionally owns GitHub-specific fetching, Markdown parsing and
promotion/release metadata. Analysis only consumes PricingCatalog or provider-neutral
ModelPricing values.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable, Iterable

from src.cache import CacheRepository
from src.domain import IntegrationHealth, ModelPricing, ModelRef, PricingTier, ProviderCapabilities
from src.runtime_errors import recoverable, recovered
from src.version import DISPLAY_VERSION

from .catalog import PricingCatalog, canonical_model_name
from .metadata_health import COMPONENT as METADATA_COMPONENT, MetadataHealthStore, default_root
from .release_metadata import (
    COPILOT_CHANGELOG_URL, INTERNAL, MODELS_DEV_URL, MetadataAttempt, SourceResult,
    enrich_release_dates, merge_release_dates, valid_date,
)

PRICING_ARTICLE_PATH = "/en/copilot/reference/copilot-billing/models-and-pricing"
DOCS_API_BODY = "https://docs.github.com/api/article/body?pathname="
CACHE_NAMESPACE = "pricing.github-copilot"
CACHE_KEY = "catalog"
CACHE_FORMAT_VERSION = 1


@dataclass(frozen=True, slots=True)
class Promotion:
    model_keys: tuple[str, ...]
    through_date: str
    expires_at_ms: int
    discount_percent: Decimal | None = None
    standard_tiers: dict[str, tuple[PricingTier, ...]] | None = None

    def active(self, now_ms: int) -> bool:
        return now_ms < self.expires_at_ms


FetchText = Callable[[str, int], str]


def _default_fetch_text(url: str, timeout_seconds: int) -> str:
    request = urllib.request.Request(
        url,
        headers={"Accept": "text/plain, application/json;q=0.9", "User-Agent": f"CostGuard/{DISPLAY_VERSION}"},
    )
    with urllib.request.urlopen(request, timeout=max(1, timeout_seconds)) as response:  # noqa: S310 - fixed HTTPS URLs
        return response.read().decode("utf-8")


def _clean_heading(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", value or "")
    value = re.sub(r"\{#.*?\}", "", value)
    return re.sub(r"[*_`]", "", value).strip()


def _provider_from_heading(value: str) -> str:
    heading = _clean_heading(value).lower()
    mapping = (
        ("openai", "OpenAI"), ("anthropic", "Anthropic"), ("google", "Google"),
        ("fine-tuned", "Fine-tuned (GitHub)"), ("microsoft", "Microsoft"),
        ("xai", "xAI"), ("moonshot", "Moonshot AI"),
    )
    for prefix, provider in mapping:
        if heading.startswith(prefix):
            return provider
    return ""


def _provider_from_model(name: str) -> str:
    for pattern, provider in (
        (r"^GPT-", "OpenAI"), (r"^Claude\b", "Anthropic"), (r"^Gemini\b", "Google"),
        (r"^Raptor\b", "Fine-tuned (GitHub)"), (r"^MAI-", "Microsoft"),
        (r"^Grok\b", "xAI"), (r"^Kimi\b", "Moonshot AI"),
    ):
        if re.search(pattern, name, re.I):
            return provider
    return ""


def _clean_model_name(value: str) -> str:
    value = re.sub(r"<sup[^>]*>.*?</sup>", "", value or "", flags=re.I | re.S)
    value = re.sub(r"\[\^[^\]]+\]", "", value)
    value = re.sub(r"\^\{.*?\}", "", value)
    return value.strip()


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _normalize_header(value: str) -> str:
    return _clean_heading(value).lower()


def _parse_decimal(value: str | None) -> Decimal | None:
    if not value or "not applicable" in value.lower():
        return None
    match = re.search(r"\$?\s*([0-9]+(?:\.[0-9]+)?)", value)
    if not match:
        return None
    try:
        return Decimal(match.group(1))
    except InvalidOperation:
        return None


def _parse_threshold(value: str | None) -> tuple[int | None, int | None]:
    if not value or "not applicable" in value.lower():
        return None, None
    clean = value.replace(",", "")
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([KkMm])?", clean)
    if not match:
        return None, None
    number = Decimal(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit == "k":
        number *= 1000
    elif unit == "m":
        number *= 1_000_000
    integer = int(number.to_integral_value())
    if ">" in value:
        return integer + 1, None
    if "≤" in value or "<" in value:
        return None, integer
    return None, None


def parse_pricing_markdown(markdown: str) -> tuple[ModelPricing, ...]:
    lines = markdown.splitlines()
    provider = ""
    models: dict[str, dict[str, object]] = {}
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        heading = re.match(r"^#{2,4}\s+(.+)$", line)
        if heading:
            resolved = _provider_from_heading(heading.group(1))
            if resolved:
                provider = resolved
            index += 1
            continue
        if "|" not in line:
            index += 1
            continue
        headers = _split_row(line)
        normalized = [_normalize_header(header) for header in headers]
        required = {"model", "input", "cached input", "output"}
        if not required.issubset(normalized) or index + 1 >= len(lines) or "---" not in lines[index + 1]:
            index += 1
            continue
        index += 2
        while index < len(lines):
            row_line = lines[index].strip()
            if not row_line or re.match(r"^#{1,6}\s+", row_line) or "|" not in row_line:
                break
            cells = _split_row(row_line)
            row = {normalized[i]: cells[i] for i in range(min(len(normalized), len(cells)))}
            name = _clean_model_name(row.get("model", ""))
            row_provider = provider or _provider_from_model(name)
            input_rate = _parse_decimal(row.get("input"))
            cached_rate = _parse_decimal(row.get("cached input"))
            output_rate = _parse_decimal(row.get("output"))
            if not name or not row_provider or input_rate is None or cached_rate is None or output_rate is None:
                index += 1
                continue
            key = canonical_model_name(name)
            model = models.setdefault(key, {"name": name, "provider": row_provider, "tiers": [], "metadata": {}})
            metadata = model["metadata"]
            assert isinstance(metadata, dict)
            for source, target in (("release status", "release_status"), ("category", "category")):
                if row.get(source):
                    metadata[target] = row[source]
            min_tokens, max_tokens = _parse_threshold(row.get("threshold (input tokens)"))
            tiers = model["tiers"]
            assert isinstance(tiers, list)
            tiers.append(PricingTier(
                name=row.get("tier") or "Default",
                min_input_tokens=min_tokens,
                max_input_tokens=max_tokens,
                per_million_input=input_rate,
                per_million_cache_read=cached_rate,
                per_million_cache_write=_parse_decimal(row.get("cache write")),
                per_million_output=output_rate,
            ))
            index += 1
        continue
    result: list[ModelPricing] = []
    for key, value in models.items():
        metadata = dict(value["metadata"])
        metadata["key"] = key
        metadata["publisher"] = str(value["provider"])
        tiers = tuple(value["tiers"])
        first = tiers[0] if tiers else PricingTier()
        result.append(ModelPricing(
            model=ModelRef(provider="github-copilot", model=key, display_name=str(value["name"])),
            currency="USD",
            per_million_input=first.per_million_input,
            per_million_cache_read=first.per_million_cache_read,
            per_million_cache_write=first.per_million_cache_write,
            per_million_output=first.per_million_output,
            tiers=tiers,
            metadata=metadata,
        ))
    return tuple(result)


def _tier_to_dict(tier: PricingTier) -> dict[str, object]:
    return {
        "name": tier.name,
        "min": tier.min_input_tokens,
        "max": tier.max_input_tokens,
        "i": str(tier.per_million_input) if tier.per_million_input is not None else None,
        "c": str(tier.per_million_cache_read) if tier.per_million_cache_read is not None else None,
        "w": str(tier.per_million_cache_write) if tier.per_million_cache_write is not None else None,
        "o": str(tier.per_million_output) if tier.per_million_output is not None else None,
    }


def _tier_from_dict(value: dict[str, object]) -> PricingTier:
    def decimal(key: str) -> Decimal | None:
        raw = value.get(key)
        return Decimal(str(raw)) if raw is not None else None
    return PricingTier(
        name=str(value.get("name") or "Default"),
        min_input_tokens=int(value["min"]) if value.get("min") is not None else None,
        max_input_tokens=int(value["max"]) if value.get("max") is not None else None,
        per_million_input=decimal("i"), per_million_cache_read=decimal("c"),
        per_million_cache_write=decimal("w"), per_million_output=decimal("o"),
    )


def _model_to_dict(model: ModelPricing) -> dict[str, object]:
    return {
        "model": model.model.model, "display": model.model.display_name, "provider": model.model.provider,
        "currency": model.currency, "tiers": [_tier_to_dict(tier) for tier in model.tiers],
        "metadata": dict(model.metadata),
    }


def _model_from_dict(value: dict[str, object]) -> ModelPricing:
    tiers = tuple(_tier_from_dict(dict(item)) for item in value.get("tiers", []) if isinstance(item, dict))
    first = tiers[0] if tiers else PricingTier()
    return ModelPricing(
        model=ModelRef(provider=str(value.get("provider") or "github-copilot"), model=str(value.get("model") or ""), display_name=str(value.get("display") or "") or None),
        currency=str(value.get("currency") or "USD"),
        per_million_input=first.per_million_input, per_million_cache_read=first.per_million_cache_read,
        per_million_cache_write=first.per_million_cache_write, per_million_output=first.per_million_output,
        tiers=tiers, metadata={str(k): str(v) for k, v in dict(value.get("metadata") or {}).items()},
    )



def _parse_promotion_date(markdown: str, model: ModelPricing) -> tuple[int, Decimal | None, int | None] | None:
    name = re.escape(model.model.display_name or model.model.model)
    date_pattern = (
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},\s+\d{4}|\d{4}-\d{2}-\d{2}"
    )
    # Only model-associated prose, never a table occurrence followed by another
    # model's unrelated footnote. Grouped promotion footnotes remain supported.
    prose = "\n".join(line for line in markdown.splitlines() if "|" not in line)
    paragraph = next((part for part in re.split(r"\n\s*\n", prose)
                      if re.search(r"(?<![\w-])" + name + r"(?![\w-])", part, re.I)
                      and re.search(r"promotional pricing", part, re.I)), "")
    match = re.search(r"through\s+(" + date_pattern + r")", paragraph, re.I)
    if match is None:
        return None
    def parse_date(value: str) -> int:
        fmt = "%Y-%m-%d" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else "%B %d, %Y"
        return int(datetime.strptime(" ".join(value.split()), fmt).replace(tzinfo=timezone.utc).timestamp() * 1000)
    try:
        expires_ms = parse_date(match.group(1)) + 86_400_000
    except ValueError:
        return None
    start = re.search(r"\b(?:from|starting(?: on)?|effective(?: from| on)?|begins?(?: on)?)\s+("
                      + date_pattern + r")", paragraph, re.I)
    starts_ms = None
    if start:
        try:
            starts_ms = parse_date(start.group(1))
        except ValueError:
            pass
    discount_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*off", paragraph, re.I)
    discount = Decimal(discount_match.group(1)) if discount_match else None
    return expires_ms, discount, starts_ms


def _scaled_standard_tiers(tiers: tuple[PricingTier, ...], discount_percent: Decimal) -> tuple[PricingTier, ...]:
    if discount_percent <= 0 or discount_percent >= 100:
        return ()
    factor = Decimal(1) / (Decimal(1) - discount_percent / Decimal(100))
    def scale(value: Decimal | None) -> Decimal | None:
        return value * factor if value is not None else None
    return tuple(PricingTier(
        name=tier.name, min_input_tokens=tier.min_input_tokens, max_input_tokens=tier.max_input_tokens,
        per_million_input=scale(tier.per_million_input),
        per_million_cache_read=scale(tier.per_million_cache_read),
        per_million_cache_write=scale(tier.per_million_cache_write),
        per_million_output=scale(tier.per_million_output),
    ) for tier in tiers)


def _annotate_promotions(models: Iterable[ModelPricing], markdown: str) -> tuple[ModelPricing, ...]:
    result: list[ModelPricing] = []
    for model in models:
        promo = _parse_promotion_date(markdown, model)
        if promo is None:
            result.append(model)
            continue
        expires_ms, discount, starts_ms = promo
        meta = dict(model.metadata)
        meta["promotion_expires_ms"] = str(expires_ms)
        meta["promotion_active"] = "true"
        if starts_ms is not None:
            meta["promotion_starts_ms"] = str(starts_ms)
        if discount is not None:
            meta["promotion_discount_percent"] = str(discount)
            standard = _scaled_standard_tiers(model.tiers, discount)
            if standard:
                meta["promotion_standard_tiers"] = json.dumps([_tier_to_dict(tier) for tier in standard], separators=(",", ":"))
        result.append(ModelPricing(
            model=model.model, currency=model.currency,
            per_million_input=model.per_million_input, per_million_cache_read=model.per_million_cache_read,
            per_million_cache_write=model.per_million_cache_write, per_million_output=model.per_million_output,
            tiers=model.tiers, metadata=meta,
        ))
    return tuple(result)


def _apply_expired_promotions(catalog: PricingCatalog, now_ms: int) -> PricingCatalog:
    models: list[ModelPricing] = []
    for model in catalog.models:
        raw_expiry = model.metadata.get("promotion_expires_ms")
        if not raw_expiry:
            models.append(model)
            continue
        try:
            expired = now_ms >= int(raw_expiry)
        except (TypeError, ValueError):
            expired = True
        meta = dict(model.metadata)
        if not expired:
            meta["promotion_active"] = "true"
            models.append(ModelPricing(
                model=model.model, currency=model.currency,
                per_million_input=model.per_million_input, per_million_cache_read=model.per_million_cache_read,
                per_million_cache_write=model.per_million_cache_write, per_million_output=model.per_million_output,
                tiers=model.tiers, metadata=meta,
            ))
            continue
        raw_standard = meta.get("promotion_standard_tiers")
        if not raw_standard:
            # Expired promotional rates without a verified standard fallback must
            # not continue to look current.  Omitting the model yields N/A.
            continue
        try:
            decoded = json.loads(raw_standard)
            standard = tuple(_tier_from_dict(dict(item)) for item in decoded if isinstance(item, dict))
        except (TypeError, ValueError, InvalidOperation):
            continue
        if not standard:
            continue
        meta["promotion_active"] = "false"
        meta["expired_promotion_fallback"] = "true"
        first = standard[0]
        models.append(ModelPricing(
            model=model.model, currency=model.currency,
            per_million_input=first.per_million_input, per_million_cache_read=first.per_million_cache_read,
            per_million_cache_write=first.per_million_cache_write, per_million_output=first.per_million_output,
            tiers=standard, metadata=meta,
        ))
    return PricingCatalog(
        models=tuple(models),
        retrieved_at_ms=catalog.retrieved_at_ms,
        source_revision=catalog.source_revision,
        refresh_not_after_ms=catalog.refresh_not_after_ms,
    )


def _catalog_payload(catalog: PricingCatalog) -> dict[str, object]:
    return {
        "version": CACHE_FORMAT_VERSION, "retrieved_at_ms": catalog.retrieved_at_ms,
        "source_revision": catalog.source_revision, "refresh_not_after_ms": catalog.refresh_not_after_ms,
        "models": [_model_to_dict(model) for model in catalog.models],
    }


def _catalog_from_payload(payload: object) -> PricingCatalog | None:
    if not isinstance(payload, dict) or int(payload.get("version", 0)) != CACHE_FORMAT_VERSION:
        return None
    try:
        models = tuple(_model_from_dict(dict(item)) for item in payload.get("models", []) if isinstance(item, dict))
        if not models:
            return None
        return PricingCatalog(
            models=models,
            retrieved_at_ms=int(payload.get("retrieved_at_ms", 0)),
            source_revision=str(payload.get("source_revision") or ""),
            refresh_not_after_ms=int(payload["refresh_not_after_ms"]) if payload.get("refresh_not_after_ms") is not None else None,
        )
    except (TypeError, ValueError, InvalidOperation):
        return None


def _tier_sets_equal(left: tuple[PricingTier, ...], right: tuple[PricingTier, ...]) -> bool:
    return left == right


def _preserve_known_promotions(
    models: Iterable[ModelPricing], previous: PricingCatalog | None, now_ms: int,
) -> tuple[ModelPricing, ...]:
    if previous is None:
        return tuple(models)
    old = {canonical_model_name(model.model.model): model for model in previous.models}
    result: list[ModelPricing] = []
    for model in models:
        known = old.get(canonical_model_name(model.model.model))
        if model.metadata.get("promotion_expires_ms"):
            # Preserve a proven start only for the same validity/rates, never
            # use retrieval/release time or carry an old start into a new offer.
            if (known is not None and _tier_sets_equal(model.tiers, known.tiers)
                    and model.metadata.get("promotion_expires_ms") == known.metadata.get("promotion_expires_ms")
                    and not model.metadata.get("promotion_starts_ms")
                    and known.metadata.get("promotion_starts_ms")):
                model = ModelPricing(
                    model=model.model, currency=model.currency,
                    per_million_input=model.per_million_input, per_million_cache_read=model.per_million_cache_read,
                    per_million_cache_write=model.per_million_cache_write, per_million_output=model.per_million_output,
                    tiers=model.tiers, metadata={**model.metadata, "promotion_starts_ms": known.metadata["promotion_starts_ms"]},
                )
            result.append(model)
            continue
        if known is None or not _tier_sets_equal(model.tiers, known.tiers):
            result.append(model)
            continue
        try:
            expires = int(known.metadata.get("promotion_expires_ms", "0"))
        except (TypeError, ValueError):
            expires = 0
        if expires <= now_ms:
            result.append(model)
            continue
        meta = dict(model.metadata)
        for key, value in known.metadata.items():
            if key.startswith("promotion_"):
                meta[key] = value
        result.append(ModelPricing(
            model=model.model, currency=model.currency,
            per_million_input=model.per_million_input, per_million_cache_read=model.per_million_cache_read,
            per_million_cache_write=model.per_million_cache_write, per_million_output=model.per_million_output,
            tiers=model.tiers, metadata=meta,
        ))
    return tuple(result)


class PricingUnavailableError(RuntimeError):
    """External pricing document no longer satisfies the supported schema."""


class GitHubCopilotPricingProvider:
    provider_id = "github-copilot"
    capabilities = ProviderCapabilities(model_pricing=True, long_context_pricing=True)

    def __init__(
        self,
        *,
        cache: CacheRepository,
        max_age_hours: float = 6.0,
        fetch_text: FetchText = _default_fetch_text,
        now_ms: Callable[[], int] | None = None,
        metadata_store: MetadataHealthStore | None = None,
        defer_metadata_refresh: bool = False,
    ) -> None:
        self.cache = cache
        self.max_age_hours = max(0.0, float(max_age_hours))
        self.fetch_text = fetch_text
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._catalog: PricingCatalog | None = None
        self.metadata = metadata_store if metadata_store is not None else MetadataHealthStore(default_root())
        # Watch runs metadata-only refreshes on its own worker; reports may block briefly.
        self.defer_metadata_refresh = bool(defer_metadata_refresh)
        self._lock = threading.RLock()
        self._metadata_active = threading.Lock()

    def probe(self) -> IntegrationHealth:
        try:
            catalog = self.get_catalog()
            return IntegrationHealth(bool(catalog.models), bool(catalog.models), f"{len(catalog.models)} priced models")
        except PricingUnavailableError as exc:
            return IntegrationHealth(True, False, f"GitHub Copilot pricing unavailable: {type(exc).__name__}")

    def get_model_pricing(self) -> tuple[ModelPricing, ...]:
        return self.get_catalog().models

    def get_catalog(self, *, force: bool = False) -> PricingCatalog:
        with self._lock:
            catalog = self._load_or_fetch(force)
        # Fresh prices do not imply healthy release dates (separate health/backoff).
        if not self.defer_metadata_refresh:
            reason = self.metadata_refresh_reason(catalog)
            if reason:
                catalog = self.refresh_release_metadata(reason=reason) or catalog
        return catalog

    def _load_or_fetch(self, force: bool) -> PricingCatalog:
        if self._catalog is not None and not force and not self._expired(self._catalog):
            return self._catalog
        cached_entry = self.cache.get(CACHE_NAMESPACE, CACHE_KEY)
        cached = _catalog_from_payload(cached_entry.payload) if cached_entry else None
        if not force and cached is not None and not self._expired(cached):
            cached = _apply_expired_promotions(cached, self.now_ms())
            self._catalog = cached
            return cached
        try:
            catalog = self._fetch_catalog(cached)
        except PricingUnavailableError:
            if cached is not None:
                safe_cached = _apply_expired_promotions(cached, self.now_ms())
                self._catalog = safe_cached
                return safe_cached
            raise
        self.cache.put(CACHE_NAMESPACE, CACHE_KEY, _catalog_payload(catalog), algorithm_version=f"pricing-{CACHE_FORMAT_VERSION}")
        self._catalog = catalog
        return catalog

    def metadata_refresh_reason(self, catalog: PricingCatalog | None = None, *,
                                now_ms: int | None = None, hint: str = "") -> str:
        catalog = catalog or self._catalog
        if catalog is None:
            return ""
        return self.metadata.refresh_reason(
            priced=len(catalog.models),
            dated=sum(bool(valid_date(m.metadata.get("release_date"))) for m in catalog.models),
            retrieved_at_ms=catalog.retrieved_at_ms,
            now_ms=self.now_ms() if now_ms is None else int(now_ms), hint=hint,
        )

    def metadata_diagnostics(self) -> dict:
        return self.metadata.snapshot()

    def _enrich(self, models, previous, *, reason: str) -> tuple[ModelPricing, ...]:
        """Optional enrichment; every outcome, including defects, is classified and recorded."""
        models, previous = tuple(models), tuple(previous)
        try:
            enriched, attempt = enrich_release_dates(models, previous, self.fetch_text)
        except Exception as exc:
            recoverable(exc, METADATA_COMPONENT)
            enriched = merge_release_dates(models, previous)[0]
            attempt = MetadataAttempt(
                (SourceResult("metadata", "failed", INTERNAL, "internal", reason=type(exc).__name__),),
                len(enriched), sum(bool(valid_date(m.metadata.get("release_date"))) for m in enriched),
                cache_fallback=True,
            )
        else:
            recovered(METADATA_COMPONENT)
        self.metadata.record(attempt, self.now_ms(), reason=reason)
        return enriched

    def refresh_release_metadata(self, *, reason: str = "manual") -> PricingCatalog | None:
        """Metadata-only refresh: prices and retrieval time never change."""
        if not self._metadata_active.acquire(blocking=False):
            self.metadata.skipped("already_running", self.now_ms())
            return None
        try:
            with self._lock:
                entry = self.cache.get(CACHE_NAMESPACE, CACHE_KEY)
                base = (_catalog_from_payload(entry.payload) if entry else None) or self._catalog
            if base is None:
                self.metadata.skipped("no_catalog", self.now_ms())
                return None
            enriched = self._enrich(base.models, base.models, reason=reason)
            with self._lock:
                # Merge into the CURRENT catalog; a concurrent price refresh wins for prices.
                entry = self.cache.get(CACHE_NAMESPACE, CACHE_KEY)
                current = (_catalog_from_payload(entry.payload) if entry else None) or base
                models, _ = merge_release_dates(current.models, enriched)
                updated = PricingCatalog(models=models, retrieved_at_ms=current.retrieved_at_ms,
                                         source_revision=current.source_revision,
                                         refresh_not_after_ms=current.refresh_not_after_ms)
                self.cache.put(CACHE_NAMESPACE, CACHE_KEY, _catalog_payload(updated),
                               algorithm_version=f"pricing-{CACHE_FORMAT_VERSION}")
                self._catalog = _apply_expired_promotions(updated, self.now_ms())
                return self._catalog
        finally:
            self._metadata_active.release()

    def _expired(self, catalog: PricingCatalog) -> bool:
        if catalog.retrieved_at_ms <= 0:
            return True
        now = self.now_ms()
        age_ms = now - catalog.retrieved_at_ms
        if age_ms > self.max_age_hours * 3_600_000:
            return True
        retrieved_month = datetime.fromtimestamp(catalog.retrieved_at_ms / 1000, tz=timezone.utc).strftime("%Y-%m")
        current_month = datetime.fromtimestamp(now / 1000, tz=timezone.utc).strftime("%Y-%m")
        if retrieved_month != current_month:
            return True
        if catalog.refresh_not_after_ms is not None and now >= catalog.refresh_not_after_ms:
            return True
        return False

    def _fetch_catalog(self, previous: PricingCatalog | None = None) -> PricingCatalog:
        try:
            pricing = self.fetch_text(DOCS_API_BODY + PRICING_ARTICLE_PATH, 20)
        except OSError:
            raise PricingUnavailableError("GitHub pricing source unavailable; retry later") from None
        models = list(_annotate_promotions(parse_pricing_markdown(pricing), pricing))
        models = list(_preserve_known_promotions(models, previous, self.now_ms()))
        if len(models) < 5:
            raise PricingUnavailableError(f"GitHub pricing parser found only {len(models)} models")
        # Release dates are enrichment only. A failed optional fetch never
        # invalidates fresh pricing and never erases previously verified dates.
        models = list(self._enrich(models, previous.models if previous else (), reason="pricing_refresh"))
        now = self.now_ms()
        revision = hashlib.sha256(pricing.encode("utf-8")).hexdigest()
        expiries = [
            int(model.metadata["promotion_expires_ms"]) for model in models
            if str(model.metadata.get("promotion_expires_ms", "")).isdigit()
            and int(model.metadata["promotion_expires_ms"]) > now
        ]
        refresh_not_after = min(expiries) if expiries else None
        return _apply_expired_promotions(
            PricingCatalog(
                models=tuple(models),
                retrieved_at_ms=now,
                source_revision=revision,
                refresh_not_after_ms=refresh_not_after,
            ),
            now,
        )
