"""Transfer a completed Models capture into the shared catalog write lane."""
from decimal import InvalidOperation
import sqlite3
from threading import Lock
import time

from src.cache.display_models import MODEL_PAGE, prepare_models
from src.reports.semantics import model_is_recent


class DisplayModels:
    def __init__(self, archive, publish):
        self.archive, self.publish = archive, publish
        self.signal = Lock()
        self.offered = None
        self.retry_at = 0
        self.prices_invalidated_ms = -1
        self.mark = None
        self.archive_epoch = None

    def binding(self):
        views = self.archive.views
        return (views, self.archive.sessions.clear_fence) if views is not None else None

    def offer(self, binding, result, *, eligible):
        if binding is None or binding != self.binding() or result.get("source", {}).get("model_scope") != binding[0].source:
            return False
        with self.signal:
            self.offered = binding, result, eligible
            self.retry_at = 0
        return True

    def pending(self):
        return self.offered is not None and time.monotonic() >= self.retry_at

    def advance(self, now_ms, *, active):
        with self.signal:
            offer = self.offered
        if offer is None:
            return
        binding, result, allowed = offer
        views, fence = binding

        def eligible():
            return self.offered is offer and self.binding() == binding and active() and allowed()

        published = False
        try:
            if eligible():
                catalog = prepare_models(result)
                if catalog.observed_ms <= now_ms:
                    published = self.archive.sessions.commit_models(views.source, views.binding, catalog,
                        clear_fence=fence, eligible=eligible)
        except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError, AttributeError):
            pass  # A malformed/incomplete producer result cannot replace the last snapshot.
        except (OSError, sqlite3.Error):
            with self.signal:
                if eligible():
                    self.retry_at = time.monotonic() + 5
            self.archive.initialize()
            return
        with self.signal:
            if published and eligible():
                self.mark = catalog.observed_ms
                self._announce(views)
            if self.offered is offer:
                self.offered = None

    def reset(self, views, *, archive_epoch=None):
        with self.signal:
            if self.archive.views is views:
                self.offered = None
                self.mark = None
                self.archive_epoch = archive_epoch
                self._announce(views)

    def invalidate_prices(self, now_ms):
        with self.signal:
            self.offered = None
            self.prices_invalidated_ms = max(self.prices_invalidated_ms, now_ms)
            self._announce(self.archive.views)

    def _announce(self, views):
        self.publish("models-cache", dict(binding=views.binding if views else None, mark=self.mark,
            price_floor_ms=self.prices_invalidated_ms, archive_epoch=self.archive_epoch))

    def snapshot(self, request, now_ms):
        bound = self.binding()
        if bound is None:
            return None
        views, _ = bound
        price_floor = self.prices_invalidated_ms
        saved, epoch = self.archive.history.models_page(views.source, request, now_ms, price_invalidated_ms=price_floor)
        page = dict(rows=[], offset=0, count=None, size=MODEL_PAGE, observed_ms=None, price_boundary_ms=None,
                    prices_valid=False, prices_historical=False, availability_empty=False, availability_unverified=False,
                    pricing_ms=None, pricing_label=None)
        if saved is not None:
            saved["rows"] = [_presentation(row, now_ms, prices_valid=saved["prices_valid"],
                             prices_historical=saved["prices_historical"]) for row in saved["rows"]]
            page.update(saved)
        if self.binding() != bound or self.prices_invalidated_ms != price_floor:
            return None
        return dict(page, binding=views.binding, archive_epoch=epoch, price_floor_ms=price_floor)

    def benchmark_references(self):
        bound = self.binding()
        if bound is None:
            return (), "UTC"
        views, _ = bound
        rows = self.archive.history.model_benchmark_references(views.source)
        return (rows, views.timezone_id) if self.binding() == bound else ((), "UTC")


def _presentation(row, now_ms, *, prices_valid, prices_historical):
    (publisher, model, category, release, cost, help_text, promo, description, through, resumes, comparison) = row
    promo = bool(promo and prices_valid and not prices_historical)
    return dict(publisher=publisher, model=model, category=category, release_date=release,
        recent=model_is_recent(release, now_ms=now_ms), promotional=promo,
        price_help=help_text if prices_valid else "Cached rates are no longer current.",
        display=dict(relative_cost=cost if prices_valid else "N/A"),
        promotion=dict(description=description, through=through, resumes=resumes,
                       price_comparison=comparison) if promo else None)
