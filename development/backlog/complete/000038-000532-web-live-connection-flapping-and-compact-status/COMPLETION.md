# FR 000532 — completed implementation

## Outcome and candidate

v80.107 removes deliberate sixty-second healthy SSE rotation and makes connected
status compact. [Implementation candidate](https://github.com/qstoffe/cost-guard/commit/df65672)
contains source, deterministic regressions, documentation and measured evidence.
This report does not invent a merge revision; native delivery records verified merge truth.

The original FR.md and bundle bytes are preserved. Exact native transaction state
advances ordinary/completion count to 38; identity high-watermark remains 533 and
retention prunes nothing. Other pending FRs and cross-FR references are preserved.

## Changes and decisions

- Keep healthy authenticated streams open; preserve admission, write deadlines,
  heartbeats, authorization expiry, bounded replay and terminal shutdown. Do not
  conceal transport errors with a delayed banner or add more acquisition/polling.
- HTTP success cannot label a broken stream connected. Recent healthy tab returns
  revalidate quietly; stale returns still mark retained data before revalidation.
- Hide the healthy full-width banner. Keep a compact accessible header label and
  non-sticky actionable notices with expandable host/source observation details.
- CLI Watch/report valuation, source mutation, host restart/scan, browser storage,
  external dependencies and shared OpenCode lifecycle are unchanged.
- Update product version/date/current docs; retain historical pre-v80 notes
  verbatim in a linked archive to respect the existing history hard cap.
- Architecture boundary unchanged; Web owner facts updated. Journal: no-update,
  focused verification record owns the causal findings.

## Verification

See [complete measured evidence and limitations](../../../architecture/governance/verification/web-live-stability.md).

- Final Full: 114 files, zero failures, 51.0 seconds/four workers.
- Final working-tree validator: eleven passes, zero failures, four existing soft
  design-budget warnings; no cap raised, no ZIP/release/tag created.
- Real V2 plus integrated-browser Overview/Watch: over ten continuous minutes each,
  extended to over 23/21 minutes respectively, no post-connected periodic error or
  reconnecting transition; one SSE request per tab. Warm finite Refresh succeeded.
- Real controlled stream interruption recovered in 3.029 seconds with rows retained;
  source unavailable, crash, auth expiry, identity replacement and actual source-guard
  shutdown showed truthful states, frozen data and appropriate disabled controls.
- Real DOM/CSS at constrained 1200/360px body widths and both shipped color palettes:
  no banner overflow, zero healthy-banner height, accessible actionable notice.
- Approved native Windows probe passed launcher/tray/restart/Exit/fault cases and
  independent CLI Watch. Zero model requests. Owned candidate host's forty-minute
  run ended with one acquisition owner and HTTP/Live joined without failure.

## Limits and follow-ups

The old host/browser baseline proved sixty-second rotation, not the owner's exact
roughly thirty-second interval, and its cold source was still starting. Its early
shutdown exceeded the join deadline and later exited nonzero; warm candidate/native
runs passed. The first real finite report timed out before a later Refresh succeeded.
Neither failure was hidden or misrepresented as source/transport success.

Constrained body/CSS-palette checks are not exact viewport emulation, physical OS-theme
switching, screen-reader or suspend proof. Physical Explorer double-click, browser
paint and native macOS were not tested. Native probes intentionally open normal local
browser tabs; reducing that noise is deferred, not another native run or cross-repo
publication. No unrelated Chrome tab/process is closed. No PR self-review or model switch.
