# FR 000602 completion — 2026-11-06

Implemented in v80.179, integrating the actual merged FR 000596 tables. The complete
original specification is preserved as `FR.md`; completion ordinal 000110 follows
the current highest Complete prefix 000109, not Ready priority 000185.

## Delivered scope

- One Watch-derived compact header/cell/gridline/rounded-shell style for Sessions
  catalog/detail, Models and both 13-column Token Mix tables. Semantic structures,
  data/sort contracts, long names, themes and document vertical scrolling remain.
- Browser-local YYYY-MM-DD HH:mm from exact timestamps, real timezone/DST conversion
  and raw-key sorting. Pending/unknown/zero/unavailable/retained metrics are distinct;
  existing observations survive failures and routine checks.
- Seven latest-visible-page admissions per background turn within the existing
  four-root/two-second admission slice. Source/dependency-valid summaries are reused;
  terminal errors wait for changed evidence. Global metric sort remains honest.
- Current successful evidence alone enables all-yellow `[RUNNING]` rows. Status can
  end while title selection remains protected. Pager buttons retain URL history,
  disabled boundaries and a centered, narrow-wrapping range/page label.
- Complete chronological detail retains pinned 25-row chunks, five-second checks,
  canonical totals, keyed selection/focus/scroll, and lease cleanup. Previews grow on
  roomy screens and yield before metrics. Initial acquisition has indeterminate
  progress, not a fabricated percentage; source errors stop alleged loading.
- Web detail selects only canonical first-request Ictx. CLI/Watch context transitions,
  accounting, independent cost splits and Token Mix acquisition remain unchanged.

## Actual verification

- **PASS:** `py -3 development/tools/run_tests.py --suite full --jobs 1`:
  **149 files, zero failures, 317.5s**. Native discovery, focused catalog/projection,
  real-HTTP/VM, long histories and compatibility tests all ran. Earlier runs are not
  PASS: the obsolete anchor selector was repaired; an unchanged concurrent Windows
  PATH-discovery failure passed isolated and final serial runs without relaxed bounds.
- **PASS:** `py -3 development/tools/validate_package.py --working-tree`:
  **11 passes, zero failures**, six existing advisory warning categories. No caps or
  baselines were raised; no product ZIP was built.
- **PASS:** hidden fresh-profile Chromium `probe_web_sessions.cjs`, shipped HTTP/auth
  and actual assets over synthetic source truth. All three themes, 1920/1366/800/360
  CSS widths and 1/1.5 CSS zoom; Watch, catalog/detail, Models and both 13-column Token
  Mix tables; compact targets, full dividers/corners, readable metrics and no nested
  vertical/document-wide horizontal overflow. It also verified 1,001→1,002 prompts,
  running/end/outage/recovery, stable navigation, selection/scroll, centered long
  pager labels and running-row colors. Final synthetic discovery: **5,131ms**.
- **PASS:** actual-browser and VM local-clock checks across Swedish/US locales,
  Stockholm/New York timezones and spring/autumn DST; isolated first-Ictx versus rich
  transition projection/display tests; 120-root visible-priority/fairness fixture with
  exactly one acquisition per unchanged root.
- **Observed:** integrated OpenCode browser compared all six table types through the
  source-neutral fixture: shared 5.25px/9px header padding and 6px corners. Its screenshot
  operation rejected a non-visible Review tab after focus; no desktop workaround was
  attempted. Separate hidden rendered screenshots were inspected.
- **PASS, bounded real-installation probe:** V2, 2,731 roots, global index **0→12**,
  50ms first response, 211ms maximum API reply; real two-prompt detail in **23.910s**,
  14,701 bytes. One Live owner/two streams retained; no inference/source writes/shared
  OpenCode stop; zero remaining owned workers and no cleanup failures. The earlier
  probe lost its host during concurrent source edits and is not PASS.

## Limits, decisions and current documentation

Cold full-catalog metric sorting **remained pending**, not fully ready; this retains
the explicitly scoped limitation documented by FR 000593 and required by this FR.
Visible-priority is not a guarantee that slow source reads finish instantly: one real
slice reached 7.005s. Natural new-session arrival, physical desktop/browser zoom,
macOS and assistive-technology behavior were not measured. Independent history phase
error counters do not establish those unrelated lanes' root cause or health.

The active read-only Decision Delegate directed omission of one optional synthetic
scratch-summary read after native `SCRATCH_SESSION_BOUNDARY`; no substitute read,
environment manipulation or repeated bootstrap was attempted. The separate owning
GitHub branch GET was authorized and succeeded. This decision waived no tests or
requirements; no new product/test exception was requested or approved.

Updated README, version history, Web user guide, current Web module contract and
`development/journal/web/sessions-live.md`. Existing application/reports/source
boundaries remain intact; the shared visual owner is CSS, not a new acquisition
component. Ordered ordinary maintenance progress advances to 49 only on merged
default. No next task was selected here.
