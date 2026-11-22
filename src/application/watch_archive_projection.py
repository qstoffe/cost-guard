"""Allowlist persisted current/recent card facts; never persist a Live DTO."""
from itertools import chain, islice

from src.analysis.timezones import local_day_start_ms
from src.cache.display_watch import WATCH_ROW_LIMIT, WatchFact, WatchObservation
from src.cache.display_watch_daily import WatchDaily
from .contracts import record
from .display import with_display
from .live_projection import project_live
from .watch_native_quota import present_native_quotas


_CARD_GROUPS = ("active_cards", "history_cards", "recent_finished_cards", "earlier_cards")
_ABORT_REASONS = frozenset({"quota_limit", "rate_limit", "tool_call_limit", "step_limit", "user"})


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
    mix = prompt.token_mix_percent if prompt and prompt.token_mix_percent else (None,) * 4
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
        prompt_number=prompt.prompt_number if prompt else None,
        prompt_duration_ms=prompt.duration_ms if outcome in {"running", "finished", "aborted", "failed"} else None,
        is_compaction=prompt.is_compaction if prompt else None,
        incoming_context_tokens=prompt.incoming_context_tokens if prompt else None,
        context_delta_tokens=prompt.watch_delta_context_tokens if outcome == "running" else None,
        mix_input=mix[0], mix_read=mix[1], mix_write=mix[2], mix_output=mix[3],
        abort_reason=prompt.abort_reason if outcome == "aborted" and prompt.abort_reason in _ABORT_REASONS else None,
    )


def _daily_fact(value, timezone_id, now_ms):
    if value is None or not 0 < value.day_start_ms <= value.observed_at_ms <= now_ms:
        return None
    start = local_day_start_ms(timezone_id, now_ms=now_ms)
    if start != value.day_start_ms:
        return None
    end = local_day_start_ms(timezone_id, now_ms=now_ms, days_ago=-1)
    total = value.total
    return WatchDaily(timezone_id, start, end, value.observed_at_ms,
                      total.known_ccost if total.priced_requests or total.complete else None,
                      total.complete, value.prompt_count, value.prompt_count_complete)


def archive_watch_observation(frame, observed_ms, timezone_id="UTC"):
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
                None, False, preview.total_ccost, preview.complete, None, None, None, None, None, None,
                catalog_activity_ms=preview.activity_ms if preview.activity_origin == "catalog" else None))
    daily = _daily_fact(frame.daily_usage, timezone_id, frame.now_ms)
    has_cards = frame.cards_state == "observed" or any(
        fact.event_id or fact.session_cost is not None for fact in indexed.values())
    if not has_cards and daily is None:
        return None
    # A daily-only update must not freshen the prior card membership or its clock.
    return WatchObservation(observed_ms, frame.now_ms, frame.cards_state, len(candidates) > WATCH_ROW_LIMIT or
                            len(candidates) + len(frame.earlier_previews) > WATCH_ROW_LIMIT,
                            tuple(indexed.values()) if has_cards else None, daily)


def with_committed_detail(value, frame, timezone_id):
    """Enrich saved cards from the in-memory frame of that same committed observation.

    Tool, preview and cost-breakdown detail is never persisted. The caller proves
    binding/clear scope; only a current, matching observation may lend its detail.
    SQLite still owns membership, grouping and liveness.
    """
    view = value["view"]
    if frame is None or value["freshness"] != "current" or value["projected_ms"] != frame.now_ms:
        return view
    settled = {(fact["session_id"], fact["event_id"]) for fact in value["cards"]
               if fact["outcome"] in ("running", "finished", "failed", "aborted")}
    live = project_live(frame, timezone_id).to_json()
    details = {}
    for group in _CARD_GROUPS:
        for card in live.get(group) or ():
            events = [row["prompt"]["event_id"] for row in card["rows"]]
            if events:
                # Same focal-or-first choice as the persisted fact.
                event = card["focal_id"] if card["focal_id"] in events else events[0]
                details.setdefault((card["session_id"], event), card)

    def enrich(saved):
        key = saved["session_id"], saved["focal_id"]
        detail = details.get(key) if key in settled else None
        # The saved fact remains the card identity, with or without detail.
        return saved if detail is None else {**detail, "focal_id": saved["focal_id"],
            "activity_scope": saved["activity_scope"], "live_detail": True}

    return {**view, **{group: [enrich(card) for card in view[group]] for group in _CARD_GROUPS}}


def cached_watch_view(value, timezone_id, *, quotas=None, now_ms=None):
    """Shape the same typed facts for both existing renderers; no Live DTO input."""
    cards = {key: [] for key in ("active", "history", "recent", "earlier")}
    previews = []
    projected_ms = value.get("projected_ms")
    uncertain_running = False
    for fact in value["cards"]:
        identity = dict(session_id=fact["session_id"], title=fact["title"])
        cost = fact["session_cost"]
        if not fact["event_id"]:
            finished = fact["finish_ms"]
            catalog = fact["catalog_activity_ms"]
            origin = "finish" if finished is not None else "catalog" if catalog is not None else None
            previews.append(record(**identity, activity_ms=finished if finished is not None else catalog,
                activity_origin=origin, total_ccost=cost,
                comparison_cost_complete=fact["session_cost_complete"], total_state="retained" if cost is not None else "pending"))
            continue
        outcome = fact["outcome"]
        running = outcome == "running"
        unverified = outcome == "unverified"
        uncertain_running |= fact["group"] == "active" and (unverified or outcome == "unknown")
        mix = tuple(fact[key] for key in ("mix_input", "mix_read", "mix_write", "mix_output"))
        is_compaction = fact["is_compaction"]
        prompt = record(event_id=fact["event_id"], at_ms=fact["start_ms"], completed_at_ms=fact["finish_ms"],
            outcome_unknown=outcome == "unknown",
            in_progress=running, execution_unverified=unverified, completed_successfully=outcome == "finished",
            has_error=outcome == "failed", aborted=outcome == "aborted", calls=fact["calls"],
            ccost=fact["prompt_cost"], unresolved_cost=not fact["prompt_cost_complete"],
            label="Compaction" if is_compaction else "Prompt", is_compaction=is_compaction,
            prompt_number=fact["prompt_number"], incoming_context_tokens=fact["incoming_context_tokens"],
            token_mix_percent=mix if all(part is not None for part in mix) else None,
            abort_reason=fact["abort_reason"])
        context = record(watch_next_context_tokens=fact["context_tokens"], context_scope=value["binding"],
                         context_epoch=value["archive_epoch"])
        session = record(state="as-of" if cost is not None else "pending", context=context,
            duration_ms=fact["duration_ms"], cost=record(known_ccost=cost, complete=fact["session_cost_complete"],
                                                         mini_session_cost=True) if cost is not None else None)
        state = "observed" if running else "retained" if unverified else "observed"
        group = "earlier" if unverified or outcome == "unknown" else fact["group"]
        cards[group].append(record(**identity, focal_id=fact["event_id"], session_summary=session,
            state=state, observed_at_ms=value["observed_ms"], activity_scope=value["binding"], invocation_verified=False,
            rows=(record(prompt=prompt, model=fact["model"] or "N/A", effort=fact["effort"] or "N/A",
                         watch_duration_ms=fact["prompt_duration_ms"],
                         live_context=record(watch_delta_context_tokens=fact["context_delta_tokens"])),)))
    complete = value["state"] == "observed" and not value["truncated"] and not uncertain_running
    daily = value["daily"]
    daily_usage = None if daily is None else record(day_start_ms=daily["day_start_ms"], day_end_ms=daily["day_end_ms"],
        observed_at_ms=daily["observed_at_ms"], prompt_count=daily["prompt_count"],
        prompt_count_complete=daily["prompt_count_complete"], cached=True,
        total=record(known_ccost=daily["known_ccost"], complete=daily["cost_complete"]))
    view = record(source_label=value["binding"], now_ms=projected_ms, timezone_id=timezone_id,
        cards_state="observed" if complete else "partial",
        history_state="retained" if cards["history"] else "unknown",
        active_cards=tuple(cards["active"]), history_cards=tuple(cards["history"]),
        earlier_cards=tuple(cards["earlier"] + cards["history"]), recent_finished_cards=tuple(cards["recent"]),
        earlier_previews=tuple(previews), daily_usage=daily_usage,
        daily_state="retained" if daily_usage else "pending",
        accounts=present_native_quotas(quotas, now_ms))
    return with_display(view, timezone_id, projected_ms).to_json()
