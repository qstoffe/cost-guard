"""Optional official Claude CLI metadata transport; never sends user messages.

The published Agent SDK types define initialize/get_usage control requests.
This stdlib bridge uses that same experimental CLI interface, not credential
files or private HTTP endpoints. Unsupported requests fail softly. CLI absence
does not affect OpenCode model availability or other account providers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ClaudeUsageResult:
    account: Mapping[str, object] = field(default_factory=dict, repr=False)
    usage: Mapping[str, object] | None = field(default=None, repr=False)
    availability: str = "available"
    reason: str = ""


def _command(args: list[str]) -> list[str] | None:
    executable = shutil.which("claude")
    if executable is None:
        return None
    command = [executable, *args]
    if executable.lower().endswith((".cmd", ".bat")):
        command = [os.environ.get("COMSPEC") or "cmd.exe", "/d", "/s", "/c", subprocess.list2cmdline(command)]
    return command


def _stop(process: subprocess.Popen) -> None:
    """Close only our helper, including a Windows npm shim's private child."""
    if process.stdin and not process.stdin.closed:
        try:
            process.stdin.close()
        except OSError:
            pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)


def read_claude_auth() -> Mapping[str, object] | None:
    command = _command(["auth", "status", "--json"])
    if command is None:
        return None
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        output, _ = process.communicate(timeout=10)
        if len(output) > 1_048_576:
            raise ValueError("Claude metadata contract changed")
        value = json.loads(output)
        if not isinstance(value, dict) or not isinstance(value.get("loggedIn"), bool):
            raise ValueError("Claude metadata contract changed")
        if process.returncode != 0 and value["loggedIn"]:
            raise ValueError("Claude account metadata unavailable")
        # Never return tokens, unrelated paths or arbitrary CLI fields.
        return {key: value[key] for key in ("loggedIn", "authMethod", "apiProvider", "subscriptionType",
                "email", "orgId", "orgName", "configDirectory") if key in value}
    finally:
        _stop(process)
        if process.stdout:
            process.stdout.close()


class _ControlReader:
    def __init__(self, process: subprocess.Popen, deadline: float):
        self.process, self.deadline = process, deadline
        self.messages: queue.Queue = queue.Queue(maxsize=64)
        self.thread = threading.Thread(target=self._read, daemon=True, name="claude-metadata")
        self.thread.start()

    def _read(self):
        try:
            while line := self.process.stdout.readline(1_048_577):
                if len(line) > 1_048_576:
                    break
                try:
                    value = json.loads(line)
                    if isinstance(value, dict) and value.get("type") == "control_response":
                        self.messages.put_nowait(value)
                except (ValueError, queue.Full):
                    break
        except OSError:
            pass
        finally:
            try:
                self.messages.put_nowait(None)
            except queue.Full:
                pass

    def request(self, identity: str, request: dict) -> dict:
        self.process.stdin.write((json.dumps({"type": "control_request", "request_id": identity,
                                             "request": request}) + "\n").encode("utf-8"))
        self.process.stdin.flush()
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            try:
                value = self.messages.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError from None
            if value is None:
                raise ValueError("Claude metadata transport ended")
            response = value.get("response")
            if isinstance(response, dict) and response.get("request_id") == identity:
                return response


def _failure(response: Mapping[str, object]) -> ClaudeUsageResult:
    error = str(response.get("error", "")).lower()[:1000]
    if any(text in error for text in ("failed to authenticate", "not logged in", "oauth token revoked", "401", "403")):
        return ClaudeUsageResult(availability="unavailable", reason="auth_failure")
    if "get_usage" in error and any(text in error for text in ("unknown", "unsupported", "unrecognized")):
        return ClaudeUsageResult(availability="unavailable", reason="method_missing")
    return ClaudeUsageResult(availability="error", reason="transport_failure")


def read_claude_usage(*, timeout_seconds: float = 20) -> ClaudeUsageResult:
    command = _command(["-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
        "--no-session-persistence", "--setting-sources", "", "--settings", '{"disableAllHooks":true}',
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--tools", "", "--permission-mode", "dontAsk",
        "--no-chrome"])
    if command is None:
        return ClaudeUsageResult(availability="unavailable", reason="cli_missing")
    process = None
    reader = None
    account = {}
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        reader = _ControlReader(process, time.monotonic() + max(.01, timeout_seconds))
        initialized = reader.request("costguard-init", {"subtype": "initialize", "hooks": {}, "sdkMcpServers": []})
        if initialized.get("subtype") != "success":
            return _failure(initialized)
        data = initialized.get("response")
        if not isinstance(data, Mapping) or not isinstance(data.get("account"), Mapping):
            return ClaudeUsageResult(availability="error", reason="format_changed")
        account = {key: data["account"][key] for key in ("email", "organization", "subscriptionType", "apiProvider")
                   if key in data["account"]}
        response = reader.request("costguard-usage", {"subtype": "get_usage", "skip_behaviors": True})
        if response.get("subtype") != "success":
            failure = _failure(response)
            return ClaudeUsageResult(account, None, failure.availability, failure.reason)
        usage = response.get("response")
        if not isinstance(usage, Mapping):
            return ClaudeUsageResult(account, None, "error", "format_changed")
        # Drop session/transcript data; no user/model message has been written.
        return ClaudeUsageResult(account, {key: usage[key] for key in
            ("subscription_type", "rate_limits_available", "rate_limits") if key in usage})
    except (TimeoutError, subprocess.TimeoutExpired):
        return ClaudeUsageResult(account, None, "error", "timeout")
    except (OSError, ValueError):
        return ClaudeUsageResult(account, None, "error", "transport_failure")
    finally:
        if process is not None:
            _stop(process)
            if reader is not None:
                reader.thread.join(timeout=1)
            if process.stdout:
                process.stdout.close()
