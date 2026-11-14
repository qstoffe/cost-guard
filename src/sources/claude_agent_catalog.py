"""Bounded, offline catalog observation shipped with the application, not history."""
from datetime import datetime
import json
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).with_name("claude-agent-catalog.json")
MAX_BYTES = 32768


def _text(value):
    return isinstance(value, str) and 0 < len(value) <= 1024 and value.isprintable()


def load_snapshot(path):
    """Fail closed for the whole asset; never infer IDs from a display name."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            return {}, None
        value = json.loads(raw)
        if (not isinstance(value, dict) or type(value.get("schemaVersion")) is not int
                or value["schemaVersion"] != 1 or value.get("providerID") != "claude-agent"
                or value.get("source") != "opencode-v2-live-model-catalog"
                or not _text(value.get("opencodeVersion"))
                or not _text(value.get("observedAtUtc"))
                or not value["observedAtUtc"].endswith("Z")
                or not isinstance(value.get("models"), list)
                or not 0 < len(value["models"]) <= 200):
            return {}, None
        datetime.fromisoformat(value["observedAtUtc"].replace("Z", "+00:00"))
        models = {}
        for model in value["models"]:
            if (not isinstance(model, dict)
                    or not all(_text(model.get(key)) for key in ("id", "name", "modelID", "status"))
                    or model["status"] not in {"active", "deprecated", "beta", "alpha"}):
                return {}, None
            if model["status"] != "deprecated":
                models[model["id"]] = (model["name"], model["modelID"])
        return models, (value["observedAtUtc"], value["opencodeVersion"])
    except (OSError, ValueError, UnicodeError, RecursionError):
        return {}, None
