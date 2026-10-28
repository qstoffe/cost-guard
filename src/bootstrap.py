"""Application composition root for Cost Guard v78."""
from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .accounts.github_copilot import GitHubCopilotAccountProvider
from .accounts.openai_subscription import OpenAIAccountProvider
from .accounts.anthropic import AnthropicAccountProvider
from .accounts.claude_code import ClaudeCodeAccountProvider
from .accounts.minimax import MiniMaxAccountProvider
from .accounts.simple_http import SIMPLE_HTTP_PROVIDERS, SimpleHttpAccountProvider
from .cache import CacheDatabase, CacheRepository
from .cli import CliUsageError, CommandKind, help_text, parse_command, startup_mode
from .config import ConfigError, load_configuration
from .presentation import ReportRenderer, StartupProgress, WatchRenderer
from .pricing.github_copilot import GitHubCopilotPricingProvider
from .pricing.github_copilot import PricingUnavailableError
from .reports import ReportKind, ReportRequest, ReportService
from .sources.errors import FailureCode, SourceError, SourceUnavailableError
from .sources.read_recovery import ReadRecovery
from .sources.connectivity_events import record as record_source_event
from .presentation.source_errors import source_error_message, source_wait_message
from .sources.discovery import default_opencode_data_dir, find_opencode_executable, has_opencode_installation_evidence
from .sources.model_availability import FallbackModelAvailabilitySource, OpenCodeModelAvailabilitySource
from .sources.selection import SourceSelector
from .version import DISPLAY_VERSION, PRODUCT_NAME, mode_heading
from .watch import WatchCoordinator
from .watch.coordinator import WatchedSessionEnded
from .runtime_errors import check_pending, context, diagnostics_hint
from .launcher_feedback import release_launcher_status
from .domain.progress import WorkProgress

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _print_error(title: str, message: str) -> None:
    release_launcher_status()
    print(title)
    print()
    print(message)


def _report_request(command) -> ReportRequest:
    if command.kind is CommandKind.ALL_MODELS:
        return ReportRequest(ReportKind.ALL_MODELS)
    if command.kind is CommandKind.SESSIONS:
        return ReportRequest(ReportKind.SESSIONS, session_limit=None if command.target == "all" else int(command.target))
    if command.kind is CommandKind.SESSION:
        return ReportRequest(ReportKind.SESSION, session_id=command.target)
    if command.kind is CommandKind.DATE:
        return ReportRequest(ReportKind.DATE, date_text=command.target)
    return ReportRequest(ReportKind.NORMAL)


def _model_availability_source(selection):
    """Reuse selected V2 service discovery/authentication; CLI is compatibility."""
    cli = OpenCodeModelAvailabilitySource()
    if callable(getattr(selection.source, "available_model_ids", None)):
        return FallbackModelAvailabilitySource(selection.source, cli)
    return cli


def _account_providers(config, selected_source):
    """Wire quota integrations only for dashboard/explicit Watch use cases."""
    providers = []
    db_path = (default_opencode_data_dir() / "opencode.db") if selected_source == "v2" else None
    for config_key, provider_type in (
        ("copilotQuota", GitHubCopilotAccountProvider),
        ("openAiQuota", OpenAIAccountProvider),
        ("anthropicQuota", AnthropicAccountProvider),
        ("minimaxQuota", MiniMaxAccountProvider),
    ):
        settings = config.get(config_key) if isinstance(config.get(config_key), dict) else {}
        providers.append(provider_type(enabled=bool(settings.get("enabled", True)),
            auth_json_path=settings.get("authJsonPath"), credential_db_path=db_path))
    settings = config.get("anthropicQuota") or {}
    providers.append(ClaudeCodeAccountProvider(enabled=bool(settings.get("enabled", True))))
    for definition in SIMPLE_HTTP_PROVIDERS:
        settings = config.get(definition.provider_id + "Quota") or {}
        providers.append(SimpleHttpAccountProvider(definition, enabled=bool(settings.get("enabled", True)),
            auth_json_path=settings.get("authJsonPath"), credential_db_path=db_path))
    return tuple(providers)


def _prepare_console_output() -> None:
    """Keep a legacy-encoded Windows pipe from aborting Unicode reports/Watch."""
    encoding = getattr(sys.stdout, "encoding", None)
    if not encoding:
        return
    try:
        "\u2192\u2588\u2591\u2713\u2014\u26a0\u25b6".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


def _wake_cli_service(executable: str) -> None:
    """The single supported CLI wake, never a recurring discovery action."""
    command = [executable, "api", "get", "/api/info"]
    if executable.lower().endswith((".cmd", ".bat")):
        command = [os.environ.get("COMSPEC") or "cmd.exe", "/d", "/s", "/c",
                   subprocess.list2cmdline(command)]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise SourceUnavailableError("OpenCode V2 background service could not be started",
            code=FailureCode.ENDPOINT_UNRESPONSIVE, phase="selection", generation="v2") from None
    if result.returncode != 0:
        raise SourceUnavailableError("OpenCode V2 background service could not be started",
            code=FailureCode.ENDPOINT_UNRESPONSIVE, phase="selection", generation="v2")


def _select_source(requested: str, *, inspect_migration_gap: bool = True):
    """Wake once if appropriate; reports share a short discovery/read retry budget."""
    selector = SourceSelector(inspect_migration_gap=inspect_migration_gap)
    recovery = ReadRecovery()
    try:
        selection = selector.select(requested)
    except SourceUnavailableError as error:
        if requested not in {"auto", "v2"} or not error.readiness_retryable:
            raise
        started = time.monotonic()
        executable = find_opencode_executable(which=shutil.which)
        if executable is not None:
            _wake_cli_service(executable)
        selection = recovery.run(lambda: selector.select(requested), initial_error=error)
        record_source_event("v2", "recovered", "available", **error.evidence(),
                            attempts=recovery.failures,
                            duration_ms=int((time.monotonic() - started) * 1000))
    if getattr(selection, "selected", None) == "v2":
        selection.source.read_recovery = recovery
    return selection


def _wait_for_watch_source(requested: str, renderer: WatchRenderer, *, sleep=time.sleep):
    """Keep Watch open while OpenCode is offline; reconnect without CLI polling."""
    selector = SourceSelector(inspect_migration_gap=False)
    message = source_wait_message(requested)
    if not renderer.interactive:
        renderer._write(message)
    started = time.monotonic()
    attempts = 0
    while True:
        renderer.render_startup_status(message, active=True)  # a waiting status, not loading
        try:
            sleep(5)
            attempts += 1
            selection = selector.select(requested)
            record_source_event(getattr(selection, "selected", "v2"), "recovered", "available",
                                phase="selection", attempts=attempts,
                                duration_ms=int((time.monotonic() - started) * 1000))
            return selection
        except SourceUnavailableError as error:
            if error.terminal or (error.code != FailureCode.UNKNOWN and not error.watch_retryable):
                raise


def _select_or_wait(requested: str, progress, renderer):
    try:
        return (_select_source(requested, inspect_migration_gap=False) if renderer is not None else _select_source(requested))
    except SourceUnavailableError as error:
        if error.terminal or (error.code != FailureCode.UNKNOWN and not error.watch_retryable):
            raise
        progress.stop()
        if renderer is not None:
            return _wait_for_watch_source(requested, renderer)
        if shutil.which("opencode") is None and not has_opencode_installation_evidence():
            _print_error("Cost Guard - OpenCode not found",
                         "OpenCode does not appear to be installed.\n"
                         "Install OpenCode and start it once, then restart Cost Guard.")
            print(diagnostics_hint(PACKAGE_ROOT), end="")
            return None
        raise


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv) if argv is not None else list(sys.argv[1:])
    if any(value in {"-h", "--help"} for value in args):
        if len(args) != 1:
            _print_error("Cost Guard - Argument error", "--help cannot be combined with report arguments.")
            return 2
        release_launcher_status()
        print(help_text(), end="")
        return 0
    if "--version" in args:
        if len(args) != 1:
            _print_error("Cost Guard - Argument error", "--version cannot be combined with report arguments.")
            return 2
        release_launcher_status()
        print(f"{PRODUCT_NAME} {DISPLAY_VERSION}")
        return 0

    try:
        command = parse_command(args)
    except CliUsageError as exc:
        _print_error("Cost Guard - Argument error", str(exc))
        print()
        print("Run 'python cost-guard.py --help' for usage.")
        return 2

    try:
        loaded = load_configuration(PACKAGE_ROOT)
    except ConfigError as exc:
        _print_error("Cost Guard - Configuration error", str(exc))
        print()
        print("Fix the setting and restart Cost Guard.")
        return 1

    _prepare_console_output()
    context(mode=startup_mode(command), phase="startup")
    progress: StartupProgress | None = None
    watch_renderer: WatchRenderer | None = None
    service: ReportService | None = None
    try:
        config = dict(loaded.values)
        if command.ccost_unit is not None:
            config["ccostDisplayUnit"] = command.ccost_unit
        if command.watch:
            watch_renderer = WatchRenderer(config)
            watch_renderer.render_initializing("detecting...")
            progress = StartupProgress(
                mode="Watch Session" if command.kind is CommandKind.SESSION else "Watch",
                line_sink=watch_renderer.render_startup_status if watch_renderer.interactive else None,
            )
        else:
            progress = StartupProgress(mode=startup_mode(command), heading=mode_heading(startup_mode(command)))

        progress.update(WorkProgress("Selecting OpenCode source", "source"))
        context(phase="source selection")
        requested_source = str(config["openCode"]["source"])
        selection = _select_or_wait(requested_source, progress, watch_renderer)
        if selection is None:
            return 1
        progress.update(WorkProgress("Initializing cache", "cache"))
        context(phase="cache initialization")
        database = CacheDatabase(PACKAGE_ROOT)
        database.initialize()
        repository = CacheRepository(database)

        pricing = GitHubCopilotPricingProvider(
            cache=repository,
            max_age_hours=float(config.get("pricingMaxAgeHours", 1)),
            # Watch recovers release-date metadata on a background worker.
            defer_metadata_refresh=command.watch,
        )
        needs_accounts = command.watch or command.kind is CommandKind.NORMAL
        accounts = _account_providers(config, selection.selected) if needs_accounts else ()
        service = ReportService(
            selection=selection,
            pricing_provider=pricing,
            account_provider=accounts[0] if accounts else None,
            account_providers=accounts,
            model_availability_source=_model_availability_source(selection),
            cache_repository=repository,
            config=config,
            now_ms=int(time.time() * 1000),
            # The deep history scan reports its own percentage, not per-root labels.
            progress=progress.update if command.kind is not CommandKind.TOKEN_MIX else (lambda _label: None),
        )
        if command.watch:
            progress.update(WorkProgress("Initializing Watch", "pricing"))
            context(phase="Watch initialization")
            coordinator = WatchCoordinator(
                selection=selection,
                report_service=service,
                config=config,
                session_id=command.target if command.kind is CommandKind.SESSION else None,
                started_at_ms=watch_renderer.started_at_ms if watch_renderer is not None else None,
            )
            # Watch uses coordinator recovery, never the short report retry policy.
            if selection.selected == "v2":
                selection.source.read_recovery = None
            initial_cycle = coordinator.initialize_with_recovery(watch_renderer, before_recovery=progress.stop)
            progress.stop(complete=True)
            assert watch_renderer is not None
            context(phase="Watch runtime")
            coordinator.run_forever(watch_renderer, initial_cycle=initial_cycle)
            return 0

        context(phase="report analysis")
        if command.kind is CommandKind.TOKEN_MIX:
            projection = service.build_token_mix_history(progress.update)
        else:
            projection = service.build(_report_request(command))
        progress.stop(complete=True)
        context(phase="report presentation")
        ReportRenderer(config).render(projection)
        return 0
    except KeyboardInterrupt:
        check_pending()
        if watch_renderer is None:
            raise
        if progress is not None:
            progress.stop()
        watch_renderer.finish("Watch stopped.")
        return 0
    except (SourceError, WatchedSessionEnded, PricingUnavailableError) as exc:
        if progress is not None:
            progress.stop()
        title, message = source_error_message(exc.code.value, exc.generation, exc.readiness_retryable, str(exc)) if isinstance(exc, SourceError) else (
            "Cost Guard - Runtime error", str(exc) or type(exc).__name__)
        _print_error(title, message)
        if not isinstance(exc, WatchedSessionEnded):
            # Stopping product errors only; recoverable outages never reach here.
            print(diagnostics_hint(PACKAGE_ROOT), end="")
        return 1
    finally:
        if service is not None:
            service.close_accounts()
        if progress is not None:
            progress.stop()
