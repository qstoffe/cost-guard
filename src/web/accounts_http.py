"""Authenticated read of one selected Accounts chart period."""
import sqlite3
import time

from src.analysis.account_timeline import PERIODS


def cached_accounts(handler, value):
    period = value.get("period")
    if set(value) != {"period"} or type(period) is not str or period not in PERIODS:
        handler.reply(400, {"error": "invalid_request"})
        return
    owner = handler.server.lifecycle
    archive = getattr(owner, "display_archive", None)
    accounts = getattr(archive, "accounts", None)
    if accounts is None:
        handler.reply(503, {"error": "cache_unavailable"})
        return
    scope = accounts.scope()
    try:
        result = accounts.snapshot(period, int(time.time() * 1000))
    except (OSError, sqlite3.Error):
        handler.reply(503, {"error": "cache_unavailable"})
        return
    if not handler.server.session.authenticated(handler.headers.get("Cookie")):
        handler.reply(401, {"error": "authentication_required"})
    elif owner.display_archive is not archive or accounts.scope() != scope or result is None or result["scope"] != scope:
        handler.reply(503, {"error": "cache_source_unbound"})
    else:
        handler.reply(200, result)
