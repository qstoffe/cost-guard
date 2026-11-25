"""Read this installation's private Web observations and probe only its recorded listener."""
from collections import Counter, deque
from http.client import HTTPConnection, HTTPException
import json
import re
import time

from src.web.instance_state import LIFECYCLE_CODES, private_web_directory
from src.web.observations import API_REASONS, SOURCE_ERROR_CODES, SOURCE_STATES
from src.web.process_identity import InstanceConflict
from development.tools.diagnostic_section import error_codes
from development.tools.diagnostic_web_errors import read_bounded, runtime_evidence

STATES = {"starting", "ready", "menu", "launcher", "source_changed", "configuration_changed",
          "runtime_fault", "gui_unavailable"}
CONFIG_STATES = {"unchecked", "verified", "configuration_changed", "configuration_unavailable"}


def _integer(value, limit):
    return type(value) is int and 0 <= value <= limit


def _counters(value, keys):
    if not isinstance(value, dict) or any(not _integer(value.get(k), 1_000_000) for k in keys):
        raise ValueError("invalid_counters")
    return {k: value[k] for k in keys}


def _snapshot(value):
    numeric = ("observed_at", "source_transitions", "uptime_ms")
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] not in (1, 2) or value.get("instance_schema") != 1
            or not isinstance(value.get("product_version"), str)
            or not re.fullmatch(r"[0-9]{1,4}\.[0-9]{1,4}", value["product_version"])
            or value.get("state") not in STATES or value.get("source_status") not in SOURCE_STATES
            or any(not _integer(value.get(k), 2**53 - 1) for k in numeric)):
        raise ValueError("invalid_snapshot")
    result = {k: value[k] for k in ("schema_version", "instance_schema", "product_version", "state",
                                   "source_status", *numeric)}
    result["api_failures"] = _counters(value.get("api_failures"), ("denied", "invalid", "busy", "unavailable"))
    if value["schema_version"] == 2:
        result["api_reasons"] = _counters(value.get("api_reasons"), API_REASONS)
        observed = value.get("source_observed_at_ms")
        config = value.get("config_status")
        error = value.get("source_error")
        progress = value.get("live_progress")
        result.update(source_observed_at_ms=observed if _integer(observed, 2**53 - 1) else None,
                      source_error=error if isinstance(error, str) and error in SOURCE_ERROR_CODES else None,
                      config_status=config if config in CONFIG_STATES else "unchecked",
                      lifecycle_write_failed=value.get("lifecycle_write_failed") is True)
        if isinstance(progress, dict):
            result["live_progress"] = {key: progress[key] for key in
                ("tick_ms", "completed_at_ms", "sessions", "roots", "active_candidates")
                if _integer(progress.get(key), 2**53 - 1)}
    return result


def _listener_probe(raw, age):
    port = raw.get("listener_port")
    if raw.get("state") != "ready" or age > 30 or not _integer(port, 65535) or port == 0:
        return {"status": "unknown", "reason": "no_recent_listener_record"}
    # No session, control token, proxy or redirects. Reachability at the recorded
    # listener is not authenticated identity, browser handoff, or source readiness.
    connection = HTTPConnection("127.0.0.1", port, timeout=0.75)
    try:
        connection.request("GET", "/health")
        with connection.getresponse() as response:
            status = response.status
            if status == 200 and response.length is not None and 0 < response.length <= 64:
                body = response.read(response.length)
                for state in ("ready", "stopping"):
                    if body == json.dumps({"http": state}).encode("ascii"):
                        return {"status": state, "evidence": "current_loopback_http", "identity_verified": False}
            return {"status": "unexpected_response", "http_status": status}
    except (OSError, HTTPException) as exc:
        return {"status": "unavailable", "exception_type": type(exc).__name__, **error_codes(exc)}
    finally:
        connection.close()


def _lifecycle(directory):
    counts = Counter()
    recent = deque(maxlen=24)
    for line in read_bounded(directory / "lifecycle.log", 65536).decode("ascii").splitlines():
        fields = line.split()
        if len(fields) == 2 and 0 < len(fields[0]) <= 10 and fields[0].isdigit() and fields[1] in LIFECYCLE_CODES:
            counts[fields[1]] += 1
            recent.append({"observed_at": int(fields[0]), "code": fields[1]})
    return dict(counts), list(recent)


def web_evidence(root, *, data_home=None):
    """Missing/stale facts are evidence limitations, never a live-health claim."""
    try:
        directory = private_web_directory(root, data_home=data_home)
    except (InstanceConflict, OSError, RuntimeError) as exc:
        return {"status": "unavailable", "exception_type": type(exc).__name__, **error_codes(exc)}
    result = {"status": "not_observed", "snapshot": None, "lifecycle_codes": {},
              "lifecycle_status": "not_observed", "host_probe": {"status": "unknown"}}
    try:
        raw = json.loads(read_bounded(directory / "diagnostics.json", 4096))
        snapshot = _snapshot(raw)
        age = int(time.time()) - snapshot["observed_at"]
        result.update(status="recorded", snapshot=snapshot, age_seconds=age,
                      stale=not 0 <= age <= 30, host_probe=_listener_probe(raw, age) if age >= 0 else {"status": "unknown"})
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        result.update(status="unavailable", exception_type=type(exc).__name__, **error_codes(exc))
    try:
        counts, recent = _lifecycle(directory)
        if recent:
            result.update(lifecycle_status="recorded", lifecycle_codes=counts,
                          lifecycle_history=recent, latest_lifecycle=recent[-1])
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        result.update(lifecycle_status="unavailable", lifecycle_error=type(exc).__name__)
    result["runtime_errors"] = runtime_evidence(directory)
    return result
