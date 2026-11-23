"""The --token-mix use case: a deep model comparison over all available history.

Its scan depth intentionally differs from the bounded normal report, so it has
its own orchestration. It reuses the shared analysis/cache and CCost catalog and
never introduces a private ledger for deleted or pruned sessions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from src.analysis.token_mix import model_token_mixes, priced_token_mix
from src.analysis.valuation import physical_usage_key, unique_usage
from src.analysis.ai_stats import windows
from src.domain import ModelRef
from src.domain.progress import WorkProgress
from src.pricing.identities import reference_identity, unverified_alias
from src.pricing.publishers import model_publisher, token_mix_publisher

from .migration_notice import migration_gap_notes
from .models import ModelTokenMixProjection, PublisherTokenMixProjection, ReportKind, ReportProjection

if TYPE_CHECKING:
    from .service import ReportService

HistoryProgress = Callable[[str, int | None], None]
HISTORY_NOTE = ("History includes OpenCode usage data that is still available; "
                "deleted or pruned history is not reconstructed.")


def _model_key(model: ModelRef) -> str:
    if unverified_alias(model.model, model.provider):
        return f"{model.provider.lower()}/{reference_identity(model.model)}"
    return reference_identity(model.model) or (model.model or "").lower()


def observed_totals(entries):
    """Web-only known-category numerators; never promote canonical unknowns."""
    totals = [0, 0, 0, 0]
    for entry in entries:
        usage = entry.tokens
        for index, name in enumerate(("input", "cache_read", "cache_write", "output")):
            if name in usage.known_fields:
                totals[index] += getattr(usage, name)
        # Reasoning is a separately recorded canonical scalar, folded into O once.
        totals[3] += usage.reasoning
    return tuple(totals)


def history_prompt_keys(bundle):
    """Model prompts belong to their executing session, not the causal root row."""
    keys = {entry: (entry.session_id, entry.logical_prompt_id) for entry in bundle.trace_entries
            if entry.logical_prompt_id and not entry.summary}
    # Older sources may lack a logical ID. Only a proven own-session prompt
    # record is a fallback; a child without one remains unknown, not a new call/prompt.
    for prompt in bundle.prompts:
        for entry in prompt.entries:
            if entry.session_id == prompt.session_id and not entry.summary:
                keys.setdefault(entry, (prompt.session_id, prompt.prompt_id))
    return keys


def build_token_mix_history(service: ReportService, progress: HistoryProgress, *, scope=None) -> ReportProjection:
    progress(WorkProgress("Loading pricing catalog", "pricing"), None)
    reference = service._load_comparison_catalog()
    progress(WorkProgress("Listing OpenCode sessions", "catalog"), None)
    roots = [item for item in service.source.list_sessions() if item.parent_session_id is None]
    entries = []
    prompt_of = {}
    for index, root in enumerate(roots):
        progress(WorkProgress("Analyzing usage history...", "history", index, len(roots)), None)
        bundle = service._analyze(root).bundle
        # A full-history scan must not retain every hydrated snapshot in memory.
        service._analyzed.pop(root.session_id, None)
        entries.extend(bundle.trace_entries)
        prompt_of.update(history_prompt_keys(bundle))
    return history_projection(service, reference, entries, prompt_of, progress, scope=scope)


def history_projection(service, reference, entries, prompt_of, progress, *, valuation=None, scope=None,
                       archived=False):
    """One CLI/Web semantic owner; callers may reuse revision-verified usage facts."""
    valuation = valuation or reference.reference_category_valuation
    progress(WorkProgress("Pricing token categories", "finalizing"), None)
    archival_prompts = {key[1:]: value for entry, value in prompt_of.items()
                        if archived and (key := physical_usage_key(entry)) is not None}
    usage = unique_usage(entries, shared_history=archived)
    if archived:
        prompt_of = {entry: value for entry in usage
                     if (value := prompt_of.get(entry) or archival_prompts.get((physical_usage_key(entry) or ())[1:]))}
    period = {}
    undated = 0
    if scope is not None:
        start = dict(windows(service.timezone_id, service.now_ms))[scope]
        undated = sum(entry.completed_at_ms <= 0 for entry in usage)
        # Deduplicate physical requests BEFORE scope membership. Child calls use
        # their own canonical event time, not their parent's prompt start.
        usage = [entry for entry in usage if (start is None or
            entry.completed_at_ms >= start) and entry.completed_at_ms <= service.now_ms]
        period = dict(period=scope, start_ms=start, end_ms=service.now_ms)
    groups = model_token_mixes(usage, prompt_of, valuation, model_key=_model_key)
    warnings = tuple(service.selection.warnings)
    if undated:
        warnings += (f"Request time unavailable for {undated} recorded calls; undated usage is included only in All time.",)
    # All-history scope: any V1 gap may make the result incomplete.
    notes = [('History includes verified usage saved locally, including previously observed deleted sessions.'
              if archived else HISTORY_NOTE), *migration_gap_notes(service.selection.migration_gap)]
    # Executed history is not a current-entitlement/model-picker roster.
    # Keep every observed model, including retired models and other routes.
    rows = []
    by_model = {}
    for entry in usage:
        by_model.setdefault(_model_key(entry.model), []).append(entry)

    def catalog_model(model):
        return None if unverified_alias(model.model, model.provider) else reference.resolve_reference(model.model)

    def publisher_key(model):
        matched = catalog_model(model)
        publisher = token_mix_publisher(model, matched) if scope is not None else model_publisher(matched)
        return publisher or "Unknown / unverified"

    for group in groups:
        matched = catalog_model(group.model)
        name = (group.model.display_name if group.model.resolution and group.model.display_name else
                reference.display_name(group.model.model, group.model.provider, exact=True))
        web_name = (matched.model.display_name or matched.model.model) if matched else (
            group.model.recorded_model if unverified_alias(group.model.model, group.model.provider) else
            group.model.display_name or group.model.recorded_model)
        key = _model_key(group.model)
        # Model groups can span routes. Never infer their manufacturer from the
        # last request; publisher aggregates below still use each request's facts.
        manufacturers = {publisher_key(entry.model) for entry in by_model[key]}
        publisher = next(iter(manufacturers)) if len(manufacturers) == 1 else "Unknown / unverified"
        rows.append(ModelTokenMixProjection(name, group.prompts, group.calls, group.mix,
            "—" if publisher == "Unknown / unverified" else publisher, key, observed_totals(by_model[key]), web_name))
    rows.sort(key=lambda row: (-sum(row.mix.costs or ()), -row.calls, row.model))
    # The total reprices the same shown requests directly, never rounded per-model rows.
    shown_keys = {_model_key(group.model) for group in groups}
    shown_usage = [entry for entry in usage if _model_key(entry.model) in shown_keys]
    by_publisher = {}
    for entry in shown_usage:
        by_publisher.setdefault(publisher_key(entry.model), []).append(entry)
    publishers = [PublisherTokenMixProjection(publisher_key(group.model), group.prompts, group.calls, group.mix,
                    observed_totals(by_publisher[publisher_key(group.model)]))
                   for group in model_token_mixes(shown_usage, prompt_of, valuation,
                                               model_key=publisher_key)]
    publishers.sort(key=lambda row: (-sum(row.mix.costs or ()), -row.calls, row.publisher))
    notes.append("Historical publisher shares use pooled shown requests, not the 100-slot comparison prior. "
                  "Prompts are distinct logical prompts in each executing session, including recorded child prompts; "
                  "mixed prompts can appear in several model/publisher rows, so row prompt counts are not additive. "
                  "Unknown / unverified is not an account provider.")
    total = priced_token_mix(((entry.model, entry.tokens) for entry in shown_usage),
                             valuation,
                              sample_size=len({prompt_of[entry] for entry in shown_usage if entry in prompt_of}))
    if scope == 'all':
        stamps = [entry.completed_at_ms for entry in shown_usage if entry.completed_at_ms > 0]
        period.update(start_ms=min(stamps) if stamps else None, end_ms=max(stamps) if stamps else None)
    elif scope is not None and undated:
        period['coverage'] = 'partial' if shown_usage else 'unknown'
    return ReportProjection(
        ReportKind.TOKEN_MIX, "Token Mix % by model", service.selection.selected.upper(), warnings,
        notes=tuple(notes), model_token_mix=tuple(rows), publisher_token_mix=tuple(publishers), token_mix=total,
        token_mix_period=period,
        token_mix_observed_totals=observed_totals(shown_usage),
    )
