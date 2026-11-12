# FR 000683 — Scope-limited completion

Product **v81.31**, 2026-11-12; implementation base `c33e761`.
The original FR payload is preserved intact in this bundle. This is **partial
acceptance authorized by Decision Delegate**, not a claim that every interaction
or installation check passed.

## Delivered safety scope

- Shared `ContextHelp` owns one open-hover-only ~1000ms exact-label/panel watchdog,
  preserving 150ms transfer grace and cleaning Popover/ARIA state without any exit
  event. No timer runs while closed or owned by focus/pin.
- A monotonic 30-second lease renewed by trusted pointer interaction bounds even
  stale/inconclusive hover. Polling, focus and Live redraws cannot extend it.
  Stationary mouse reading may expire; keyboard/pinned alternatives have no lease.
- The 600ms opening delay revalidates target/hover/lifetime. Ticket checks isolate
  obsolete callbacks; close, actions, Escape, owner changes and teardown cancel
  owned work. No extra Mini interval, HTTP, host work, component or dependency.

## Actual verification

- Full deterministic: **185 isolated groups, zero failures, 150.9s**.
- Working-tree validation: **11 passes, zero failures**, seven existing advisory
  warnings; no budget/baseline changed.
- Edge **157.0.4341.46**, Chrome **157.0.8103.51** targeted watchdog probe PASS:
  24 theme/zoom/label cases each, actual Document PiP + Full Watch native exits
  intercepted before all handlers, silent opening exits, ~1.15–1.20s dismissal,
  ARIA/Popover cleanup, panel transfer, keyboard/touch/actions and no Live revival.
  Deterministic stale-true/inconclusive hover expires at thirty seconds, with one
  watchdog/zero closed timers and independent documents/owners.
- Broader Edge Mini invocation **FAILED** at the mixed-input Total-heading hover
  case, after 122 layout observations/nine completed groups. Separate
  `manual-only` **PASS**: 25 layouts, Fit, both sizing modes, input dismissal,
  narrow panning, remembered reopen and one SSE. Remaining duration cases after
  the abort and history-readiness subprobe **NOT RUN**.

## Approved exclusions and remaining work

**Decision Delegate**, not the owner, authorizes scope-limited delivery excluding
reliable hover opening for the reproduced mixed touch/keyboard → Total-heading
mouse path, **FAILED in both browsers**. Distinct geometry, realm, observation,
input-setup, fixed-motion and pre-entry compositor experiments did not resolve it.
Render correlation is not proven causation; physical prevalence remains unknown.
The original failing assertion remains intact. The verified orphan protection is
useful independently; tested keyboard/touch alternatives remain, with no identified
accounting/security/data-loss consequence or blocked Ready dependency.

The non-executable, same-PR published [Suggestion 000684](../../suggestions/000684-mini-help-mixed-input-hover-opening/SUGGESTION.md)
retains the exact gap and future acceptance. It has no Ready priority or approval
to execute. This is a substantial separable deferral, not a negligible caveat.

**Decision Delegate minor verification exception:** complete real history
certification and zero-worker teardown proof are excluded for this browser-only
FR. `probe_web_live.py --watch-cards` **FAILED** at its 90s observation bound
(`probe_watch_cards_timeout`, 872/3149 checked). The distinct basic probe also
**FAILED** (`probe_owned_workers_remaining`, two provider waiters). Verified V2,
one owner, advancing publications/stream IDs and two basic streams are positive
observations, **not full-probe PASS**. No owned processes/pending final work or
reported cleanup failures; natural provider-thread retirement remains
**UNVERIFIED**, not established leakage. No source/provider repair is claimed.

Physical Windows PiP → browser chrome → another app pointer travel/native blur
remains **UNVERIFIED under the FR's explicit allowance**. Injected blur is handler
proof only. Original intermittent OS trigger is not claimed reproduced. No visible
desktop action, inference, shared-service stop, ZIP, tag or GitHub Release.

[Journal: exact evidence, limits and decision attribution](../../../journal/web/contextual-help.md#fr-000683-bounded-hover-watchdog-2026-11-12).
Shared-help architecture/code map and user help guide were updated. Maintenance
progress includes the authorized scoped delivery; unrelated deferred learning is
unchanged. Only merged default makes this completion/progress effective.
