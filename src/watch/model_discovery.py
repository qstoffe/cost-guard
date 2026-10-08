"""Watch-only model discovery; V2 is an early pricing-refresh hint, not release evidence.

CCost always uses the report service's pinned catalog. These later catalog
observations change only the Watch new-model notice. Release-date metadata
recovers on its own bounded worker so a slow or failing metadata source never
blocks Watch polling.
"""
from __future__ import annotations

import threading
from typing import Callable

from src.pricing.catalog import PricingCatalog, canonical_model_name
from src.pricing.release_metadata import valid_date
from src.reports.semantics import model_is_recent
from src.runtime_errors import recoverable, recovered
from src.sources.errors import SourceError

PRICE_CHECK_MS = 3_600_000
AVAILABILITY_CHECK_MS = 900_000
NEW_NOTICE_MS = 7 * 86_400_000
MAX_NOTICE_MODELS = 4
_CACHE_NAMESPACE = "watch.model-discovery"


def _key(model) -> str:
    return canonical_model_name(model.model.model)


def _name(model) -> str:
    return (model.model.display_name or model.model.model).strip()


def _priced(model) -> bool:
    """A model ID alone is not evidence of published reference prices."""
    options = model.tiers or (model,)
    return any(t.per_million_input is not None and t.per_million_output is not None
               for t in options)


def _released(model) -> str:
    return valid_date(model.metadata.get("release_date"))


def _thread_runner(work: Callable[[], None]) -> None:
    threading.Thread(target=work, name="cost-guard-model-metadata", daemon=True).start()


class WatchModelDiscovery:
    """Poll V2 every 15 minutes; a new ID forces one immediate Copilot fetch."""

    def __init__(self, service, *, run_async: Callable[[Callable[[], None]], None] | None = None) -> None:
        self.service = service
        self.catalog: PricingCatalog | None = None
        self._catalog_keys: set[str] = set()
        self._first_seen: dict[str, tuple[str, int]] = {}
        self.available_ids: tuple[str, ...] | None = None
        self._availability_known = False
        self._last_price_check_ms: int | None = None
        self._last_availability_check_ms: int | None = None
        self._v2_price_triggers = 0
        self._last_v2_price_trigger_ms: int | None = None
        self.last_price_error = ""
        self.last_availability_error = ""
        self._run_async = run_async or _thread_runner
        self._metadata_lock = threading.Lock()
        self._metadata_active = False
        self._metadata_result: PricingCatalog | None = None
        self._metadata_runs = 0
        self._metadata_reason = ""
        self.last_metadata_error = ""

    def _repository(self):
        return getattr(self.service, "cache_repository", None)

    def _persist_known(self) -> None:
        repository = self._repository()
        if repository is None:
            return
        try:
            repository.put(_CACHE_NAMESPACE, "known-catalog-ids",
                           sorted(self._catalog_keys), algorithm_version="v1")
            repository.put(_CACHE_NAMESPACE, "recent-discoveries",
                           {key: [name, seen] for key, (name, seen) in self._first_seen.items()},
                           algorithm_version="v1")
        except (OSError, ValueError):
            pass  # optional, non-authoritative notice history

    def _initialize(self, now_ms: int) -> None:
        self.catalog = self.service._load_catalog()
        self._catalog_keys = {_key(model) for model in self.catalog.models}
        repository = self._repository()
        if repository is not None:
            try:
                entry = repository.get(_CACHE_NAMESPACE, "known-catalog-ids")
                known = entry.payload if entry is not None else None
                entry = repository.get(_CACHE_NAMESPACE, "recent-discoveries")
                discoveries = entry.payload if entry is not None else None
                if isinstance(discoveries, dict):
                    for key, value in list(discoveries.items())[:256]:
                        if (isinstance(key, str) and isinstance(value, list)
                            and len(value) == 2 and isinstance(value[0], str)
                            and type(value[1]) is int and 0 <= now_ms - value[1] < NEW_NOTICE_MS):
                            self._first_seen[key] = (value[0], value[1])
                # Without earlier history a first read proves nothing new.
                if isinstance(known, list):
                    known_ids = {key for key in known if isinstance(key, str)}
                    for model in self.catalog.models:
                        key = _key(model)
                        if key and key not in known_ids and _priced(model) and not _released(model):
                            self._first_seen[key] = (_name(model), now_ms)
            except (OSError, ValueError):
                pass
        self._last_price_check_ms = now_ms
        self._persist_known()

    def _observe(self, latest: PricingCatalog, now_ms: int) -> None:
        """Catalog-diff evidence is needed only while no verified date exists."""
        for model in latest.models:
            key = _key(model)
            if key and key not in self._catalog_keys and _priced(model) and not _released(model):
                self._first_seen[key] = (_name(model), now_ms)
        self._catalog_keys.update(_key(model) for model in latest.models)
        self.catalog = latest
        self._persist_known()

    def _refresh_catalog(self, now_ms: int, *, force: bool = False) -> None:
        self._last_price_check_ms = now_ms  # bounded even when upstream is down
        try:
            latest = self.service.pricing_provider.get_catalog(force=force)
        except (SourceError, OSError, ValueError):
            self.last_price_error = "unavailable"
            return
        except Exception as exc:
            recoverable(exc, "watch-model-discovery-pricing")
            self.last_price_error = type(exc).__name__
            return
        recovered("watch-model-discovery-pricing")
        self.last_price_error = ""
        self._observe(latest, now_ms)

    def _adopt_metadata(self, now_ms: int) -> None:
        with self._metadata_lock:
            result, self._metadata_result = self._metadata_result, None
        if result is not None and self.catalog is not None and result.retrieved_at_ms >= self.catalog.retrieved_at_ms:
            self._observe(result, now_ms)

    def _maybe_refresh_metadata(self, now_ms: int, hint: str = "") -> None:
        """At most one bounded metadata worker; the provider owns backoff/429 rules."""
        provider = self.service.pricing_provider
        reason_of = getattr(provider, "metadata_refresh_reason", None)
        refresh = getattr(provider, "refresh_release_metadata", None)
        if not callable(reason_of) or not callable(refresh) or self.catalog is None:
            return
        with self._metadata_lock:
            if self._metadata_active:
                return
        reason = reason_of(self.catalog, now_ms=now_ms, hint=hint)
        if not reason:
            return
        with self._metadata_lock:
            self._metadata_active = True
        self._metadata_runs += 1
        self._metadata_reason = reason

        def work() -> None:
            result, error = None, ""
            try:
                result = refresh(reason=reason)
                recovered("watch-model-metadata")
            except Exception as exc:  # isolated optional enrichment worker
                error = type(exc).__name__
                recoverable(exc, "watch-model-metadata")
            finally:
                with self._metadata_lock:
                    self._metadata_active = False
                    self.last_metadata_error = error
                    if result is not None:
                        self._metadata_result = result
        self._run_async(work)

    def refresh(self, now_ms: int, *, resumed: bool = False) -> None:
        now_ms = int(now_ms)
        if self.catalog is None:
            self._initialize(now_ms)
        elif (resumed or self._last_price_check_ms is None
              or now_ms - self._last_price_check_ms >= PRICE_CHECK_MS):
            self._refresh_catalog(now_ms)
        self._adopt_metadata(now_ms)
        # Startup, resume and every poll: due only by health/backoff state.
        self._maybe_refresh_metadata(now_ms)

        # Read only the selected V2 service. No CLI fallback, process startup,
        # quota queries or provider entitlements are inferred.
        read = getattr(self.service.selection.source, "available_model_ids", None)
        if callable(read) and (self._last_availability_check_ms is None or resumed
                              or now_ms - self._last_availability_check_ms >= AVAILABILITY_CHECK_MS):
            self._last_availability_check_ms = now_ms
            try:
                result = read()
            except (SourceError, OSError, ValueError):
                self.last_availability_error = "unavailable"
            except Exception as exc:
                recoverable(exc, "watch-model-discovery-availability")
                self.last_availability_error = type(exc).__name__
            else:
                recovered("watch-model-discovery-availability")
                if result is None:
                    self.last_availability_error = "unverified"
                else:
                    self._observe_availability(result, now_ms)

        self._first_seen = {
            key: item for key, item in self._first_seen.items()
            if 0 <= now_ms - item[1] < NEW_NOTICE_MS
        }

    def _observe_availability(self, result, now_ms: int) -> None:
        ids = {item.lower(): item for item in result if isinstance(item, str)}
        first_read = not self._availability_known
        previous = {item.lower() for item in (self.available_ids or ())}
        novel = ({key for key in ids if key.startswith("github-copilot/") and key not in previous}
                 if not first_read else set())
        self.available_ids = tuple(ids.values())
        self._availability_known = True
        self.last_availability_error = ""
        if novel:
            # Bypass even a fresh 60-minute pricing cache. V2-only
            # models NEVER appear in the user-facing notice.
            self._v2_price_triggers += 1
            self._last_v2_price_trigger_ms = now_ms
            self._refresh_catalog(now_ms, force=True)
        elif first_read and self.catalog is not None:
            # The initial list proves nothing new, but a selectable model
            # still lacking a verified date is a reason to recheck metadata.
            selectable = {canonical_model_name(key) for key in ids if key.startswith("github-copilot/")}
            if any(_key(model) in selectable and _priced(model) and not _released(model)
                   for model in self.catalog.models):
                self._maybe_refresh_metadata(now_ms, hint="v2_undated_model")

    def notice(self, now_ms: int) -> str:
        """One Unicode heading; only verified priced catalog models qualify."""
        catalog = self.catalog or self.service._load_catalog()
        names: dict[str, tuple[str, str]] = {}
        for model in catalog.models:
            if not _priced(model):
                continue
            key = _key(model)
            released = _released(model)
            if released:
                # A verified old release date is never "new", whatever the history.
                if model_is_recent(released, now_ms=now_ms):
                    names[key] = (_name(model), released)
            elif key in self._first_seen and 0 <= now_ms - self._first_seen[key][1] < NEW_NOTICE_MS:
                names[key] = (_name(model), "")
        if not names:
            return ""
        values = sorted(names.values(), key=lambda item: item[0].lower())
        labels = [f"{name} ({date})" if date else name for name, date in values[:MAX_NOTICE_MODELS]]
        suffix = f" (+{len(values)-MAX_NOTICE_MODELS})" if len(values) > MAX_NOTICE_MODELS else ""
        return "✦ New Models: " + ", ".join(labels) + suffix

    def diagnostics(self, now_ms: int) -> dict[str, object]:
        provider_metadata = getattr(self.service.pricing_provider, "metadata_diagnostics", None)
        with self._metadata_lock:
            active, error = self._metadata_active, self.last_metadata_error
        return {
            "pricing_check_interval_minutes": PRICE_CHECK_MS // 60_000,
            "availability_check_interval_minutes": AVAILABILITY_CHECK_MS // 60_000,
            "catalog_models": len(self.catalog.models) if self.catalog else None,
            "dated_catalog_models": sum(bool(_released(m)) for m in self.catalog.models) if self.catalog else None,
            "verified_release_models": sum(
                model_is_recent(_released(m), now_ms=now_ms)
                for m in self.catalog.models if _priced(m)
            ) if self.catalog else None,
            "availability_known": self._availability_known,
            "available_model_count": len(self.available_ids) if self.available_ids is not None else None,
            "pricing_status": self.last_price_error or "ok",
            "availability_status": self.last_availability_error or ("ok" if self._availability_known else "unknown"),
            "new_catalog_model_count": len(self._first_seen),
            "v2_price_refresh_triggers": self._v2_price_triggers,
            "last_v2_price_refresh_ms": self._last_v2_price_trigger_ms,
            "metadata_refresh_runs": self._metadata_runs,
            "metadata_refresh_active": active,
            "last_metadata_refresh_reason": self._metadata_reason,
            "metadata_worker_status": error or "ok",
            "metadata": provider_metadata() if callable(provider_metadata) else None,
        }
