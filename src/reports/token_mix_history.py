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
from src.pricing.identities import reference_identity

from .models import ModelTokenMixProjection, ReportKind, ReportProjection

if TYPE_CHECKING:
    from .service import ReportService

HistoryProgress = Callable[[str, int], None]
HISTORY_NOTE = ("History includes OpenCode usage data that is still available; "
                "deleted or pruned history is not reconstructed.")


def _model_key(model: ModelRef) -> str:
    return reference_identity(model.model) or (model.model or "").lower()


def build_token_mix_history(service: ReportService, progress: HistoryProgress) -> ReportProjection:
    progress("Loading pricing catalog", 2)
    reference = service._load_comparison_catalog()
    progress("Listing OpenCode sessions", 4)
    roots = [item for item in service.source.list_sessions() if item.parent_session_id is None]
    entries = []
    prompt_of = {}
    for index, root in enumerate(roots):
        progress("Analyzing usage history...", 5 + 85 * index // len(roots))
        bundle = service._analyze(root).bundle
        # A full-history scan must not retain every hydrated snapshot in memory.
        service._analyzed.pop(root.session_id, None)
        entries.extend(bundle.trace_entries)
        for prompt in bundle.prompts:
            for entry in prompt.entries:
                prompt_of.setdefault(entry, (prompt.session_id, prompt.prompt_id))
    progress("Checking available OpenCode models", 92)
    try:
        source = service.model_availability_source
        available = source.available_model_ids() if source is not None else None
    except Exception:
        available = None
    progress("Pricing token categories", 96)
    usage = unique_usage(entries)
    groups = model_token_mixes(usage, prompt_of, reference.reference_category_valuation, model_key=_model_key)
    warnings = tuple(service.selection.warnings)
    notes = [HISTORY_NOTE]
    if available is None:
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
    total = priced_token_mix(((entry.model, entry.tokens) for entry in shown_usage),
                             reference.reference_category_valuation,
                             sample_size=len({prompt_of[entry] for entry in shown_usage if entry in prompt_of}))
    return ReportProjection(
        ReportKind.TOKEN_MIX, "Token Mix % by model", service.selection.selected.upper(), warnings,
        notes=tuple(notes), model_token_mix=tuple(rows), token_mix=total,
    )
