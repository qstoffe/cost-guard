# FR 000576 completion — 2026-11-04

Implemented in v80.156, with the **Decision Delegate-approved scope/verification
exception below**, not full physical Windows acceptance.

- Three immediately-saving dropdowns: Theme, CCost display, Mini Watch placement.
  Each has Default (current canonical default) first, then two explicit choices.
  Symbolic `default` persists without snapshotting today's value; explicit values
  equal to defaults stay explicit. Missing user overrides never create a file.
- Canonical config resolves choices before consumers and preserves legacy `webTheme`
  precedence, including nested Default bypass. API separately exposes effective values,
  choices and shipped defaults. Narrow authenticated/CSRF-protected JSONC writes retain
  unrelated bytes, legacy keys and CLI behavior; failed saves roll back intent/focus.
- Mini defaults to Remember last, permitting browser-native position/size reuse in
  the same live opener/server. Standard requests initial placement every time. First
  opening, reload/new opener or host restart requests 560×250 DIPs and initial placement.
  Mode persists; geometry/On state do not. No geometry editor, storage, native positioning,
  forced current-window resize, extra connection or acquisition was introduced.

## Actual verification

- Local Full: **140 bounded units, zero failures, 1659 passes/one standard macOS
  shell-platform skip, 83.4s**. Working-tree validator: **11 passes/zero failures,
  six existing advisory prose/Python warnings**. No weakened assertions/caps/dependencies.
- Actual hidden Chrome156.0.8078.80 / Edge156.0.4314.58, emulated scale1.5: real Document
  PiP native CDP move+resize, app close and Window.close/pagehide, remembered bounds,
  Standard resets, unchanged open window on mode switch, actual Python subprocess
  restart in the same browser profile/disposable settings directory, opener reload,
  persisted explicit mode and Theme/CCost, three real selects, empty browser storage,
  live Theme/USD, single SSE, existing tables/layout/keyboard/scroll/host-stop behavior.
- Read-only installed V2 Watch: one owner/two streams/three accounts, active/history
  cards, clean owned shutdown. One history-read error/Daily unpublished: not a Daily
  or full-history PASS. Shared OpenCode/running Web Beta untouched; no inference.
- Current guides, architecture overview/module and code map updated in place. Journal
  updated with evidence/limits; no additional architecture owner/flow was introduced.

Evidence and precise qualifications: [Mini journal](../../../journal/web/mini-watch.md),
[per-unit report](../../../architecture/governance/verification/mini-placement/full-tests.json),
[Chrome](../../../architecture/governance/verification/mini-placement/chrome-placement.json),
[Edge](../../../architecture/governance/verification/mini-placement/edge-placement.json).

## Explicit exception and remaining uncertainty

**Decision Delegate, 2026-11-04, FR 000576 only** authorized proceeding without fresh
physical Windows150% manual move/resize, native-X clicking, native frame/display-edge
or monitor/work-area-change verification. It accepted per-live-opener/server memory:
reload/navigation/new tabs start standard, with no server-wide cross-opener retention.
Reason: adequate actual hidden browser API/cache evidence; further physical reassurance
does not justify desktop disruption or unsupported geometry workarounds.

CDP is not manual dragging; Window.close/pagehide is not a physical X click. The reload
test proves the application's explicit reset, not independent native-cache clearing.
Physical DPI/native interactions, monitor transitions and untested browsers/platforms
remain **UNVERIFIED**. No visible probe ran or desktop permission was granted. Historical
native geometry is not fresh proof. No functional failing tests, security/Git protections,
other requirements or future FRs were waived. No owner question/On Hold was needed.

Product metadata/date/history/README updated. Current main remains the distribution;
no ZIP, tag or GitHub Release. Maintenance progress advances only when this PR merges.
