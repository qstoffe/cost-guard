"""Disposable derived-analysis cache keyed by explicit semantic dependencies."""
from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext
from dataclasses import asdict, dataclass, fields
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Protocol, Sequence

from src.cache import CacheRepository
from src.cache.session_scope import snapshot_scope
from src.domain import AccountRef, CostDisposition, ModelRef, NormalizedSession, Provenance, SessionSnapshot, TokenUsage
from src.domain.acquisition import AcquisitionMetrics
from src.pricing.identities import MODEL_IDENTITY_SEMANTICS, identity_cache_current

from .models import CompactionRecord, PromptRecord, RootAnalysisBundle, TraceEntry
from .model_identity import encode_model, decode_model

ANALYSIS_ALGORITHM_VERSION = "v78-analysis-22-owned-child-lifecycle"
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


@dataclass(frozen=True, slots=True)
class CacheObservation:
    root_session_id: str
    provenance: Provenance
    source_revision: str
    dependencies: AnalysisDependencies
    bundle: RootAnalysisBundle | None

    def matches(self, root: NormalizedSession, revision: str, dependencies: AnalysisDependencies) -> bool:
        return (self.root_session_id == root.session_id and self.provenance == root.provenance
            and self.source_revision == revision and self.dependencies == dependencies
            and (self.bundle is None or (self.bundle.root_session_id == root.session_id
                and self.bundle.source_revision == revision)))


def dependency_signature(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _flat_fields(value: Any, nested: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Top-level dataclass fields; unlike ``asdict`` never deep-converts, so callers serialize nested values."""
    return {item.name: getattr(value, item.name) for item in fields(value) if item.name not in nested}


def _trace_to_dict(entry: TraceEntry) -> dict[str, Any]:
    return {
        "session_id": entry.session_id,
        "parent_event_id": entry.parent_event_id,
        "message_id": entry.message_id,
        "step_part_id": entry.step_part_id,
        "completed_at_ms": entry.completed_at_ms,
        "sort_order": entry.sort_order,
        "model": encode_model(entry.model),
        "variant": entry.variant,
        "tokens": _flat_fields(entry.tokens),
        "reported_cost": str(entry.reported_cost),
        "summary": entry.summary,
        "finish_reason": entry.finish_reason,
        "error_name": entry.error_name,
        "cost_disposition": entry.cost_disposition.value,
        "source_instance": entry.source_instance,
        "account_ref": _flat_fields(entry.account_ref) if entry.account_ref else None,
        "logical_prompt_id": entry.logical_prompt_id,
        "selected_effort": entry.selected_effort,
        "root_session_id": entry.root_session_id,
        "invocation_id": entry.invocation_id,
        "parent_session_id": entry.parent_session_id,
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
        model=decode_model(model),
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
        logical_prompt_id=data.get("logical_prompt_id"),
        selected_effort=data.get("selected_effort"),
        root_session_id=data.get("root_session_id"),
        invocation_id=data.get("invocation_id"),
        parent_session_id=data.get("parent_session_id"),
    )


_PROMPT_NESTED = frozenset({"entries", "model_costs", "previous_entry", "pre_prompt_entry", "last_root_entry", "agent_coverage"})


def _prompt_to_dict(record: PromptRecord) -> dict[str, Any]:
    scalar = _flat_fields(record, _PROMPT_NESTED)
    for key in ("cost", "main_cost", "subagent_cost"):
        scalar[key] = str(getattr(record, key))
    scalar["entries"] = [_trace_to_dict(entry) for entry in record.entries]
    scalar["agent_coverage"] = [asdict(agent) for agent in record.agent_coverage]
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
    values["linked_session_ids"] = tuple(str(value) for value in values.get("linked_session_ids", ()))
    from .coverage import AgentCoverage
    values["agent_coverage"] = tuple(AgentCoverage(**value) for value in values.get("agent_coverage", ()))
    return PromptRecord(**values)


def _compaction_to_dict(record: CompactionRecord) -> dict[str, Any]:
    values = _flat_fields(record, frozenset({"entries"}))
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
        "model_identity_semantics": MODEL_IDENTITY_SEMANTICS,
        "source_revision": bundle.source_revision,
        "cacheable": bundle.cacheable,
        "usage_coverage_complete": bundle.usage_coverage_complete,
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
        usage_coverage_complete=bool(data.get("usage_coverage_complete", False)),
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
    def __init__(self, repository: CacheRepository, *, metrics: AcquisitionMetrics | None = None,
                 identity_validator=None) -> None:
        self.repository = repository
        self.metrics = metrics
        self.write_enabled = True
        self.identity_validator = identity_validator

    def load(
        self,
        *,
        provenance: Provenance,
        root_session_id: str,
        source_revision: str,
        dependencies: AnalysisDependencies,
    ) -> RootAnalysisBundle | None:
        if self.metrics is None:
            return self._load(provenance, root_session_id, source_revision, dependencies)
        self.metrics.add("cache_reads")
        with self.metrics.measure("cache_reads"):
            bundle = self._load(provenance, root_session_id, source_revision, dependencies)
        self.metrics.add("cache_hits" if bundle is not None else "cache_misses")
        return bundle

    def _load(self, provenance: Provenance, root_session_id: str, source_revision: str,
               dependencies: AnalysisDependencies) -> RootAnalysisBundle | None:
        if self.metrics is not None:
            self.metrics.add('cache_repository_reads')
        entry = self.repository.get(_CACHE_NAMESPACE, _source_key(provenance, root_session_id))
        return self._decode(entry, root_session_id, source_revision, dependencies)

    def _decode(self, entry, root_session_id: str, source_revision: str,
                dependencies: AnalysisDependencies) -> RootAnalysisBundle | None:
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
            with self.metrics.measure('cache_decode') if self.metrics is not None else nullcontext():
                bundle = _bundle_from_dict(payload)
            if payload.get("model_identity_semantics") != MODEL_IDENTITY_SEMANTICS:
                models = [(entry.model.provider, entry.model.recorded_model) for entry in bundle.trace_entries]
                models.extend((record.main_provider_id, record.main_model_id) for record in bundle.prompts)
                models.extend((record.provider_id, record.model_id) for record in bundle.compactions)
                if not identity_cache_current(None, models):
                    return None
            identities = tuple(entry.model for entry in bundle.trace_entries)
            if self.identity_validator is not None and not self.identity_validator(identities):
                return None
            if self.identity_validator is None and any(model.resolution is not None for model in identities):
                return None
        except (KeyError, TypeError, ValueError, InvalidOperation):
            return None
        return (bundle if bundle.cacheable and bundle.root_session_id == root_session_id
            and bundle.source_revision == source_revision else None)

    def observe_many(self, requests: Sequence[tuple[NormalizedSession, str]],
                     dependencies: AnalysisDependencies) -> dict[str, CacheObservation]:
        """One small decoded cache observation; no retained read transaction."""
        if len(requests) > 8:
            raise ValueError('invalid_cache_observation_window')
        if not requests:
            return {}
        if self.metrics is not None:
            self.metrics.add('cache_reads', len(requests))
            self.metrics.add('cache_repository_reads')
            self.metrics.add('cache_bulk_reads')
        with self.metrics.measure('cache_reads') if self.metrics is not None else nullcontext():
            keys = [_source_key(root.provenance, root.session_id) for root, _revision in requests]
            entries = self.repository.get_many(_CACHE_NAMESPACE, keys)
            observations = {}
            for (root, revision), key in zip(requests, keys):
                bundle = self._decode(entries.get(key), root.session_id, revision, dependencies)
                observations[root.session_id] = CacheObservation(root.session_id, root.provenance,
                    revision, dependencies, bundle)
                if self.metrics is not None:
                    self.metrics.add('cache_hits' if bundle is not None else 'cache_misses')
        return observations

    def store(
        self,
        bundle: RootAnalysisBundle,
        *,
        provenance: Provenance,
        dependencies: AnalysisDependencies,
        snapshot: SessionSnapshot | None = None,
    ) -> None:
        if not bundle.cacheable or not self.write_enabled:
            return
        if self.metrics is not None:
            self.metrics.add("cache_writes")
        self.repository.put(
            _CACHE_NAMESPACE,
            _source_key(provenance, bundle.root_session_id),
            _bundle_to_dict(bundle, dependencies),
            source_revision=bundle.source_revision,
            algorithm_version=dependencies.algorithm_version,
            session_scope=snapshot_scope(snapshot) if snapshot is not None else None,
        )


def cached_analysis(
    source: AnalysisSessionSource,
    root_session: NormalizedSession,
    cache: DerivedAnalysisCache,
    dependencies: AnalysisDependencies,
) -> tuple[str, RootAnalysisBundle | None]:
    """Current tree revision plus its stable cached analysis, never hydrating."""
    revision = source.get_session_tree_revision(root_session.session_id)
    return revision, cache.load(
        provenance=root_session.provenance,
        root_session_id=root_session.session_id,
        source_revision=revision,
        dependencies=dependencies,
    )


def analyze_with_cache(
    source: AnalysisSessionSource,
    root_session: NormalizedSession,
    cache: DerivedAnalysisCache,
    dependencies: AnalysisDependencies,
    analyzer: Callable[[SessionSnapshot], RootAnalysisBundle],
    *, snapshot: SessionSnapshot | None = None, observation: CacheObservation | None = None,
) -> CachedAnalysisResult:
    """Reuse stable derived analysis or hydrate/analyze conservatively.

    Cheap source revisions gate reuse.  A miss loads one authoritative snapshot;
    before persistence the revision is rechecked so changed/unstable trees never
    become durable cache hits.
    """
    root_session_id = root_session.session_id
    revision = source.get_session_tree_revision(root_session_id)
    if observation is not None and snapshot is not None and (snapshot.root.session_id != root_session_id
            or snapshot.root.provenance != root_session.provenance):
        snapshot = None  # Reject a staged value from another root/source entirely.
    qualified = (observation is not None and observation.matches(root_session, revision, dependencies)
        and (snapshot is None or snapshot.source_revision == revision)
        and (observation.bundle is not None or (snapshot is not None and snapshot.complete)))
    metrics = getattr(cache, 'metrics', None)
    if qualified:
        cached = observation.bundle
        if metrics is not None:
            metrics.add('cache_observation_hit_reuse' if cached is not None else 'cache_observation_miss_reuse')
    else:
        if observation is not None and metrics is not None:
            metrics.add('cache_observation_invalidations')
        cached = cache.load(provenance=root_session.provenance, root_session_id=root_session_id,
            source_revision=revision, dependencies=dependencies)
    if cached is not None and (snapshot is None or snapshot.source_revision == revision):
        return CachedAnalysisResult(cached, True, snapshot)

    snapshot = snapshot or source.load_session_snapshot(root_session_id)
    bundle = analyzer(snapshot)
    if bundle.source_revision != snapshot.source_revision:
        raise ValueError("Analyzer returned a bundle with mismatched source revision")
    if bundle.cacheable:
        post_revision = source.get_session_tree_revision(root_session_id)
        if post_revision == snapshot.source_revision == revision:
            cache.store(bundle, provenance=snapshot.root.provenance, dependencies=dependencies, snapshot=snapshot)
    return CachedAnalysisResult(bundle, False, snapshot)
