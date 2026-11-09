"""Disposable scalar catalog keys; source/dependency checked, never a user ledger."""
from dataclasses import asdict, fields, replace
from decimal import Decimal, InvalidOperation
import sqlite3

from src.analysis.cache import dependency_signature
from src.domain.reference_cost import ReferenceCostIssue, REASONS
from src.cache.session_scope import snapshot_scope
from src.pricing.identities import MODEL_IDENTITY_SEMANTICS, identity_cache_current
from .models import SessionUsageRow

ALGORITHM = "session-summary-2"
NAMESPACE = "session-summary"


def summary_key(service, root):
    provenance = root.provenance
    return dependency_signature((ALGORITHM, provenance.source_type, provenance.source_generation,
        provenance.source_instance, root.session_id, service._dependencies(service._load_catalog()),
        service._load_comparison_catalog().diagnostic_signature))


def session_summary(service, root, revision, *, active=False):
    """One root only. A cache miss may acquire history, never all catalog roots."""
    key = summary_key(service, root)
    try:
        cached = service.cache_repository.get(NAMESPACE, key, busy_timeout_ms=50)
    except (OSError, sqlite3.Error):
        cached = None
    if not active and cached is not None and cached.source_revision == revision and cached.algorithm_version == ALGORITHM:
        try:
            values = dict(cached.payload)
            semantics = values.pop("model_identity_semantics", None)
            # Older zero-request summaries retain only a derived label, not the
            # selected source ID. Reacquire this root rather than trust that label.
            if (semantics != MODEL_IDENTITY_SEMANTICS and not values.get("contributor_models")
                    and values.get("model") != "N/A"):
                raise ValueError("unproven_model_label")
            models = (value.split("/", 1) for value in values.get("contributor_models", ()))
            if not identity_cache_current(semantics, models):
                raise ValueError("outdated_model_identity")
            if set(values) != {field.name for field in fields(SessionUsageRow)}:
                raise ValueError("incomplete_summary")
            values["ccost"] = Decimal(values["ccost"])
            values["contributor_models"] = tuple(values["contributor_models"])
            issues = tuple(ReferenceCostIssue(**issue) for issue in values["ccost_unavailable"])
            if len(issues) > 6 or any(issue.reason not in REASONS or not all(
                    isinstance(value, str) and len(value) <= 128 and (not value or value.isprintable())
                    for value in (issue.model, issue.detail)) for issue in issues):
                raise ValueError("invalid_reference_issues")
            values["ccost_unavailable"] = issues
            row = SessionUsageRow(**values)
            if (row.session_id == root.session_id and row.ccost.is_finite() and row.ccost >= 0
                    and isinstance(row.title, str) and isinstance(row.model, str)
                    and all(type(getattr(row, name)) is bool for name in ("complete", "multiple_models", "archived", "running", "contributor_models_complete", "model_pending"))
                    and len(row.contributor_models) <= 64
                    and all(isinstance(value, str) and 0 < len(value) <= 256
                            and all(value.partition("/")[::2]) for value in row.contributor_models)
                    and row.contributor_models == tuple(sorted(set(row.contributor_models)))
                    and not row.running
                    and not row.model_pending
                    and type(row.prompt_count) is int and row.prompt_count >= 0
                    and (row.duration_ms is None or type(row.duration_ms) is int and row.duration_ms >= 0)):
                return row, revision
        except (KeyError, TypeError, ValueError, InvalidOperation):
            pass  # Disposable malformed summaries are misses, never source evidence.
    service.invalidate_roots((root.session_id,))
    # Derived analysis alone does not carry full-source acquisition completeness.
    # Establish it once on scalar-cache miss, without changing finite-report semantics.
    item = service._analyze(root, detail=True, force_fresh=active)
    row = service._session_rows((item,))[0]
    row = replace(row, complete=row.complete and item.snapshot.complete)
    actual = item.bundle.source_revision
    if item.bundle.cacheable and not row.running:
        values = asdict(row)
        values["model_identity_semantics"] = MODEL_IDENTITY_SEMANTICS
        values["ccost"] = str(row.ccost)
        try:
            service.cache_repository.put(NAMESPACE, key, values,
                source_revision=actual, algorithm_version=ALGORITHM, busy_timeout_ms=50,
                session_scope=snapshot_scope(item.snapshot))
        except (OSError, sqlite3.Error):
            pass
    return row, actual
