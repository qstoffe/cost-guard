"""Allowlist shared current/recent card facts; never serialize a Live DTO."""
from itertools import chain, islice

from src.cache.display_watch import WATCH_ROW_LIMIT, WatchFact, WatchObservation
from .contracts import record
from .display import with_display


def _label(value, limit=1024):
    if value:
        data = value.encode("utf-8")
        return value if len(data) <= limit else data[:limit - 3].decode("utf-8", errors="ignore") + "…"
    return None


def _outcome(prompt, *, verified):
    if prompt.in_progress:
        return "running" if verified and not prompt.execution_unverified else "unverified"
    if prompt.execution_unverified:
        return "unverified"
    if prompt.watch_error:
        return "failed"
    if prompt.aborted:
        return "aborted"
    if prompt.completed_successfully:
        return "finished"
    return "unknown"


def _card_fact(card, group):
    row = next((row for row in card.rows if row.prompt.event_id == card.focal_id), None)
    row = row or next(iter(card.rows), None)
    prompt = row.prompt if row is not None else None
    cost = card.session_cost
    prompt_cost = None
    if prompt is not None and (not prompt.unresolved_cost or
            prompt.comparison_cost is not None and prompt.comparison_cost.priced_requests):
        prompt_cost = prompt.ccost
    session_cost = None
    if cost is not None and (cost.total.complete or cost.total.priced_requests):
        session_cost = cost.total.known_ccost
    verified = group == "active" and card.observed_at_ms is not None and (
        card.invocation_verified is True or card.invocation_verified is None and card.state == "observed")
    outcome = _outcome(prompt, verified=verified) if prompt else None
    finish = prompt.completed_at_ms if outcome in {"finished", "failed", "aborted"} else None
    return WatchFact(
        card.session_id, prompt.event_id if prompt else "", _label(card.title) or card.session_id, group,
        (prompt.at_ms or None) if prompt else None, finish, outcome,
        prompt_cost, bool(prompt and not prompt.unresolved_cost),
        session_cost, bool(cost and cost.source_complete and cost.total.complete),
        card.session_context.tokens if card.session_context is not None else None,
        _label(row.prompt.watch_model or row.prompt.model_effort) if row else None,
        _label(prompt.watch_effort) if prompt else None,
        prompt.calls if prompt else None, card.session_duration_ms if not (prompt and prompt.in_progress) else None,
        card.observed_at_ms if verified else None,
    )


def archive_watch_observation(frame, observed_ms):
    if type(observed_ms) is not int or not 0 < observed_ms <= frame.now_ms:
        return None
    groups = (("active", frame.active_cards), ("recent", frame.recent_finished_cards),
              ("history", frame.history_cards), ("earlier", frame.earlier_cards))
    candidates = tuple(islice(chain.from_iterable(((kind, card) for card in cards) for kind, cards in groups),
                              WATCH_ROW_LIMIT + 1))
    indexed = {}
    for group, card in candidates[:WATCH_ROW_LIMIT]:
        if card.session_id:
            fact = _card_fact(card, group)
            indexed.setdefault((fact.session_id, fact.event_id), fact)
    rich_sessions = {fact.session_id for fact in indexed.values()}
    for preview in islice(frame.earlier_previews, max(0, WATCH_ROW_LIMIT - len(candidates))):
        if preview.session_id and preview.session_id not in rich_sessions:
            indexed.setdefault((preview.session_id, ""), WatchFact(
                preview.session_id, "", _label(preview.title) or preview.session_id, "earlier",
                None, preview.activity_ms if preview.activity_origin == "finish" else None, None,
                None, False, preview.total_ccost, preview.complete, None, None, None, None, None, None))
    if frame.cards_state != "observed" and not any(fact.event_id or fact.session_cost is not None for fact in indexed.values()):
        return None  # A placeholder-only turn is not evidence against the warm snapshot.
    return WatchObservation(observed_ms, frame.now_ms, frame.cards_state, len(candidates) > WATCH_ROW_LIMIT or
                            len(candidates) + len(frame.earlier_previews) > WATCH_ROW_LIMIT, tuple(indexed.values()))


def cached_watch_view(value, timezone_id):
    """Shape the same typed facts for both existing renderers; no Live DTO input."""
    cards = {key: [] for key in ("active", "history", "recent", "earlier")}
    previews = []
    projected_ms = value.get("projected_ms")
    uncertain_running = False
    for fact in value["cards"]:
        identity = dict(session_id=fact["session_id"], title=fact["title"])
        cost = fact["session_cost"]
        if not fact["event_id"]:
            previews.append(record(**identity, activity_ms=fact["finish_ms"],
                activity_origin="finish" if fact["finish_ms"] is not None else None, total_ccost=cost,
                comparison_cost_complete=fact["session_cost_complete"], total_state="retained" if cost is not None else "pending"))
            continue
        outcome = fact["outcome"]
        running = outcome == "running"
        unverified = outcome == "unverified"
        uncertain_running |= fact["group"] == "active" and (unverified or outcome == "unknown")
        duration = max(0, projected_ms - fact["start_ms"]) if running and fact["start_ms"] else None
        prompt = record(event_id=fact["event_id"], at_ms=fact["start_ms"], completed_at_ms=fact["finish_ms"],
            outcome_unknown=outcome == "unknown",
            in_progress=running, execution_unverified=unverified, completed_successfully=outcome == "finished",
            has_error=outcome == "failed", aborted=outcome == "aborted", calls=fact["calls"],
            ccost=fact["prompt_cost"], unresolved_cost=not fact["prompt_cost_complete"], label="Prompt")
        context = record(watch_next_context_tokens=fact["context_tokens"], context_scope=value["binding"],
                         context_epoch=value["archive_epoch"])
        session = record(state="as-of" if cost is not None else "pending", context=context,
            duration_ms=fact["duration_ms"], cost=record(known_ccost=cost, complete=fact["session_cost_complete"],
                                                         mini_session_cost=True) if cost is not None else None)
        state = "observed" if running else "retained" if unverified else "observed"
        group = "earlier" if unverified or outcome == "unknown" else fact["group"]
        cards[group].append(record(**identity, focal_id=fact["event_id"], session_summary=session,
            state=state, observed_at_ms=value["observed_ms"], activity_scope=value["binding"], invocation_verified=False,
            rows=(record(prompt=prompt, model=fact["model"], effort=fact["effort"], watch_duration_ms=duration),)))
    complete = value["state"] == "observed" and not value["truncated"] and not uncertain_running
    view = record(source_label=value["binding"], now_ms=projected_ms, timezone_id=timezone_id,
        cards_state="observed" if complete else "partial",
        history_state="retained" if cards["history"] else "unknown",
        active_cards=tuple(cards["active"]), history_cards=tuple(cards["history"]),
        earlier_cards=tuple(cards["earlier"] + cards["history"]), recent_finished_cards=tuple(cards["recent"]),
        earlier_previews=tuple(previews), daily_state="pending", quota_stale=True)
    return with_display(view, timezone_id, projected_ms).to_json()
