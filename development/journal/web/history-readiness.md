# Verified Earlier history — 2026-11-07

FR 000623, v80.203; baseline `c52c320400b98b4bae9e1a0143a5acabf4e72fc7`.

## Cause and implementation

Before implementation, fixed-catalog regressions failed because the first older
capture immediately became authoritative-looking history and refresh mixed old/new
cards. A Mini DOM fixture also rendered supplied candidates during loading. These
reproduce a causal mechanism, not the owner's exact private desktop chronology.

`WatchCards` keeps generation-bound scalar coverage after heavy captures are evicted;
`HistoryPublication` publishes at most five coherent cards only after complete,
revision-matched source coverage and representative availability. Active-status-only
changes invalidate coverage too. Captures from older generations/revisions cannot
certify winners. Source scope, catalog/proof epochs, original verification time,
checked/total and typed failure cause are exported once for both views. Cost-only
updates and UI ticks do not renew source proof. Removed/resumed roots invalidate
retained entries; Mini cannot resurrect its own cached rows.

Metadata is a bounded admission hint, never a finish-time upper bound. No safe
preexisting persistent supported-finish certificate was found: daily/account facts
have different populations and cannot replace global Earlier coverage. No second
scanner, raw-history ledger, extra threads or source writes were added. Cold startup
still needs complete coverage; this is correctness-first, not a cold-start speedup.
V2 per-root full-catalog revision brackets remain a real acquisition bottleneck.

## Executed evidence

- RED before code: fixed twelve-root provisional membership and mixed refresh tests;
  Mini loading DOM regression. GREEN after code, plus actual bounded workers with a
  delayed newer root, partial/failure/recovery, status-only resumption, timestamp/ID
  ties, representative/unknown ends, source generations, eviction and cost freshness.
- Final `run_tests.py --suite full`: all 155 test files passed, 107.6s. Includes an owned
  synthetic Web coordinator with blocked history: five actual Live publications advance
  active duration by four seconds; each acquisition/projection/publication stays below
  0.5s. Existing competing-report/HTTP/SSE/lifecycle checks pass. No private attribution
  to the finite dispatcher is established or claimed.
- `validate_package.py --working-tree`: zero failures; six existing advisory/design
  warnings (README/history/Web guide prose and legacy Python module sizes).
- Integrated browser unavailable (`browser.disconnected`); permitted hidden Edge with
  an owned profile ran the current `probe_mini_fit.cjs`: PASS, 204 layout cases,
  scale/real browser zoom 1. Includes actual Full/Mini DOM and Chromium accessibility
  trees for loading, halfway opening, verified five/three, qualified refresh/failure,
  source switch and no background resizing. Finished/local date/offset/DST/unknown,
  focus/keyboard/hover/touch, themes, units, widths and enlarged font/CSS zoom pass.
  This is not physical desktop, screen-reader or macOS proof.
  Re-executed against final product sources: PASS, 204 cases, seven check groups;
  `scratch:/mini-history-browser-final.json` (scale/browser zoom both 1).
- Standalone `probe_watch_cards.cjs`: PASS, 12 Full Watch cases across three themes
  and four viewports in hidden Edge 156.0.4314.58. Actual DOM/AX loading with grounded
  4/12 coverage and restored five-card publication pass alongside existing geometry,
  cost/context help, quota, focus and transition assertions. Three stale probe
  expectations were aligned with already-shipped capacity labels, quiet brief-stale
  refresh and simplified I/E reference-cost help; product behavior was not changed
  to satisfy them. Evidence: `scratch:/full-watch-browser/browser.json`.

## Fixed 2,700-root benchmark

`benchmark_history_readiness.py --baseline <above>` asserts independently known winner
IDs, current coverage/state, exact logical source-read counts and bounded retained
captures. Four-capture slices execute serially, unlike production background workers;
synthetic capture time is separated from synchronous admission/projection overhead.
The final run overlapped the full test suite; absolute wall times are not portable.

| Measure | Baseline | Candidate |
| --- | ---: | ---: |
| First visible history | 0.0673s, provisional | 20.8717s, verified |
| Complete capture endpoint | 17.6190s, no product proof contract | 20.8719s, proof observed/2700 of 2700 |
| Winner replacements without new activity | 674 | 0 |
| Cold / warm / changed-root reads | 2700 / 0 / 1 | 2700 / 0 / 1 |
| Revision checks | 8100 | 8100 |
| CPU | 17.5156s | 20.8594s |
| Peak traced bytes | 2469927 | 2837387 |
| Serial capture time | 6.0600s | 6.7006s |
| Max synchronous admission + projection | 0.0547s | 0.0688s |
| Retained heavy captures | 5 | 5 |

Proof has measurable CPU/memory overhead, not a demonstrated speedup. These small
synthetic trees do not measure physical disk/network/provider latency. The serial
slice duration is not a production Live-publication gap or account-latency metric.

## Installed-source limit and approved exception

The supported read-only `probe_web_live.py --watch-cards` **FAILED to reach final
verification** in its bounded 90s window: **20 of 2793 roots**, history unavailable,
typed `concurrent_source_change`. Final winners and time-to-first-verified history
remain **INCONCLUSIVE**, not PASS. Before cleanup, 32 captures finished (36 by
shutdown); one capture took 57.7292s. Live published 224 frames (maximum publication
operation 0.2863s); 342 authenticated live HTTP samples had maximum 0.2139s. Daily
published by 14.0446s. Host shutdown took 0.3009s without cleanup failures. These
candidate observations alone do not prove baseline-relative private latency parity.

**Decision Delegate approved a narrow verification exception:** real 2793-root final
winner verification and its elapsed readiness time need not be established before
delivery. A prolonged private archive scan is disproportionate and may still lack a
stable oracle. Truthful loading/unavailability is explicitly allowed by the FR;
On Hold would unnecessarily withhold the correctness improvement. No further private
archive-wide scan was required. Exact reconstruction of the original private incident
was already outside the FR's claimed evidence, not an additional waiver. Correctness,
deterministic gates, versioning and protected delivery were not waived.

Practical remaining limitation: a large/churning installation can remain Loading or
Unable to verify latest sessions. Prompt availability of the verified list there has
not been demonstrated. No source authentication failure, raw session details, model
calls, service restart/stop or physical desktop work is claimed.
