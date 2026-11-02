# Web Watch prompt cards — FR 000542

Date: 2026-11-02. Product version: v80.123. Evidence applies to this delivery,
not the older combined-table Watch or native launcher acceptance.

## Reusable ownership findings

Web Watch cannot reuse CLI's startup-only/capped history or open one Sessions
detail lease per card. `watch/cards.py` maintains canonical active/grace identity,
five eligible historical sessions ranked by latest actual prompt, and a small
revision/generation catalog. Only active/top-five captured snapshots are retained.
Exclude active/grace sessions before limiting; stale capture results cannot
restore evicted membership or overwrite a new running generation.

`reports/watch_capture.py` captures/analyzes a session once, publishes selected
prompt windows, then calculates optional full totals. A 10,000-prompt session's
total includes canonical compaction/child attribution and overlap-safe execution
duration, not five displayed rows or session age. Rows can precede full totals;
source capture and canonical prompt analysis themselves are not streaming.

`watch/card_workers.py` owns four isolated service/source/cache integrations,
shared by concurrent cards for the same session, with no queued futures.
`watch/web_coordinator.py` adapts existing catalog/hint/cadence policy without
changing CLI hydration. Separate single-worker account-history and Sessions-detail
lanes keep blocking history off Live's thread and mutable service. Native account
acquisition keeps its existing scheduler. The shared refresh EMA must measure
actual capture duration, not newly cheap admission time (0.60 slower / 0.20 faster,
then clamp ceil(6×EMA) to 5–30 seconds). Close joins owned work; unexpected faults
still cross the host fatal boundary. Minimal detached DTOs keep 100 five-row cards
inside the existing SSE size bound.

The earlier Decision Delegate chose this full staged/isolated approach over
premature scope reduction. Its scratch read was denied; that decision relied on
worker-supplied findings, not an independent source review. No blanket test or
behavior waiver was granted.

## Deterministic verification and budget repair

`test_watch_cards.py` covers 100 concurrent prompts, focal windows, 10,000-prompt
canonical totals/duration, history exclude-before-limit/ranking, startup and
terminal/restart/concurrent/removal/stale-result races, bounded fair admission,
local source failure, deliberately blocked totals while another session finishes,
the ten-second running-tool threshold, EMA and wire size. `test_web_live.py` and
`integration/web_live.cjs` retain transport ordering/terminal/recovery tests and
pin the nine columns, units, safe text, Watch-only account cleanup, 0/1/5/7 tool
and skill groups, keyed DOM/focus/disclosure/selection/scroll and 100→0 cards.

The focused 23-test run passed before checkpoint. One earlier Full passed all
122 files; the subsequent run failed three foundation validator assertions because
VERSION_HISTORY.md was 33,145 bytes against its 32,768-byte hard cap. Condensing
the version notes repaired the cause without changing caps. Validator
then passed all 11 checks, retaining four existing design warnings (README,
analysis/context.py, reports/service.py, watch/coordinator.py).

Final-candidate Full passed all 122 files with zero failures in 58.3s (four
isolated workers). Working-tree validator passed all 11 checks with zero failures
and the four existing design warnings above. VERSION_HISTORY.md is now 31,904
bytes (31,917 with Windows line endings), retaining headroom below the hard cap.
Earlier failed runs do not substitute for the final passing gate.

## Rendered browser evidence

[Measured JSON](../../tests/evidence/watch-cards/browser.json) and nine adjacent
`watch-<theme>-<width>.png` files retain the synthetic rendered evidence.
Chrome/156.0.8078.76 on Windows passed Classic/Web light/Web dark at 1920×1080,
1366×768 and 360×800. The final run loaded current shipped assets and had
scrollY=0: each 1080p case's expanded history was 702px high, first active card
began at 869.75px, leaving about 210px of active content. All cases checked five
historical cards, no panel/table frames, no active/table vertical inner scroll,
narrow horizontal panning, amber/success/error text, native Enter disclosure,
focus/disclosure/history-scroll stability and 100-card document scrolling.
Representative desktop/laptop/mobile pixels were inspected.

Integrated-browser read/evaluate independently observed matching layout but its
screenshot failed because the tab was not desktop-visible despite focus. There
is no integrated screenshot claim. A prior Decision Delegate explicitly authorized
bounded headless Chrome on only the owned synthetic loopback fixture, with a
fresh temporary profile and bounded repair reruns; it did not authorize personal
tabs/profiles, login, OS input or shared-service control. Probe-owned fixture
servers stopped and browser profiles were removed.

## Fresh read-only real installation

`py -3 development/tests/integration/probe_web_live.py --watch-cards --detail`
passed on the final implementation on 2026-11-02:

- V2, one host acquisition owner, two HTTP streams, three accounts; preserved run
  origin and advancing sequence.
- Two active cards, one progressively loaded history card, three cards with rows
  and full totals, at most four rows/card, four bounded pending capture jobs.
- First rows and totals were both observed at 3.082s. Poll granularity does not
  independently prove live phase timing; the deliberately blocked-total fixture
  proves phase independence instead.
- Detail had one available/page row, first/latest access and frozen consistency,
  with one account owner. Owned Live/HTTP workers joined; shared OpenCode was
  untouched. No inference, login or user-data mutation occurred.

The real-source observation is not proof of the complete catalog's final top-five
membership or browser/SSE integration. Synthetic browser and real-source transport
checks are complementary, not a claimed end-to-end real-source browser run.

## Explicit acceptance limitation

On continuation, the foreground **Decision Delegate**, not the owner, authorized
delivery after final applicable gates pass with a limited FR 000542 acceptance #9
exception: **headless viewport verification completed; native-fullscreen
verification excepted**. The nine rendered cases, interaction checks and separate
layout observations were judged adequate; expanding personal-desktop automation
would add limited value relative to disruption. No additional desktop permission
or blanket waiver was granted, and final failures still require repair.

Native fullscreen/physical-display and physical-input behavior, screen readers,
macOS, real-source browser/SSE integration and independently measured live
progressive timing remain unverified. Exact headless viewport geometry is not
native-fullscreen proof. Keep these unknowns separate from the actual passing
deterministic, rendered-fixture and read-only V2 results.
