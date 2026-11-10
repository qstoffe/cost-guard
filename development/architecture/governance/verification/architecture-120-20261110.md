# Architecture assessment — milestone 120

Source revision: 3f994921849ae2cf6f87245c6f3a010353fcbd08
Checked revision: 3f994921849ae2cf6f87245c6f3a010353fcbd08
Last checked: 2026-11-10
Status: completed static assessment; not a runtime correctness certification

## Outcome and scope

**Global runtime NO_CHANGE; independently justified local runtime NO_CHANGE.**
The representative source traces below did not establish overlapping orchestration
authority, a second accounting engine, or a material local simplification with a
demonstrated net benefit. Working code and tests were not treated as immunity from
redesign: each candidate was compared with a simpler target and its actual lifetime
and evidence obligations. This is a whole-repository inventory plus representative
source assessment, not line-by-line review, exhaustive dead-code/security analysis,
runtime parity, a performance result or acceptance of outstanding feature gaps.

Development-only changes refresh the overview, add the Web module's current flow,
correct its obsolete six-column Sessions summary to seven, retain prior assessments
in the journal, and publish this report plus maintenance progress. No runtime, test,
tool, dependency, user configuration, launcher, release or version changes; no FR move
or speculative proposal. Architecture advances **90 → 120** only after merge.
Ordinary count **120**, `lastOrdinaryId=fr/000670`, Test Health **105**, Performance
**80**, Session Learning **0** and its milestone-100 deferral remain unchanged.
That existing learning deferral is not completed/PASS.

## Whole-repository inventory

Read-only installed `maintenance_evidence.py inventory --repo-root <owned-clone>`:
**1,246 text/config records** (381 source-or-config, 519 documentation, 346 test),
**343 binary/over-1-MiB exclusions**, **zero exact-byte duplicate groups**. Scope is
tracked plus nonignored untracked files, excluding runtime artifacts. Large text
hotspots are mostly retained development measurements; sizes and exact-byte matching
do not prove semantic duplication, dead code or sound orchestration. Excluded
assets were counted, not semantically audited.

`py -3 development/tools/code_inventory.py --json` parsed source without importing
the product: **248 runtime Python modules / 37,618 lines**, development tools
**15 / 3,073**, test tree **313 / 63,388**, nested fixtures **58 / 5,217** (nested
counts are not additive). All 248 runtime purpose/size/local-import records were
read in a compact projection; representative source appears below. Browser assets:
**19 JavaScript, two CSS, one HTML, one icon**. Platform wrappers and both CI workflow
paths were inventoried; only the common workflow and named wrappers were read.

Static reachability leaves only `src/__init__.py` and `src/pricing/__init__.py`
without a test-import path. This is navigation, not executed coverage. Remaining
sibling-test imports are `test_v2_synthetic_attribution.py` →
`test_effort_presentation.py` and `test_v784_regressions.py` →
`test_v783_regressions.py`; neither was expanded, repaired or newly approved.
Runner ownership is `development/tools/run_tests.py`; focused routes remain in
[CODE_MAP](../../modules/CODE_MAP.md). Its registration, not test-file inventory
count, defines actual Quick/Full execution.

Full temporary inventories: `scratch:/architecture-inventory.json` and
`scratch:/code-inventory.json`. This report preserves the source, counts, candidates
and decisions after cleanup. No personal history, credentials, provider observations,
other workers' records or private session storage was acquired. The ordinary checkout
was not changed. The current default has no `development/MAINTAINER.md`; its existing
README, mirrored development guide and `development/repository.json` supplied the
actual development-only/release routes rather than a guessed replacement file.

## Level 1 — end-to-end ownership and alternatives

| Source trace actually inspected | State, normal/error route and simpler-target decision |
| --- | --- |
| `src/product_entry.py`; full `bootstrap.py`; `config.py::validate_configuration`; `reports/service.py::build/_build/_build_dashboard` | Help/version avoid Web; explicit arguments remain CLI. Parse/config precede cache/source/providers. Reports own scope and close account work in `finally`; terminal presentation consumes projections. Routing CLI through Web would add host, HTTP and browser lifetimes, not remove a duplicated calculation. |
| `web/host.py`; full `dispatch.py`; `jobs.py::_park` through `close`; full `application/service.py` | Host owns tick/shutdown; dispatcher owns demand, source-qualified retained results, due/backoff/priority; jobs own active/parked/retiring process handles; application owns fresh-service admission and allowlisted detached results. Valid terminal IPC publishes before reap; uncertain exit retains handles and latches host failure. A single scheduler/result/service object would conflate source freshness, logical work and OS exit proof. No redundant authority established. |
| Full `application/live.py`, `watch/acquisition.py`, `watch/web_coordinator.py`; `assets/live.js` | One Live owner drives canonical observations; HTTP/tabs do not tick acquisition. Hints demand authoritative reads, not completion. Outages preserve frames/age and retry the selected generation; terminal failure does not become success. Catalog, cards, detail and account-history readers isolate blocking/cancel lifetimes. Merging lanes would introduce head-of-line blocking and shared cancellation. |
| Full `application/session_catalog.py`, `assets/sessions.js`; catalog capture in `watch/web_coordinator.py` | Authoritative membership/revisions qualify per-root scalars; global metric order waits for every key. Older-page epochs pin membership/order while values can refresh. A source change invalidates relevant keys, not all work. Browser generation/AbortController/Cancel owns navigation only; explicit failures keep Retry/Cancel visible, expired epochs reopen once. Reusing the finite-report dispatcher or sorting the current page would lose shared Live proof or exact global ordering. Separate dictionaries represent rows, revision validity, failed attempts and leases, not duplicate authorities. |
| `sources/selection.py`, V1 `load_session_snapshot`, full `opencode_v2_snapshot.py`; `reports/acquisition.py` | Select one generation, never merge histories. V1 pins tree/revision/messages/parts in one read transaction; V2 accepts before/after-equal tree revisions with bounded fresh attempts. Speculative sampling is not report-owned evidence and releases its tail. A universal adapter or hint-based cache hit would hide different consistency proofs. |
| `accounts/acquisition.py::_schedule/_worker/poll/finish/close`; `pricing/github_copilot.py::get_catalog/refresh_catalog/_load_or_fetch/refresh_release_metadata` | Account attempt sequence, credential revision and deadline reject late observations without freeing an occupied call prematurely. Ordinary pricing may retain a marked fallback; explicit strict refresh cannot. Metadata-only enrichment preserves prices/retrieval identity. A common retry/freshness state machine would erase these distinct guarantees. |
| Full `web/benchmark.py`; `host.py`; HTTP benchmark route | New public aggregate lane reuses `ReportJobs` with its own target/cache and host tick/close, 24-hour freshness, coalesced forced refresh, timeout/backoff and retained fallback. It is not a canonical history/pricing dependency. Putting it into source-qualified report freshness would create coupling; inventing another worker framework would duplicate existing process ownership. |
| `web/http.py::route` guards/POST routes; full `security.py`; `lifecycle.py::_existing_process/stop_existing/spawn_detached/launch`; `assets/data-demand.js` | Host/Origin/method/body/cookie/CSRF precede protected demand. Native restart uses recorded birth identity, not process names; browser handoff failure leaves the managed host available. Browser leases describe demand, not capacity or account authority. Collapsing authorization, source recovery and native launch would obscure security and lifetime boundaries. No actual desktop interaction was performed. |

**Global decision:** preserve the modular monolith and explicit observation/process/
navigation ownership. The overview now includes the independent benchmark lane; the
[Web module map](../../modules/web.md#architecture-120-source-map) traces Sessions
and the source-qualified V1 notice. Runtime nodes, handoffs, authority and behavior
are unchanged; diagram additions are not a measured simplification or speedup.

## Level 2 — independently assessed local coverage

All substantial groups have metadata coverage; the named samples are source reads,
not claims that every routine was read. Counts are observed baselines, never caps to raise.

| Area: Python modules / lines | Representative code and local judgment |
| --- | --- |
| Root: 12 / 1,820 | Full product entry/bootstrap; configuration validation; root purpose/import records. Intent routing, integration composition, numeric display and fault handling remain distinct. The 162-line validator enumerates concrete settings; splitting it into generic rule objects would add navigation without evidence of fewer decisions. |
| Domain: 11 / 799 | Full `accounts.py`, `models.py` import/type boundary. Native capacity, billing, source-qualified identity and reference valuation remain separate values. The models→accounts edge is type-checking-only, not a proven runtime cycle. No concrete integration appears in domain's local-import records. |
| Sources: 27 / 5,052 | Selection, V1 snapshot and V2 snapshot consistency/retry/owned-pool paths. Catalog, wire adaptation and bracket lifetimes remain below canonical snapshots. Scoped/global entrypoints are separate proof domains; no evidence supports deleting one as a duplicate. |
| Accounts: 20 / 3,290 | Scheduling, worker results, deadline/credential turnover and close paths in acquisition; provider/transport/mapping records. Acquisition owns publication while adapters own native quota shapes. Consolidating them would couple semantics to worker lifecycle. |
| Pricing: 11 / 1,712 | Markdown parser/tier construction and ordinary/strict/metadata acquisition paths. Parsing, pure catalog valuation and freshness have different inputs. No second rate engine or dead adapter was established. |
| Analysis: 28 / 4,963 | Full `valuation.py`; complete `causal.py::build_prompt_record/build_prompt_records`; all purpose/import records. Causal child scopes, native termination, unverified execution and billing/reference costs are explicit. The 186-line constructor is a navigation hotspot; distributing its one attempt decision among helper objects would not yet reduce state/proof burden. |
| Cache: 9 / 740 | Full `lifecycle.py`, benchmark cache's use site, repository/database dependency records. Pruning writes only disposable state, checks revision/activity/use and rolls back cancellation. Benchmark aggregates stay separately keyed. A new history ledger or cleanup framework would add authority rather than remove duplication. |
| Reports: 28 / 4,470 | Full root acquisition; service build/list/detail/date/dashboard paths. Samples, account periods and whole history have different populations; speculative prefetch never establishes report provenance. The 864-line service remains a composition hotspot, but named acquisition/history/projection owners have real contracts. No second valuation engine found in these traces. |
| Watch: 29 / 4,873 | Full Live acquisition/Web coordinator; all card/tracker/tool/totals purpose/dependency records. Source cadence, certified history membership, retained daily/run usage and capture resources have distinct scopes. No generic merged state bag or new scheduler justified. |
| Application: 18 / 2,511 | Full finite service, Live runtime, scalar catalog and `quota_estimates.py`. Admission/export, complete global sort keys, and presentation-only Decimal rounding are coherent independent responsibilities; rounding never changes canonical cost. |
| Presentation: 19 / 2,725 | Full `watch_screen.py`; report/account/context/compatibility import routes. Frame buffering and terminal geometry do not acquire history or revalue it. Tiny compatibility routes have static consumers; size alone does not justify removal. No exhaustive layout or terminal audit claimed. |
| Web: 36 / 4,663 plus assets | Host/dispatcher/jobs/HTTP/security/lifecycle/benchmark plus full Live/Sessions/demand JavaScript. The 193-line HTTP route is a fixed guarded protocol, not evidence for a generic router framework. Sessions browser operations are separate from server validity. Corrected the stale six-column description and added a source-backed module diagram; no runtime split justified. |
| Development/platform | Runner registration, Diagnostics summary/subprocess isolation, full common CI workflow and Windows/macOS public Web wrappers. Development evidence, product verification, read-only installation proof and actual desktop launch have different triggers. No new gate, inference, native UI, install or reload. |

**Local decision:** no evidence-backed runtime removal/replacement now. Long routines,
the large Web contract's accumulated feature narratives and the two sibling-test
edges remain concrete navigation/debt risks, not proof of an execution defect.
Documentation was corrected rather than representing a cosmetic split as redesign.
No exception baseline, file budget, assertion, timeout or safety mechanism changed.

## Characterization and checks

Representative test source actually read, **not executed**:

- `test_web_session_catalog.py:614–813`: 3,217 scalar keys, exact global sorts/last
  page, pinned arrivals, canonical CTX, malformed/partial cache rejection, changed-root
  requalification, and safe work-stage/failure publication.
- `test_web_runtime.py:870–969`: forced cancel versus natural grace, unconfirmed
  retiree failure retention, admission refusal after failure, resident-child bound.
- `test_web_live.py:183–282`: retained source age/rows, same-source recovery,
  prolonged revision churn, bounded hint overflow and hints not proving completion.
- Full `test_v1_web_watch.py`: separate actual SQLite CLI/Web owners, finite-report
  read-only behavior, source selection/parity and withholding unverified generation.

These establish the intended normal/negative/recovery contracts considered before
the no-change decision, not fresh runtime results. No mechanism was replaced, so
new negative fixtures and before/after runtime parity are not claimed.

Actually run: read-only maintenance inventory and product AST inventory. Delivery
checks cover changed-path scope, exact progress delta, source identity, new/edited
local Markdown destinations, Mermaid structure and whitespace; results belong in
the PR. Product Quick/Full, package validation, Diagnostics, live-source probes,
browser/native execution, benchmarks and paid/model evaluation are **not run / not
applicable to this development-only change**, not waived and not PASS. Common CI's
path filter excludes this documentation/progress-only diff; actual PR checks and
merge protection still decide delivery.

## Limits and retained work

The assessment does not close the [foreground-recovery acceptance ledger](../../../journal/web/foreground-recovery.md),
feature-specific real-source/native gaps, macOS Finder/Gatekeeper acceptance or the
existing Session Learning deferral. Source reading cannot establish current retained
memory/backpressure/fanout, latency, provider combinations, physical rendering or
workstation-specific correctness. Those quantities remain unmeasured here, not zero.
Earlier [architecture assessments](../../../journal/architecture.md) retain their
own source identity and tests; historical passes are not current PASS or immunity
from a future evidence-backed redesign. No additional task was selected or implemented.
