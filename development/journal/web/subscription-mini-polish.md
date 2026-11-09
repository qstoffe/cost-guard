# Subscription and Mini display polish — FR000654

Scoped v81.3 change against `a520a1ba0a3df27e5090dfbc69cabad057a69b29`,
checked on the Windows workstation, 2026-11-09. This is not a fresh audit of
unchanged acquisition, billing, native desktop geometry or other platforms.

## Ownership and live updates

`quota_ccost.py` retains canonical Decimal/reference fields and rounding, adding
concise Capacity help and leading `~` to ratio Capacity and numerical 30-day
equivalents. Raw Remaining/pace and Mini calculation help stay separate. Shared
`account-cards.js` checks numeric availability, removing unknown primary/secondary
rows and targets rather than trusting formatted `N/A`. Bound insert/remove effects
retain card/bar/help identity. `render.js` snapshots child traversal so removing a
capacity node cannot skip the reset/details sibling. Stale observations retain
native facts but no current capacity rows. Unknown primaries receive no spacer;
known period-only peers align only beside a known monthly equivalent.

Displayed labels capitalize only the first Unicode letter. Provider identifiers,
period metadata, raw math, native usage/reset/warnings and acquisition are unchanged.

Mini has five actual cells: Activity / Session / CCost / Total / Ctx. Each cost has
its own header, value help and accessible scope. Measurement includes all four
non-Session columns; no CSS spacing workaround or larger opening was needed.
`ContextHelp.runningDuration` privately brands three text parts. Only the known
Duration part becomes a fixed-class span; untrusted text is never HTML. Stable
text nodes preserve selection during ticks. Non-running/error/abort/unverified/
historical/replacement outcomes remove the cue in already-open help.

## Measured fit and interaction

Owned official Chrome for Testing **157.0.8103.38**, headless Document PiP, isolated
profile/config, shipped HTTP/CSP/SSE; no personal browser or visible desktop helper.
The integrated browser was disconnected. Decision Delegate authorized the isolated
portable runtime route after restricted system-binary discovery was refused; no
retry of those paths, system install, shared cache or visible-desktop authority.

- Matched normal-zoom before/after opening request: **550 → 541 CSS px** in both
  Classic/light Credits and Web/light USD, with realistic/oversized cost values.
  Credits combined cost width **89.39** became independent **44.41 + 39.81 px**;
  USD **91.73** became **44.41 + 47.83 px**. The new table was narrower overall.
- Full after-layout fit matrix passed; a further full **125% actual browser zoom**
  run passed **91 layouts**, including themes/fonts/units, five-row capacity,
  0/1/3/5/6/10 sessions, 0/1/6 accounts, internal overflow, narrow panning, sticky
  headers, history, explicit Fit, remembered sizing, AX and no passive resizing.
- Focused real-PiP help passed both cost columns across Classic/Web light/dark and
  Credits/USD. It verified the complete Duration fragment's computed running color,
  11s→12s ticking with selected text and focus preserved, outcome cue removal,
  literal hostile model text, real keyboard/hover/touch/Escape and refresh behavior.

Artifacts are task-owned `scratch:/mini-before.json`, `scratch:/mini-after.json`,
`scratch:/mini-help-final.json`, `scratch:/mini-zoom-final.json`. The baseline JSON
was complete/PASS before a server restart cancelled its shell notification; that
artifact does not establish the old producer's exit/cleanup. Later probes completed.

## Regression development and limits

The first Full run passed 177/180 groups. The three failing groups exposed an old
four-column fixture path and a genuine dynamic-child traversal defect; these were
repaired. The new availability fixture also needed a syntax correction, an explicit
Remaining-mode expectation and the real root-scoped unit-refresh contract. Targeted
Mini, daily/shared-card and quota groups then passed. No assertion, cap or structural
baseline was weakened to hide a product defect.

Final local Full passed **180 groups, zero failures, 127.7s**
(`scratch:/full-tests-final.json`). Package validation passed **11 checks, zero
failures, seven existing advisory budget warnings**. The corrected full Accounts
browser driver passed **231 layouts at 125% actual browser zoom**, including
**168 shared-capacity scenarios** (four widths, two CSS zooms, three themes,
seven availability/period/membership scenes), known-peer alignment, no unknown
spacer or phantom line, normalized help/ARIA, native values, both units/modes,
settings persistence, unchanged-tick focus/selection, touch/hover/keyboard and
owned-host terminal delivery (`scratch:/accounts-zoom-final.json`).

Synthetic browser scenes must isolate their deliberately replaced account DTO from
the ordinary snapshot heartbeat, then restore the real update method. Otherwise a
heartbeat changes the scenario mid-assertion. The extended capacity matrix also
exceeds Chromium's rapid-navigation IPC quota; only its disposable hidden test
browser disables that quota. The production browser/host is unchanged. Capacity
keyboard traversal starts at the new native-summary help target before testing Tab
to the existing Remaining amount. Exploratory failures remain failures, not PASS.

## Real-installation proof and scoped exception

The combined `probe_web_live.py --accounts --watch-cards` is **FAIL**, not a broad
PASS. Its first attempt passed Accounts then hit a connection reset. The later
source-stable run passed Accounts but left historical certification **loading,
757/3044 checked at the 90-second observation deadline**, ending with
`probe_watch_cards_timeout`. HTTP and publication continued; final cleanup had
no pending work, owned threads/processes or cleanup failures. Neither run proves
the root cause of the earlier reset or historical completion/ranking.

Focused `probe_web_live.py --accounts` subsequently **PASS**: V2, three cards,
one refresh owner/one Live owner, advancing publication, one native capacity /
amount pair / pace and three estimated-amount checks; two coherent streams,
verified sequence/IDs, retained run origin, no finite jobs or model calls,
**5.762s** total and clean owned-worker shutdown. Shared OpenCode was untouched.
Aggregate evidence: `scratch:/live-accounts-final.log`.

The existing bounded `probe_mini_source.py` main, observed through the task-local
aggregate-only `scratch:/mini_source_display.py`, **PASS**: V2, four coherent
publications, three accounts/five quota projections, **one genuinely running
populated represented row**, and prepared prompt CCost, session-total CCost
(Credits/USD), canonical duration and duration text checked for that row.
**Zero natural historical rows** were observed. It took **2.134s**, closed its
owned acquisition in **0.153s**, exported no private identity/text/amount and
started no inference or new source mutation.

**Decision Delegate authorized a task-local journal-only exception** to successful
completion of the broader combined Watch/history probe. No FR functionality or
functional assertion is waived: changed display paths have independent non-vacuous
live, deterministic and browser evidence; missing broad proof concerns unchanged
historical acquisition. Whole-population historical completion/ranking and natural
historical transitions remain **unverified by these live runs**. Synthetic history
coverage is not natural-source proof. No further history retries, acquisition repair,
Suggestion or hold is required for this scoped delivery.

Headless native PiP is not physical desktop/monitor/work-area, macOS, or screen-reader
proof. Synthetic unknown/recovery/outcome transitions are not claimed as naturally
observed provider or personal-session transitions. No model calls, shared OpenCode
stop, ZIP, tag or GitHub Release is part of this delivery.
