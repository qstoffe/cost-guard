"""Bounded, typed Models catalog snapshots and exact tier-vector order."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import unicodedata

from .display_sort_keys import decimal_key


MODEL_LIMIT = 512
MODEL_PAGE = 50
TIER_LIMIT = 16
MODEL_ORDERS = ("publisher", "model", "cost", "release")
DEFAULT_MODEL_ORDER = (("cost", "desc"),)


def order_sql(column, direction):
    if column == "cost":
        return f"cost_{direction}"
    return f"({column}_key IS NULL), {column}_key {direction}"


def models_schema():
    indexes = "\n".join(
        f"CREATE INDEX IF NOT EXISTS display_models_{column}_{direction} "
        f"ON display_models(source, {order_sql(column, direction)}, ordinal);"
        for column in MODEL_ORDERS for direction in ("asc", "desc"))
    return f"""
        CREATE TABLE IF NOT EXISTS display_model_state (
            source TEXT NOT NULL PRIMARY KEY REFERENCES sources(source),
            observed_ms INTEGER NOT NULL, pricing_ms INTEGER, pricing_label TEXT,
            price_boundary_ms INTEGER, price_stale INTEGER NOT NULL,
            availability_empty INTEGER NOT NULL, availability_unverified INTEGER NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS display_models (
            source TEXT NOT NULL REFERENCES display_model_state(source) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL,
            publisher TEXT, model TEXT NOT NULL, category TEXT, release_date TEXT,
            publisher_key TEXT, model_key TEXT NOT NULL, release_key INTEGER,
            selectable INTEGER NOT NULL, superseded INTEGER NOT NULL, superseded_selectable INTEGER NOT NULL,
            cost_asc BLOB NOT NULL, cost_desc BLOB NOT NULL,
            cost_label TEXT NOT NULL, price_help TEXT,
            promotional INTEGER NOT NULL, offer_description TEXT,
            offer_through TEXT, offer_resumes TEXT, offer_comparison TEXT,
            PRIMARY KEY(source, ordinal)
        ) WITHOUT ROWID;
        {indexes}
    """


@dataclass(frozen=True, slots=True)
class ModelPage:
    show_all: bool = False
    latest: bool = True
    orders: tuple[tuple[str, str], ...] = DEFAULT_MODEL_ORDER
    offset: int = 0

    def __post_init__(self):
        if (type(self.show_all) is not bool or type(self.latest) is not bool
                or type(self.offset) is not int or not 0 <= self.offset < MODEL_LIMIT or self.offset % MODEL_PAGE
                or not 1 <= len(self.orders) <= len(MODEL_ORDERS)
                or any(column not in MODEL_ORDERS or direction not in ("asc", "desc")
                       for column, direction in self.orders)
                or len({column for column, _ in self.orders}) != len(self.orders)):
            raise ValueError("invalid_model_page")


@dataclass(frozen=True, slots=True)
class ModelCatalog:
    observed_ms: int
    pricing_ms: int | None
    pricing_label: str | None
    price_boundary_ms: int | None
    price_stale: bool
    availability_empty: bool
    availability_unverified: bool
    rows: tuple


def text_value(value, limit):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("invalid_model_text")
    return value


def text_key(value):
    # Deterministic catalog order independent of the OS collation database.
    return ("".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                    if not unicodedata.combining(char)) if value else None)


def release_key(value):
    if value is None or len(value) != 10:
        return None
    try:
        return date.fromisoformat(value).toordinal()
    except ValueError:
        return None


def tier_keys(values):
    """Missing tiers compare as NULL, last in both directions at every level."""
    if not 1 <= len(values) <= TIER_LIMIT:
        raise ValueError("invalid_model_tiers")
    ascending, descending = bytearray(), bytearray()
    for value in (*values, *((None,) * (TIER_LIMIT - len(values)))):
        if value is None:
            ascending.append(255)
            descending.append(255)
            continue
        if not isinstance(value, str) or len(value) > 128:
            raise ValueError("invalid_model_price")
        key = decimal_key(Decimal(value))
        ascending.extend(b"\x00" + key)
        descending.extend(b"\x00" + bytes(255 - byte for byte in key))
    return bytes(ascending), bytes(descending)


def _model_values(row):
    publisher, model = text_value(row["publisher"], 256), text_value(row["model"], 256)
    if not model:
        raise ValueError("invalid_model_identity")
    tiers = row.get("relative_levels") or ()
    costs = [level["relative_cost"] for level in tiers] if tiers else [row["relative_cost"]]
    release = text_value(row["release_date"], 64)
    release_rank = release_key(release)
    promo = row.get("promotion") or {}
    return (publisher, model, text_value(row.get("category"), 256), release if release_rank else None,
            text_key(publisher), text_key(model), release_rank,
            row["selectable"] is True, row["superseded"] is True, row["superseded_selectable"] is True,
            *tier_keys(costs), text_value(row["display"]["relative_cost"], 4096) or "N/A",
            text_value(row.get("price_help"), 8192), row["promotional"] is True,
            *(text_value(promo.get(key), 4096) for key in ("description", "through", "resumes", "price_comparison")))


def prepare_models(result):
    """Validate one complete worker result before taking the SQLite writer."""
    source = result["source"]
    view = result["view"]
    observed, priced = source["observed_at_ms"], view.get("pricing_retrieved_at_ms")
    boundary = source["model_price_boundary_ms"]
    if (type(observed) is not int or observed < 0
            or priced is not None and (type(priced) is not int or priced < 0)
            or boundary is not None and (type(boundary) is not int or boundary < 0)):
        raise ValueError("invalid_model_observation")
    rows = view["model_catalog"]["rows"]
    if len(rows) > MODEL_LIMIT or any(row["promotional"] is True for row in rows) and boundary is None:
        raise ValueError("incomplete_model_catalog")
    values = tuple(_model_values(row) for row in rows)
    if len({row[:2] for row in values}) != len(values):
        raise ValueError("duplicate_model_identity")
    return ModelCatalog(observed, priced, text_value(view["display"].get("pricing_retrieved_at_ms"), 256), boundary,
                        source["model_price_stale"] is True,
                        view["model_availability_empty"] is True, view["model_availability_unverified"] is True, values)


def write_models(db, source, catalog):
    previous = db.execute("SELECT observed_ms FROM display_model_state WHERE source=?", (source,)).fetchone()
    if previous is not None and previous[0] >= catalog.observed_ms:
        return False
    db.execute("INSERT OR IGNORE INTO sources(source) VALUES(?)", (source,))
    db.execute("DELETE FROM display_model_state WHERE source=?", (source,))
    db.execute("INSERT INTO display_model_state VALUES(?,?,?,?,?,?,?,?)",
               (source, catalog.observed_ms, catalog.pricing_ms, catalog.pricing_label, catalog.price_boundary_ms,
                catalog.price_stale, catalog.availability_empty, catalog.availability_unverified))
    db.executemany("INSERT INTO display_models VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   ((source, ordinal, *row) for ordinal, row in enumerate(catalog.rows)))
    return True


def read_models(db, source, request, now_ms, price_invalidated_ms):
    state = db.execute("""
        SELECT observed_ms, pricing_ms, pricing_label, price_boundary_ms, price_stale,
            availability_empty, availability_unverified
        FROM display_model_state WHERE source=? AND observed_ms<=?
    """, (source, now_ms)).fetchone()
    if state is None:
        return None
    observed, pricing, pricing_label, boundary, stale, empty, unverified = state
    prices_valid = observed > price_invalidated_ms and (boundary is None or now_ms < boundary)
    match = ["source=?"]
    if not request.show_all:
        match.append("selectable=1")
    if request.latest:
        match.append("superseded=0" if request.show_all else "superseded_selectable=0")
    where = " AND ".join(match)
    orders = [order_sql(column, direction) for column, direction in request.orders if prices_valid or column != "cost"]
    order = ", ".join((*orders, "ordinal"))
    count = db.execute(f"SELECT count(*) FROM display_models WHERE {where}", (source,)).fetchone()[0]
    offset = min(request.offset, max(0, (count - 1) // MODEL_PAGE * MODEL_PAGE))
    rows = db.execute(f"""
        SELECT publisher, model, category, release_date, cost_label, price_help,
            promotional, offer_description, offer_through, offer_resumes, offer_comparison
        FROM display_models WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?
    """, (source, MODEL_PAGE, offset)).fetchall()
    return dict(observed_ms=observed, pricing_ms=pricing, pricing_label=pricing_label, price_boundary_ms=boundary,
                prices_valid=prices_valid, prices_historical=bool(stale), availability_empty=bool(empty),
                availability_unverified=bool(unverified),
                offset=offset, count=count, size=MODEL_PAGE, rows=rows)


def benchmark_references(db, source):
    return tuple(dict(publisher=publisher, model=model, release_date=release, selectable=bool(selectable),
                      superseded=bool(old), superseded_selectable=bool(selected_old))
                 for publisher, model, release, selectable, old, selected_old in db.execute("""
        SELECT publisher,model,release_date,selectable,superseded,superseded_selectable
        FROM display_models WHERE source=? ORDER BY ordinal LIMIT ?
    """, (source, MODEL_LIMIT)))
