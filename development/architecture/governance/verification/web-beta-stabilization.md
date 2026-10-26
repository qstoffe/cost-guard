# Web Beta stabilization evidence

Date: 2026-10-26. Base: `99b0fc78f19da2d40bd74d3405a47d492153bf29`; candidate v80.89.
This scoped Beta milestone is not promotion, CLI retirement, an accounting audit or a permanent release gate.

## Completed mode-to-view inventory

All numerical comparisons use the **same normalized records, catalog, configuration, observation clock and scope**. `test_application_reports.py` compares the shared CLI ReportService with the detached application export; the existing focused analysis/report tests remain the independent semantic assertions. `test_web_views.py`, `test_web_session_detail.py` and their shipped-asset VM harnesses check presentation/facade integration, not a second calculator.

| CLI mode / Web view | Parity evidence and protected distinctions |
| --- | --- |
| Normal / Overview, selectable Models, Accounts | Both independent 100-priced-prompt samples, exact price tiers/ranking, native quota units/reset/Pace, fetched-at/error states, billed month and named period CCost scopes. Accounts share the retained normal observation, not a per-tab scheduler. |
| All models / full Models | Complete catalog, native I/C/W/O USD rates/thresholds, shared exact Decimal ranking; no selectable/account substitution. |
| Sessions N/all / Sessions form and table | Whole root/child totals, completeness/duration, archived availability; no total fabricated by summing pages. |
| Session / Snapshot and Live detail | CCost, billing/zero/unknown, provisional running values, request counts, token/cache mixes, main/child breakdowns, clone deduplication, compaction, effort, incoming/delta/next context and union duration. 151-row uncapped facade fixture and 100/1,000/10,000-row revision-paging fixtures; all logical rows remain available with a 50-row client page. |
| Date / Reports inclusive date/range | Same canonical range totals/context/duration; 23/25-hour Stockholm DST boundaries remain explicit. |
| Token Mix / explicit historical capture | Same distinct requests, per-model calls/prompts, I/C/W/O quantities/costs and price coverage, dependency-bound cache invalidation; navigation does not start scans. |
| Global/session Watch / global Live and complete Live detail | Same Watch acquisition seam, run/Today totals, row subtotals, lifecycle and account-only refresh; complete session detail uses report semantics rather than capped Watch rows. Engine-start run origin is not the CLI process's later start time. |

Frozen snapshots do not advance with wall time. Independently timed live screens may legitimately differ in running duration, newly observed requests, price/account freshness, run origin and availability; no formula was changed to make screenshots coincide. Neither quota observations nor positive reference CCost establish billed spend/account attribution.

## Reproduction and observed results

Windows 11 `10.0.26300`, CPython **3.14.7**, **AMD64**. No packages/compiler/SDK were installed; no model calls, private account/session dumps or shared OpenCode stop. Commands run in the isolated candidate checkout.

```text
py -3 development/tools/run_tests.py --suite full
py -3 development/tools/validate_package.py --working-tree
py -3 -S development/tests/integration/probe_windows_web.py --allow-native-ui
py -3 development/tests/integration/probe_web_live.py --detail --reports
py -3 development/tests/integration/probe_web_lifecycle.py
py -3 development/tests/integration/probe_web_bounds.py
```

Native Windows probe: real menu labels/message delivery, failed Open retry, Exit, HTTP-fault icon removal, transient console exit, detached survival/no console inheritance, overlap coalescing, deliberate restart, preflight tray failure preserving the old host, source-change shutdown, independent real CLI Watch survival and ShellExecute of a no-Git source copy with spaces/Unicode **passed**. Its in-process native startup ran with `-S` and external socket connections denied; this proves that bounded offline native-shell path, not every detached child's entire network lifecycle or a separately provisioned package-free OS. Windows needs no helper compilation. Default-browser handoff was exercised; physical Explorer mouse actions and visual quality were not.

Final Full suite: **105 files, zero failures, 41.4 seconds**. Validator: **11 passes, zero failures**, four pre-existing design warnings (README and analysis/context, reports/service, watch/coordinator); no budget was raised. The first Full run exposed an outdated HTTP-detail lifecycle fixture; supplying its required root/observation dependencies repaired it without weakening assertions.

Real V2 Live probe: one acquisition owner, two HTTP streams, preserved run origin, acquired/frozen detail, normal/all-models/sessions/date finite reports, deep-history cancellation and joined owned live/HTTP shutdown **passed**. Native restart probe simultaneously kept a real redirected CLI Watch alive. Standalone lifecycle probe separately checks CLI one-shot reporting against the same real installation. Native/source-change probes must run **sequentially** with other probes of this checkout: an initial overlapping run timed out in `/api/live` and then live shutdown while the native probe deliberately changed shipped-source membership; sequential rerun passed. The timeout is retained here, not represented as a successful first attempt or universal responsiveness proof.

Synthetic replay stress: **5,000 publications**, **3 simulated tabs**, **300 detached snapshots**, maximum **32 replay events / 526,976 encoded bytes**, **651,125 traced peak bytes**, **516.72 ms** on this run. A lagged client and foreign instance required resync; terminal source-change state remained readable. A virtual nine-hour monotonic jump expired authentication. These are finite operation/memory measurements, not a physical suspend or long-duration soak/latency guarantee. Existing real-HTTP tests bound four streams/twelve slots and prove stop alongside a slow finite report; session VM tests bound current-page DOM to 50 rows. Runtime has one live/account owner independent of subscriber count. No account/source acquisition is performed by replay or tab snapshots.

## Security, state and diagnostics audit

- **Fixed:** shared `cg_session` cookie names let a second checkout overwrite the first, because cookies ignore ports. Names are now canonical-checkout scoped; opaque session/CSRF credentials remain instance-specific. A real HTTP CookieJar regression authorizes two checkouts and preserves both cookies; deterministic replacement tests reject old credentials. This does not prevent same-user software from seeing host-wide loopback cookies.
- Existing real HTTP/asset tests exercise exact Host/Origin/Fetch-Site/CSRF, one-use 120-second bootstrap expiry/replay, framing/duplicate/traversal denial, safe hostile text, no browser-side credentials/control tokens, bounded streams and old-instance rejection. Public health exposes shell state only; private control requires its distinct credential and forbids browser Origin/Cookie. Cookies remain host-only, HttpOnly, SameSite=Strict and Path=/; loopback HTTP has no HTTPS Secure-cookie claim.
- SQLite remains **generation 2**, unchanged schema/namespace/account-refresh ownership. No Web-owned durable account schema was added. Existing `test_cache.py` proves generation coexistence without migration/deletion, WAL/busy timeout, concurrent readers/writers and first-sighting arbitration. CLI does not import Web or acquire its instance lock; Web lifecycle/diagnostic state lives in private checkout-keyed OS app data, not shared cache. Old caches, configuration and historical logs were not removed. WAL alone is not cross-version compatibility proof; incompatible future schemas must choose new disposable generations.
- Managed Web now writes an atomic bounded diagnostic snapshot at most once/five seconds plus shutdown: schema/product version, lifecycle/source state, capped transition/API counters and uptime. Diagnostics reads it and bounded allowlisted lifecycle codes without importing/starting Web or reading control state. No raw IDs/paths, titles/prompts, URLs, tokens/cookies, provider responses or uncontrolled exceptions cross this interface. Bad/oversize/linked files fail closed. Tests cover missing/invalid input, persistence failure, retained shutdown facts and secret filtering. Observed native snapshot survived `instance.json` removal with `source_changed`, schema 1, v80.89 and 5,059 ms uptime; lifecycle codes retained injected tray failure and shutdown history.

## Remaining Beta limitations / owner testing

**Unverified, not passed:** real macOS Intel/Apple Silicon AppKit, default browser, Finder `.app`/Gatekeeper/quarantine/executable bits, offline first launch, in-box osacompile progress/cache/rebuild, native crash/stale ownership and ZIP/Unicode lifecycle. Existing macOS tests simulate callback/compile/cache faults only. No Mac is available on this host. No downloaded compiler, distributed binary or security bypass is authorized.

Physical suspend/resume, hours-long soak, physical mouse actions, browser visual light/dark/narrow layout, selection/scroll geometry and screen-reader acceptance remain owner-platform checks. Synthetic clock jumps and Node DOM/VM checks are not substitutes. Stale/corrupt PID and occupied-port/no-kill behavior are deterministic lifecycle regressions, not a claim that every native crash was reproduced. Source-unavailable and OS API failures use fixtures/fault injection where noted. Current API result/time/stream/detail limits are explicit and can reject very large/slow histories rather than silently truncate them.

No concrete new owner UI feedback was supplied; refinements remain proposals, not proven defects. Keep root Windows/macOS CLI entries unchanged. Promotion and later Legacy retirement remain unnumbered suggestions requiring a fresh owner decision and newly allocated FR.

## Knowledge assessment

Web module/code-map routes updated for the cookie and diagnostic owners; analysis, reports, Watch, account and cache boundaries are unchanged. No new journal topic: these are current Web contract facts, not a reusable cross-project investigation. This evidence records measured limits without duplicating release history or raw private logs.
