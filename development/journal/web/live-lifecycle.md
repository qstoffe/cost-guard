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
- Stop set flags then joined pools whose in-flight source reads could continue
  across whole trees. Real serial/control shutdown spent 4.968/6.030s in card-pool
  joins. A held real HTTP header/body read reproduced the mechanism deterministically:
  baseline close did not return before the causal fixture released that request.
  Cross-thread `socket.shutdown` alone also remained RED on this Windows runtime.
  Cancellable raw read waits now preserve the original timeout and abort on owner
  cancellation. No unjoined executor/daemon replacement or longer deadline is used.
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
