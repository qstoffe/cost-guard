"""Protected Models paging, with no legacy lookup or acquisition fallback."""
import sqlite3
import time

from src.cache.display_models import ModelPage


def model_page(value):
    if set(value) != {"show_all", "latest", "orders", "offset"} or type(value["orders"]) is not list:
        raise ValueError("invalid_model_page")
    if any(type(item) is not list or len(item) != 2 or not all(type(part) is str for part in item)
           for item in value["orders"]):
        raise ValueError("invalid_model_order")
    return ModelPage(value["show_all"], value["latest"], tuple(tuple(item) for item in value["orders"]), value["offset"])


def cached_models(handler, value):
    try:
        request = model_page(value)
    except ValueError:
        handler.reply(400, {"error": "invalid_request"})
        return
    owner = handler.server.lifecycle
    archive = getattr(owner, "display_archive", None)
    models = getattr(archive, "models", None)
    if models is None:
        handler.reply(503, {"error": "cache_unavailable"})
        return
    binding, price_floor = models.binding(), models.prices_invalidated_ms
    try:
        result = models.snapshot(request, int(time.time() * 1000))
    except (OSError, sqlite3.Error):
        handler.reply(503, {"error": "cache_unavailable"})
        return
    if not handler.server.session.authenticated(handler.headers.get("Cookie")):
        handler.reply(401, {"error": "authentication_required"})
    elif (owner.display_archive is not archive or result is None or models.binding() != binding
            or models.prices_invalidated_ms != price_floor):
        handler.reply(503, {"error": "cache_source_unbound"})
    else:
        handler.reply(200, result)
