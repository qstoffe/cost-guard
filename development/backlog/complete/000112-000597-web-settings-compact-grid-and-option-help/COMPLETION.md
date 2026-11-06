# FR 000597 completion — 2026-11-06

Implemented in v80.181. Settings is an unframed, compact two-column grid with
responsive stacking, no redundant toolbar/panel heading or permanent help prose,
and stable visible read/save/error feedback. All five fields already shipped on the
starting default, including separate Mini position/size, retain their API/storage
and confirmed-only behavior.

Intrinsic labels and current values use shared ContextHelp. Feature-detected
customizable native selects show each hovered/keyboard-focused choice's explanation
beside the list; touch/narrow layouts expose descriptions inside the popup. Native
focus, typeahead, preview/commit, Escape and touch remain browser-owned. Unsupported
browsers keep a functional native select plus an accessible Choice help disclosure.
Default help/labels follow actual shipped defaults without converting explicit choices.

## Verification

- Full: **149 files, zero failures** (91.7s). Working-tree validation: **11 passes,
  zero failures**, six advisory prose/design warnings; no limit raised.
- Actual hidden Chrome 156.0.8078.80 and Edge 156.0.4314.58 passed all 15 native
  option hover previews, no-preview-save, pointer/keyboard commitment, Space/arrows/
  Escape, touch, AX names/descriptions, failed-save rollback/retry, reload, changed
  defaults, route dismissal and feature-disabled native fallback.
- Classic/Web light/Web dark × wide/narrow/mobile widths × CSS zoom 100/200%,
  plus actual disposable-profile browser zoom 200%, retained aligned unclipped rows
  and bounded option help. Inspected the final native picker screenshot.
- Read-only real V2 account-aware HTTP/SSE probe: one owner, two streams, three
  account cards, zero model calls/finite jobs, no owned threads/processes after close;
  shared OpenCode remained running.
- [Evidence and earlier failed attempts](../../../architecture/governance/verification/web-settings-597.json).

The initial short live probe's shutdown assertion failed while a quota request was
pending; it is not PASS. Waiting for account publication in the account-aware probe
provided the successful integration/shutdown evidence. History-phase cancellation
on shutdown is not a claim of full history coverage.

## Documentation and limits

Updated current Settings, quota/cost/Mini navigation docs, shared-help guidance,
Web architecture/code map, journal, version/date presentation and ordinary progress.
No backend/security/storage change or release ZIP. No requirement/test waiver.

Physical OS interaction and a real screen-reader session were not performed; native
AX association was checked. Firefox/Safari were not run. Their native OS option
popups cannot promise per-option hover: Choice help is the documented fallback.
Integrated Review browsing was unavailable; only hidden disposable browsers were used.
