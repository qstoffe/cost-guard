# Web AI Stats and historical re-entry

Source revision: e4d715e170917f5ef2d69d31a68dbc3eb297ff8a
Checked revision: e4d715e170917f5ef2d69d31a68dbc3eb297ff8a
Last checked: 2026-11-06
Status: current

## Summary

FR000612 checks the implementation above, based on
`417899fc1f68f675b844841e1f6ba0f7c84b746e`. Selector help labels inherit the control
foreground; foreground/background switch atomically, avoiding low-contrast cross-fades.
Month/all retain delayed label hover, keyboard and passive touch explanations.
Canonical `Stat.reasons` distinguish coverage, unknown execution boundaries,
unpriced requests, missing token telemetry, pending usage and provisional timing.
Completely observed absent denominators use No data; true zero totals remain zero.
Supported partial subtotals remain qualified, not exact totals. Application-owned
allowlisted prose appears in-card and current-period title help; complete values
retain their original traits. Compact evidence algorithm 3 retains snapshot coverage
and invalidates older payloads. Finite loading/deadlines remain unchanged.

The ten baseline cards reuse event-time cost, overlap-safe execution unions and
configured-local calendar/DST analysis. Month/all extend history lazily; no separate
Comparisons scan, account acquisition, model request or durable history is added.
Optional matched-input facts have independent coverage. FR000611's content-sized
detail tracks, wrapping and equal within-row heights remain. `cached-reports.js`
retains AI Stats/Token Mix's 15/5-minute cadence and one-hour re-entry bands.
Acquisition clocks, not navigation/HTTP success, establish freshness.

## Evidence

### FR000612: rendered contrast and evidence states

```text
node development/tests/integration/probe_ai_stats.cjs <browser-executable> <output-json>
```

Integrated browsing returned `browser.disconnected`; installed Edge ran headlessly
with a disposable profile and shipped authenticated HTTP/CSP/assets. No personal
profile, visible desktop or shared OS input. Original selector CSS reproduced
selected This month's label **rgb(120,220,232)** on the identical background:
**contrast 1.0**, versus the parent's foreground contrast **10.43**.

Final browser: **13 checks, 9 normal layouts, 80 text layouts, 1,350 computed color
samples and 16 canonical state/unit cases, PASS**. Minimum measured label contrast
is **5.81**. All five selected/unselected controls are checked before hover, on
label/padding, pressed and after departure in Classic/Web light/dark at
360/1366/1920px, 200% text and 125% CSS zoom. Immediate selection avoids transient
unreadable color blends. Month/all keyboard focus/Escape and selected All time's
actual label hover/touch expose scope help without native titles or hover acquisition.

`probe_ai_stats_states.cjs` consumes Python analysis/application projections for
complete populated, complete empty/zero, source gap, unknown duration, missing
price/telemetry, pending and provisional cases in Credits/USD. In-card state/reason
matches canonical display; quiet replacement refreshes open help while retaining
the focused heading. Controlled slow All time shows progress below 100%, not
Unavailable cards. Smaller cached scope, route return, cancellation, terminal
failure/retry and in-flight reuse retain independent lifecycle checks.
`probe_ai_stats_layout.cjs` retains actual text-range/clipping/focus/link geometry,
large values/long names, fonts, enlarged text and optional matched-card cases.

The populated AI Stats fixture now explicitly declares complete synthetic coverage;
its snapshots previously defaulted to incomplete. Optional matched facts are
deliberately omitted from its ten-card baseline and tested separately. A repeated
focus-help check needed blur before refocusing the same escaped target; assertions
were retained. An attempted inline-style baseline was CSP-blocked and discarded;
the recorded reproduction used the actual shipped pre-fix selector rules.

Local Full: **153 files, zero failures, 95.0s**. Final focused AI Stats: **21 tests,
zero failures**, rerun after the source-warning/migration fixture addition.
Validator: **11 passes, zero failures, six existing advisory warnings**: Web guide,
README, context, report service, Watch coordinator and version history. No caps or
structure baselines changed. Evidence: `scratch:/ai-stats-before.json`,
`scratch:/ai-stats-final.json`, `scratch:/full-tests.json`.

### FR000612: real installation and limits

```text
py -3 development/tests/integration/probe_ai_stats.py --cold-and-warm
```

Production ReportJobs used real read-only V2 and an isolated disposable cache.
No inference, account refresh or shared-service stop. Numeric/status/reason evidence
only: `scratch:/ai-stats-live.jsonl`; no prompts, titles, IDs or raw source payloads.

| Attempt | Result | Seconds | Coverage |
| --- | --- | ---: | --- |
| Cold 30 days | complete | 89.047 | four periods |
| Warm 30 days | complete | 3.656 | four periods |
| All-time extension | complete | 6.075 | five periods |
| Warm All time | complete | 4.465 | five periods |

Both All time observations return null timing with **unknown-duration**, partial
total cost and unavailable cost averages/record with **unpriced-requests**; the
rate carries both limitations. Current executions add provisional timing reasons.
The 30-day acquisition supports timing but already contains unpriced work;
extending history exposes unknown older timing. Unknown ends cannot prove
non-overlap even in shorter windows, so broader results conservatively qualify
those period rows too. This reproduces the symptom class, not the owner's exact
earlier run or particular responsible record. No calculation check was relaxed,
missing evidence reconstructed or cause guessed from provider error text.

Current source is mutable; timings are observations, not performance guarantees.
Rendered evidence is synthetic, not real-source browser paint. Physical devices,
screen-reader speech and non-Chromium engines remain unverified. AX names,
keyboard/touch behavior and visible/accessibly described reasons are checked.

### FR000612 documentation exception

The knowledge read failed before writes with `KNOWLEDGE_LIMIT`: existing analysis,
reports and Web help documents exceed 12 KiB. The **Decision Delegate** independently
inspected the helper and current ancestor routing, then approved ordinary versioned
patches only to reports' AI Stats section, Web help's optional passive-heading API
and consolidation of this leaf to **≤12 KiB**. Another journal apply attempt was
unnecessary: ancestors still exceed eight routes and use a backticked AI Stats
route. No new route, cap increase, unrelated migration or inherited exception.
Other module claims retain their old scoped checks; analysis/overview/indexes are
unchanged. Legacy knowledge structure is not fully validated; no helper PASS is
claimed. Product tests, live checks, versioning and protected delivery were not waived.

### Historical findings, not renewed acceptance or inherited exceptions

FR000611 (base `558eabfd31c727b1df6ef599d33b71de15956348` plus its diff) proved a
15px inner detail region clipped 20px text despite fitting outer cards. Its final
browser passed 10 checks/9 layouts/80 text layouts; Full passed 153 files/105.5s.
Cold V2 timed out at 120.029s (2688/2725 roots); warm/extension/warm completed in
9.003/10.212/5.165s. Its delegate waived cold success only for that CSS change and
approved a narrow journal `INDEX_LIMIT` workaround; neither exception carries forward.

FR000599 (base `42cc45f624d7b9cda560e365e53a93cec36ff7bc` plus its diff) found a
16-root prototype timed out at 120.026s because repeated catalog brackets dominated.
Existing 64-root batching completed cold/warm/extension/warm in
84.692/3.452/6.274/4.053s. Its hidden UI used immediate canonical fixture jobs,
not production spawning/coalescing; separate spawned-process and live tests proved
those boundaries. A combined Node→Python→Models child harness stalled. Optional
whole-app help audit failed before AI Stats because its Sessions fixture lacked a
live catalog/detail runtime; it was not a later-route PASS or product failure.
FR000599's delegate accepted that split, waived actual speech and authorized scoped
oversized-document edits only then. Historical full evidence remains in Git.

## Next investigations

Historical cold acquisition sometimes timed out; this FR's cold run completed.
Performance variance and dominant catalog/hydration costs need separately scoped
investigation, not a guarantee inferred from one successful sample. Historical
combined-harness and whole-app help-fixture gaps remain if those become necessary;
the focused UI, separate real process/coalescing tests and current live acquisition
are independent evidence. Physical assistive-tech/device/engine behavior and the
owner's exact prior source incident remain unverified. Oversized legacy knowledge
documents/routing need separate consolidation, not inflated feature budgets.

## Rejected hypotheses

- Inner text fits whenever its outer card fits: false; text ranges and clipping
  ancestors must be checked. Content-sized tracks preserve enlarged line height.
- A help label may choose its own accent color on a selected accent background:
  false; the nested foreground must inherit the control's readable selected color.
- Cross-fading inverse selected/unselected colors is always readable: false;
  intermediate foreground/background can converge even if endpoints pass contrast.
- Missing metric means still loading or zero: false. Returned evidence determines
  unavailable/partial/provisional/no-data states, independent of job completion.
- All time guarantees complete lifetime history: false. Deleted/pruned history
  cannot be recovered, and unknown old ends cannot prove non-overlap with new work.
- HTTP success, navigation or a fresh timer proves fresh history: false;
  observation clocks and coherent acquisition own freshness and failed updates.
- Immediate synthetic jobs prove production spawning/coalescing: false; those
  boundaries require the separate real-process and real-installation observations.
- Every over-hour active view must blank: false; withholding is re-entry/inactive
  scope policy, not a disruptive active-page timer.
