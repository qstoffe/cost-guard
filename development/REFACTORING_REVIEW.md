# v80.34 performance and structure review

## Scope and authority

The authoritative baseline was the locally delivered v80.33 filesystem, including all earlier uncommitted work, copied before editing. No Git restore, dependency, cache-generation change or remote operation was used. v80.32/v80.33 ownership splits, growth ratchets and the code map remain; this pass targets execution speed, Watch robustness, Diagnostics relevance and test cost without a second analysis path.

## Measured hot spots and fixes

| Hot spot (live V2 data, 60 roots) | Owner and fix | Effect |
| --- | --- | --- |
| ~26 ms per V2 request opening a fresh connection | `opencode_v2_transport.py`: bounded pool of keep-alive loopback connections, one retry on a service-closed idle socket | ~0.3 ms overhead per request |
| 0.5M regex calls resolving model identities | `PricingCatalog` memoizes identity/closest resolution per immutable instance | resolution leaves the profile |
| Two full catalog listings per snapshot | `opencode_v2.py` reuses a <=2 s old complete catalog as the before-bracket; mismatch retries fresh | consistency proof unchanged |
| Watch startup hydrating 20 mostly idle roots | `watch_root_is_quiet`: only stable cached analysis (never running work) with nothing since start is skipped | 6.2 s → 0.65 s |
| Resync hydrating all history roots | `_changed_roots`: hydrated + changed + hinted roots | 13 s → 1.4 s |
| Sequential availability/Claude helper waits | `AvailabilityPrefetch`; Claude helper stopped on a non-daemon cleanup thread | report 2.1 s → 0.65 s |
| Watch discovery network reads on the main thread | `WatchModelDiscovery` check worker; main thread applies results | no poll stalls |

Parallel message hydration was measured and rejected: the local service serializes responses (20 roots: 736 ms sequential vs 597 ms with 8 threads), not worth the complexity.

Post-v80.36 behavior-neutral cleanup (median of 5, captured live snapshots analyzed offline):

| Hot spot | Owner and fix | Effect |
| --- | --- | --- |
| Trace entries, sorted prompt events and active compaction re-derived per prompt (quadratic per root) | `causal.py`: one `_RootTimeline` per `build_prompt_records` pass | 74 live roots 252 → 92 ms; largest root 60 → 12 ms; synthetic 500-prompt root 1.72 → 0.23 s |
| Cache store deep-converted nested entries with `asdict` only to discard them | `analysis/cache.py`: flat field copies; nested values serialized once | 74 live bundles 90 → 31 ms; byte-identical JSON |

Analysis records (2,528 across fixtures/live variants), cache JSON and Watch rows/markers over replayed live snapshots hashed identically before and after. Watch's per-second status path (≈2 ms for 20 hydrated 200-prompt roots) was measured and left unchanged.

## Behavioral evidence

Baseline (v80.33 copy) and current trees rendered the same live data against one shared cache: Watch initial frame and token mix, and normal, all-models, sessions, session-detail and date reports were byte-identical. New regressions cover pooled transport reuse/retry/bounded idle sockets, overlapping discovery checks, the stuck Claude helper not delaying answers, Watch resync scope, and the numbers-only Diagnostics Watch smoke.

## Tests and tools

Full runs concurrently with its slowest files first (151 s → 32 s). Validator-negative checks call their owning check on a package copy instead of the whole validator subprocess; builder regressions are their own module. The validator parses each file once per run. Fake V2 services, the V1 database and package copies are fixtures; test-to-test edges fell from 43 to 33. Fake services now drop keep-alive sockets on stop, matching a real process exit.

## Remaining bounded opportunities

Server-side message serialization now dominates hydration. `collect_diagnostics.collect` (159 lines) and the release builder's double clean-extract Full run are the next tool costs. Causal attribution still scans messages/events linearly per prompt inside the legacy `build_prompt_record`; with snapshot-wide inputs shared it is no longer dominant. It and prompt rendering remain behavior-sensitive legacy routines; characterize before splitting. Keep this review current in place.

## Live-proof limits

Live checks were read-only: headless report/Watch probes and Diagnostics against the shared V2 service, never stopping it. No interactive terminal/UI, native macOS, sleep/wake or Ctrl+C session was exercised.
