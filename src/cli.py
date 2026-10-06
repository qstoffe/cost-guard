"""v77-compatible command-line parsing for the Python entry point."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Sequence

from .version import DISPLAY_VERSION, PRODUCT_NAME

_SESSION_RE = re.compile(r"^ses_[A-Za-z0-9._-]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?::\d{4}-\d{2}-\d{2})?$")


class CommandKind(str, Enum):
    NORMAL = "normal"
    ALL_MODELS = "all-models"
    SESSIONS = "sessions"
    SESSION = "session"
    DATE = "date"
    TOKEN_MIX = "token-mix"


@dataclass(frozen=True, slots=True)
class CliCommand:
    kind: CommandKind
    target: str | None = None
    watch: bool = False


class CliUsageError(ValueError):
    pass


def startup_mode(command: CliCommand) -> str:
    if command.watch:
        return "Watch"
    if command.kind is CommandKind.DATE:
        return "Date Range" if ":" in (command.target or "") else "Date"
    return {CommandKind.NORMAL: "Report", CommandKind.ALL_MODELS: "All Models",
            CommandKind.SESSIONS: "Sessions", CommandKind.SESSION: "Session",
            CommandKind.TOKEN_MIX: "Token Mix"}[command.kind]


def help_text() -> str:
    return f"""{PRODUCT_NAME} {DISPLAY_VERSION}

Usage:
  python cost-guard.py
  python cost-guard.py --all-models
  python cost-guard.py --token-mix
  python cost-guard.py --sessions N|all
  python cost-guard.py --watch
  python cost-guard.py <session-id>
  python cost-guard.py <session-id> --watch
  python cost-guard.py YYYY-MM-DD
  python cost-guard.py YYYY-MM-DD:YYYY-MM-DD

Options:
  --all-models     Full pricing/model catalog only; ignore availability.
  --token-mix      Total Token Mix % and CCost, then per currently selectable
                   model, over all OpenCode history still available (deep scan).
  --sessions N|all Latest N (or all) currently available root sessions.
  -watch, --watch   Keep the selected scope live until Ctrl+C.
  -h, --help       Show this help.
  --version        Show the Cost Guard version.

Token Mix %: I = uncached input (Input); C = cache read (Cache);
             W = cache write (Write); O = output (Output), including
             separately reported reasoning. Each share shows its CCost.
Report: last 100 prompts with usage. Watch: requests observed during this run.
-- means unavailable shares (incomplete telemetry or no positive token total).
CCost is Copilot AI-credit-equivalent reference valuation, not actual billing
or credits deducted. Non-Copilot subscription usage can have positive CCost.
Naked amounts round upward; Token Mix % parentheses are CCost; ? marks partial
pricing. Model rates are CCost/M. Actual billed/account money stays monetary.
Remaining AI credits round downward; quantities never use thousands separators.
"""


def parse_command(argv: Sequence[str]) -> CliCommand:
    if "--all-models" in argv:
        if tuple(argv) != ("--all-models",):
            raise CliUsageError("--all-models is a standalone one-shot report.")
        return CliCommand(CommandKind.ALL_MODELS)
    if "--token-mix" in argv:
        if tuple(argv) != ("--token-mix",):
            raise CliUsageError("--token-mix is a standalone one-shot report.")
        return CliCommand(CommandKind.TOKEN_MIX)
    if "--sessions" in argv:
        if len(argv) != 2 or argv[0] != "--sessions":
            raise CliUsageError("Use --sessions N or --sessions all without other arguments.")
        limit = str(argv[1])
        if limit != "all" and not re.fullmatch(r"[1-9][0-9]*", limit):
            raise CliUsageError("--sessions requires a positive integer or 'all'.")
        return CliCommand(CommandKind.SESSIONS, limit)
    target: str | None = None
    watch = False
    for raw in argv:
        value = str(raw)
        if value.lower() in {"-watch", "--watch"}:
            if watch:
                raise CliUsageError(f"Duplicate watch switch '{value}'.")
            watch = True
            continue
        if value.startswith("-"):
            raise CliUsageError(f"Unknown option '{value}'.")
        if target is not None:
            raise CliUsageError(
                "Invalid arguments. Expected at most one OpenCode session ID, YYYY-MM-DD date, "
                "or YYYY-MM-DD:YYYY-MM-DD date range plus optional -watch/--watch."
            )
        target = value

    if target is None:
        return CliCommand(CommandKind.NORMAL, None, watch)
    if _SESSION_RE.fullmatch(target):
        return CliCommand(CommandKind.SESSION, target, watch)
    if _DATE_RE.fullmatch(target):
        if watch:
            raise CliUsageError("Date/date-range reports are one-shot and cannot be combined with -watch/--watch.")
        return CliCommand(CommandKind.DATE, target, False)
    raise CliUsageError(
        f"Invalid argument '{target}'. Expected a session ID starting with 'ses_', "
        "YYYY-MM-DD, or YYYY-MM-DD:YYYY-MM-DD."
    )
