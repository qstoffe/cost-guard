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
from .sources.errors import SourceError, SourceUnavailableError
from .sources.discovery import default_opencode_data_dir, find_opencode_executable, has_opencode_installation_evidence
from .sources.model_availability import FallbackModelAvailabilitySource, OpenCodeModelAvailabilitySource
from .sources.selection import SourceSelector
from .version import DISPLAY_VERSION, PRODUCT_NAME, mode_heading
from .watch import WatchCoordinator
from .watch.coordinator import WatchedSessionEnded
from .runtime_errors import check_pending, context, diagnostics_hint

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _print_error(title: str, message: str) -> None:
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
        "→█░✓—⚠".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(errors="replace")


def _select_source(requested: str):
    """Wake the shared V2 service once when no requested source is usable.

    The OpenCode API CLI discovers/starts its own background service. Never
    launch a TUI or re-run this on Watch polls; forced V1 remains process-free.
    """
    selector = SourceSelector()
    try:
        return selector.select(requested)
    except SourceUnavailableError:
        if requested not in {"auto", "v2"}:
            raise
        executable = find_opencode_executable(which=shutil.which)
        if executable is None:
            raise
        command = [executable, "api", "get", "/api/info"]
        if executable.lower().endswith((".cmd", ".bat")):
            command = [
                os.environ.get("COMSPEC") or "cmd.exe", "/d", "/s", "/c",
                subprocess.list2cmdline(command),
            ]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=20, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise SourceUnavailableError(
                "OpenCode V2 background service could not be started. Start OpenCode or check its service status."
            ) from None
        if result.returncode != 0:
            raise SourceUnavailableError(
                "OpenCode V2 background service could not be started. Start OpenCode or check its service status."
            )
        return selector.select(requested)


def _wait_for_watch_source(requested: str, renderer: WatchRenderer, *, sleep=time.sleep):
    """Keep Watch open while OpenCode is offline; reconnect without CLI polling."""
    selector = SourceSelector()
    message = "Watch: Waiting for OpenCode source · retrying every 5s (Ctrl+C to stop)"
    if not renderer.interactive:
        renderer._write(message)
    while True:
        renderer.render_startup_status(message, active=True)  # a waiting status, not loading
        try:
            sleep(5)
            return selector.select(requested)
        except SourceUnavailableError:
            continue


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv) if argv is not None else list(sys.argv[1:])
    if any(value in {"-h", "--help"} for value in args):
        if len(args) != 1:
            _print_error("Cost Guard - Argument error", "--help cannot be combined with report arguments.")
            return 2
        print(help_text(), end="")
        return 0
    if "--version" in args:
        if len(args) != 1:
            _print_error("Cost Guard - Argument error", "--version cannot be combined with report arguments.")
            return 2
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
    try:
        config = loaded.values
        if command.watch:
            watch_renderer = WatchRenderer(config)
            watch_renderer.render_initializing("detecting...")
            progress = StartupProgress(
                mode="watch",
                line_sink=watch_renderer.render_startup_status if watch_renderer.interactive else None,
            )
        else:
            progress = StartupProgress(mode="normal", heading=mode_heading(startup_mode(command)))

        progress.update("Selecting OpenCode source")
        context(phase="source selection")
        requested_source = str(config["openCode"]["source"])
        try:
            selection = _select_source(requested_source)
        except SourceUnavailableError:
            if not command.watch or watch_renderer is None:
                if shutil.which("opencode") is None and not has_opencode_installation_evidence():
                    progress.stop()
                    _print_error("Cost Guard - OpenCode not found",
                                 "OpenCode does not appear to be installed.\n"
                                 "Install OpenCode and start it once, then restart Cost Guard.")
                    return 1
                raise
            progress.stop()
            try:
                selection = _wait_for_watch_source(requested_source, watch_renderer)
            except KeyboardInterrupt:
                watch_renderer.finish("Watch stopped.")
                return 0
        if command.watch and watch_renderer is not None:
            # The transient two-line startup surface gives way to the full dashboard.
            watch_renderer.render_initializing(selection.selected.upper())

        progress.update("Initializing cache")
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
            progress.update("Initializing Watch")
            context(phase="Watch initialization")
            coordinator = WatchCoordinator(
                selection=selection,
                report_service=service,
                config=config,
                session_id=command.target if command.kind is CommandKind.SESSION else None,
            )
            initial_cycle = coordinator.initialize()
            progress.stop()
            assert watch_renderer is not None
            context(phase="Watch runtime")
            coordinator.run_forever(watch_renderer, initial_cycle=initial_cycle)
            return 0

        context(phase="report analysis")
        if command.kind is CommandKind.TOKEN_MIX:
            projection = service.build_token_mix_history(progress.update)
        else:
            projection = service.build(_report_request(command))
        progress.stop()
        context(phase="report presentation")
        ReportRenderer(config).render(projection)
        if command.kind is CommandKind.SESSION and any(
            row.in_progress for block in projection.prompt_blocks for row in block.rows
        ):
            coordinator = WatchCoordinator(
                selection=selection,
                report_service=service,
                config=config,
                session_id=command.target,
            )
            coordinator.run_until_inactive(WatchRenderer(config))
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
        _print_error("Cost Guard - Runtime error", str(exc) or type(exc).__name__)
        if not isinstance(exc, WatchedSessionEnded):
            # Stopping product errors only; recoverable outages never reach here.
            print(diagnostics_hint(PACKAGE_ROOT), end="")
        return 1
    finally:
        if progress is not None:
            progress.stop()
