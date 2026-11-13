"""Request-matched live help assertions; private source facts stay in memory."""
from collections import Counter
import json
import re
import time


# Independent, deliberately small oracle from the reviewed official Claude docs.
# Other documentation routes are not certified by this focused installation probe.
DOCUMENTED = {
    "claude-opus-5-5": "medium", "claude-haiku-5-5": "medium",
    "claude-sonnet-5-5": "high", "claude-fable-5-1": "high",
}
NOTES = {
    "request": "Observed in the recorded request",
    "current-configuration": "Inferred from current OpenCode",
    "current-package": "Inferred from the current OpenCode provider package",
    "documentation": "Likely effort based on provider documentation",
    "unknown": "No supported concrete effort evidence",
}


def expected_default(invocation):
    actual = (invocation.variant or "").lower()
    if actual and actual != "default":
        return actual, "request"
    observed = invocation.model.effort_default
    if observed and observed.level:
        return observed.level, observed.source
    model = invocation.model
    if model.provider in {"anthropic", "claude-agent"}:
        identity = observed.model_id if observed else model.model
        if model.provider == "claude-agent" and model.resolution:
            identity = {
                "Opus 5.5": "claude-opus-5-5", "Haiku 5.5": "claude-haiku-5-5",
                "Sonnet 5.5": "claude-sonnet-5-5", "Fable 5.1": "claude-fable-5-1",
            }.get(model.display_name, identity)
        level = DOCUMENTED.get(identity.replace(".", "-"))
        if level:
            return level, "documentation"
    return None


def matching_requests(session_id, row, snapshot):
    events = {event.event_id: event for event in snapshot.events if event.session_id == session_id}
    event = events.get(row.event_id)
    if event is None:
        return {}, ()
    metadata = event.metadata
    invocations = tuple(item for item in snapshot.invocations if item.session_id == session_id
        and item.initiating_event_id == event.event_id and not item.summary
        and item.model.provider == metadata.get("provider_id")
        and item.model.recorded_model == metadata.get("model_id"))
    return metadata, invocations


def check_row(session_id, row, wire, snapshot):
    """Compare source-qualified physical calls, never use the formatter as oracle."""
    metadata, invocations = matching_requests(session_id, row, snapshot)
    parts = wire["prompt"].get("cost_detail", {}).get("parts", [])
    display = wire["prompt"]["display"]
    counts = Counter(matched_events=1, qualified_invocations=len(invocations))
    for invocation in invocations:
        selected = metadata.get("variant", "")
        if selected is None:
            continue
        counts["selected_explicit" if selected and selected.lower() != "default" else "selected_default"] += 1
        matching = [part for part in parts if part["role"] == "main"
            and part["provider_id"] == invocation.model.provider
            and part["model_id"] == invocation.model.model
            and invocation.model.recorded_model in part["selected_models"]
            and part["variant"] == invocation.variant]
        if not matching:
            counts["missing_dto_groups"] += 1
            assert wire["prompt"]["cost_detail"]["omitted_parts"], "source-qualified request missing DTO group"
            counts["bounded_group_omissions"] += 1
            continue
        counts["matched_requests"] += 1
        facts = [fact for part in matching for fact in part["effort_evidence"]]
        assert any(fact["selected"] == selected for fact in facts), "recorded selection lost"
        if selected and selected.lower() != "default":
            assert not any(fact["selected"] == selected and fact["effective"] for fact in facts), "explicit relabeled"
            counts["explicit_requests"] += 1
            continue
        expected = expected_default(invocation)
        if expected is None:
            counts["unsupported_oracle_defaults"] += 1
            continue
        level, source = expected
        assert any((fact["selected"], fact["effective"], fact["source"]) == (selected, level, source)
                   for fact in facts), "request-matched evidence differs"
        token = f"default ({level})"
        for key in ("model_detail_help", "cost_detail_help", "calls_help", "main_model_help", "effort_tooltip"):
            text = display[key]
            assert token in text, "ordinary default missing"
            assert not re.search(r"default \([^)\n]+\)\*", text), "default marker leaked"
            assert not any(note in text for note in NOTES.values()), "default provenance leaked"
        assert token + "*\n* " in display["effort_help"], "value marker missing"
        assert NOTES[source] in display["effort_help"], "source note differs"
        counts["default_requests"] += 1
        counts["source_" + source] += 1
        counts["absent_variant_defaults" if selected == "" else "named_defaults"] += 1
    if counts:
        assert wire["effort"] == (row.watch_effort or "N/A"), "visible effort changed"
        assert wire["model"] == (row.watch_model or "N/A"), "visible model changed"
    return counts


def observe_pinned_detail(get, cookie, session_id, row, snapshot):
    def detail(**value):
        return get("/api/detail", value=value, cookie=cookie)[0]
    token = detail(action="open", session_id=session_id, mode="snapshot")["token"]
    deadline = time.monotonic() + 60
    try:
        while time.monotonic() < deadline:
            page = detail(action="begin", token=token, offset=2**52)
            if page.get("result"):
                break
            time.sleep(.25)
        else:
            raise RuntimeError("probe_pinned_effort_detail_unobserved")
        while time.monotonic() < deadline:
            assert page["state"] == "observed" and page["result"]["source"]["status"] == "acquired", "partial detail"
            rows = page["result"]["view"]["prompt_blocks"][0]["rows"]
            observed = next((value for value in rows if value["event_id"] == row.event_id), None)
            if observed is not None:
                assert not observed["retained"], "retained detail"
                wire = dict(prompt=observed, model=observed["watch_model"], effort=observed["watch_effort"])
                counts = check_row(session_id, row, wire, snapshot)
                assert counts["default_requests"], "pinned default not matched"
                return counts
            offset = page["offset"] + len(rows)
            if not rows or offset >= page["total"]:
                break
            page = detail(action="chunk", token=token, offset=offset, revision=page["revision"])
        raise RuntimeError("probe_pinned_effort_event_unobserved")
    finally:
        detail(action="close", token=token)


def observe_effort_tooltips(get, cookie, owner):
    deadline = time.monotonic() + 90
    raced = 0
    coverage = {}
    inspected = Counter()
    while time.monotonic() < deadline:
        state, _ = get("/api/live", cookie=cookie)
        view = (state["values"].get("live") or {}).get("view") or {}
        for card in view.get("active_cards", []):
            entry = owner.coordinator.cards.sessions.get(card["session_id"])
            if entry is None or card["state"] != "observed":
                continue
            capture, snapshot, revision, generation = entry.capture, entry.snapshot, entry.revision, entry.generation
            if (capture is None or snapshot is None or capture.retained or not capture.authoritative
                    or entry.verified_generation != generation or snapshot.source_revision != revision
                    or card["observed_at_ms"] != capture.observed_at_ms):
                continue
            latest, _ = get("/api/live", cookie=cookie)
            current = next((item for item in latest["values"]["live"]["view"]["active_cards"]
                if item["session_id"] == card["session_id"] and item["focal_id"] == card["focal_id"]), None)
            if (entry.capture is not capture or entry.snapshot is not snapshot or entry.revision != revision
                    or entry.generation != generation or current != card):
                raced += 1
                continue
            inspected["eligible_captures"] += 1
            counts = Counter()
            before = tuple(item.variant for item in snapshot.invocations)
            for wire in card["rows"]:
                row = next((value for value in capture.rows if value.event_id == wire["prompt"]["event_id"]), None)
                if row is not None:
                    result = check_row(card["session_id"], row, wire, snapshot)
                    counts.update(result)
                    coverage[card["session_id"], row.event_id] = result
            assert before == tuple(item.variant for item in snapshot.invocations), "recorded variant changed"
            if counts["default_requests"]:
                print(json.dumps(dict(effort_tooltips="PASS", scope="matched_active_requests_only",
                    **counts, raced_samples_discarded=raced, history_state=view.get("history_state"),
                    full_history_certified=False, model_calls_started_by_probe=0)))
                return
            for row in capture.rows:
                metadata, invocations = matching_requests(card["session_id"], row, snapshot)
                selected = metadata.get("variant", "")
                if selected is None or selected and selected.lower() != "default":
                    inspected["nonfocal_explicit_requests"] += len(invocations)
                    continue
                inspected["nonfocal_default_requests"] += len(invocations)
                supported = [item for item in invocations if expected_default(item) is not None]
                if not supported:
                    inspected["defaults_outside_oracle"] += len(invocations)
                    continue
                print(json.dumps(dict(effort_candidate="recorded_session", **inspected,
                    evidence_source=expected_default(supported[0])[1])))
                result = observe_pinned_detail(get, cookie, card["session_id"], row, snapshot)
                print(json.dumps(dict(effort_tooltips="PASS", scope="matched_recorded_session_detail",
                    **result, **inspected, full_history_certified=False, model_calls_started_by_probe=0)))
                return
        if inspected["eligible_captures"]:
            break  # Diagnose this discovered evidence, not wait for different traffic.
        time.sleep(.25)
    print(json.dumps(dict(effort_tooltips="unobserved", scope="matched_active_requests_only",
        **sum(coverage.values(), Counter()), raced_samples_discarded=raced,
        **inspected, full_history_certified=False)))
    raise RuntimeError("probe_no_matched_default_request")
