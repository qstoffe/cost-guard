"""The --token-mix use case: a deep model comparison over all available history.

Its scan depth intentionally differs from the bounded normal report, so it has
its own orchestration. It reuses the shared analysis/cache and CCost catalog and
never introduces a private ledger for deleted or pruned sessions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from src.analysis.token_mix import model_token_mixes, priced_token_mix
from src.analysis.valuation import unique_usage
from src.domain import ModelRef
from src.domain.progress import WorkProgress
from src.pricing.identities import reference_identity
from src.pricing.publishers import publisher_for

from .migration_notice import migration_gap_notes
from .models import ModelTokenMixProjection, PublisherTokenMixProjection, ReportKind, ReportProjection

if TYPE_CHECKING:
    from .service import ReportService

HistoryProgress = Callable[[str, int | None], None]
HISTORY_NOTE = ("History includes OpenCode usage data that is still available; "
                "deleted or pruned history is not reconstructed.")


def _model_key(model: ModelRef) -> str:
    return reference_identity(model.model) or (model.model or "").lower()


def build_token_mix_history(service: ReportService, progress: HistoryProgress) -> ReportProjection:
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
        for prompt in bundle.prompts:
            for entry in prompt.entries:
                prompt_of.setdefault(entry, (prompt.session_id, prompt.prompt_id))
    progress(WorkProgress("Checking available OpenCode models", "availability"), None)
    try:
        source = service.model_availability_source
        available = source.available_model_ids() if source is not None else None
    except Exception as exc:
        from src.sources.errors import SourceError
        from src.runtime_errors import recoverable
        if not isinstance(exc, (SourceError, OSError)):
            recoverable(exc, "history-model-availability")
            software_fault = True
        else:
            software_fault = False
        available = None
    else:
        from src.runtime_errors import recovered
        recovered("history-model-availability")
        software_fault = False
    progress(WorkProgress("Pricing token categories", "finalizing"), None)
    usage = unique_usage(entries)
    groups = model_token_mixes(usage, prompt_of, reference.reference_category_valuation, model_key=_model_key)
    warnings = tuple(service.selection.warnings)
    # All-history scope: any V1 gap may make the result incomplete.
    notes = [HISTORY_NOTE, *migration_gap_notes(service.selection.migration_gap)]
    if available is None:
        if software_fault:
            warnings += ("ERROR: Model availability lookup failed internally; showing all historically used models.",)
        # Fail open: hiding usable history is worse than an unverified filter.
        warnings += ("⚠ Could not verify currently selectable OpenCode models; showing all historically used models.",)
    else:
        selectable = {reference_identity(value) for value in available}
        shown = tuple(group for group in groups if _model_key(group.model) in selectable)
        if len(shown) != len(groups):
            notes.append(f"Only currently selectable OpenCode models are shown; "
                         f"{len(groups) - len(shown)} other historically used model(s) omitted.")
        groups = shown
    rows = []
    for group in groups:
        resolved = reference.resolve_reference(group.model.model)
        name = resolved.model.display_name if resolved and resolved.model.display_name else (group.model.model or "N/A")
        rows.append(ModelTokenMixProjection(name, group.prompts, group.calls, group.mix))
    rows.sort(key=lambda row: (-sum(row.mix.costs or ()), -row.calls, row.model))
    # The total reprices the same shown requests directly, never rounded per-model rows.
    shown_keys = {_model_key(group.model) for group in groups}
    shown_usage = [entry for entry in usage if _model_key(entry.model) in shown_keys]
    publisher_key = lambda model: publisher_for(reference, model.model) or "Unknown / unverified"
    publishers = [PublisherTokenMixProjection(publisher_key(group.model), group.prompts, group.calls, group.mix)
                  for group in model_token_mixes(shown_usage, prompt_of, reference.reference_category_valuation,
                                               model_key=publisher_key)]
    publishers.sort(key=lambda row: (-sum(row.mix.costs or ()), -row.calls, row.publisher))
    notes.append("Historical publisher shares use pooled shown requests, not the 100-slot comparison prior. "
                 "Prompts are distinct within each model/publisher; mixed prompts can appear in several rows, "
                 "so row prompt counts are not additive. Unknown / unverified is not an account provider.")
    total = priced_token_mix(((entry.model, entry.tokens) for entry in shown_usage),
                             reference.reference_category_valuation,
                             sample_size=len({prompt_of[entry] for entry in shown_usage if entry in prompt_of}))
    return ReportProjection(
        ReportKind.TOKEN_MIX, "Token Mix % by model", service.selection.selected.upper(), warnings,
        notes=tuple(notes), model_token_mix=tuple(rows), publisher_token_mix=tuple(publishers), token_mix=total,
    )
