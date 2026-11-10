# Permanent quota Capacity slots — FR000661

Scoped v81.11 change against `eece82687a736173a33024a4b114949f4aa88bd8`,
Windows workstation, 2026-11-10. This reverses FR000654's unknown-row suppression,
not its numeric estimate markers, concise help, label capitalization or Mini split.

## Presentation ownership

- `application/display.py` exports the existing `monthly_applicable` result alongside
  `ccost_reference`; no Decimal, native quota, acquisition or pricing calculation changes.
  The opaque reference map preserves this boolean without display conversion.
- Shared `account-cards.js::quotaTrack` always owns one visible period Capacity row.
  Nonmonthly/unknown periods also own one Monthly Capacity row. Only numeric text
  depends on current knownness: unavailable reference amounts become `?`, never
  `N/A`, blank or `~?`. Independently proved native unlimited remains `Unlimited` in
  its own period row; an unavailable theoretical equivalent remains `?` with reason help.
  Legacy reports, API display tokens and Mini retain their existing formatting.
- `View.align` derives an unbounded ordinal slot plan per responsive comparison row.
  Each real level has summary, Capacity, applicable monthly, track and details slots;
  each later real level also has a divider. CSS `display: contents` wrappers allow
  secondary nodes to participate in the root subgrid instead of independent footers.
  Missing tails are empty grid cells, never synthetic quota DOM/accessibility nodes.
  A native monthly peer gets only a necessary empty, aria-hidden comparison slot.
- Title, reset, pace and warning text use intrinsic shared tracks, not estimated
  heights, absolute coordinates or provider-specific padding. Resize, DPR/page/pinch
  scale and publication/membership/order changes recompute the plan; single-column
  and lone cards have no unrelated peer slots. Numeric updates and monthly eligibility
  changes retain progress/help nodes, active help, selection and focus.

## Regression and browser proof

The old disappearance expectations in `fixtures/account_capacity.cjs`,
`web_watch_summary.cjs`, `probe_subscription_capacity.cjs` and
`probe_quota_display.cjs` are explicitly reversed, not skipped. Native/estimated
numeric formatting, concise help, capitalization, Used/Remaining, Credits/USD,
unknown/unlimited/idle states and Mini compatibility retain assertions. Source
projection tests assert native monthly/nonmonthly eligibility independently of text.

The hidden browser uses shipped HTTP/assets/CSP/SSE and disposable profile/config,
not the person's browser or visible desktop. The integrated browser was disconnected.
Each browser matrix covers 264 scenes: 360/800/1280/1920 CSS-pixel viewports,
100/125% CSS zoom, Classic/Web light/dark and 11 mixed/single/all-monthly/period/
unknown/recovered/unknown-again/reorder/missing/unlimited/stale scenarios. Accounts
contain 0–4 genuine secondaries, long headings and reset details, wrapped/lone rows.
Assertions measure actual `progress.getBoundingClientRect().top`, track and divider
coordinates, real row counts, empty-spacer semantics, route text/help/ARIA parity,
no overflow, stable bars and open-help/focus retention through updates. Full drivers
also exercise real Settings saves/reloads, SSE membership/availability updates and
already-open headless Document PiP compatibility.

Two unrelated probe synchronization races were exposed rather than hidden:
snapshot paint can precede the final reloaded tab's SSE connection, so terminal
delivery waits for its actual OPEN handshake; CDP popup close acknowledgement can
precede target destruction, so the next gesture waits for that owned target to close.
The initial fixture-lifetime hypothesis was disproved by the subsequent fast Chrome
run. Synthetic host/driver safety lifetimes remain unchanged. No product transport,
terminal assertion, popup count or timeout policy was relaxed.

## Retained evidence and gates

- Local Full: **181 groups PASS**, zero failures, **136.6s**
  (`scratch:/full-tests-final.json`). Package validation: **11 PASS**, zero failures,
  seven existing advisory prose/design-budget warnings; no caps raised or baselines reset.
- Chrome **156.0.8078.80**, actual browser zoom **100%**: full driver **PASS**, **48s**,
  264 capacity scenes and **1428 directed same-row actual-progress comparisons**,
  maximum Y difference **0 CSS px** (`scratch:/capacity-chrome-delivery-final.json`).
- Edge **157.0.4341.42**, actual browser zoom **125%**: full driver **PASS**,
  **58.04s**, 264 scenes / **2028 directed comparisons**, maximum Y difference
  **0 CSS px** (`scratch:/capacity-edge-css-widths.json`). Device emulation accounts
  for native zoom and asserts the actual CSS viewport is exactly 360/800/1280/1920,
  rather than misreporting pre-zoom device widths. Both browsers retain all native/estimate,
  Settings, help/input, SSE, Mini and terminal-delivery assertions described above.
- [Before screenshot](../../architecture/governance/verification/account-capacity-661/before.png),
  [after screenshot](../../architecture/governance/verification/account-capacity-661/after.png)
  and [bounded coordinate/coverage evidence](../../architecture/governance/verification/account-capacity-661/evidence.json).
  Matched 1920 CSS px / 100% / Web light / Remaining USD scene: first-row actual
  primary Y values **461.890625, 461.890625, 245.4375 → 285.125 each**; secondaries
  **625.375 vs 318.890625 → 466.359375 each**. The unknown card gains its five
  truthful Capacity lines. Later peer tracks and real dividers align at each ordinal.
  Before uses old-main product code in an owned detached baseline worktree; the same
  synthetic scene/helper is copied there. Screenshots contain synthetic accounts only.

## Real-installation evidence and scoped exception

`probe_web_live.py --accounts` **PASS**: V2, three cards, one account-refresh/Live
owner, advancing publications, two coherent streams, verified sequence/stream IDs
and retained run origin; one native capacity, amount pair and pace each. No finite
jobs or inference; **6.7057s**, no pending work/owned threads/owned processes or
cleanup failures afterward; shared OpenCode untouched.

The extra combined `--accounts --watch-cards` run is **FAIL**, not broad PASS:
Accounts passed, but Earlier-history certification remained loading at **559/3085**
after its **90-second** observation cap (`probe_watch_cards_timeout`). Total
**96.864s**, owned cleanup clean. The timeout's cause is unresolved; this is not a
history correctness/performance diagnosis.

**Decision Delegate authorized an FR000661-only minor journal verification
exception:** delivery need not await whole-population history completion/ranking.
The probe's Earlier certification is independent of shared quota rendering; focused
Accounts live proof plus deterministic and browser checks cover the changed path.
**No functional acceptance is waived.** Whole-population history completion/ranking
remains **UNVERIFIED**. Both live runs had **zero estimated-amount checks**; natural
unknown/recovery/ratio trajectories were not observed or claimed. Synthetic/source-
shaped coverage is not natural-source evidence. No further history retry, acquisition
change, new FR, Suggestion or hold is required by that scoped decision.

Raw bounded task evidence: `scratch:/live-accounts.txt`,
`scratch:/live-accounts-focused.txt`. Headless proof is not physical monitor/native
window, screen-reader or macOS proof. No inference, shared-service stop, ZIP, tag or
GitHub Release is part of this delivery.
