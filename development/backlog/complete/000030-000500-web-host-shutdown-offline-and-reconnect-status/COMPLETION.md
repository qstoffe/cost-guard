# FR 000500 — delivery

## Outcome

Implemented in Cost Guard v80.99 (2026-10-28).
[Delivery PR](https://github.com/qstoffe/cost-guard/pull/85).
[Tested source candidate](https://github.com/qstoffe/cost-guard/commit/7cf5f37d6df1bd83d173a63db0aa13220dc9820a).
The original FR and selected bundle payload are preserved byte-for-byte; no attachments
were added. Native transaction advances ordinary/completion count to 30; retention prunes none.

## Changes and choices

- Persistent common-shell banner and Watch status distinguish source health, HTTP transport,
  reconnecting/offline, expired authorization, changed identity and intentional stopped state.
  Last authenticated host check/source timestamps remain distinct from frozen report/account data.
- Ten-second serialized authenticated watchdog and five-second request deadlines bound unknown
  loss detection, including initial connection failure. Idle/visibility/page restoration marks
  old data not live before revalidation. Existing one-stream replay/resync remains authoritative.
- Terminal pages retain readable report/Watch values, stop retries, disable acquisition controls
  and instruct manual OS-launcher use. API identity is pinned before accepting response data,
  including when a different tab renewed its host cookie. In-flight requests cannot restore
  a terminal page. No browser storage, secrets, host spawning or network scans were introduced.
- Repaired the empty-read/terminal-close SSE race. No CLI/Watch acquisition, valuation,
  source/account provider, private control credential or new sensitive-route changes.

Kept one browser transport owner rather than adding a server supervisor, service worker,
unauthenticated status route or per-tab acquisition. These alternatives would widen ownership
or privacy scope and do not solve authorized same-instance reconnection more safely.

## Verification

- Full deterministic suite: **112 files, zero failures**, four isolated workers, final
  functional run 45.0 seconds. New virtual-clock/stream-race regressions are in the full inventory.
- Working-tree product validator: **11 passes, zero failures**, four existing soft size warnings.
  Release metadata regressions after the midnight date update: **25 tests passed**.
- Actual **OpenCode Desktop built-in browser**: authorized Overview/Watch; source loss with
  HTTP up; injected request interruption and recovery/visibility revalidation; server session
  expiry; controlled response-identity replacement; actual abrupt owned-process exit; production
  menu/source-change stop and terminal SSE. Both views retained tables/rows and disabled
  acquisition on terminal/offline states. No external/headless browser was used.
- Real-installation read-only V2 probe: one owner/two streams, four rows/three accounts,
  preserved origin/advancing sequence; shell 0.046 s, source view 4.772 s. Owned workers joined;
  no model inference or shared OpenCode stop.

Detailed reproducible setup, cases and proof limits:
[Web connection evidence](../../../architecture/governance/verification/web-connection.md).
Early full-run failures were repaired causally: malformed-request replies no longer assume
parsed path state, the lifecycle test double carries its real nonce contract, and reload
test contexts await their own authorization/result rather than stale shared DOM. A failed
browser fixture report used the wrong Jobs method; corrected to the production snapshot API
and reran the browser cases. No assertions, budgets or protections were weakened.

## Exclusions, limits and knowledge assessment

No physical tray click, actual long OS suspend, physical launcher restart/new-cookie browser
combination, assistive-technology, narrow/dark viewport or native macOS proof is claimed.
Menu tests invoke the same production stop method; restart/security are independently covered
by existing lifecycle tests. Newly navigated dead-host URLs can show the browser's own network
error page; already-loaded dashboards mark the loss. A browser/OS suspension can delay timers.
These remaining physical/platform checks are not represented as PASS.

Journal **no-update**: no new reusable general engineering topic. Architecture boundaries/routes
**no-update**: existing Web/Live/security ownership is unchanged; current behavior and focused
evidence were updated in the owning Web documentation. Optional knowledge read rejected the
pre-existing oversized Web module; its consolidation is deferred, not a new gate or permission
to expand this FR. No Toolkit runtime/source was changed. All owned fixture servers stopped;
no eval workers or paid model calls were started. No release ZIP/tag/Release was generated.
