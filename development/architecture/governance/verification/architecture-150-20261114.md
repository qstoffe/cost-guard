# Architecture assessment — milestone 150

Source revision: a874c664cc67d8b08be40debc7821b9317eef5ab
Checked revision: a874c664cc67d8b08be40debc7821b9317eef5ab
Last checked: 2026-11-14
Status: completed two-level static assessment; not runtime correctness certification

## Outcome

**Global runtime NO_CHANGE; independently justified local runtime NO_CHANGE.**
Representative normal/failure/recovery traces did not establish duplicate
coordination authority or a material local replacement with net conceptual benefit.
Working code was challenged against simpler targets, not protected merely because
tests exist. Preserve the modular monolith and its distinct proof/lifetime owners.

Development-only delivery corrects architecture navigation, refreshes the two-level
map and publishes this evidence/progress. No product, test, tool, dependency,
configuration, launcher, version, release or ZIP changes; no FR move or proposal
implementation. Only Architecture **120 → 150** advances after merge. Ordinary
count **150**, `lastOrdinaryId=fr/000705`, Test Health **135**, Performance **120**,
Session Learning **0** and its existing milestone-100 deferral remain unchanged.
That learning assessment is still deferred, not completed/PASS.

## Inventory and coverage

Read-only installed `maintenance_evidence.py inventory --repo-root <owned-clone>`
returned **1,397 text/config records**: 408 source-or-config, 613 documentation,
376 test; **370 binary/over-1-MiB exclusions**, **zero exact-byte duplicate groups**.
Scope is tracked plus nonignored untracked files, excluding runtime artifacts.
The largest text records are retained development measurement JSON, not runtime
orchestration. Counts/byte equality do not establish semantic duplication or dead
code; excluded assets were counted, not semantically reviewed.

`py -3 development/tools/code_inventory.py --json` parsed without importing the
product: **267 runtime Python modules / 40,141 lines**; development tools
**15 / 3,093**; tests **343 / 69,270**; nested fixtures **65 / 5,665** (not additive).
All 267 runtime purpose/size/local-import records were consumed in compact
projections, plus longest-routine candidates. Representative source reads appear
below; this is not a line-by-line audit of every module.

Browser inventory: **20 JavaScript, two CSS, one HTML, one icon**. Script ownership
headers were inspected; actual source samples were `app.js` period/acceptance paths,
full `live.js`/`token-mix.js`, and `sessions.js:1–145`. Platform wrappers and two CI
workflow paths were inventoried; public Windows/macOS Web wrappers and the complete
common workflow were read. No browser, native app or launcher was executed.

Static test-import reachability leaves only `src/__init__.py` and
`src/pricing/__init__.py` without a test path; this is navigation, not executed
coverage. Two existing sibling-test edges remain:
`test_v2_synthetic_attribution.py` → `test_effort_presentation.py` and
`test_v784_regressions.py` → `test_v783_regressions.py`. Neither was expanded or
accepted as new growth. Runner registration in `development/tools/run_tests.py`,
not inventory count, defines actual execution. Focused routes remain in
[CODE_MAP](../../modules/CODE_MAP.md).

Temporary full metadata: `scratch:/architecture-inventory.json` and
`scratch:/architecture-code-inventory.json`. Counts, source, candidates and
decisions in this report survive cleanup. No live history, account observations,
credentials, private sessions or other workers' records were acquired. The ordinary
checkout stayed read-only. Actual default has no `development/MAINTAINER.md`;
README, mirrored development guide and `development/repository.json` supplied the
existing development-only/release facts, rather than a guessed replacement.

## Level 1 — red-thread traces and simpler targets

All implementation paths below are relative to `src/`. Named source was actually
read, with selected routines where stated; the map is not the evidence by itself.

| Representative trace | Normal/error authority and simpler-target decision |
| --- | --- |
| Full `product_entry.py`; `bootstrap.py::main`; `reports/service.py:695–881` | Help/version do not launch Web; explicit CLI remains independent. Parse/config precede integration/cache work. Normal reports overlap independent account/availability acquisition, then close owned account work in `finally`. Samples, account periods and detail scopes differ. Forcing CLI through HTTP/Live adds host/browser lifetimes; it does not remove a second analysis engine. |
| Full `web/host.py`, `web/dispatch.py`, `application/service.py`; `web/jobs.py:340–579` | Host owns ticks/shutdown; dispatcher owns demand, source-qualified retained publications, due/backoff and priority; Jobs owns execution/parking/retirement and exact handles. Application admits fresh private services and allowlisted results. Typed failures cannot become successful observations; unconfirmed child exit latches host failure and retains cleanup ownership. Combining these into one state object would conflate source age, logical work and OS exit proof. |
| Full `application/live.py`, `watch/acquisition.py`, `watch/web_coordinator.py`, `assets/live.js` | One Live driver owns source cadence, hints, same-generation recovery and publication. Hints never establish completion. Outage retains age/rows, discards partial initialization and retries; terminal source evidence stops. Cards, daily history, detail, scalar index and cost reconciliation isolate blocking/cancellation. One combined reader would introduce head-of-line blocking; per-tab acquisition would multiply work. |
| Full `application/session_catalog.py`; `assets/sessions.js:1–145` | Period-qualified membership precedes scalar indexing. Exact metric sorts require every eligible key; pinned older-page windows/order survive arrivals. Display retention does not set `_key_current`; source provenance/revision checks reject late output and foreign retention. Browser generation/abort owns navigation, not shared index cancellation. A single “ready” flag or page-only sort would erase required distinctions. |
| Full `reports/token_mix_history.py`; `token_mix_cache.py:100–194`; `assets/app.js::selectTokenMix` and acceptance/finalization path; full `assets/token-mix.js` | Compact facts reuse canonical valuation. Physical deduplication precedes request-time period membership, including children. Browser period changes retire only their attempt; foreign-period/obsolete-attempt results cannot replace it. Shared calendar windows do not make Sessions activity membership equivalent to Token Mix request membership. A universal period/population engine would hide that difference; duplicating pricing in JS would create another authority. |
| `sources/selection.py:119–215`; V1 `load_session_snapshot`; full `opencode_v2_snapshot.py` | Select exactly one generation; no history merge. V1 pins metadata/revision/messages/parts in one read transaction. V2 brackets hydration with tree revisions, bounded fresh retries and joined owned reads on failure. A universal raw adapter or hint-as-proof would remove consistency guarantees, not redundant coordination. |
| `accounts/acquisition.py:155–361`; `pricing/github_copilot.py:473–642` | Attempt sequence, credential revision and deadline reject late quota observations; occupied calls remain bounded. Ordinary prices permit marked fallback; explicit strict refresh requires upstream; metadata-only refresh preserves current prices/retrieval identity. A generic retry/freshness owner cannot safely unify these contracts. |
| `web/http.py:238–325`; full `security.py`; `lifecycle.py:46–157`; full `benchmark.py` | Host/Origin/method/body/session/CSRF precede protected work. Native retirement proves exact process identity; access denial is not absence. Benchmark reuses Jobs under host tick/close, but retains its own public aggregate/cache/time budget and cannot supply history/prices. Folding it into source-qualified history cadence adds coupling. No actual desktop interaction or service stop occurred. |

**Global decision:** keep these distinct owners; no demonstrated overlapping
orchestration required a rewrite. The overview and
[module map](../../modules/web.md#architecture-150-source-map) now expose current
period, retained/fresh-key and failure routes. New diagram labels are navigation
corrections, not removed runtime handoffs or a measured performance gain.

## Level 2 — independent substantial-module review

Every substantial group has metadata coverage plus the named source samples.
Counts are observed baselines, never caps to raise. “No change” does not certify
unread routines or all possible inputs.

| Area: modules / lines | Representative implementation and independent local judgment |
| --- | --- |
| Root: 12 / 1,820 | Full product routing and bootstrap main. Intent routing, integration composition, config validation and fault/display owners have distinct consumers. No generic command framework justified. |
| Domain: 12 / 906 | `models.py:270–406` and all purpose/import records. Background evidence, snapshot completeness, native quota and pricing contracts are separate facts. Integration imports do not appear in domain metadata. Static type-only edges are not runtime-cycle proof. |
| Sources: 29 / 5,261 | Selection, V1 pinned snapshot, full V2 snapshot/retry/pool cleanup. Wire normalization, native background evidence and catalog consistency have explicit owners. Combining scoped/global proofs or transport/normalization would obscure different inputs/lifetimes. |
| Accounts: 20 / 3,290 | Acquisition discovery turnover, scheduling, workers, poll/deadline/finish/close; provider/transport/mapping metadata. Worker acquisition and owner-only publication remain separate. No second quota mapper or safe adapter removal established. |
| Pricing: 11 / 1,732 | Ordinary/strict/cache/metadata paths above. Parsing/catalog/tier/identity metadata remains cohesive; metadata recovery cannot overwrite current prices. No shared-retry wrapper or rate engine replacement justified. |
| Analysis: 32 / 5,464 | Full `valuation.py`; complete `causal.py::build_prompt_record/build_prompt_records`. Physical dedup retains sibling multiplicity; linked coverage qualifies completeness independently of known cost. Terminal failure, cancellation and unverified execution differ. The 190-line prompt constructor is a navigation risk, but splitting the one attempt/child/terminal decision across new objects has no demonstrated net gain. |
| Cache: 9 / 740 | Full `lifecycle.py`, benchmark use site, database/repository dependency records. Demand touches differ from passive reads. Bounded pruning protects unknown/changed/active evidence and rolls back cancellation. It writes disposable Cost Guard state only; no source-history ledger or generic cleanup engine is needed. |
| Reports: 31 / 5,016 | Service dispatch/list/detail/date/dashboard, Token Mix cache/projection, full `session_models.py`/`session_effort.py`. Model facts include dispatched zero-token success with same-root role proof; selected effort uses positive-token contributors. Unifying their eligibility loops would silently change their populations. The 881-line service remains a composition hotspot, not evidence of a second valuation authority. |
| Watch: 31 / 5,310 | Full acquisition/Web coordinator and `invocation.py`. One privacy/size filter serves native and registry fallback; conflicting identity withholds commands. Recent history, invocation disclosure, source status and daily/run accounting have different evidence lifetimes. No merge into a generic mutable state bag justified. |
| Application: 23 / 3,121 | Full service/Live/catalog/`mini_costs.py`. Mini groups canonical unrounded parts and prepares unit-specific copy, not request valuation. Merging Mini display groups with report role/model/effort evidence would couple formatting with source eligibility. Retained values remain separate from fresh sort qualification. |
| Presentation: 19 / 2,725 | Full `watch_screen.py`, report/display/compatibility metadata. Buffering handles changed rows and overflow without history acquisition. Tiny routes have static consumers; no dead-code conclusion follows from their size. Physical terminal rendering was not exercised. |
| Web: 38 / 4,756 plus assets | Host/dispatcher/jobs/security/HTTP/lifecycle/benchmark and browser samples above. Fixed guarded routes differ from acquisition; DOM ordering differs from canonical membership. Corrected seven-column/six-key summary drift to current eight-column/scoped-sort contracts. No new router, scheduler, UI framework or cosmetic runtime split. |
| Development/platform | Runner's complete isolated-process/timeout/concurrent execution path; Diagnostics imports and `_timed` section; common workflow; public Web wrappers. Product checks, private diagnostics and actual desktop launch have different triggers. No new gate, inference, installation or reload. |

**Local decision:** independently justified runtime NO_CHANGE. Large routines,
the accumulated CODE_MAP/Web feature narratives and two sibling-test edges remain
specific navigation/debt risks, not proof of unreachable code or duplicated state.
No budget, legacy exception, assertion, timeout, permission or safety mechanism changed.

## Characterization, checks and limitations

Test source actually read, **not executed**:

- Full `test_stable_refresh.py`: retained scalars never qualify new sorts;
  partial/zero replacement, source change/removal and late-revision rejection.
- Full `test_token_mix_periods.py`: independently enumerated period membership,
  child/dedup/unknown/pricing semantics, DST/month boundaries, warm facts without
  hydration/repricing and page-specific request identity.
- `test_web_runtime.py:841–963`: bounded retirement, forced cancellation/malformed
  IPC, retained handles/failure latch and resident-child admission.
- `test_watch_source_recovery.py:72–223`: retained dashboard, no subprocess/reselection,
  independent account cadence, fresh recovery and terminal/bounded unreadability.

These characterize intended normal/negative/recovery contracts, not fresh PASS.
No mechanism changed, so no new negative fixtures or before/after runtime parity
are claimed. Actually run: read-only maintenance inventory and AST inventory;
delivery checks cover exact development-only paths, unchanged runtime blobs,
progress delta, changed local Markdown routes/anchors, source identity, diagram
lexical structure and whitespace. These are not a rendered Mermaid validation.

Static delivery checks passed for **six changed development files / eleven added
or changed local Markdown links**. Progress differs only at
`completed.architecture`; runtime blobs are unchanged. Overview graphs retain
**17 nodes / 28 edges** and **21 / 26**. The module graph changes **11 / 13 → 15 / 18**
to expose existing period/history owners, not to add runtime handoffs.
The first one-off checker attempt failed on Windows' default text encoding;
explicit UTF-8 repaired the checker and the full check passed. That failed attempt
was not PASS and did not change product code or checks.

Product Quick/Full, package validator, Diagnostics/live-source probes, browser/native
runs, benchmarks and model evaluations: **not run / not applicable to this
development-only change**, not waived or PASS. No current runtime latency, memory,
fanout or provider values were measured. Common CI's cumulative path filter excludes
this evidence/docs/progress-only diff; actual PR checks/protections still govern merge.

This report does not close the [foreground-recovery ledger](../../../journal/web/foreground-recovery.md),
feature-specific live/native gaps, macOS physical Finder/Gatekeeper acceptance,
or the existing Session Learning deferral. Earlier assessments in the
[journal](../../../journal/architecture.md) retain their own identities/evidence;
historical successes neither prove current correctness nor protect a flawed design.
No second task was selected.
