"""Serialized one-shot jobs over existing report owners; no HTTP or live scheduler."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from threading import Lock
from time import time_ns
from uuid import uuid4
from weakref import WeakSet

from src.analysis import local_report_range, local_day_start_ms, local_month_start_ms
from src.reports import ReportKind, ReportRequest, ReportService
from src.reports.service import ReportRequestError, SessionNotFoundError, SessionCatalogChangedError
from src.pricing.base import PricingUnavailableError
from src.runtime_errors import recoverable, recovered
from src.sources.errors import FailureCode, SourceError
from src.domain.progress import WorkProgress
from src.analysis.cache import dependency_signature

from .contracts import ObjectValue, ProgressEvent, ReportError, ReportResult, record
from .projection import identity, project
from src.reports.ai_stats import StatsCheckpointError
from src.reports.history_work import HistoryContinuation, HistoryCheckpointError


ServiceFactory = Callable[[int, Callable[[str], None]], ReportService]
ProgressSink = Callable[[ProgressEvent], None]
_PHASES = frozenset({"pricing", "catalog", "history", "projection", "quotas", "availability", "finalizing"})
_STAGES = frozenset({"sampling", "availability", "comparison", "models", "quotas", "account-cache",
                     "account-load", "account-analysis", "account-projection", "finalizing",
                     "date-cache", "date-load", "date-catalog-before", "date-messages", "date-catalog-after", "date-analysis",
                     "history-cache", "history-load", "history-projection", "history-verify"})


class ReportApplication:
    """Own a fresh isolated ReportService per job, never a Watch service.

    The composition root supplies canonical source/config/pricing/cache owners via
    factory(now_ms, progress). The factory transfers a new one-shot service and
    owns any additional external context cleanup. No job starts a second account
    scheduler. Concurrent/reentrant callers receive busy and can retry; observer
    callbacks receive only stage/count DTOs, never arbitrary progress text.
    """

    def __init__(self, factory: ServiceFactory, *, clock: Callable[[], int] | None = None):
        self._factory = factory
        self._clock = clock or (lambda: time_ns() // 1_000_000)
        self._instance_id = str(uuid4())
        self._lock = Lock()
        self._sequences: dict[ReportRequest, int] = defaultdict(int)
        self._used: WeakSet[ReportService] = WeakSet()

    def execute(self, request: ReportRequest, *, progress: ProgressSink | None = None) -> ReportResult:
        scope = record(kind=request.kind, session_id=request.session_id, date_text=request.date_text,
                       session_limit=request.session_limit, stats_scope=request.stats_scope)
        now = int(self._clock())
        unknown = record(status="not_acquired", observed_at_ms=None, revisions=(), atomicity="per_root_snapshot")
        if not self._lock.acquire(blocking=False):
            return ReportResult(self._instance_id, 0, now, scope, unknown, error=ReportError("busy", True))
        service = None
        admitted = False
        try:
            self._sequences[request] += 1
            sequence = self._sequences[request]
            error = self._validate(request)
            if error is not None:
                return ReportResult(self._instance_id, sequence, now, scope, unknown, error=ReportError(error))

            def observe(label):
                if progress is not None:
                    phase = getattr(label, "phase", "working")
                    stage = getattr(label, "stage", None)
                    progress(ProgressEvent(phase if phase in _PHASES else "working",
                                           getattr(label, "completed", 0), getattr(label, "total", None),
                                           stage if stage in _STAGES else None))

            service = self._factory(now, observe)
            # Reject ownership mistakes without closing someone else's scheduler.
            if service in self._used or service._watch_accounts or service._account_work is not None:
                return ReportResult(self._instance_id, sequence, now, scope, unknown,
                                    error=ReportError("service_ownership"))
            self._used.add(service)
            admitted = True
            scope = ObjectValue(scope.fields + (
                ("timezone_id", service.timezone_id), ("duration_metric", "report_execution"),
                ("history_policy", {
                    ReportKind.NORMAL: "recent_priceable_samples_and_independent_account_periods",
                    ReportKind.ALL_MODELS: "recent_priceable_samples",
                    ReportKind.SESSIONS: "requested_root_list",
                    ReportKind.SESSION: "complete_root_tree",
                    ReportKind.DATE: "local_range",
                    ReportKind.TOKEN_MIX: "all_available_history_selectable_models",
                    ReportKind.COST_PER_HOUR: "explicit_period_execution_history",
                    ReportKind.AI_STATS: "available_execution_history",
                    ReportKind.COMPARISONS: "all_available_root_first_inputs",
                }[request.kind]),
                ("local_day_start_ms", local_day_start_ms(service.timezone_id, now_ms=now)),
                ("local_month_start_ms", local_month_start_ms(service.timezone_id, now_ms=now)),
            ))
            if request.kind is ReportKind.DATE:
                try:
                    period = local_report_range(request.date_text, service.timezone_id)
                except (ValueError, OverflowError):
                    return ReportResult(self._instance_id, sequence, now, scope, unknown,
                                        error=ReportError("invalid_request"))
                scope = ObjectValue(scope.fields + (("start_ms", period.start_ms), ("end_ms", period.end_ms)))
            report = (service.build_token_mix_history(lambda label, _percent: observe(label))
                       if request.kind is ReportKind.TOKEN_MIX else service.build(request, include_model_catalog=True))
            observe(WorkProgress("Preparing report", "finalizing", 0, 2, stage="finalizing"))
            revisions = tuple(record(session_id=root, revision=identity(revision))
                              for root, revision in service.report_source_revisions())
            source = record(
                generation=service.selection.selected, status="partial" if report.source_warnings else "acquired",
                omitted_roots=report.history_omitted_roots,
                identity=dependency_signature((service.selection.selected, getattr(service.source, 'source_instance', None))),
                dependencies=dependency_signature(service._dependencies(service._load_catalog())),
                pricing_signature=service._load_comparison_catalog().analysis_signature,
                observed_at_ms=now, revisions=revisions, atomicity="per_root_snapshot",
                accounts_atomic_with_sessions=False,
            )
            requests = tuple(record(id=identity(parts), session_id=parts[0], event_id=parts[1],
                                    message_id=parts[2], step_part_id=parts[3])
                             # Normal is an aggregate comparison/account report. Its
                             # month-wide causal identities are not displayed and can
                             # dwarf the report; per-root revision evidence stays above.
                              for parts in (() if request.session_page_size or request.kind in {ReportKind.NORMAL, ReportKind.COST_PER_HOUR, ReportKind.AI_STATS, ReportKind.COMPARISONS}
                                           else service.report_request_identities()))
            observe(WorkProgress("Preparing report", "finalizing", 1, 2, stage="finalizing"))
            view = project(report, service.timezone_id, service.config.get("ccostDisplayUnit", "credits"))
            view = ObjectValue(view.fields + (("request_identities", requests),))
            observe(WorkProgress("Preparing report", "finalizing", 2, 2, stage="finalizing"))
            recovered("application-report")
            return ReportResult(self._instance_id, sequence, now, scope, source, view)
        except HistoryContinuation:
            return ReportResult(self._instance_id, sequence, now, scope, unknown,
                                error=ReportError('history_continue'))
        except (StatsCheckpointError, HistoryCheckpointError) as exc:
            return ReportResult(self._instance_id, sequence, now, scope, unknown,
                                error=ReportError(str(exc), str(exc) in {
                                    'history_revision_churn', 'ai_stats_revision_churn', 'ai_stats_checkpoint_busy'}))
        except SourceError as exc:
            permission = exc.exception_type == 'PermissionError'
            return ReportResult(self._instance_id, sequence, now, scope,
                                record(status="error", observed_at_ms=now, revisions=(),
                                       atomicity="per_root_snapshot"),
                                error=ReportError('source_permission_denied' if permission else exc.code.value,
                                                  (exc.readiness_retryable or exc.code == FailureCode.CONCURRENT)
                                                  and not permission))
        except PricingUnavailableError:
            return ReportResult(self._instance_id, sequence, now, scope, unknown,
                                error=ReportError("pricing_unavailable", True))
        except SessionCatalogChangedError:
            return ReportResult(self._instance_id, sequence, now, scope, unknown,
                                error=ReportError("session_catalog_changed", True))
        except SessionNotFoundError:
            return ReportResult(self._instance_id, sequence, now, scope, unknown,
                                error=ReportError("session_not_found"))
        except ReportRequestError:
            # Never leak interpolated targets/paths.
            return ReportResult(self._instance_id, sequence, now, scope, unknown,
                                error=ReportError("report_unavailable"))
        except Exception as exc:
            # An adapter can contain arbitrary transport text in its exception.
            recoverable(exc, "application-report")
            return ReportResult(self._instance_id, sequence, now, scope, unknown,
                                error=ReportError("internal_error"))
        finally:
            try:
                if admitted:
                    service.close_accounts()
            finally:
                self._lock.release()

    @staticmethod
    def _validate(request: ReportRequest) -> str | None:
        if not isinstance(request.kind, ReportKind):
            return "invalid_request"
        if request.stats_scope not in ('today', '7-days', '30-days', 'month', 'all'):
            return 'invalid_request'
        if type(request.comparison_offset) is not int or request.comparison_offset < 0 or request.comparison_offset % 10:
            return 'invalid_request'
        if request.kind is ReportKind.SESSION and not request.session_id:
            return "invalid_request"
        if request.kind is ReportKind.DATE and not request.date_text:
            return "invalid_request"
        if request.session_limit is not None and (type(request.session_limit) is not int or request.session_limit < 1):
            return "invalid_request"
        return None
