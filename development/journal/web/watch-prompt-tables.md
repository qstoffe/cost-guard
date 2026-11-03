# Watch prompt tables and observed token mix — FR 000558

2026-11-03, v80.138. `watch_capture.py` already enables canonical observed running
metrics. Exporting the existing `token_mix_percent` fixes the missing card data
route without adding source scans, provider polling, valuation or browser math.
Canonical entries retain child/multi-model/compaction inclusion and reasoning→Output;
known values use the CLI prompt projector's rounding, not the aggregate TokenMix
largest-remainder rule. Source corrections replace observations, never add them twice.

## Coverage decision

Foreground **Decision Delegate**, session `ses_e5d5e9ff4ffe24zEC1wT2GQj3Q`, approved
a narrow FR 000558 exception: completed partial I/C/W/O telemetry may be Web `N/A`
when the corresponding CLI row shows numeric percentages (acceptance point 3 only).
The existing completed CLI projector bypasses its coverage check; changing CLI is
explicitly outside the FR. Watch therefore checks every canonical entry against
shared `MIX_FIELDS` and suppresses only its projected mix when any category is missing.
Incomplete calls are not dropped and other metrics are unchanged. This is not owner
approval, a CLI fix or a general waiver; the CLI discrepancy remains unresolved.
Fully known/zero/live parity and all other acceptance checks remain required.

## Verification

- `test_watch_token_mix.py`: known/cache/reasoning/multi-model child/compaction parity,
  partial child Web unknown with CLI unchanged, zero/absent usage, coverage corrections,
  stale capture/generation rejection, terminal freeze, DST/local dates and #12 retention.
- Native fake V2 HTTP observations in `test_watch_card_lifecycle.py` produce
  `100/0/0/0` → `25/75/0/0` → `20/60/0/20`, repeated captures stay at three calls,
  and terminal Web/CLI values agree.
- `integration/web_live.cjs` uses actual LiveConnection and Watch rendering to verify
  accepted SSE mix changes in the same DOM row without reload, stale event rejection,
  disconnect/reconnect and gap→HTTP resync without token reconstruction.
- Headless Edge **156.0.4314.58**: nine synthetic cases, Classic/light/dark ×
  1920×1080, 1366×768, 360×800, passed. Both tables have ten ordered columns, local
  HH:mm with full-date disclosure, visible #12 beside preview-only ellipsis, complete
  metrics, narrow horizontal panning, unframed history and a 2px expanded-only divider.
  Native Enter disclosure, header focus/Escape/click explanations outside clipping,
  DOM reuse, selection/focus, scrolling, currency switching and 100-card behavior passed.
  Classic desktop and light narrow screenshots were visually inspected.
  [Retained measured cases](../../tests/evidence/watch-prompt-tables/browser.json)
  omit disposable screenshot filenames; screenshots are not committed.
- Package validation: 11 checks pass, zero failures, six advisory prose/design warnings.
  Initial Full had two failures from the summary DOM mock lacking event listeners and
  expecting the old cells; the mock and assertions were updated, and both focused
  reruns pass. Final `run_tests.py --suite full` passes all **132 files**, zero
  failures, four isolated workers, 72.5s on Windows/Python 3.14.7.

Fresh read-only `probe_web_live.py --watch-cards --prompt-token-mix --detail`:

- First run alongside Full verified feature exports (three known rows), one owner,
  two advancing SSE streams and detail freeze, but **FAILED overall** at shutdown:
  one `cost-guard-account-quota` daemon was still in Claude metadata initialization.
  Host close took 0.3843s. Existing account close's shared 200ms join budget does not
  wait out an in-flight external-provider request (20s metadata-control timeout).
- Decision Delegate authorized one unchanged hidden repeat after Full, and a
  conditional exception only if the same shutdown failure persisted with all feature
  checks passing. **That conditional exception was not needed**: the repeat passed
  in 35.164s, with zero tracked `cost-guard-*` threads or multiprocessing children
  remaining, host close 0.1644s, one owner/two verified streams, preserved origin,
  one active/two history cards, one row/card, at most four pending captures, and
  consistent frozen detail. No lifecycle/provider configuration or assertion changed.
- Five real rows exported valid known mix; neither 12-second observation window
  captured a natural call-count/mix change. Real-source transition timing is therefore
  unverified, not PASS. Native V2 and LiveConnection/DOM regressions prove controlled
  transitions separately. The probe started no model calls and left shared OpenCode alone.

The resource observation counts only `cost-guard-*` threads and tracked multiprocessing
children. It does **not** inventory Claude metadata helpers/subprocesses, so it is not
proof of zero owned OS processes or eventual helper cleanup. Shutdown cancellation
also generated one instrumented Daily-history error per run; neither run claims a
complete Daily campaign. Those are not token-mix or detail assertion failures.

These browser cases use a synthetic loopback fixture and fresh owned headless profile,
not personal browser state. They select the actual light/dark CSS branches, not OS theme
switching. Physical touch/input, screen-reader behavior, macOS/native fullscreen and
real-source browser/SSE timing are not independently verified. No model call, login,
visible desktop action or shared OpenCode stop is authorized or performed by the probes.
