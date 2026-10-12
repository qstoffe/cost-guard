"""Conservative skill execution identity and bounded Toolkit result contracts.

Only already-normalized tool inputs/metadata are examined. Output decoding is
gated by a known directly executed script, never prose, exit codes or recency.
No filesystem access, command execution or raw-output logging occurs here.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import re
import shlex

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_PYTHON = re.compile(r"(?:py|python(?:\d+(?:\.\d+)?)?)(?:\.exe)?\Z", re.I)
_SCRIPT = re.compile(r"(?:^|/)skills/([^/]+)/scripts/([^/]+(?:/[^/]+)*\.py)\Z")
_MAX_RESULT_CHARS = 65_536
# Each entry is a verified one-JSON-object status/error.class execution contract.
_TOOLKIT_SCHEMAS = {
    ("auto-agent-browser", "browser_cli.py"): "opencode-toolkit/agent-browser-wrapper/v1",
    ("auto-github-api", "github_api.py"): "opencode-toolkit/github-api/v1",
    ("auto-jira-api", "jira_api.py"): "opencode-toolkit/jira-api/v1",
    ("auto-confluence-docs", "confluence_read.py"): "opencode-toolkit/confluence-read/v1",
    ("auto-log-debugging", "elastic_read.py"): "opencode-toolkit/elastic-read/v1",
    ("auto-log-debugging", "openshift_read.py"): "opencode-toolkit/openshift-read/v1",
    ("auto-log-debugging", "kibana_link.py"): "opencode-toolkit/kibana-link/v1",
    ("auto-document-reading", "docling_convert.py"): "opencode-toolkit/docling-convert/v1",
    ("auto-document-reading", "spreadsheet_extract.py"): "opencode-toolkit/spreadsheet-extract/v1",
    ("auto-media-transcription", "transcribe.py"): "opencode-toolkit/media-transcription/v1",
    ("shared-checkpoint-memory-contract", "resume_bootstrap.py"): "opencode-toolkit/checkpoint-resume-bootstrap/v2",
    ("shared-checkpoint-memory-contract", "lineage.py"): "opencode-toolkit/checkpoint-lineage/v7",
    ("shared-checkpoint-memory-contract", "validate_tree.py"): "opencode-toolkit/memory-tree-validation/v4",
    ("shared-checkpoint-memory-contract", "inspect_tree.py"): "opencode-toolkit/memory-tree-inspection/v4",
    ("shared-checkpoint-memory-contract", "heal_layout.py"): "opencode-toolkit/memory-layout-heal/v1",
}
_CANCELLED_CLASSES = frozenset({"ABORTED", "CANCELLED", "CANCELED", "INTERRUPTED", "AbortedError", "AbortError"})


def _skill_id(value: object) -> str:
    return value if isinstance(value, str) and _ID.fullmatch(value) and value not in {".", ".."} else ""


def tool_input(data: Mapping) -> Mapping:
    state = data.get("state")
    value = state.get("input") if isinstance(state, Mapping) else None
    if not isinstance(value, Mapping):
        value = data.get("input")
    return value if isinstance(value, Mapping) else {}


def loaded_skill(data: Mapping) -> str:
    """Native skill tools use name (V1) or id (V2); success confirms the load."""
    name = str(data.get("tool") or data.get("name") or "").lower()
    state = data.get("state")
    if name not in {"skill", "functions.skill"} or not isinstance(state, Mapping) or state.get("status") != "completed":
        return ""
    inputs = tool_input(data)
    return _skill_id(inputs.get("id", inputs.get("name")))


def _command_tokens(command: str) -> list[str]:
    try:
        raw = shlex.split(command, posix=False)
    except ValueError:
        return []
    tokens = []
    for token in raw:
        if token[:1] in {"\"", "'"} and token[-1:] == token[:1]:
            token = token[1:-1]
        if "\"" in token or "'" in token:
            return []
        tokens.append(token)
    return tokens


def executed_skill_script(data: Mapping) -> tuple[str, str] | None:
    """Accept a single direct Python invocation, not reads/echoes or shell programs."""
    name = str(data.get("tool") or data.get("name") or "").lower()
    if name not in {"shell", "bash", "functions.shell"}:
        return None
    command = tool_input(data).get("command")
    if not isinstance(command, str) or "skills/" not in command.replace("\\", "/"):
        return None
    # Ambiguous programs, interpolation and compound commands fail closed.
    if any(char in command for char in ";|&\r\n<>`$"):
        return None
    tokens = _command_tokens(command)
    if not tokens or not _PYTHON.fullmatch(tokens.pop(0).replace("\\", "/").rsplit("/", 1)[-1]):
        return None
    while tokens and tokens[0] in {"-3", "-u", "-B", "-X"}:
        flag = tokens.pop(0)
        if flag == "-X" and (not tokens or tokens.pop(0) != "utf8"):
            return None
    if not tokens:
        return None
    path = tokens[0].replace("\\", "/")
    if any(piece in {".", ".."} for piece in path.split("/")):
        return None
    match = _SCRIPT.search(path)
    if match and _skill_id(match[1]):
        return match[1], match[2]
    return None


def failure_skill(data: Mapping, script: tuple[str, str] | None) -> str:
    """Conflicting explicit identities are uncertain, never resolved by recency."""
    identities = {script[0]} if script else set()
    state = data.get("state")
    for container in (data, state if isinstance(state, Mapping) else {}):
        metadata = container.get("metadata")
        if isinstance(metadata, Mapping):
            identities.update(_skill_id(metadata.get(key)) for key in ("skill_id", "skillID", "skillId"))
    name = str(data.get("tool") or data.get("name") or "").lower()
    if name in {"skill", "functions.skill"}:
        inputs = tool_input(data)
        identities.add(_skill_id(inputs.get("id", inputs.get("name"))))
    identities.discard("")
    return next(iter(identities)) if len(identities) == 1 else ""


def _result(value: object) -> Mapping:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str) or len(value) > _MAX_RESULT_CHARS:
        return {}
    try:
        result, end = json.JSONDecoder().raw_decode(value.lstrip())
    except (ValueError, RecursionError):
        return {}
    trailing = value.lstrip()[end:].strip()
    if trailing and not re.fullmatch(r"(?:Process exited|Exited) with code \d+", trailing):
        return {}
    return result if isinstance(result, Mapping) else {}


def structured_outcome(data: Mapping, script: tuple[str, str] | None) -> str:
    """Return only a verified error/cancellation outcome; unknown output stays neutral."""
    schema = _TOOLKIT_SCHEMAS.get(script)
    state = data.get("state")
    if not schema or not isinstance(state, Mapping) or str(state.get("status") or "").lower() not in {"completed", "error"}:
        return ""
    result = _result(state.get("output"))
    # Known scripts always emit this schema; malformed/unrecognized output is not evidence.
    if result.get("schema") != schema or result.get("status") != "error":
        return ""
    error = result.get("error")
    error_class = error.get("class") if isinstance(error, Mapping) else None
    if not isinstance(error_class, str) or not error_class:
        return ""
    return "cancelled" if error_class in _CANCELLED_CLASSES else "error"
