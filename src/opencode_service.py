"""Explicit, bounded shared-service wake for trusted CLI/Web startup only.

Source discovery and recurring acquisition remain process-free. This command
uses OpenCode's installed service discovery; it never owns/stops the service.
"""
import os
import subprocess

from .sources.errors import FailureCode, SourceUnavailableError


def wake_cli_service(executable: str, *, timeout: float = 20) -> None:
    """Discard CLI output; callers must independently probe actual readiness."""
    command = [executable, "api", "get", "/api/info"]
    if executable.lower().endswith((".cmd", ".bat")):
        # list2cmdline quotes spaces, not cmd expansion/operators. Refuse these
        # unusual install paths rather than interpret any part as shell syntax.
        if any(character in executable for character in '&|<>^%!"\r\n'):
            raise _unavailable()
        interpreter = subprocess.list2cmdline([os.environ.get("COMSPEC") or "cmd.exe"])
        # cmd parses its /c tail itself, not CommandLineToArgvW's backslash-quote
        # convention. Quote the entire fixed tail and its executable separately.
        command = f'{interpreter} /d /s /c ""{executable}" api get /api/info"'
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout, check=False, **options)
    except (OSError, subprocess.TimeoutExpired):
        raise _unavailable() from None
    if result.returncode != 0:
        raise _unavailable()


def _unavailable():
    return SourceUnavailableError("OpenCode V2 background service could not be started",
        code=FailureCode.ENDPOINT_UNRESPONSIVE, phase="selection", generation="v2")
