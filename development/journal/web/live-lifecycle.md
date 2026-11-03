# Web Daily and shutdown lifecycle

FR 000555, investigated on Windows/Python 3.14, baseline
`8c96f5c9f7e41ed7dd205e1471294d13780df776` (2026-11-03).

## Causal findings

- The Web history lane forced one root per slice, although `RootAcquisition.prepare`
  and V2 snapshots can share authoritative before/after brackets across a bounded
  batch. Real phase evidence found repeated whole-catalog waits in history/cards,
  a 71.432s first history plan, and 1–2s catalog operations. The 64-root real-V2
  fixture requires 64 catalog fetches before the fix. Charging the observed
  two-second operation cost gives 128s, beyond the unchanged 120s Daily budget.
  Four-root slices require 16 fetches/32s in the same causal work model, retaining
  all 64 requests/prompts and the same revision checks. This is a controlled work
  model, not an observed 128-second real-source run or a provider latency promise.
  A second actual-HTTP regression gates the redundant second catalog response:
  baseline publication blocks, while the bounded shared bracket publishes all four
  requests/prompts without needing that response. Both baseline-owner tests are RED
  and both candidate tests GREEN, not just a modeled performance comparison.
- Stop set flags then joined pools whose in-flight source reads could continue
  across whole trees. Real serial/control shutdown spent 4.968/6.030s in card-pool
  joins. A held real HTTP header/body read reproduced the mechanism deterministically:
  baseline close did not return before the causal fixture released that request.
  Cross-thread `socket.shutdown` alone also remained RED on this Windows runtime.
  Cancellable raw read waits now preserve the original timeout and abort on owner
  cancellation. No unjoined executor/daemon replacement or longer deadline is used.
- The first three candidate real runs also exposed idle account workers still in
  their 100ms queue wait after host close. These were not accepted as leak-free
  runs. A third RED/GREEN regression requires reaping them before return; account
  close now joins against one shared 200ms budget. In-flight external-provider
  HTTP keeps its existing bounded daemon contract, rather than extending host
  shutdown or altering provider timeouts. The real probe now rejects any remaining
  owned thread/process instead of printing PASS based only on Live/HTTP threads.
- The probe's former `finally: host.close()` could replace the primary exception
  with a cleanup exception. The probe now retains both original objects in a group
  and exports their separate sanitized phase/classification and pre-cleanup state.
  A blocked authenticated snapshot is separately tested as a real HTTP timeout,
  not mislabeled as source no-data or a successful Daily publication.

## Reuse and limits

Run the focused lifecycle tests, then `probe_web_repeat.py --cycles 10` and the
same command with `--competing` for explicit finite repetition. These use real
production acquisition, projection, authenticated HTTP, SSE and report-process
owners over synthetic sources. Competing mode adds CPU/serialization work, two
subscribers and cancellation of a pending report. No model or provider calls occur.
The normal full suite includes the focused tests, not twenty recurring cycles.

Use `probe_web_live.py --watch-cards --daily --detail` for the separate read-only
V2 acceptance. Preserve its complete phase output and require owned-host shutdown,
not merely direct acquisition close. A warm cache, smaller eligible history and
absence of overlapping work explain how earlier serial reruns could pass without
removing either mechanism. No retained historical trace identifies which precise
catalog or source operation caused every old failure; do not invent that detail
or claim immunity to arbitrary source outages. Real-source verification and exact
commands/counts belong in the task's completion and PR. Native desktop/macOS proof
is separate from Windows/headless ownership evidence.

## Representative competing work is not every historical report

Final real `--watch-cards --daily --detail --reports` passed Daily/cards/detail/SSE
and Normal/All-models/Sessions reports but FAILED overall: its fixed historical-date
job hit the existing 120s limit at 868/872 roots. Cleanup still reaped every owned
resource in 0.0884s. Do not call that whole campaign PASS, infer the complete cause
of the date-report slowdown, or assume the slowdown predates the candidate.

For FR 000555, Decision Delegate independently confirmed the existing `--models`
variant as representative concurrent work under §3.4, without an exception: real
Normal and All-models report processes run sequentially beside continuing Live,
not simultaneously with each other. That whole run passed, as did three consecutive
full serial source runs and final 10+10 synthetic cycles. Exact commands, failures,
phase timings and platform limits are in the
[completion evidence](../../backlog/complete/000068-000555-web-live-daily-shutdown-timeouts/COMPLETION.md).
