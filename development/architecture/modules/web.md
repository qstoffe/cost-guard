# Optional Web runtime

Source revision: e6b2ad827f3f3681123e6ba1eac292b5dc8f31c3
Checked revision: e6b2ad827f3f3681123e6ba1eac292b5dc8f31c3
Last checked: 2026-10-30
Status: current

## Responsibility and ownership

`src/web/http.py` owns bounded loopback HTTP, fixed assets and routing; `src/web/security.py` owns one-use bootstrap/HttpOnly sessions/CSRF; `src/web/jobs.py` owns finite admission, process isolation, progress, cancellation and retention; at most 64 progress messages drain per host turn to prevent scan backpressure without starving control/Live. `src/web/composition.py` creates fresh canonical ReportApplication integrations.

`src/web/assets/app.js` owns finite refresh/stale/cancel state and memory-only observations; unified Models/Accounts reuse one frozen normal report. `src/web/assets/reports.js` owns scope forms and explicit-only deep-history admission. `render.js` presents DTOs with exact Decimal/vector sorting; generic reports retain presentation search/50-row paging, while Models has independent catalog/version filters and complete document-scrolling rows. Totals never come from cells. `session.js` owns Snapshot/Live detail, canonical DOM identities, anchored paging, selection/focus protection and follow-latest. `src/application/session_detail.py` round-robins captures on the Web adapter's isolated single detail lane and returns frozen revision-aware pages/full totals. `src/reports/session_history.py` retains canonical evidence outside durable caches; omissions freeze lifecycle/time rather than falsely complete rows. Unchanged running evidence reuses attribution/valuation. Web→application→reports is unchanged; missing/archive/outage is not empty success. Scope/cache/route inventory: `docs/web-beta.md`.

`src/web/host.py` owns shutdown of HTTP/jobs and one `src/application/live.py` thread; GUI run/close stays on main. Composition transfers the Watch service to `src/watch/acquisition.py`; tabs only read detached values. Live persists without tabs, preserving engine-start origin and independent account cadence. Finite reports never borrow/close that context. Unexpected faults reach main RuntimeErrors (managed logs outside checkout); children monitor their exact parent sentinel. OpenCode is never stopped.

LiveRuntime requests optional driver cancellation before joining. Web's
`watch/source_reads.py` tracks only its isolated in-flight sources; cancellation
retires their V2 transports before pool joins, including late service admission.
V2 buffered reads use a cancellation-aware raw socket wait because cross-thread
socket shutdown alone did not wake a timed Windows read in the causal fixture.
Original per-read timeouts remain intact; idle connections and response bodies
remain owner-closed, without a daemon escape or shared-service stop. Daily history
uses the existing four-root slices and authoritative shared V2 brackets, rather
than one complete catalog fetch per root. Finished-plan publication, retained
history, native periods, revision proof and CLI cadence are unchanged. Probe-only
phase observations and primary-plus-cleanup exceptions are development evidence,
not a production telemetry or timeout/retry system. See
[lifecycle findings](../../journal/web/live-lifecycle.md).
Account close additionally reaps idle quota workers within one shared 200ms budget;
it does not extend or wait out external-provider HTTP. The real probe rejects any
remaining owned worker, not just a live serving/publisher thread.

`src/web/events.py` publishes immutable full live/progress/terminal state with instance-bound IDs, 32-event/8 MiB replay and 2 MiB publications. `src/application/live_projection.py` allowlists Watch/tool/skill/context, subtotals and run/Today (not normal month/billing). `src/web/assets/live.js` owns one cookie-authenticated EventSource per tab. Gaps require HTTP resync; duplicates/older events cannot reset values; old instances require authorization. Terminal notices stop retry across gaps; offline retains evidence, never invents completion or launches servers.

`watch/running.py` aggregates distinct canonical in-progress focal prompts once per
Web publication, excluding compaction/history/placeholders/terminal grace. Count,
prompt-only CCost and maximum canonical duration travel together with completeness
and pricing state. Empty success differs from missing/partial acquisition; source
capture failure freezes retained card duration. `assets/mini.js` owns one explicit
Document PiP session per owning document, independent DOM and route lifetime. It
consumes app-level Live/health/settings directly, without another connection, auth
or acquisition owner. Window-identity checks reject stale callbacks/replacements;
main pagehide ends the session. The PiP document's timer only detects stale
publications, never extrapolates duration; repeated progress/snapshots cannot
refresh its epoch. External `mini.css` reuses `app.css` theme tokens under unchanged
CSP. Primary subscription costs reuse the indexed native-period history lane and
stable server primary selection, with estimated/partial attribution retained.

`src/web/lifecycle.py` owns deliberate launcher restart, overlap coalescing, bounded readiness/stop and detached spawn. `src/web/instance_state.py` owns canonical checkout/user identity, transition and lifetime OS locks, private atomic records and bounded allowlisted lifecycle diagnostics. `src/web/process_identity.py` owns native birth/image proof and safe termination handles. `src/web/change_guard.py` owns the allowlisted five-second runtime metadata baseline and terminal source_changed state; it never reloads/restarts code.

`src/web/native_windows.py` owns same-process main-thread GUI integration and one asynchronous registered-browser handoff. `src/web/win32_tray.py` owns typed in-box Win32 resources/message dispatch and Explorer taskbar recovery; `src/web/tray_icon.py` owns the original source-rendered artwork. `src/web/windows_launch.py` and `src/web/windows_launch.ps1` own Beta-only Python/configuration/native preflight and sanitized failure feedback; stable terminal launchers do not import them. The Windows Beta batch waits synchronously for PowerShell's launch status; indeterminate activity spans bounded Python discovery and streamed startup stages until validated ready plus the OS browser-open result. The managed pythonw host remains detached/tray-owned, never console-owned; exit does not prove browser first paint. No compiler/cache/daemon is added. [Earlier hidden-delegation evidence](../governance/verification/windows-handoff.md) is historical, superseded by FR 000537.

`src/web/startup.py` owns fixed, flushed, elapsed-time launcher stage text shared by Windows/macOS. Lifecycle's optional progress sink reports arbitration/restart/host/browser boundaries without receiving secrets. PowerShell drains stages privately and prints one `Starting CostGuard web...` label, updating only a spinner cell at 120ms intervals through discovery and handoff. Progress panels are suppressed; redirected/noninteractive output stays plain. A finally block clears the cell before errors or exit. Browser startup is static branded HTML until authorization; initial report activity remains separate from HTTP/source/account readiness. No new supervisor, auth route, acquisition owner or dependency boundary is introduced.

`src/web/native_macos.py`, `macos_status.py` and `objc_bridge.py` own the experimental main-thread NSStatusItem, typed 64-bit callbacks/default-tracking pump, host-loss dismissal and asynchronous `/usr/bin/open`. `macos_launch.py` preflights in a bounded child; `macos_app.py` uses in-box osacompile for the optional fingerprinted/cache-verified Finder app. No new dependency/server owner. Native acceptance remains pending; exact limitations are in `docs/web-beta.md`.

## Public contract

`src/web/settings.py` is the sole write exception: `webSettings.theme` (`classic`
default or `web`) and `webSettings.ccostDisplayUnit` (`credits` default or `usd`)
in this checkout's `config/user-config.jsonc`. `config.validated_values`
shares startup validation, normalization and color resolution; neither merged
defaults nor CLI colors are serialized. Bounded JSONC token offsets preserve every
unrelated byte; duplicate keys and malformed/unsupported settings fail safely.
Owned/non-reparse paths, 1 MiB bounds, private same-directory temporaries, in-host
serialization and last-moment file identity/byte comparison precede atomic replace.
This is ordinary editor-conflict detection, not a hostile same-user race guarantee.

`GET /api/settings` and fixed `POST /api/settings/theme` / `POST /api/settings/ccost`
expose only those enums and allowlisted error codes,
behind existing Host/Origin/session/CSRF/body/stopping guards. Early HTML selects
the effective theme before CSS paint. `assets/settings.js` owns the sole native
two dropdowns under Web settings and confirmed-only CSS/display-token switching, rollback and
keyboard focus recovery. `#/settings` reads on entry, never submits report jobs,
restarts the host or polls. Other tabs converge on their next read, not a broadcast.
Explicit nested theme overrides legacy user `webTheme`; normalization happens before
shipped nested defaults merge. Web CCost never follows CLI `ccostDisplayUnit` after
promotion. Only separately approved promotions get independent Web fields; other
settings remain shared. CLI/Watch settings and acquisition stay unchanged. Tests: `test_web_theme.py`,
`integration/web_theme.cjs`, and `integration/web_views.cjs`; evidence/limits:
[Web settings verification](../governance/verification/web-settings.md); historical
[theme verification](../governance/verification/web-theme.md).

`cost-guard-web.py --foreground` is explicit icon-free developer mode, independent of managed discovery and CLI. Only 127.0.0.1 with an assigned port is supported; exact Host/Origin and authenticated sensitive reads are mandatory. Standard-library only, no installation, updater, generic proxy/shell/filesystem routes or browser-side calculator. Accounts/source/analysis readiness remain independent of HTTP-shell readiness.

`windows/Beta/Cost-Guard-Web.cmd` and experimental `macos/Beta/Cost-Guard-Web.command` accept only approved adapters. Readiness requires a usable icon/event loop; GUI failure cannot advertise an unmanaged host. Native preflight precedes restart. Open uses the registered browser; Exit stops only its matching host. Detached handles/private cwd, no packages/downloaded compiler/service/autostart. macOS/Finder/Gatekeeper remains unverified; in-box osacompile is optional, never an SDK install. Mocks are not native proof.

Overlapping clicks coalesce; deliberate later launches restart. Private lifetime locks and nonce/PID/birth/image/port/build/schema/control records prevent duplicate or foreign ownership. Corrupt state is conflict; reused PIDs are never kill authority. Windows stale retirement (including inaccessible reused PIDs) requires the existing lifetime lock to be free under transition serialization, plus an unchanged full record. Every legacy schema-1 managed host already holds lifetime before publication through cleanup; an open Windows lock file cannot be replaced/deleted. No boot metadata, clock inference or schema extension is needed. Busy/unavailable/unsafe proof preserves state; no old control secret is sent on recovery. Lifetime releases for child admission, while transition stays held through readiness; the exclusive lifetime lock also prevents delayed children from creating a duplicate host. Non-Windows identity/termination policy is unchanged. Graceful stop allows ten seconds; forced stop requires a revalidated Windows handle/Linux pidfd (macOS refuses). Other checkouts, CLI, browser, unknown port occupants and OpenCode are never stopped.

Private /control/status, /control/stop and /control/open require a separate secret header, exact Host, empty body and no Origin/Cookie. No control secret reaches browser storage or normal logs. Open issues a fresh one-use fragment without invalidating same-instance browser sessions; old-instance cookies/control fail against replacements. Browser-open failure is distinct from server failure and retryable via native Open.

Twelve HTTP slots admit four streams; ordinary requests have five-second absolute deadlines. Healthy authenticated streams have no rotation timer; two-second writes, ten-second heartbeats, per-turn authorization and three-second native reconnect remain. HTTP health cannot mask an interrupted stream. Connected status is compact; actionable non-sticky notices retain expandable observation details. [FR 000532 evidence](../governance/verification/web-live-stability.md) records real-source soak and fault checks. Finite work: four outstanding jobs, one process, sixteen results, 8 MiB/result, 120 seconds. Detail admission: sixteen observed trees, thirty-two handles; abandoned handles expire after five minutes, never rows/history. Stop publishes terminal state and joins owned work; retained `/api/live` stays readable while stopping. DTOs retain decimal strings/null/provisional values, not raw errors. No same-user-malware boundary.

Guard membership/mtime_ns/size covers shipped Python/assets/Beta launchers/root entries/manifests, excluding development/docs/user config/cache/log/bytecode/environment. No links are followed; stat errors retry the original baseline. Proven change triggers terminal source_changed/shutdown without browser acknowledgement. Identical metadata can be missed; no atomic-update/file-lock guarantee. Changed code needs manual launch.

Wire/adapter/resource details: `docs/web-beta.md`. No new permanent gate.

v80.89 stabilization: `security.py` names cookies by canonical checkout (not port); opaque session/CSRF values remain instance-specific. `observations.py` owns bounded numeric API/source/lifecycle facts, persisted through InstanceStore's private atomic `diagnostics.json` at most every five seconds plus shutdown. `development/tools/diagnostic_web.py` reads this checkout's snapshot and allowlisted lifecycle codes without importing/starting Web or reading the control record; bad/missing/stale facts are not readiness proof. Shutdown retains diagnostic facts after instance removal. No account/cache schema or analysis boundary changes. Full parity/native/privacy inventory and explicit platform limits: [stabilization evidence](../governance/verification/web-beta-stabilization.md).

`development/tests/test_web_views.py` / `development/tests/integration/web_views.cjs` exercise served assets/facade: navigation, exact sorting, filters, tiers, independent accounts, deferred history, long lists and frozen/stale/empty/missing/hostile-text states. Node is optional VM tooling, not visual/assistive-technology proof.

The shared numeric display seam is `src/display.py` / `src/numbers.py` → terminal and `src/application/display.py` → immutable DTO `display` / `display_roles` → `render.js`. Raw exact values remain separate sort keys. Application never imports terminal presentation; formatting never acquires or values usage. `development/tests/test_web_display.py` and `development/tests/integration/web_display.cjs` pin CLI-derived goldens. The [per-view display baseline](../governance/verification/web-display-parity.md) distinguishes formatting coverage, browser-only interactions and page-specific remaining work; it is not visual acceptance.

FR 000528 adds sparse `display_units.credits/usd` tokens only where CCost text differs.
`render.js` owns weak DOM text bindings; file-backed Web Settings selects the unit before
report/Live startup and synchronizes visible and detached detail roots. Switching changes
text nodes, not tables, sort keys, report identities or acquisition. Session/Watch presenters
bind summaries, subtotals and context amounts too. Report projections retain structured
date-range and provider-only note costs rather than parsing formatted prose in JavaScript.
Reload/fresh tabs read the saved Web-only unit; CLI/native quotas/billing stay independent.
Architecture boundaries are unchanged; journal assessment: no-update. Evidence and explicit
browser/platform limits: [historical selector verification](../governance/verification/web-ccost-toggle.md)
and [current Settings verification](../governance/verification/web-settings.md).

FR 000537 unifies the former Overview and Models at `#/models`; `#/overview` and `#/models/all` replace legacy history entries, preserving bootstrap erasure and Models keyboard focus. Exactly Publisher/Model/Relative CCost/Release date fill main-content width with intrinsic subgrid tracks. All matching rows scroll with the document; narrow screens alone use horizontal overflow. Models has no account cards, search, pager, catalog links, native-rate column or superseded fading. New Models and two accessible checkboxes precede the table; collapsed More information and matching Price Promotion follow. CCost selection now belongs only to Settings. Accounts retains full shared acquisition/data. Other routes retain their controls and scroll contracts.

One opt-in `ModelCatalogProjection` freezes full catalog, selectable publisher/name membership, notices and candidate-local supersession from the same acquired sample, without new availability/history/account calls. Every filter combination uses the same full-catalog cheapest-positive base; CLI ranking/denominator remain unchanged. Defaults: all-priced off, latest-only on, exact Relative CCost descending. Candidate scope precedes conservative supersession and stable exact tier-vector sorting; missing ratios/dates stay last. Shift mouse/keyboard supports ordered multi-sort with primary-only aria-sort; ordinary click/touch replaces keys, with no persistent additive mode or extra sort control. Unknown prices remain rows; unverified fail-open and verified-empty remain distinct, never subscription entitlement proof. Prepared tokens align tiers without browser valuation.

`app.js` retains approximate honest initial progress and heartbeat-stable frozen DOM. `test_web_models.py`, `test_web_overview.py`, `integration/web_models.cjs` and `integration/web_views.cjs` cover filters, uncapped rows, exact tiers, warnings, route/focus and shared acquisition. `integration/serve_web_models.py` is a bounded loopback fixture for the integrated browser; explicit-browser `integration/probe_web_models.py` requires independent approval. Historical [Overview](../governance/verification/web-minimal-overview.md) and [Models](../governance/verification/models-display-parity.md) results are not current UI acceptance; [current evidence](../../journal/web-overview.md) distinguishes actual checks from physical/native limits. No security/lifecycle/CLI valuation boundary changes.

## Allowed dependencies

Normal loading observations additionally allowlist a `stage`: sampling, availability,
comparison/catalog, quotas, account cache/load/analysis/projection, then application
packaging. They retain source-neutral phases/counts for CLI compatibility. Sampling
reports completed roots without inventing a denominator; counted cache/analysis/model
units report after completion. `jobs.ProgressRelay` bounds child publications to one
latest observation per 100ms plus final flush; host-assigned per-job sequences reject
stale polling/SSE labels. Each consuming stage owns its own estimated band, without
serializing the existing availability/account prefetch. Blocked source batches,
provider waits and projection calls without internal observations can pause honestly.
Only receipt of a full acquired result paints 100%; partial/error/lifecycle semantics
and frozen-navigation acquisition remain unchanged. Focused tests and headless real
Normal-workflow browser fixture: `integration/web_minimal_overview.py`.

Accounts' Normal-only detailed mode reuses `overviewAccounts` and shared card/semantic styles, not a new acquisition owner. `src/display.py` now owns the unchanged CLI `format_reset`, re-exported by terminal accounts; `with_display` propagates frozen `now_ms` to quota reset tokens in the configured timezone. Exact raw fields remain untouched. `test_web_accounts.py`, `fixtures/account_views.py` and `integration/web_accounts.cjs` cover equivalent CLI/DTO/DOM states, native amounts, periods, Pace and private-field exclusions. Explicit synthetic browser/keyboard evidence and its limits: [Accounts parity](../governance/verification/accounts-display-parity.md). No application/presentation import, report scope, formula, freshness or source/privacy boundary change; journal assessment: no-update, these durable owner facts suffice.

FR 000542 replaces Web's retained-row table with `watch.js` keyed prompt cards;
`watch/cards.py` owns uncapped active membership, observed grace and top-five
actual-prompt history. `reports/watch_capture.py` preserves canonical row anchors/context
evidence while `cards.py` selects exactly one focal/latest actual prompt per card.
No dedicated complete-session totals phase/state is acquired. `watch/card_workers.py` admits four isolated services,
sources and caches, no queued futures or per-card detail leases. One session's
capture/analysis is shared across its concurrent cards. Revision refresh retains
visible history membership and coherent metrics until replacement; collapsed history
uses the same scheduling. Canonical prompt background fields feed activity DTOs.
Only active/top-five snapshots are retained; catalog revisions/generations reject
stale results. Source capture/analysis is necessary per session, not streaming.
Capture fairness uses successful admission order, not result time or a revision-reset
timestamp. Invalidated/delayed captures retain their turn; changing early session IDs
cannot repeatedly overtake a retained running card waiting to observe retirement.
The active/history rotation, four-worker bound and canonical lifecycle are unchanged.

`watch/web_coordinator.py` adapts the existing coordinator, leaving CLI hydration
and retention unchanged. It isolates account-history aggregation and Sessions
detail in separate single-worker lanes; native account acquisition retains its
existing scheduler. Live owns publication/lifecycle and the shared EMA, measured
from actual capture work, not just catalog admission. `application/live.py` calls
the optional detail adapter without importing Watch. `live_projection.py` exports
minimal detached card DTOs so 100 one-row cards fit the existing SSE bound.
`/api/status` exports the process-loaded `DISPLAY_VERSION`; the persistent header
uses it only after authorization, without a new poll or source-file reread.
Watch account DTOs carry each actual quota's associated period cost and canonical
pace from `QuotaPeriodProjection`, not label-based browser joins. Native monthly
history shares the existing single-worker account lane and revision reuse. The
subscription subgrid aligns title/Today/primary label/bar tracks; complete primary
reset/pace precedes any secondary-only divider. Title bands use theme tokens while
body values stay left aligned; Accounts detail semantics are unchanged.
`watch.js` uses Started sequence/time, preview-only ellipsized flexible cells,
intrinsic non-Prompt subgrid tracks and horizontal overflow. History alone has a
restrained frame/40vh cap; keyed disclosures retain focus/scroll. Running yellow,
activity gold/brown, red failures and context gold/orange have separate theme roles.
`render.js` scopes account-detail cleanup through its Watch-only flag; Accounts,
Models, settings, navigation and security are unchanged. User-visible scope and
failure semantics: `docs/web-beta.md`. Current evidence and explicit native/pixel
limits: [Watch cards](../../journal/web/watch-cards.md). The older
`probe_web_watch.py`/`web_watch_browser.js` table probe is historical, not current
acceptance; use approval-only `probe_watch_cards.cjs` and the integrated-browser
`serve_web_watch.py` fixture, plus read-only `probe_web_live.py --watch-cards --detail`.

HTTP/security/assets and lifecycle/process/state/guard depend on standard library and their Web owners. Jobs consume shared application/report contracts. Composition alone wires concrete source/config/cache/pricing/providers and the Watch acquisition driver, never CLI dispatch/source wake. LiveRuntime consumes that supplied driver and exports immutable values; application/reports never import Web. CLI and Diagnostics do not import Web.

## Entrypoints

Runtime: `cost-guard-web.py`, `src/web/main.py`, `src/web/host.py`, `src/web/composition.py`, `src/web/http.py`, `src/web/assets/index.html`, `src/web/assets/app.js`, `src/web/assets/session.js`. Supporting lifecycle/security/process/asset owners are named above.

Native entries: `windows/Beta/Cost-Guard-Web.cmd`, `src/web/windows_launch.ps1`, `macos/Beta/Cost-Guard-Web.command`, `macos/Beta/launcher.applescript`. Generated applets stay outside Git, source/product/OS/architecture/Python-fingerprinted and hash-checked; failures preserve the command fallback.

## Tests

`development/tests/test_web_live.py` covers shared CLI/global projections, terminal transitions, partial pricing, midnight/DST, source recovery and hint resync, account-only publication, detached exports, replay/overflow/old instances, actual HTTP stream bounds/terminal delivery and stop beside a slow finite report. `development/tests/integration/web_live.cjs` exercises client ordering/offline/terminal/safe rendering in an optional Node VM, not a browser. Read-only `development/tests/integration/probe_web_live.py` observed V2, one owner/two streams, preserved run origin and joined shutdown on Windows/Python 3.14 on 2026-10-26. No inference, shared-service stop or native/visual/macOS acceptance is implied.

`development/tests/test_web_lifecycle.py` covers metadata changes/exclusions/faults, private state/locks/process identity, concurrent launches/restart, control/browser separation, main-thread/cleanup and force-stopped parent/blocked child. It uses an idle acquisition fixture, never live providers. `development/tests/test_runtime_errors.py` retains execution-root inventory. Windows process handles/locks are exercised; GUI assertions are not native tray/macOS proof.

`development/tests/test_web_runtime.py` / `development/tests/fixtures/web_reports.py` own wire/security/DTO/bounds/cancellation; `development/tests/test_application_reports.py` owns calculator parity. Read-only `development/tests/integration/probe_web_lifecycle.py` starts/stops only its own host. `development/tests/test_windows_web.py` covers adapter failure/readiness/Open/Exit, PowerShell discovery/arguments and private logs without UI. Approval-only `development/tests/integration/probe_windows_web.py` covers native menu/WM_COMMAND, browser failure, shutdown, transient consoles, overlap/restart, old-host preservation, source-change, independent Watch and spaces/Unicode ZIP launches. Windows 11/Python 3.14 observations date to 2026-10-26; physical mouse/visual/macOS acceptance remains untested. No inference or new gate.

`test_web_diagnostics.py` checks real two-checkout HTTP cookie-jar coexistence, bounded/allowlisted diagnostic export, missing/corrupt/oversize facts, write failure and retained shutdown evidence; replacement credential rejection is in `test_web_runtime.py`. `integration/probe_web_bounds.py` measures 5,000 synthetic replay publications/three simulated tabs and virtual authentication expiry, not physical suspend or hours-long soak. Native source-change probes must not overlap real-source probes of the same checkout.

`development/tests/test_macos_web.py` / `development/tests/test_macos_app.py` cover typed callbacks/faults, main-thread/tracking timers, preflight/readiness/cleanup, asynchronous actions and cache/quoting/rebuild failures without AppKit/UI. Approval-only `development/tests/integration/probe_macos_web.py` was not run here. Finder/Gatekeeper/clone/ZIP/executable-bit/no-Terminal/browser/tracking/source-change/orphan/CPU-architecture checks remain pending as documented in `docs/web-beta.md`.

`development/tests/test_web_session_detail.py` / `development/tests/integration/web_session.cjs` cover 100/1,000/10,000-prompt first/middle/latest access, full totals, bounded pages/DOM, strict timestamp windows, unchanged work, row identity/anchor/focus/selection, transitions, omissions/outages/reconnect and late children/partial prices. `development/tests/integration/probe_web_live.py` with --detail --reports observed V2 detail/freeze, normal/all-models/sessions/date completion and cancelled deep history, preserving one owner/two streams/run origin and joined shutdown on 2026-10-26. No browser or model was invoked. Copy/selection covers the fetched page; physical layout and screen-reader proof remain unclaimed.

Remaining report presentation shares `display.history_tokens` for configured prompt clocks,
Next Ictx guidance and CLI historical mix category cells. `projection.token_mix` exports the
exact aggregate cost separately for sorting; JavaScript never totals displayed cells.
Session summary/footer use the same frozen block tokens; Freeze/Follow forces a mode-aware
redraw without changing canonical row IDs or page ownership. Date range prose omits raw
epoch boundaries. `test_web_remaining.py` / `integration/web_remaining.cjs` compare the same
CLI fixtures, including partial/unknown mix coverage. Approval-only
`integration/serve_web_remaining.py` serves the actual app over synthetic HTTP fixtures,
never a product host or provider. The [owner matrix](../governance/verification/remaining-web-parity.md)
records Windows built-in-browser inspection and remaining native/assistive limitations.
Architecture boundaries are unchanged; journal assessment: no-update, these owner facts
and the focused evidence are sufficient.

Session-detail scroll retention uses the inner `.table-scroll` owner and captures
the visible row after the HTTP response, immediately before DOM mutation. Internal
scrolling away from the bottom disables follow; background retention never calls
document scrolling. Frozen reports also retain their actual DOM during host-health
checks unless the report, search, view or output changes. This applies to every
finite report, not only Overview: health is not a new snapshot. Session detail's
attach is also idempotent for its current parent, avoiding a disconnect/reinsert
that loses native focus/scroll during health updates. The deterministic
pending-response/geometry/heartbeat regressions and browser evidence are recorded in
[table-scroll investigation](../governance/verification/web-table-scroll.md).

## Native launcher maintenance notes

Windows startup maps native access denied separately from unavailable identity and preserves allowlisted state/coordination/control/readiness causes through console, existing dialog and lifecycle log. Diagnostics exports the latest bounded lifecycle event independently of historical host snapshots. `stale_instance_recovered` is retirement evidence, not an active ownership conflict. Regression tests cover legacy recovery, busy/unavailable proof, overlapping replacement, concurrent record changes, native API error/handle mapping and privacy-safe feedback/export. Non-UI Windows observation and isolated fixture evidence: [stale recovery](../governance/verification/windows-stale-recovery.md). Journal assessment: no-update; protocol ownership remains here, with no new coordinator or layer boundary.

PowerShell 5.1: preserve `[array]$pythonArgs` (scalar `-3` splatting lost the command in a real probe). Use DirectoryInfo.SetAccessControl/private DACL, not Set-Acl requiring SeSecurityPrivilege. AST-extracted production functions/assignments test real py.exe handoff/private logs. Never elevate or change global policy. These owner facts replace a redundant journal log; historical evidence is unchanged.
