"""Project source-backed page epochs under the SessionCatalog owner lock."""
from collections import OrderedDict
from heapq import nsmallest
from uuid import uuid4

from src.analysis.metric_evidence import EMPTY_HISTORY

from .session_archive import session_view
from .session_arrivals import ARRIVAL_SECONDS, recent_live_roots
from .session_catalog_scope import (
    CatalogEpoch, PAGE_SIZE, catalog_window, event_members, in_window,
    live_activity_order, provisional_order, retained_positions,
)
from .session_navigation import Navigation
from .session_row_sort import sort_value


ARRIVAL_SLOTS = 5


def ordered(rows, key, direction, recent_finishes=None):
    # Stable value sorting preserves ascending IDs for ties in either direction.
    # Extract each value once; unknown values stay last, including descending.
    running, finishing, known, unknown = [], [], [], []
    for row in sorted(rows, key=lambda row: row.session_id):
        if row.running and type(row.prompt_started_ms) is int and row.prompt_started_ms > 0:
            running.append(row)
            continue
        if recent_finishes and row.session_id in recent_finishes:
            finishing.append(row)
            continue
        value = sort_value(row, key)
        if value is None:
            unknown.append(row)
        else:
            known.append((value, row))
    known.sort(key=lambda item: item[0], reverse=direction == -1)
    running.sort(key=lambda row: -row.prompt_started_ms)
    if finishing:
        finishing.sort(key=lambda row: -recent_finishes[row.session_id])
    return tuple(running) + tuple(finishing) + tuple(row for _, row in known) + tuple(unknown)


def _progress(catalog, sort, pending, selected, indexed, pinned, candidates, *, scope):
    keys = candidates if pending or scope else tuple(row.session_id for row in selected)
    completed = indexed if pending or scope else sum(catalog._current(key) for key in keys)
    waiting = [key for key in keys if key in catalog.failures]
    failed = [key for key in waiting if catalog.failures[key][1]]
    reason = ('source_unavailable' if catalog.state == 'source_unavailable' else
              catalog.index_failure if catalog.index_unavailable else
              catalog.failure_reasons.get((failed or waiting)[0], 'source_key_unavailable') if waiting else None)
    terminal = bool(failed) or catalog.index_terminal
    more = pending or completed < len(keys)
    work = dict(catalog.work) if catalog.work else dict(
        active=False, sequence=catalog.work_sequence,
        stage='waiting_retry' if waiting else 'queued' if more else 'ready')
    return dict(generation=catalog.generation, phase='index' if pending else 'page',
                status='failed' if terminal else 'pending' if reason or more else 'ready',
                retryable=not terminal, completed=completed, total=len(keys), reason=reason,
                failed=len(failed), waiting=len(waiting), pinned=pinned, metrics=dict(catalog.metrics),
                revalidating=sum(key in catalog.rows and not catalog._key_current(key, sort) for key in keys),
                work=work)


def epoch_page(self, pages, *, token, offset, sort, direction, epoch, period, navigation,
               applied, cancelled, passive):
    # An epoch names an order independently of the slice, including
    # page one. Passive page-one reads use it only as a fallback.
    pinned = bool(offset or epoch and not passive)
    pages.expire(self.clock)
    if token is None:
        if pinned:
            raise KeyError('catalog_expired')
        if len(pages.leases) >= 32:
            raise RuntimeError("catalog_busy")
        token = uuid4().hex
        pages.leases[token] = dict(touched=self.clock(), epochs=OrderedDict())
    lease = pages.leases.get(token)
    if lease is None:
        raise KeyError("catalog_expired")
    lease["touched"] = self.clock()
    if 'interest_until' in lease:
        lease['interest_until'] = self.clock() + 90
    nav = lease.get('navigation')
    if cancelled is not None:
        lease['navigation_sequence'] = max(cancelled, lease.get('navigation_sequence', 0))
    if nav is not None and cancelled == nav.sequence:
        lease.pop('navigation')
        nav = None
    if nav is not None and applied == nav.sequence and not nav.pending:
        lease.pop('navigation')
        lease['released'] = True
        nav = None
    issued = lease['epochs'].get(epoch)
    page_rows = issued.rows[offset:offset + PAGE_SIZE] if issued else ()
    compatible = (issued is not None and (issued.sort, issued.direction, issued.window.period,
        issued.window.timezone_id) == (sort, direction, period, self.timezone_id)
        and (offset == 0 or bool(page_rows))
        and all(row.session_id in self.roots for row in page_rows))
    current_window = (catalog_window(period, self.timezone_id, self.clock_ms()) if not offset else None)
    if not offset and compatible:
        compatible = issued.window.identity == current_window.identity
    if pinned and (not compatible or not offset and issued.provisional and not issued.browsable_candidates):
        raise KeyError('catalog_expired')
    usable = (self.state == 'observed' and not self.index_unavailable
        and not any(self.failures.get(row.session_id, (None, False))[1] for row in page_rows))
    # Older historical windows may still be displayed, but are not a
    # current-calendar warm hit. A continued action keeps its own facts.
    reuse = bool(pinned and compatible and usable and not issued.provisional and offset in issued.served
        and issued.window.identity == (current_window or catalog_window(
            period, self.timezone_id, self.clock_ms())).identity
        and (navigation is None or nav is None or nav.sequence != navigation))
    # A live candidate epoch already owns the order of these slices.
    # Scalar qualification can improve cells without blocking navigation.
    reuse = reuse or bool(pinned and compatible and issued.browsable_candidates
         and (nav is None or nav.sequence != navigation))
    retained_page = bool(compatible and navigation is None and nav is None
        and self.state == 'source_unavailable')
    reuse = reuse or retained_page
    if not pinned:
        window, candidates = pages.population(self, period)
    if navigation is not None:
        intent = sort, direction, period, offset, epoch if pinned else None
        if nav is None or nav.sequence != navigation:
            if navigation <= lease.get('navigation_sequence', 0):
                raise ValueError('invalid_request')
            lease['navigation_sequence'] = navigation
            if reuse:
                lease.pop('navigation', None)
                lease['released'] = True
                nav = None
            else:
                nav_window = issued.window if pinned else window
                keys = (tuple(row.session_id for row in page_rows) if pinned else candidates)
                previous_period = lease.get('period')
                previous_start = (catalog_window(previous_period, self.timezone_id, window.end_ms - 1).start_ms
                    if previous_period is not None and previous_period != period and not pinned else None)
                nav = Navigation(navigation, intent, nav_window,
                    {key: self.roots[key] for key in keys}, self.last_observation.source_epoch
                    if self.last_observation else None,
                    expanded_period=previous_start is not None and (
                        nav_window.start_ms is None or nav_window.start_ms < previous_start))
                if pinned and issued.facts:
                    nav.facts.update((key, fact) for key, fact in issued.facts if key in nav.roots)
                lease['navigation'] = nav
        elif nav.intent != intent:
            raise ValueError('invalid_request')
        if nav is not None:
            nav.check(self, issued.window if pinned else window)
            nav.capture(self)
            if not pinned:
                window, candidates = nav.window, tuple(nav.roots)
    display_rows = {row.session_id: row for row in self._rows(candidates)} if not pinned else {}
    event_current = lambda key: self._activity_current(key) or self._finish_known(key)
    qualified = lambda key: (not pinned and display_rows[key].running or (
        (sort == 'name' or self._key_current(key, sort))
        and (period == 'all' and sort != 'activity' or self._activity_current(key))
        and (key not in self.active or self._activity_current(key))))
    live_page = passive and navigation is None and nav is None
    if not pinned:
        indexed = sum(qualified(key) for key in candidates)
        pending = indexed != len(candidates)
        if nav is not None and navigation is not None:
            indexed, pending = len(nav.facts), bool(nav.pending)
    if not pinned and not reuse:
        applied = "activity" if pending and not live_page else sort
        order = -1 if pending and not live_page else direction
        cache_key = window.identity, applied, order, pending, live_page
        recent = self.recent_finishes
        members = event_members(candidates, window, display_rows, event_current, recent)
        latest, previous = next(((key, value) for key, value in reversed(lease["epochs"].items())
            if (value.sort, value.direction, value.window.identity) == (applied, order, window.identity)),
            (None, None))
        # An admission hint is not a prompt clock or a final period
        # match. Do not show unqualified out-of-window roots.
        metadata = {key: self.activity.get(key) for key in members
            if in_window(self.activity.get(key), window)}
        if live_page:
            members = tuple(key for key in members if display_rows[key].running or key in recent
                  or event_current(key) or key in metadata or window.period == 'all')
        positions = {}
        arrivals = ()
        if live_page and pending and (sort, direction) != ("activity", -1):
            # Only newly discovered, in-window roots get a temporary
            # tier. Revisions do not renew it. Old unresolved positions
            # remain display-only, never current-key proof.
            arrivals = tuple(nsmallest(ARRIVAL_SLOTS, (key for key in members if key in metadata
                and self.clock() - self.recent_arrivals.get(key, float('-inf')) < ARRIVAL_SECONDS
                 and not display_rows[key].running and key not in recent and not qualified(key)),
                key=lambda key: (-metadata[key], key)))
            if previous:
                allowed = set(members)
                positions = {row.session_id: index for index, row in enumerate(
                    row for row in previous.rows if not row.running and row.session_id not in previous.arrivals)
                    if row.session_id in allowed and not display_rows[row.session_id].running
                    and not qualified(row.session_id) and row.session_id not in arrivals and row.session_id not in recent}
            members = tuple(key for key in members if display_rows[key].running or key in recent or qualified(key))
        signature = (tuple((key, metadata.get(key), display_rows[key], event_current(key))
                            for key in (*members, *positions, *arrivals)), tuple(positions.items()), arrivals,
                     tuple(recent.items()))
        cached = pages.orders.get(cache_key)
        if nav is not None and navigation is not None and not pending:
            rows = ordered(self._with_lifecycle(nav.rows, display_rows), sort, direction, recent)
        elif cached and cached[0] == signature:
            rows = cached[1]
        else:
            rows = ordered((display_rows[key] for key in members), applied, order, recent)
            front = tuple(row for row in rows if row.running or row.session_id in recent)
            tail = tuple(row for row in rows if not row.running and row.session_id not in recent)
            if pending and (applied, order) == ("activity", -1):
                tail = (live_activity_order(tail, metadata, event_current) if live_page else
                        provisional_order(tail, self.activity))
            elif positions:
                tail = retained_positions(tail, positions, display_rows)
            rows = front + tuple(display_rows[key] for key in arrivals) + tail
        pages.orders[cache_key] = signature, rows
        pages.orders.move_to_end(cache_key)
        while len(pages.orders) > 32:
            pages.orders.popitem(last=False)
        if (previous is not None and (previous.sort, previous.direction) == (applied, order)
                and previous.provisional == pending
                and previous.browsable_candidates == (live_page and pending)
                and previous.arrivals == frozenset(arrivals)
                and previous.window.identity == window.identity and tuple(
                row.session_id for row in previous.rows) == tuple(row.session_id for row in rows)
                and (live_page or not previous.facts or previous.rows == rows)):
            epoch = latest
            window = previous.window
        else:
            epoch = uuid4().hex
            facts = tuple(nav.facts.items()) if nav is not None and navigation is not None and not pending else ()
            lease["epochs"][epoch] = CatalogEpoch(rows, applied, order, window, pending, facts,
                browsable_candidates=live_page and pending, arrivals=frozenset(arrivals))
        while len(lease["epochs"]) > 8:
            lease["epochs"].popitem(last=False)
    else:
        rows, applied, order = issued.rows, issued.sort, issued.direction
        window = issued.window
        candidates = tuple(row.session_id for row in (page_rows if reuse else rows))
        indexed = sum(qualified(key) for key in candidates)
        # Published membership/order is independent of live scalar readiness.
        pending = False
    snapshot = lease['epochs'][epoch]
    frozen = not reuse and not live_page and (bool(snapshot.facts)
        or nav is not None and navigation is not None and not pending)
    lease.update(sort=sort, period=period, candidates=candidates, pinned=offset > 0 or snapshot.browsable_candidates and pinned,
                  cohort_verified=not snapshot.provisional)
    selected = rows[offset:offset + PAGE_SIZE]
    lease["visible"] = tuple(row.session_id for row in selected)
    lease["nearby"] = tuple(row.session_id for row in rows[
        offset + PAGE_SIZE:offset + PAGE_SIZE * 3]) if snapshot.browsable_candidates else ()
    pages.last_page = lease['visible']
    # Older pages retain membership/order; only independently observed
    # values may change. Deleted rows retain their epoch evidence.
    if not frozen:
        fresh = {row.session_id: row for row in self._rows(lease['visible'])}
        selected = tuple(fresh.get(row.session_id, row) for row in selected)
    if nav is not None and navigation is not None and pinned:
        selected = tuple(nav.facts[row.session_id][0] if row.session_id in nav.facts else row
                         for row in selected)
    if frozen:
        # Frozen metrics/membership are historical facts, not a license
        # to keep claiming an old prompt is currently executing.
        selected = self._with_lifecycle(selected)
    retained_order = reuse and any(
        old.running != fresh.running or (old.prompt_started_ms != fresh.prompt_started_ms if fresh.running
            else sort_value(old, sort) != sort_value(fresh, sort))
        for old, fresh in zip(page_rows, selected))
    result = session_view(selected, self.timezone_id, self.unit)
    facts = (nav.facts if nav is not None and navigation is not None else {
        key: fact for key, fact in snapshot.facts if key in lease['visible']}) if frozen else {}
    # Reusing the same issued order must not freeze the metadata clock
    # on the live page. Explicitly pinned slices keep their own window.
    metadata_window = current_window if live_page and not pinned else window
    for row, usage in zip(result["session_usage"], selected):
        key = row["session_id"]
        current = key in self.roots and self._current(key)
        row["indexed"] = current
        activity_current = event_current(key)
        hint = self.activity.get(key)
        row["catalog_activity_ms"] = hint if (snapshot.browsable_candidates and not activity_current
            and not row["running"] and in_window(hint, metadata_window)) else None
        row["new_arrival"] = key in snapshot.arrivals
        row["activity_state"] = ('retained' if row["last_activity_ms"] is not None else 'unavailable') if (
            self.state == 'source_unavailable' or self.index_unavailable) else (
                'ready' if activity_current else 'partial' if key in self.rows and not self.rows[key].activity_qualified
                else 'retained' if row["last_activity_ms"] is not None
                 else 'unavailable' if key in self.failures else 'pending')
        if key in self.running_roots and not row["running"]:
            row["activity_state"] = 'unverified'
        row["has_summary"] = key in self.rows or row["prompt_count"] is not None
        unavailable = self.index_unavailable or self.state == "source_unavailable" or key in self.failures or key not in self.roots
        row["metric_state"] = ("retained" if row["has_summary"] else "unavailable") if unavailable else (
            "ready" if current else "retained" if row["has_summary"] else "pending")
        if current and (key in self.active or self.rows[key].running) and self.clock() - self.valid[key][1] > 15:
            row["metric_state"] = "retained"
        # Running and its bound start were qualified before ordering (or
        # captured together in a frozen navigation fact), never upgraded
        # afterward from a boolean Watch hint with no prompt identity.
        row["metric_states"] = {name: row["metric_state"] for name in ("model", "effort", "ccost", "prompts", "duration", "ctx")}
        if current and not self.rows[key].context_qualified:
            row["metric_states"]["ctx"] = "retained" if row["context_tokens"] is not None else "pending"
        if key in self.rows and (key not in self.valid or self.valid[key][0] != self.revisions.get(key)):
            row["metric_states"]["ctx"] = ("retained" if row["context_tokens"] is not None else
                "unavailable" if unavailable else "pending")
        if row["running"] and not unavailable and self.rows.get(key) and self.rows[key].model_pending:
            row["metric_states"]["model"] = "pending"
        if current and not self.rows[key].effort_qualified:
            row["metric_states"]["effort"] = "retained" if self.rows[key].effort_key is not None else "pending"
        if row["running"] and not unavailable and self.rows.get(key) and self.rows[key].effort_pending:
            row["metric_states"]["effort"] = "pending"
        if (usage.empty_history and current and not unavailable and self.state == "observed"
                and key not in self.active and not row["running"]
                and (not frozen or key in facts and facts[key][1] is not None
                     and facts[key][1] == self.revisions.get(key))):
            row["metric_absences"] = dict.fromkeys(("model", "ctx", "activity"), EMPTY_HISTORY)
        if key in facts:
            row['snapshot_revision'] = facts[key][1]
            if facts[key][1] is None:
                # Frozen running order is not proof of current metrics.
                row['snapshot_semantics'] = 'qualified-running-lifecycle; retained-scalars'
                row['indexed'] = False
                row['metric_state'] = 'retained' if row['has_summary'] else 'pending'
                row['metric_states'] = {name: 'retained' if state == 'ready' else state
                    for name, state in row['metric_states'].items()}
                continue
            row['snapshot_semantics'] = 'independently-qualified-navigation-facts'
            row['metric_state'] = 'snapshot'
            row['metric_states'] = dict.fromkeys(row['metric_states'], 'snapshot')
            evidence = facts[key][0]
            if not evidence.context_qualified:
                row['metric_states']['ctx'] = 'retained' if row['context_tokens'] is not None else 'pending'
            if evidence.model_pending:
                row['metric_states']['model'] = 'retained' if row['model'] != 'N/A' else 'pending'
            row['indexed'] = False
    progress = _progress(self, sort, pending, selected, indexed, pinned, candidates,
        scope=not pinned and not reuse and (period != 'all' or sort != 'name'))
    if nav is not None and navigation is not None:
        progress.update(completed=len(nav.facts), total=len(nav.roots),
            phase='page' if pinned else 'index')
        if not nav.pending and not progress['reason']:
            progress['status'] = 'ready'
    if (usable and not snapshot.provisional and not pending
            and (nav is None or navigation is None or not nav.pending)
            and (not offset or reuse or progress['status'] == 'ready')):
        snapshot.remember_page(offset)
    return dict(token=token, epoch=epoch, offset=offset, total=len(rows), size=PAGE_SIZE,
        page_reused=reuse, retained_order=retained_order,
          passive=bool(passive and not offset and navigation is None and nav is None),
         candidate_scope='source_catalog_metadata',
         membership_pending=snapshot.provisional, candidate_navigation=snapshot.browsable_candidates,
         order_state='provisional' if snapshot.provisional else 'verified',
        period=period, window=dict(start_ms=window.start_ms, end_ms=window.end_ms, timezone_id=window.timezone_id),
        sort=applied, direction=order, pending_sort=pending, indexed=indexed,
        available=len(rows) if reuse else len(candidates), state=self.state, view=result,
        requested_sort=sort, requested_direction=direction,
        navigation=navigation, progress=progress,
        age_ms=None if self.observed is None else int(max(0, self.clock() - self.observed) * 1000),
        page_ready=sum(self._current(row.session_id) for row in selected if row.session_id in self.roots))
