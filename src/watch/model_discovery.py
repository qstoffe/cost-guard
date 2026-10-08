"""Bounded Watch-only discovery of Copilot models, independent of CCost valuation.

The report's price catalog remains pinned for the Watch run. Refreshes here
change notifications only; they never replace analysis prices or quotas.
"""
from __future__ import annotations

from src.pricing.catalog import PricingCatalog, canonical_model_name
from src.reports.semantics import model_is_recent
from src.sources.errors import SourceError
from src.runtime_errors import recoverable, recovered

PRICE_CHECK_MS = 3_600_000
AVAILABILITY_CHECK_MS = 900_000
NEW_NOTICE_MS = 7 * 86_400_000
MAX_NOTICE_MODELS = 4


def _model_key(model) -> str:
    return canonical_model_name(model.model.model)


def _model_name(model) -> str:
    return (model.model.display_name or model.model.model).strip()


class WatchModelDiscovery:
    """Observe upstream catalog and selected V2 availability on separate schedules.

    No CLI fallback: Watch must never launch OpenCode as part of discovery.
    No mutable valuation state: all newly fetched prices are notice-only.
    """

    def __init__(self, service) -> None:
        self.service = service
        self.catalog: PricingCatalog | None = None
        self._catalog_keys: set[str] = set()
        self._first_seen: dict[str, tuple[str, int]] = {}
        self._opencode_new: dict[str, int] = {}
        self.available_ids: tuple[str, ...] | None = None
        self._availability_known = False
        self._last_price_check_ms: int | None = None
        self._last_availability_check_ms: int | None = None
        self.last_price_error = ""
        self.last_availability_error = ""

    def refresh(self, now_ms: int, *, resumed: bool = False) -> None:
        now_ms = int(now_ms)
        if self.catalog is None:
            # The normal report's pinned catalog is the baseline, not a new release.
            self.catalog = self.service._load_catalog()
            self._catalog_keys = {_model_key(model) for model in self.catalog.models}
            # Persist only catalog identities so a model discovered between Watch
            # runs is still recognized. No private/session/account data is stored.
            repo = getattr(self.service, "cache_repository", None)
            if repo is not None:
                try:
                    old = repo.get("watch.model-discovery", "known-catalog-ids")
                    prior = old.payload if old is not None else None
                    if isinstance(prior, list):
                        known = {v for v in prior if isinstance(v, str)}
                        for model in self.catalog.models:
                            key = _model_key(model)
                            if key not in known and not model_is_recent(
                                str(model.metadata.get("release_date") or ""), now_ms=now_ms
                            ):
                                self._first_seen[key] = (_model_name(model), now_ms)
                    repo.put("watch.model-discovery", "known-catalog-ids",
                             sorted(self._catalog_keys), algorithm_version="v1")
                except (OSError, ValueError):
                    pass
            self._last_price_check_ms = now_ms
        elif (resumed or self._last_price_check_ms is None
              or now_ms - self._last_price_check_ms >= PRICE_CHECK_MS):
            self._last_price_check_ms = now_ms  # one attempt per window, including outages
            try:
                latest = self.service.pricing_provider.get_catalog()
            except (SourceError, OSError, ValueError):
                self.last_price_error = "unavailable"
            except Exception as exc:
                recoverable(exc, "watch-model-discovery-pricing")
                self.last_price_error = type(exc).__name__
            else:
                recovered("watch-model-discovery-pricing")
                self.last_price_error = ""
                new_models = [model for model in latest.models if _model_key(model) not in self._catalog_keys]
                for model in new_models:
                    key = _model_key(model)
                    if key and not model_is_recent(str(model.metadata.get("release_date") or ""), now_ms=now_ms):
                        self._first_seen[key] = (_model_name(model), now_ms)
                self._catalog_keys.update(_model_key(model) for model in latest.models)
                self.catalog = latest
                repo = getattr(self.service, "cache_repository", None)
                if repo is not None:
                    try:
                        repo.put("watch.model-discovery", "known-catalog-ids",
                                 sorted(self._catalog_keys), algorithm_version="v1")
                    except (OSError, ValueError):
                        pass

        # V2's current service is the read-only authority for *selectability*.
        # Do not use the CLI fallback (which may wake OpenCode after suspend).
        selected = self.service.selection.source
        read = getattr(selected, "available_model_ids", None)
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
                if result is not None:
                    new_ids = {item.lower(): item for item in result if isinstance(item, str)}
                    previous = {item.lower() for item in (self.available_ids or ())}
                    if self._availability_known:
                        for key, model_id in new_ids.items():
                            if key not in previous and key.startswith("github-copilot/"):
                                self._opencode_new[key] = now_ms
                    self.available_ids = tuple(new_ids.values())
                    self._availability_known = True
                    self.last_availability_error = ""
                else:
                    self.last_availability_error = "unverified"
        self._first_seen = {
            k: v for k, v in self._first_seen.items()
            if 0 <= now_ms - v[1] < NEW_NOTICE_MS
        }
        self._opencode_new = {
            k: t for k, t in self._opencode_new.items()
            if 0 <= now_ms - t < NEW_NOTICE_MS
        }

    def notice(self, now_ms: int) -> str:
        """One normalized notice for release, catalog and availability evidence."""
        catalog = self.catalog or self.service._load_catalog()
        names: dict[str, tuple[str, str]] = {}
        for model in catalog.models:
            date = str(model.metadata.get("release_date") or "")
            if model_is_recent(date, now_ms=now_ms):
                names[_model_key(model)] = (_model_name(model), date)
        for key, (name, seen) in self._first_seen.items():
            if 0 <= now_ms - seen < NEW_NOTICE_MS:
                names.setdefault(key, (name, ""))
        for key, seen in self._opencode_new.items():
            if 0 <= now_ms - seen < NEW_NOTICE_MS:
                identity = next((s for s in self.available_ids or () if s.lower() == key), key)
                match = catalog.resolve_reference(identity)
                display = _model_name(match) if match is not None else identity.split("/", 1)[-1]
                canonical = _model_key(match) if match is not None else canonical_model_name(display)
                names.setdefault(canonical, (display, ""))
        if not names:
            return ""
        values = sorted(names.values(), key=lambda x: x[0].lower())
        formatted = [f"{name} ({date})" if date else name for name, date in values[:MAX_NOTICE_MODELS]]
        suffix = f" (+{len(values)-MAX_NOTICE_MODELS})" if len(values) > MAX_NOTICE_MODELS else ""
        return "✦ New Models: " + ", ".join(formatted) + suffix

    def diagnostics(self, now_ms: int) -> dict[str, object]:
        return {
            "pricing_check_interval_minutes": PRICE_CHECK_MS // 60_000,
            "availability_check_interval_minutes": AVAILABILITY_CHECK_MS // 60_000,
            "catalog_models": len(self.catalog.models) if self.catalog else None,
            "verified_release_models": sum(
                model_is_recent(str(model.metadata.get("release_date") or ""), now_ms=now_ms)
                for model in self.catalog.models
            ) if self.catalog else None,
            "availability_known": self._availability_known,
            "available_model_count": len(self.available_ids) if self.available_ids is not None else None,
            "pricing_status": self.last_price_error or "ok",
            "availability_status": self.last_availability_error or ("ok" if self._availability_known else "unknown"),
            "new_catalog_model_count": len(self._first_seen),
            "new_opencode_model_count": len(self._opencode_new),
        }
