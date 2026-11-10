# Selected-V1 notice and Watch investigation — FR000670

2026-11-10; v81.20; implementation base `de228c45be5db3325eb13a5c18eb6e4dd173627a`.
This is scoped evidence, not a reproduction of the reported private installation.

## Source/publication ownership

`LiveRuntime._publish_frame` exports one non-sensitive `source_generation` enum
(`v1|v2|unknown`) from the active coordinator's established `SourceSelection.selected`.
A frame, successful acquisition and source observation time qualify it. Missing,
invalid or failed evidence exports unknown; startup/fault publications without the
field are likewise unknown to the browser. No source paths, configuration values,
registration data, credentials, process arguments or session metadata are added.

`LiveConnection` retains existing authenticated `/api/live` snapshot, one SSE stream,
instance/sequence replay and reconnect ordering. Only connected health passes an
allowlisted generation to `app.js`. One static `index.html` aside directly below
navigation is visible only for connected V1. It remains outside route-specific DOM
and Mini. Startup/source error/offline/reconnect/authentication/terminal/changed-instance
states hide it, rather than calling last-known V1 current. A fresh V2 state hides it.
ResizeObserver updates only root scroll-padding for the sticky aside's actual height.
No extra browser polling, endpoint, report job, source switch/wake or preference is added.

The source-selection, CLI, Watch, provider and export implementations are unchanged.
Architecture navigation is updated in `modules/web.md` and `modules/CODE_MAP.md`;
the user-facing support matrix is in `docs/web-beta.md#selected-source-compatibility`.

## Paired SQLite evidence

`fixtures/v1_watch.py` creates a synthetic supported V1 schema and uses independent
read-only `OpenCodeV1Source` instances. Actual `SourceSelector` selection and
`SourceStartup.prepare` agree on V1 under forced `v1` and `auto` with absent V2
registration. Healthy V1 never wakes OpenCode. Independent CLI `WatchCoordinator`
and genuine asynchronous `WebWatchCoordinator`/card workers/`LiveAcquisition` consume
the same database, including real writes from the fixture producer while open.

`test_v1_web_watch.py` covers twelve paired scenarios: auto/forced V1 × minimal/
plugin-rich × successful/cancelled/error termination. Each has initial, idle polling,
terminal/recent and Earlier phases. It compares canonical prompt lifecycle, context,
CCost/usage, counts, outcomes and running-tool duration, with no duplicated Web session.
The fixture includes repeated custom calls, a copied physical callID, opaque custom
metadata/part type, skill tool parts, pending and running tools, error output, child/
subtask sessions and compaction. Six physical tools remain six despite the copied
callID; long-running custom tool timing agrees (13 seconds after crossing the existing
10-second visibility threshold). Unknown plugin parts add no invented usage. V1
without registry proof does not assert a custom skill origin. Normal/All Models,
Sessions/Session, Token Mix, AI Stats and Comparisons build from V1 without changing
the source database bytes.

Two existing intentional presentation differences were established, not “fixed” by
changing CLI behavior: before any usage invocation exists, CLI duration is zero while
Web cards display the observed running prompt age; rich bounded invocation help is
Web-only, while shared tool counts/outcomes/timing match. Terminal duration values
match. Web history cards use a different focal/layout contract, not missing prompts.

A real loopback V2 fixture alongside healthy V1 verifies that the same auto request
selects V2 independently in CLI and host startup. Forced CLI V1 can intentionally
differ from auto Web V2. Existing `test_opencode_v2.py` also compares matched V1/V2
sessions/messages/events/invocations; the Full suite passed that canonical adapter
comparison. V1 lacks V2 event hints and native registry/status telemetry; source gaps
must not be mistaken for Web filtering. No narrow Web-only data-loss regression was
demonstrated, so no acquisition/normalization repair or unrelated FR was invented.

## Genuine host/browser evidence

`serve_v1_watch.py` composes actual SQLite acquisition, LiveRuntime, WebHost, private
authentication, HTTP, CSP, SSE, shipped assets and disposable Settings. Finite report
jobs are synthetic; fault-state wire injection is explicit and separate from the
unmodified V1 baseline. `probe_v1_watch.cjs` uses a new headless Chrome profile only;
no visible desktop, private browser profile, external URL or model inference.

- Auto fallback Chrome: PASS, five check groups, sixteen layouts.
- Forced V1 Chrome: PASS, five check groups, sixteen layouts; measured text contrast
  at least 4.5:1. Synthetic screenshots were inspected at 150% narrow width.
- All eight routes, Back/Forward, one top-level notice/one owner-page SSE, filtering,
  Mini open/no duplicate notice, actual SQLite terminal update through polling and
  Full/Mini publication passed.
- Pending/failed/V2/invalid enum, offline then authenticated reconnect, and stale
  other-instance SSE hide/restore behavior passed without stale V1 claims.
- Classic/Web light/dark, reduced motion, 360/1440 viewport widths at actual
  100/150% browser zoom, sticky/nav separation, overflow and keyboard target clearance
  passed. Chrome version was `157.0.8103.39`.

An Edge attempt failed to connect its CDP pipe (`Browser.getVersion` timeout).
An initial Chrome harness attempt timed out waiting on a background-tab animation
frame after opening Chrome Settings; explicitly foregrounding the owned headless
target repaired that probe. These failed attempts are not browser PASS; Chrome's
successful required real-browser coverage is the evidence above. Synthetic headless
layout does not claim physical-desktop proof or every third-party plugin combination.

## Workstation checks and bounded limitations

The real installation's `auto` selection was healthy **V2**, not evidence of private
V1 parity. No private V1 database or credentials were requested or exported.

| Check | Actual result |
| --- | --- |
| Full repository suite | PASS: 182 isolated groups, zero failures, 141.2 seconds |
| Latest strengthened V1 group | PASS: four tests including the twelve paired scenarios, finite reports, actual dual-source selection and generation allowlist/failure gating |
| Working-tree validator | PASS: zero failures; seven existing advisory prose/module-budget warnings, no raised caps |
| `probe_web_live.py --watch-cards --tool-outcomes --watch-seconds 90` | INCONCLUSIVE global-history verification; exit 1 `probe_watch_cards_timeout`; 869/3098 roots checked, 241 advancing Live publications, no provisional history published |
| Original default `probe_web_live.py` with generation assertion | Source enum/owner/HTTP/instance/two-stream/sequence checks succeeded; overall FAILED cleanup assertion `probe_owned_workers_remaining`, two provider quota workers still in flight at that observation |
| `probe_source_generation.py` | PASS with normal providers retained: actual selected V2 equals authenticated Live enum, one acquisition owner, two instance-qualified SSE streams, advancing sequence and unchanged run origin; initial/final remaining workers 0/0 and processes 0/0, natural retirement wait 0.0 seconds |

The last probe disables only the unrelated public benchmark and allows up to 45
seconds total for exact owned workers to retire naturally after ordinary close. It
does not kill workers, remove providers or change product deadlines. No shared
OpenCode service was stopped. The successful run does not explain the earlier
in-flight workers, prove universal cleanup reliability or certify actual quota values.

**Decision Delegate, 2026-11-10:** requested the providers-retained focused check and
then approved completion with journal-only treatment of incidental verification
limitations; no additional acceptance waiver, Suggestion or On Hold. Reason: source/
publication purpose and synthesized parity/browser acceptance are adequately proven;
global installation-history certification is outside that purpose, and neither the
timeout nor transient worker observation demonstrates a notice regression. Prior
failed/inconclusive runs remain exactly that, never retroactive PASS. No repeat Full
cycle was required solely for this bounded observation; subsequently strengthened
fixture assertions were rerun in their own group.

**Still unknown:** exact reported Web symptom, that environment's actual CLI/Web
source selection, plugin causation and full private-installation parity. The incident
was not reproduced. The support matrix distinguishes supported normalized behavior,
polling/native-telemetry limits, V2-only sanitized native export, provider-dependent
quotas and unverified plugin/installation combinations. These unknowns are disclosed,
not hidden behind the compatibility notice or claimed as a complete root cause.
