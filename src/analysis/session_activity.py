"""Prompt-event clocks over one acquired tree, independent of modification clocks."""
from collections import defaultdict

from src.domain import EventKind, MessageRole
from src.domain.models import OngoingStatus
from src.domain.session_tree import root_by_session

from .child_activity import descendant_activity, running_tool
from .child_links import OPEN_END, ChildLinkIndex
from .prompt_index import prompt_owners

KINDS = {EventKind.USER_PROMPT, EventKind.SUBTASK, EventKind.COMPACTION}


def source_identity(provenance):
    return provenance.source_type, provenance.source_generation, provenance.source_instance


def _prompt_keys(messages, owners):
    return {(message.session_id, owners.get((message.session_id,
        message.parent_message_id if message.role is MessageRole.ASSISTANT else message.message_id)))
        for message in messages}


def _observed_ends(snapshot, children, events, attempts, owners, unsettled, ended_attempts):
    """Match end evidence to its own root turn, never to the next turn in history."""
    background_by_owner = defaultdict(list)
    for work in snapshot.background:
        background_by_owner[work.session_id, work.owner_message_id].append(work)
    for event in events:
        key = event.session_id, event.event_id
        if key in unsettled:
            continue
        own = attempts[key]
        # A child or job may finish between requests of a root continuation.
        # If the root has issued a request, its own end must be observed too.
        if key not in ended_attempts and any(message.role is MessageRole.ASSISTANT for message in own):
            continue
        scopes = children.scopes(own)
        if scopes and any(descendant_activity(snapshot, children, scopes)):
            continue
        linked = children.messages(scopes)
        child_keys = _prompt_keys(linked, owners)
        background = [work for message in (*own, *linked)
                      for work in background_by_owner.get((message.session_id, message.message_id), ())]
        if (not (child_keys & unsettled) and not any(work.running for work in background)
                and (key in ended_attempts or child_keys & ended_attempts or background)):
            yield event.created_at_ms, event.event_id


def _terminal_outcomes(prompts, root_id):
    return {(record.prompt_time_ms, record.prompt_id):
            ('aborted' if record.aborted else 'completed' if record.completed_successfully else None)
            for record in prompts if record.session_id == root_id and not record.execution_unverified
            and not record.in_progress}


def _ongoing(snapshot, children, event, messages, running, *, newest, child_candidates):
    """Use owned jobs/continuations without turning dormant time into execution."""
    if newest and running and snapshot.root.active is True:
        return OngoingStatus('running')
    if not (snapshot.background or snapshot.continuations):
        if running or (child_candidates and descendant_activity(snapshot, children, children.scopes(messages))[0]):
            return OngoingStatus('running')
        return None
    scopes = children.scopes(messages)
    if (running and any(running_tool(message, foreground_only=True) for message in messages)) or (
            child_candidates and descendant_activity(snapshot, children, scopes, foreground_only=True)[0]):
        return OngoingStatus('running')
    owned = {(message.session_id, message.message_id)
             for message in (*messages, *children.messages(scopes))}
    job = next((job for job in snapshot.background if job.running and job.registry_verified
                and (job.session_id, job.owner_message_id) in owned), None)
    if job is not None:
        kind = 'shell' if job.kind in ('shell', 'bash', 'functions.shell', 'functions.bash') else 'job'
        awaits = f'A descendant {kind}' if job.session_id != event.session_id else f'A background {kind}'
        return OngoingStatus('background', awaits=awaits)
    if running or (child_candidates and descendant_activity(snapshot, children, scopes)[0]):
        return OngoingStatus('running')
    if newest:
        continuations = [item for item in snapshot.continuations or () if (
            item.session_id == event.session_id and event.created_at_ms <= item.created_ms or any(
                item.session_id == scope.session_id and scope.invocation_end_ms == OPEN_END
                and scope.start_ms <= item.created_ms < scope.end_ms
                and not any(child.session_id == scope.session_id and child.kind in KINDS
                            and item.created_ms < child.created_at_ms < scope.end_ms
                            for child in snapshot.events)
                for scope in scopes))]
        if continuations:
            first = min(continuations, key=lambda item: (item.wake_at_ms is None, item.wake_at_ms or 0))
            return OngoingStatus('waiting', first.wake_at_ms, first.awaits)
    return None


def activity_fields(item, *, on_activity=None, on_prompt_ends=None):
    """Focal root prompt start while running, explicit causal end when finished.

    A catalog touch, part rewrite, polling time, and inferred inactivity are not
    prompt events. Child work uses the same bounded causal windows as accounting;
    a later independent turn in a reused child is not the root's activity.
    """
    snapshot = item.snapshot
    if (snapshot is None or snapshot.root.provenance != item.session.provenance
            or snapshot.source_revision != item.bundle.source_revision):
        return dict(last_activity_ms=None, activity_qualified=False, running=False,
                    activity_prompt_id="", prompt_started_ms=None, activity_latest_ms=None)
    identity = source_identity(snapshot.root.provenance)
    mapping = root_by_session(tuple(session for session in snapshot.sessions
                                   if source_identity(session.provenance) == identity))
    messages = [message for message in snapshot.messages
                if source_identity(message.provenance) == identity
                and mapping.get(message.session_id) == snapshot.root.session_id]
    root_messages = [message for message in messages if message.session_id == snapshot.root.session_id]
    children = ChildLinkIndex(snapshot)
    scopes = children.scopes(root_messages)
    child_messages = children.messages(scopes)
    allowed_messages = {(message.session_id, message.message_id)
                        for message in (*root_messages, *child_messages)}
    events = {(event.session_id, event.event_id): event for event in snapshot.events
        if event.kind in KINDS and source_identity(event.provenance) == identity
        and mapping.get(event.session_id) == snapshot.root.session_id and (
            event.session_id == snapshot.root.session_id or any(
                event.session_id == scope.session_id and scope.start_ms <= event.created_at_ms < scope.end_ms
                or event.session_id == scope.session_id and event.event_id == scope.owner_id
                for scope in scopes))}
    owners = prompt_owners(snapshot)
    owners.update({key: key[1] for key, event in events.items() if event.kind is EventKind.COMPACTION})
    attempts = defaultdict(list)
    for message in messages:
        if (message.session_id, message.message_id) not in allowed_messages:
            continue
        parent = message.parent_message_id if message.role is MessageRole.ASSISTANT else message.message_id
        owner = owners.get((message.session_id, parent))
        if (message.session_id, owner) in events:
            attempts[message.session_id, owner].append(message)
    running = {(record.session_id, record.prompt_id) for record in item.bundle.prompts
               if record.in_progress and not record.execution_unverified}
    running.update((record.session_id, record.user_message_id) for record in item.bundle.compactions
                   if record.in_progress)
    unsettled = {(record.session_id, record.prompt_id) for record in item.bundle.prompts
                  if record.in_progress or record.execution_unverified}
    unsettled.update((record.session_id, record.user_message_id) for record in item.bundle.compactions
                     if record.in_progress)
    values, terminals, ended_attempts = [], {}, set()
    for key, event in events.items():
        start = event.created_at_ms
        if type(start) is not int or start <= 0:
            continue
        values.append(start)
        latest = max(attempts[key], key=lambda message: (message.created_at_ms, message.message_id), default=None)
        if latest is None or key in unsettled:
            continue
        # Completion belongs to the actual attempt, not its mutable parts or the
        # last request of a still-unfinished tool-calls continuation.
        terminal = (latest.termination.completed_at_ms if latest.termination else
                    latest.completed_at_ms if latest.finish_reason not in (None, "tool-calls") or latest.error_name else None)
        if latest.termination or latest.error_name or terminal is not None:
            ended_attempts.add(key)
        if type(terminal) is int and terminal >= start:
            values.append(terminal)
            terminals[key] = terminal
    root_events = sorted((event for event in events.values() if event.session_id == snapshot.root.session_id),
                         key=lambda event: (event.created_at_ms, event.event_id), reverse=True)
    has_live_children = any(session.active is True for session in snapshot.sessions
                            if session.session_id != snapshot.root.session_id) or any(
        session_id != snapshot.root.session_id for session_id, _ in running)
    live = ongoing = waiting = None
    for event in root_events:
        key = event.session_id, event.event_id
        status = _ongoing(snapshot, children, event, attempts[key], key in running,
                          newest=event is root_events[0], child_candidates=has_live_children)
        if status is None:
            continue
        if status.phase == 'waiting':
            waiting = status
        else:
            live, ongoing = event, status
            break
    if live is None and waiting is not None:
        live, ongoing = root_events[0], waiting
    outcomes = (_terminal_outcomes(item.bundle.prompts, snapshot.root.session_id)
                if snapshot.continuations is None or on_prompt_ends is not None else {})
    if on_prompt_ends is not None and snapshot.complete and live is None:
        on_prompt_ends({key: outcomes.get(key) for key in
                        _observed_ends(snapshot, children, root_events, attempts, owners, unsettled, ended_attempts)
                        if snapshot.continuations is not None or outcomes.get(key) == 'aborted'})
    focal = live or (root_events[0] if root_events else None)
    start = focal.created_at_ms if focal is not None else None
    if type(start) is not int or start <= 0:
        if on_activity is not None:
            on_activity(values, snapshot.complete)
        return dict(last_activity_ms=None, activity_qualified=snapshot.complete, running=False,
                    activity_prompt_id="", prompt_started_ms=None, activity_latest_ms=max(values, default=None))
    key = focal.session_id, focal.event_id
    is_running = bool(live)
    # Scope child finishes to this root prompt, not the latest activity anywhere
    # in the tree. A reused child's independent turn cannot advance this clock.
    focal_children = children.messages(children.scopes(attempts[key]))
    child_keys = _prompt_keys(focal_children, owners)
    terminal = terminals.get(key)
    if (terminal is not None and not is_running and not (child_keys & unsettled)
            and (snapshot.continuations is not None or outcomes.get((start, focal.event_id)) == 'aborted')):
        message_ids = {(message.session_id, message.message_id) for message in (*attempts[key], *focal_children)}
        background = [work for work in snapshot.background
                      if (work.session_id, work.owner_message_id) in message_ids]
        ends = [terminal, *(terminals[child] for child in child_keys if child in terminals)]
        ends.extend(work.ended_at_ms for work in background
                    if type(work.ended_at_ms) is int and work.ended_at_ms >= start)
        terminal = None if any(work.running or work.ended_at_ms is None for work in background) else max(ends)
    else:
        terminal = None
    if terminal is not None:
        values.append(terminal)
    if on_activity is not None:
        on_activity(values, snapshot.complete)
    return dict(last_activity_ms=start if is_running else terminal, activity_qualified=snapshot.complete,
                running=is_running, activity_prompt_id=focal.event_id, prompt_started_ms=start,
                activity_latest_ms=max(values, default=None), ongoing=ongoing)
