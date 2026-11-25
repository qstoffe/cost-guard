"""Independent local dependency checks used by Web Diagnostics."""
from contextlib import closing, contextmanager
import json
import sqlite3
import stat
import time

from development.tools.diagnostic_section import section


def config_evidence(root):
    from src.config import load_configuration

    result = load_configuration(root)
    return result.values, {"status": "readable", "user_config_present": result.user_config_present,
                           "open_code_source": result.open_code_source}


@contextmanager
def _read_database(path):
    from src.log_paths import safe_path

    if not stat.S_ISREG(path.lstat().st_mode) or not safe_path(path.parents[1], path):
        raise ValueError("unsafe_cache_path")
    with closing(sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True, timeout=0.2)) as db:
        db.execute("PRAGMA query_only=ON")
        yield db


def _cache_probe(path, *, application_id=None, schema=None):
    try:
        with _read_database(path) as db:
            actual_schema = db.execute("PRAGMA user_version").fetchone()[0]
            actual_app = db.execute("PRAGMA application_id").fetchone()[0]
            result = {"status": "readable", "user_version": actual_schema}
            if application_id is not None and (actual_app, actual_schema) != (application_id, schema):
                result.update(status="unexpected_schema", expected_user_version=schema,
                              application_matches=actual_app == application_id)
            if application_id is None:
                row = db.execute("SELECT value FROM cache_metadata WHERE key='schema_generation'").fetchone()
                result["generation_matches"] = bool(row and row[0] == str(schema))
                if not result["generation_matches"]:
                    result["status"] = "unexpected_schema"
            return result
    except FileNotFoundError:
        return {"status": "missing"}


def cache_evidence(root):
    from src.cache.database import CACHE_SCHEMA_GENERATION, cache_paths
    from src.cache.web_archive import APPLICATION_ID, SCHEMA, WEB_ARCHIVE_FILENAME

    paths = cache_paths(root)
    return {
        "disposable": section(lambda: _cache_probe(paths.database, schema=CACHE_SCHEMA_GENERATION),
                              phase="disposable_cache_read"),
        "web_report": section(lambda: _cache_probe(paths.directory / WEB_ARCHIVE_FILENAME,
                                                   application_id=APPLICATION_ID, schema=SCHEMA),
                              phase="web_report_cache_read"),
    }


_PROVIDER_CONFIG = ("copilotQuota", "openAiQuota", "anthropicQuota", "minimaxQuota", "deepseekQuota", "openrouterQuota")


def _cached_pricing(root):
    from src.cache.database import cache_paths
    from src.pricing.github_copilot import CACHE_KEY, CACHE_NAMESPACE, _catalog_from_payload
    from src.pricing.release_metadata import valid_date

    try:
        with _read_database(cache_paths(root).database) as db:
            row = db.execute("SELECT substr(payload_json, 1, 1048577) FROM cache_entries "
                             "WHERE namespace=? AND cache_key=?", (CACHE_NAMESPACE, CACHE_KEY)).fetchone()
    except FileNotFoundError:
        return {"status": "missing"}
    if not row:
        return {"status": "not_observed"}
    if len(row[0]) > 1_048_576:
        return {"status": "oversize"}
    catalog = _catalog_from_payload(json.loads(row[0]))
    if catalog is None:
        return {"status": "unreadable_catalog"}
    return {"status": "recorded", "model_count": len(catalog.models),
            "release_dates_known": sum(bool(valid_date(model.metadata.get("release_date"))) for model in catalog.models),
            "retrieved_at_ms": catalog.retrieved_at_ms}


def _metadata_state(root):
    from src.cache.metadata_state import read_state
    from src.pricing.release_metadata import SOURCES

    recorded = read_state(root)
    if not recorded:
        return {"status": "not_observed"}
    evidence = {name: recorded[name] for name in ("last_complete_ms", "next_retry_ms", "consecutive_failures")
                if type(recorded.get(name)) is int}
    sources = recorded.get("sources")
    if isinstance(sources, dict):
        evidence["recorded_failures"] = {name: bool(entry.get("period")) for name in SOURCES
                                         if isinstance(entry := sources.get(name), dict)}
    return {"status": "recorded", **evidence}


def provider_evidence(root, config):
    return {
        "configured_integrations": {} if config is None else
            {key: bool(config[key].get("enabled", True)) for key in _PROVIDER_CONFIG if isinstance(config.get(key), dict)},
        "pricing_cache": section(lambda: _cached_pricing(root), phase="pricing_cache_read"),
        "release_metadata": section(lambda: _metadata_state(root), phase="recorded_release_metadata"),
        "active_provider_requests": "not_run",
    }


def local_source(generation):
    start = time.monotonic()
    if generation == "v1":
        from src.sources.opencode_v1 import OpenCodeV1Source
        source = OpenCodeV1Source()
    else:
        from src.sources.opencode_v2 import OpenCodeV2Source
        source = OpenCodeV2Source(timeout_seconds=1.0, record_connectivity=False)
    health = source.probe()
    probe = {key: getattr(health, key) for key in ("available", "healthy", "failure_code", "failure_phase",
                                                 "exception_type", "http_status")}
    result = {"status": "probed", "probe": probe, "elapsed_ms": round((time.monotonic() - start) * 1000, 2)}
    if generation == "v2":
        result["connectivity"] = source.diagnostic_metadata()["connectivity"]
    return result
