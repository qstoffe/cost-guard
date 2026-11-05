# FR 000592 — Watch loading status truth

Implemented and locally verified: v80.172, 2026-11-05. Remote checks and merge
truth are recorded in [PR #178](https://github.com/qstoffe/cost-guard/pull/178).

## Change

- Removed the elapsed-time generic warning from both `app.js` (missing initial
  view) and `watch.js` (independent history/accounts/prompt loading).
- **No running prompts** now requires observed prompt membership on a healthy
  running source/connection. Unknown/loading/partial/retained is not empty success.
- Existing host/source/auth/offline/terminal guidance, component-specific messages,
  keyed DOM, one SSE owner and source/account cadence remain unchanged.
- Preserved the whole specification bundle and advanced ordinary progress to 42.

## Verification

- Baseline headless real DOM reproduced the generic warning after 30 seconds of
  history loading through 180 virtual seconds, with changing calls/duration and
  card arrival. This is causal reproduction, not the owner's original incident.
- Full: 144 files, zero failures, 89.5s; 1,695 passed tests and one existing macOS
  zsh/PTY platform skip. Focused Watch Daily and Web Views regressions also passed.
- Working-tree validator: 11 passing checks, zero failures, six existing advisory
  size warnings. No caps were changed; no release ZIP was generated.
- Edge 156.0.4314.58: six Classic/Web-light/Web-dark × 1366px/360px cases passed,
  including separate three-minute virtual history/accounts/daily/partial delays,
  new cards, counters/durations, selection/focus/scroll and disclosure retention.
- Full app/HTTP/SSE browser probe passed 19 publications across 180.265 wall-clock
  seconds with delayed history, absent accounts and pending Daily, advancing prompt
  counters, card arrival and route changes. Initial missing-view fallback remained
  quiet at three virtual minutes. Source retry/unavailable/recovery, offline/online
  and terminal shutdown retained accurate feedback; one EventSource, zero page errors.
  An earlier run reached the final instrumentation assertion but failed because
  the probe had not enabled the CDP Page domain; explicit enablement repaired the
  harness, and the entire three-minute probe then passed. No product gate was waived.
- Read-only installed V2 probe: one Live owner, two streams, three accounts,
  one active/two history cards, coherent run origin/sequence, joined owned workers,
  shared OpenCode untouched. No model calls initiated. Daily had not published
  and history phase instrumentation recorded an error; no Daily success is claimed.

## Evidence and boundaries

Reusable findings: `development/journal/web/watch-cards.md`; current ownership and
test routes updated in Web architecture/CODE_MAP and `docs/web-beta.md`.
No layer-boundary change. No user/Decision Delegate requirement exceptions.
The integrated browser was disconnected; hidden browsers used fresh owned profiles.
Native desktop/physical input, screen readers, macOS desktop and an end-to-end
capture of the owner's original real-source browser incident are not claimed.
