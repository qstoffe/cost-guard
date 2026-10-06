"""Disposable derived-analysis cache keyed by explicit semantic dependencies."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Protocol

from src.cache import CacheRepository
from src.domain import AccountRef, CostDisposition, ModelRef, NormalizedSession, Provenance, SessionSnapshot, TokenUsage

from .models import CompactionRecord, PromptRecord, RootAnalysisBundle, TraceEntry

ANALYSIS_ALGORITHM_VERSION = "v78-analysis-10-background"
_CACHE_NAMESPACE = "derived-analysis"


@dataclass(frozen=True, slots=True)
class AnalysisDependencies:
    config_signature: str
    pricing_signature: str
    algorithm_version: str = ANALYSIS_ALGORITHM_VERSION


@dataclass(frozen=True, slots=True)
class CachedAnalysisResult:
    bundle: RootAnalysisBundle
    cache_hit: bool
    snapshot: SessionSnapshot | None = None


def dependency_signature(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _trace_to_dict(entry: TraceEntry) -> dict[str, Any]:
    return {
        "session_id": entry.session_id,
        "parent_event_id": entry.parent_event_id,
        "message_id": entry.message_id,
        "step_part_id": entry.step_part_id,
        "completed_at_ms": entry.completed_at_ms,
        "sort_order": entry.sort_order,
        "model": {"provider": entry.model.provider, "model": entry.model.model, "display_name": entry.model.display_name},
        "variant": entry.variant,
        "tokens": asdict(entry.tokens),
        "reported_cost": str(entry.reported_cost),
        "summary": entry.summary,
        "finish_reason": entry.finish_reason,
        "error_name": entry.error_name,
        "cost_disposition": entry.cost_disposition.value,
        "source_instance": entry.source_instance,
        "account_ref": asdict(entry.account_ref) if entry.account_ref else None,
    }


def _trace_from_dict(data: Mapping[str, Any]) -> TraceEntry:
    model = data["model"]
    return TraceEntry(
        session_id=str(data["session_id"]),
        parent_event_id=data.get("parent_event_id"),
        message_id=data.get("message_id"),
        step_part_id=data.get("step_part_id"),
        completed_at_ms=int(data["completed_at_ms"]),
        sort_order=int(data["sort_order"]),
        model=ModelRef(str(model["provider"]), str(model["model"]), model.get("display_name")),
        variant=data.get("variant"),
        tokens=TokenUsage(**{key: int(value) for key, value in data["tokens"].items() if key != "known_fields"},
                          known_fields=tuple(data["tokens"]["known_fields"])),
        reported_cost=Decimal(str(data.get("reported_cost", "0"))),
        summary=bool(data.get("summary", False)),
        finish_reason=data.get("finish_reason"),
        error_name=data.get("error_name"),
        cost_disposition=CostDisposition(str(data.get("cost_disposition", "unknown"))),
        source_instance=data.get("source_instance"),
        account_ref=AccountRef(**data["account_ref"]) if data.get("account_ref") else None,
    )


def _prompt_to_dict(record: PromptRecord) -> dict[str, Any]:
    scalar = {
        key: value for key, value in asdict(record).items()
        if key not in {"entries", "model_costs", "previous_entry", "pre_prompt_entry", "last_root_entry"}
    }
    for key in ("cost", "main_cost", "subagent_cost"):
        scalar[key] = str(getattr(record, key))
    scalar["entries"] = [_trace_to_dict(entry) for entry in record.entries]
    scalar["model_costs"] = {key: str(value) for key, value in record.model_costs.items()}
    scalar["previous_entry"] = _trace_to_dict(record.previous_entry) if record.previous_entry else None
    scalar["pre_prompt_entry"] = _trace_to_dict(record.pre_prompt_entry) if record.pre_prompt_entry else None
    scalar["last_root_entry"] = _trace_to_dict(record.last_root_entry) if record.last_root_entry else None
    return scalar


def _prompt_from_dict(data: Mapping[str, Any]) -> PromptRecord:
    values = dict(data)
    values["cost"] = Decimal(str(values["cost"]))
    values["main_cost"] = Decimal(str(values["main_cost"]))
    values["subagent_cost"] = Decimal(str(values["subagent_cost"]))
    values["entries"] = tuple(_trace_from_dict(item) for item in values.get("entries", ()))
    values["model_costs"] = {str(key): Decimal(str(value)) for key, value in values.get("model_costs", {}).items()}
    for key in ("previous_entry", "pre_prompt_entry", "last_root_entry"):
        values[key] = _trace_from_dict(values[key]) if values.get(key) else None
    values["background_kinds"] = tuple(str(value) for value in values.get("background_kinds", ()))
    return PromptRecord(**values)


def _compaction_to_dict(record: CompactionRecord) -> dict[str, Any]:
    values = {key: value for key, value in asdict(record).items() if key != "entries"}
    values["cost"] = str(record.cost)
    values["entries"] = [_trace_to_dict(entry) for entry in record.entries]
    return values


def _compaction_from_dict(data: Mapping[str, Any]) -> CompactionRecord:
    values = dict(data)
    values["cost"] = Decimal(str(values["cost"]))
    values["entries"] = tuple(_trace_from_dict(item) for item in values.get("entries", ()))
    return CompactionRecord(**values)


def _bundle_to_dict(bundle: RootAnalysisBundle, dependencies: AnalysisDependencies) -> dict[str, Any]:
    return {
        "root_session_id": bundle.root_session_id,
        "source_revision": bundle.source_revision,
        "cacheable": bundle.cacheable,
        "config_signature": dependencies.config_signature,
        "pricing_signature": dependencies.pricing_signature,
        "trace_entries": [_trace_to_dict(entry) for entry in bundle.trace_entries],
        "prompts": [_prompt_to_dict(record) for record in bundle.prompts],
        "compactions": [_compaction_to_dict(record) for record in bundle.compactions],
    }


def _bundle_from_dict(data: Mapping[str, Any]) -> RootAnalysisBundle:
    return RootAnalysisBundle(
        root_session_id=str(data["root_session_id"]),
        source_revision=str(data["source_revision"]),
        trace_entries=tuple(_trace_from_dict(item) for item in data.get("trace_entries", ())),
        prompts=tuple(_prompt_from_dict(item) for item in data.get("prompts", ())),
        compactions=tuple(_compaction_from_dict(item) for item in data.get("compactions", ())),
        cacheable=bool(data.get("cacheable", False)),
    )


def _source_key(provenance: Provenance, root_session_id: str) -> str:
    raw = "|".join((
        provenance.source_type,
        provenance.source_generation,
        provenance.source_instance or "",
        root_session_id,
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AnalysisSessionSource(Protocol):
    def get_session_tree_revision(self, session_id: str) -> str: ...
    def load_session_snapshot(self, session_id: str) -> SessionSnapshot: ...


class DerivedAnalysisCache:
    def __init__(self, repository: CacheRepository) -> None:
        self.repository = repository

    def load(
        self,
        *,
        provenance: Provenance,
        root_session_id: str,
        source_revision: str,
        dependencies: AnalysisDependencies,
    ) -> RootAnalysisBundle | None:
        entry = self.repository.get(_CACHE_NAMESPACE, _source_key(provenance, root_session_id))
        if entry is None:
            return None
        if entry.source_revision != source_revision or entry.algorithm_version != dependencies.algorithm_version:
            return None
        payload = entry.payload
        if not isinstance(payload, Mapping):
            return None
        if payload.get("config_signature") != dependencies.config_signature:
            return None
        if payload.get("pricing_signature") != dependencies.pricing_signature:
            return None
        try:
            bundle = _bundle_from_dict(payload)
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return None
        return bundle if bundle.cacheable else None

    def store(
        self,
        bundle: RootAnalysisBundle,
        *,
        provenance: Provenance,
        dependencies: AnalysisDependencies,
    ) -> None:
        if not bundle.cacheable:
            return
        self.repository.put(
            _CACHE_NAMESPACE,
            _source_key(provenance, bundle.root_session_id),
            _bundle_to_dict(bundle, dependencies),
            source_revision=bundle.source_revision,
            algorithm_version=dependencies.algorithm_version,
        )


def analyze_with_cache(
    source: AnalysisSessionSource,
    root_session: NormalizedSession,
    cache: DerivedAnalysisCache,
    dependencies: AnalysisDependencies,
    analyzer: Callable[[SessionSnapshot], RootAnalysisBundle],
) -> CachedAnalysisResult:
    """Reuse stable derived analysis or hydrate/analyze conservatively.

    Cheap source revisions gate reuse.  A miss loads one authoritative snapshot;
    before persistence the revision is rechecked so changed/unstable trees never
    become durable cache hits.
    """
    root_session_id = root_session.session_id
    revision = source.get_session_tree_revision(root_session_id)
    cached = cache.load(
        provenance=root_session.provenance,
        root_session_id=root_session_id,
        source_revision=revision,
        dependencies=dependencies,
    )
    if cached is not None:
        return CachedAnalysisResult(cached, True, None)

    snapshot = source.load_session_snapshot(root_session_id)
    bundle = analyzer(snapshot)
    if bundle.source_revision != snapshot.source_revision:
        raise ValueError("Analyzer returned a bundle with mismatched source revision")
    if bundle.cacheable:
        post_revision = source.get_session_tree_revision(root_session_id)
        if post_revision == snapshot.source_revision == revision:
            cache.store(bundle, provenance=snapshot.root.provenance, dependencies=dependencies)
    return CachedAnalysisResult(bundle, False, snapshot)
