"""Release-date enrichment: independent sources, failure classes and merge rules.

Dates are optional enrichment and never pricing truth. Date meaning rule:
`models.dev` supplies the model's own release date and wins whenever it has
exactly one date for an exact identity. The official GitHub changelog supplies
the date GitHub announced the model *in Copilot*; it is used only when no
models.dev date exists. `release_date_source` records which meaning applies.
A previously verified date is carried forward only for the identical model
identity (catalog ID, display name and publisher), never to a neighbouring
version.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
import json
import re
import socket
import ssl
from typing import Callable, Iterable
import urllib.error
from xml.etree import ElementTree

from src.domain import ModelPricing

from .catalog import canonical_model_name

MODELS_DEV_URL = "https://models.dev/models.json"
COPILOT_CHANGELOG_URL = "https://github.blog/changelog/feed/"
MODELS_DEV = "models.dev"
CHANGELOG = "github-changelog"
SOURCES = (MODELS_DEV, CHANGELOG)
SOURCE_TIMEOUT_SECONDS = {MODELS_DEV: 15, CHANGELOG: 8}

# Stable machine-readable classification codes (diagnostics contract).
OK = "ok"
DNS = "dns_failure"
CONNECTION = "connection_failure"
TLS = "tls_failure"
HTTP = "http_error"
TIMEOUT = "timeout"
JSON_PARSE = "json_parse_error"
XML_PARSE = "xml_parse_error"
SCHEMA = "invalid_schema"
MISSING_FIELDS = "missing_fields"
ZERO_MATCHES = "zero_matches"
PARTIAL_MATCHES = "partial_matches"
CACHE_FALLBACK = "cache_fallback"
SKIPPED = "skipped_refresh"
INTERNAL = "unexpected_internal_error"
FAILURE_CODES = frozenset({DNS, CONNECTION, TLS, HTTP, TIMEOUT, JSON_PARSE, XML_PARSE,
                           SCHEMA, MISSING_FIELDS, ZERO_MATCHES, INTERNAL})
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PUBLISHER_PREFIXES = {
    "OpenAI": ("openai/",), "Anthropic": ("anthropic/",), "Google": ("google/",),
    "Microsoft": ("microsoft/",), "xAI": ("xai/", "x-ai/"), "Moonshot AI": ("moonshotai/", "moonshot/"),
}

FetchText = Callable[[str, int], str]


class MetadataSourceError(Exception):
    """A classified, message-free metadata failure."""

    def __init__(self, code: str, phase: str, *, http_status: int | None = None,
                 timeout_seconds: int | None = None, retry_after_seconds: int | None = None) -> None:
        super().__init__(code)
        self.code, self.phase = code, phase
        self.http_status, self.timeout_seconds = http_status, timeout_seconds
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class SourceResult:
    source: str
    status: str  # ok | failed | skipped
    code: str
    phase: str
    matched: int = 0
    http_status: int | None = None
    timeout_seconds: int | None = None
    retry_after_seconds: int | None = None
    reason: str = ""

    def as_dict(self) -> dict[str, object]:
        return {key: value for key, value in asdict(self).items() if value not in (None, "")}


@dataclass(frozen=True, slots=True)
class MetadataAttempt:
    sources: tuple[SourceResult, ...]
    priced_models: int
    dated_models: int
    cache_fallback: bool

    @property
    def failed(self) -> bool:
        return any(item.status == "failed" for item in self.sources)

    @property
    def health(self) -> str:
        return metadata_health(self.priced_models, self.dated_models, failed=self.failed)


def metadata_health(priced: int, dated: int, *, failed: bool = False) -> str:
    """healthy / partial / unavailable; an empty catalog is unknown."""
    if priced <= 0:
        return "unknown"
    if dated <= 0:
        return "unavailable"
    return "partial" if failed or dated * 2 < priced else "healthy"


def valid_date(value: object) -> str:
    text = str(value or "")
    if not _DATE.fullmatch(text):
        return ""
    try:
        date.fromisoformat(text)
    except ValueError:
        return ""
    return text


def _retry_after(headers) -> int | None:
    raw = headers.get("Retry-After") if headers is not None else None
    if not raw:
        return None
    raw = str(raw).strip()
    if raw.isdigit():
        return min(int(raw), 86_400)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0, min(86_400, int((when - datetime.now(timezone.utc)).total_seconds())))


def classify_transport(exc: BaseException, timeout_seconds: int) -> MetadataSourceError:
    """Map transport exceptions to stable codes without retaining their messages."""
    if isinstance(exc, urllib.error.HTTPError):
        status = exc.code if isinstance(exc.code, int) else None
        return MetadataSourceError(HTTP, "fetch", http_status=status, retry_after_seconds=_retry_after(exc.headers))
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, socket.gaierror):
        return MetadataSourceError(DNS, "dns")
    if isinstance(reason, (ssl.SSLError, ssl.CertificateError)):
        return MetadataSourceError(TLS, "tls")
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return MetadataSourceError(TIMEOUT, "fetch", timeout_seconds=timeout_seconds)
    return MetadataSourceError(CONNECTION, "connect")


def _fetch(fetch_text: FetchText, source: str, url: str) -> str:
    timeout = SOURCE_TIMEOUT_SECONDS[source]
    try:
        return fetch_text(url, timeout)
    except (OSError, HTTPException) as exc:
        error = classify_transport(exc, timeout)
        if isinstance(exc, urllib.error.HTTPError):
            exc.close()  # release the response body; it is never read
        raise error from None
    except ValueError:  # undecodable body
        raise MetadataSourceError(JSON_PARSE if source == MODELS_DEV else XML_PARSE, "decode") from None


def _models_dev_dates(models: Iterable[ModelPricing], text: str) -> dict[str, str]:
    try:
        payload = json.loads(text)
    except ValueError:
        raise MetadataSourceError(JSON_PARSE, "parse") from None
    records = [(str(key).lower(), value) for key, value in payload.items()
               if isinstance(value, dict)] if isinstance(payload, dict) else []
    if not records:
        raise MetadataSourceError(SCHEMA, "schema")
    if not any("release_date" in raw and "name" in raw for _, raw in records):
        raise MetadataSourceError(MISSING_FIELDS, "schema")
    result: dict[str, str] = {}
    for model in models:
        target = canonical_model_name(model.model.display_name or model.model.model)
        prefixes = _PUBLISHER_PREFIXES.get(str(model.metadata.get("publisher", "")), ())
        matches = {
            valid_date(raw.get("release_date")) for model_id, raw in records
            if (not prefixes or model_id.startswith(prefixes))
            and target in {canonical_model_name(str(raw.get("name") or "")),
                           canonical_model_name(model_id.rsplit("/", 1)[-1])}
        } - {""}
        if len(matches) == 1:  # ambiguous identities stay undated
            result[canonical_model_name(model.model.model)] = next(iter(matches))
    return result


def _changelog_dates(models: Iterable[ModelPricing], text: str) -> dict[str, str]:
    """Strict official `<Model> in GitHub Copilot` titles, never fuzzy guesses."""
    try:
        tree = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        raise MetadataSourceError(XML_PARSE, "parse") from None
    items = tree.findall(".//item")
    if not items:
        raise MetadataSourceError(SCHEMA, "schema")
    announced: dict[str, set[str]] = {}
    complete = 0
    for entry in items[:80]:
        title = str(entry.findtext("title") or "").strip()
        published = entry.findtext("pubDate")
        if not title or not published:
            continue
        complete += 1
        match = re.fullmatch(r"(.+?) in GitHub Copilot", title, re.I)
        if not match:
            continue
        try:
            day = parsedate_to_datetime(published).astimezone(timezone.utc).date().isoformat()
        except (TypeError, ValueError, OverflowError, IndexError):
            continue
        announced.setdefault(canonical_model_name(match.group(1)), set()).add(day)
    if not complete:
        raise MetadataSourceError(MISSING_FIELDS, "schema")
    result: dict[str, str] = {}
    for model in models:
        dates = announced.get(canonical_model_name(model.model.display_name or model.model.model), set())
        if len(dates) == 1:
            result[canonical_model_name(model.model.model)] = next(iter(dates))
    return result


def _run_source(source: str, url: str, parse, models, fetch_text: FetchText) -> tuple[SourceResult, dict[str, str]]:
    try:
        dates = parse(models, _fetch(fetch_text, source, url))
    except MetadataSourceError as exc:
        return SourceResult(source, "failed", exc.code, exc.phase, http_status=exc.http_status,
                            timeout_seconds=exc.timeout_seconds,
                            retry_after_seconds=exc.retry_after_seconds), {}
    if source == MODELS_DEV and not dates:
        return SourceResult(source, "failed", ZERO_MATCHES, "match"), {}
    # The changelog only covers recent announcements; zero matches is normal.
    code = OK if len(dates) >= len(models) else (PARTIAL_MATCHES if dates else ZERO_MATCHES)
    return SourceResult(source, "ok", code, "complete", matched=len(dates)), dates


_STAGES = ("https", "parse", "schema", "match")
_FAILED_STAGE = {"dns": 0, "connect": 0, "tls": 0, "fetch": 0, "decode": 1, "parse": 1,
                 "schema": 2, "match": 3, "internal": 0}


def stage_flags(result: dict) -> dict[str, bool | None]:
    """Which pipeline stages succeeded for one recorded source result."""
    if result.get("status") == "skipped" or not result:
        return {stage: None for stage in _STAGES}
    if result.get("status") == "ok":
        return {stage: True for stage in _STAGES}
    failed = _FAILED_STAGE.get(str(result.get("phase")), 0)
    return {stage: (True if index < failed else False if index == failed else None)
            for index, stage in enumerate(_STAGES)}


def probe_sources(models: Iterable[ModelPricing], fetch_text: FetchText) -> dict[str, dict]:
    """Diagnostics-only live probe of BOTH sources, each independently classified."""
    models = tuple(models)
    probes = {}
    for source, url, parse in ((MODELS_DEV, MODELS_DEV_URL, _models_dev_dates),
                               (CHANGELOG, COPILOT_CHANGELOG_URL, _changelog_dates)):
        result = _run_source(source, url, parse, models, fetch_text)[0].as_dict()
        probes[source] = {**result, "stages": stage_flags(result)}
    return probes


def _identity(model: ModelPricing) -> tuple[str, str, str]:
    return (canonical_model_name(model.model.model),
            canonical_model_name(model.model.display_name or model.model.model),
            str(model.metadata.get("publisher", "")).lower())


def merge_release_dates(
    models: Iterable[ModelPricing], previous: Iterable[ModelPricing],
    models_dev: dict[str, str] | None = None, changelog: dict[str, str] | None = None,
) -> tuple[tuple[ModelPricing, ...], int]:
    """Apply the documented precedence; returns models and carried-forward count."""
    prior = {_identity(item): (valid_date(item.metadata.get("release_date")),
                               str(item.metadata.get("release_date_source") or "legacy-cache"))
             for item in previous if valid_date(item.metadata.get("release_date"))}
    models_dev, changelog = models_dev or {}, changelog or {}
    result: list[ModelPricing] = []
    carried = 0
    for model in models:
        key = canonical_model_name(model.model.model)
        own = valid_date(model.metadata.get("release_date"))
        if key in models_dev:
            value = (models_dev[key], MODELS_DEV)
        elif _identity(model) in prior:
            value, carried = prior[_identity(model)], carried + 1
        elif key in changelog:
            value = (changelog[key], CHANGELOG)
        elif own:
            value = (own, str(model.metadata.get("release_date_source") or "legacy-cache"))
        else:
            value = None
        meta = {k: v for k, v in model.metadata.items() if k not in {"release_date", "release_date_source"}}
        if value is not None:
            meta["release_date"], meta["release_date_source"] = value
        result.append(model if dict(model.metadata) == meta else replace(model, metadata=meta))
    return tuple(result), carried


def enrich_release_dates(
    models: Iterable[ModelPricing], previous: Iterable[ModelPricing], fetch_text: FetchText,
) -> tuple[tuple[ModelPricing, ...], MetadataAttempt]:
    """Query each source independently; one failing source never blocks the other."""
    models, previous = tuple(models), tuple(previous)
    md_result, md_dates = _run_source(MODELS_DEV, MODELS_DEV_URL, _models_dev_dates, models, fetch_text)
    interim, _ = merge_release_dates(models, previous, md_dates)
    if all(valid_date(item.metadata.get("release_date")) for item in interim):
        cl_result, cl_dates = SourceResult(CHANGELOG, "skipped", SKIPPED, "skipped", reason="all_models_dated"), {}
    else:
        cl_result, cl_dates = _run_source(CHANGELOG, COPILOT_CHANGELOG_URL, _changelog_dates, models, fetch_text)
    merged, carried = merge_release_dates(models, previous, md_dates, cl_dates)
    dated = sum(bool(valid_date(item.metadata.get("release_date"))) for item in merged)
    failed = md_result.status == "failed" or cl_result.status == "failed"
    return merged, MetadataAttempt((md_result, cl_result), len(merged), dated, bool(failed and carried))
