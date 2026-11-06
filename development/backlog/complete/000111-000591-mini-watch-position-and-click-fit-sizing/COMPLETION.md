# FR 000591 — completion, 2026-11-06

Implemented the owner-approved open/click-fit scope in v80.180. The specification
and entire bundle are preserved; the superseded passive Auto-height goal was not
reintroduced. No automatic native resize occurs on Live publications or timers.

## Delivered behavior

- Separate position and size preferences; existing placement choices remain intact.
  The sole new enum/endpoint is `miniWatchSize` / `/api/settings/mini-size`, retaining
  symbolic Default, allowlisting, authenticated CSRF protection and atomic JSONC edits.
- Default opening measures real styled content before requesting approximately 650
  outer DIPs, including all accounts/warnings and two running-row capacity. No dummy
  live rows or post-opening resize. Total height uses a conservative frame allowance
  and min(1000 DIPs, known available screen height); measured native clamps are disclosed.
- One eligible pointer/Enter/Space disclosure adjustment; collapse fits current compact
  content or restores valid remembered pre-expansion bounds. Manual resizing invalidates
  stale restoration. Native width rounding is observed and compensated on later eligible
  clicks, never through extra calls or passive correction. Native clamps can still alter width.
- Natural prompt/account/status height removes premature inner vertical scrollbars.
  Capped/manual/passive overflow uses accessible document scrolling; narrow tables pan
  horizontally. Native position/size coupling is explicit, not promised independent.

## Executed verification

- Local Full: **149 bounded units, zero failures, 93.0s**. Follow-up focused Mini,
  config, settings and Web views: **34 tests passed**, including the new rounding test.
- Working-tree validation: **11 passes, zero failures**, six existing advisory warnings.
- Real strictly headless Chrome 156.0.8078.80: scale 1, scale 1.5, scale 1.5 with
  genuine browser default zoom 125%; Edge 156.0.4314.58: scale 1 and scale 1.5 / genuine zoom 125%.
  **110 recorded layouts across five successful runs**: zero/one/two/four prompts,
  zero/one/three/six accounts, warnings/wrapping, two-row reserve, native pointer/keyboard
  expansion/shrink, repeated toggles without cumulative width drift, remembered-size
  restoration/manual invalidation, missing activation, passive SSE without resizing,
  four position/size intentions, Classic/Web light/dark, 40-row caps and narrow panning.
  Native-clamped cases are separately marked, not reported as full-fit PASS.
- Read-only installed V2: **17 coherent publications**, one running prompt, three
  accounts, four known-finish cards, 9.475s; owned close 0.051s. Shared OpenCode was
  untouched; no inference or real-user settings mutation.

[Measurements, Full report and inspected headless screenshot](../../../architecture/governance/verification/mini-fit/).
[Engineering account and limits](../../../journal/web/mini-watch.md).
Current Mini/Settings user guides, architecture overview/module/code map and version
history were updated. No acquisition/accounting/layer boundary changed; no broader
architecture redesign or release archive is needed.

## Limits and exceptions

No user/Decision-Delegate test or requirement exception was requested or granted.
First-open native frame/zoom conversion is a conservative estimate, not an exact
OS-frame query. Actual native clamps may reduce height **and width**, including a
first disclosure resize; scroll remains functional and no repair loop runs. Browser
position and size restoration cannot be completely independent. Physical Windows
frames/manual dragging, multi-monitor transitions, macOS and screen-reader speech
were not exercised and are **not claimed PASS**. Headless screen/DPR emulation is
not physical display proof. Historical On Hold measurements remain historical.
