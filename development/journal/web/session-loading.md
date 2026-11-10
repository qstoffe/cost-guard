# Determinate session-detail loading — FR 000662

## Ownership and progress

`session.js` reuses `ReportLoading.View` and `.report-loading`, not finite-report
admission or its waiting policy. Shared report code is unchanged. The first-open
bar is a stable DOM instance with explicit `max=100` and numeric `value`.
Opening/source waits start at 0 and cannot advance from elapsed time or polls.

The documented overall phase budget is verified rich-history transfer **0–95%**,
then applied complete DOM **95–100%**. A 220-row session in 50-row chunks reports
50/100/150/200/220 of 220 at 21/43/64/86/95%; zero-row success can prepare directly.
Retries retain the last verified phase watermark, not a fake upstream fraction.
There is no completion delay or extra source request. Stage-only polite status
is a sibling of the busy history region, not inside a busy ancestor that could
suppress announcements. Terminal failure/cancellation clears history busy state.

Begin validates total/offset/revision and row shape. Every chunk validates the
pinned revision, total, exact next offset, positive bounded length and unique IDs
before counting it. A final post-yield generation check prevents abandoned
assembly. Only applied complete rows mark 100%. Retained history never reenters
the initial loader; focus, selection, scroll, export and polling keep their owners.

## Verification

- Focused session tests: 11 tests passed, including API revision pinning, paging,
  empty/one/multi-chunk DOM, exact 220-row counts, malformed/duplicate/oversized
  chunks, expiry/recovery, terminal/auth/identity failures and navigation races.
- Real hidden Chrome and Edge: each passed 48 layout cases — Classic/Web ×
  light/dark × 360/768/1366/1920 widths × 100/125/150% CSS zoom, reduced motion.
  Geometry checks cover centered stable progress, shared bar height, explicit
  value/max, absent normal warning/overflow and stage accessibility structure.
  Actual authenticated Sessions click transfers 1001 canonical synthetic rows;
  controlled 220/1/0-row cases prove counts/completion, cancellation, hidden polling,
  retained refresh/outage, focus/selection/scroll, hover, keyboard, emulated touch
  and real browser Back.
- Read-only real V2 installation: 3088 available sessions; 47 visible scalar keys
  acquired during the bounded observation. Pinned detail returned 2 rows in one
  chunk; independent detail/freeze check returned 1 row consistently. Live owner
  stayed intact; no model calls were initiated, no cleanup failures or owned
  worker survivors, and shared OpenCode was untouched.
- Native Chrome page zoom also passed 48 cases at 100/125/150%. At fixed requested
  window width 1366 with no metrics override and CSS zoom 1, actual CSS viewport/DPR
  were 1344/1, 1075/1.25 and 896/1.5. Thus browser zoom is independently established,
  not inferred from settings readback. Matrix-only device bounds accommodate the
  headless minimum-window clamp; measured CSS widths are 360/768/1366/1920.
- Full ran all 181 groups: 180 passed and one failed on the obsolete expectation
  that retained history removes every progress node. The corrected test asserts
  one stable **hidden** loader plus unchanged 151 rows. Focused real-HTTP view and
  detail rerun passed all 13 tests on current source. The original Full run is not
  reported as green. Working-tree validator result is in `COMPLETION.md`.
- Decision Delegate accepted acceptance-6 evidence after the native-zoom check:
  actual viewport/DPR plus 48 real-zoom layouts and earlier interactions suffice.
  No verification exception, disruptive testing or correctness waiver was needed.
  Compact browser evidence: `architecture/governance/verification/session-loading-662.json`.

## Limits

The integrated browser was disconnected; existing hidden fresh-profile Chromium
transport supplied real browser evidence without desktop effects. Native page zoom
was tested independently of the CSS-zoom matrix. Renderer-local input does not prove
physical hardware input, OS scaling, spoken screen-reader output or macOS. Real installation observations are counts/
contracts, not a reconstruction of the owner's private visual incident. Natural
arrivals and complete global metric sorting were not established by the bounded
installation probe and are outside this detail-loading change. No paid inference,
new acquisition scan, shared-service stop or packaging was introduced.
