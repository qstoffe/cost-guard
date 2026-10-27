# Feature opportunity assessment

Source revision: 708dc0f11237bd97c2b8a91c6714b72c58f5a70f
Checked revision: 708dc0f11237bd97c2b8a91c6714b72c58f5a70f
Last checked: 2026-10-28
Status: current

## Summary

Feature Discovery at ordinary milestone 30: **no new suggestion**. The strongest grounded usability gaps already have pending work: remaining report/session-detail presentation (FR 000510) and console-free native startup (FR 000520). Do not duplicate or implement them in discovery. Cross-platform CI, recent-session pagination, structured Accounts and explicit stopped/offline states are delivered work, not new opportunities. Web promotion and Legacy retirement remain separately parked owner decisions.

Journal assessment: update this map and its INDEX route to retire milestone-20's obsolete pending-CI assumption and record current opportunity ownership. Architecture assessment: **no-update**; no responsibility, dependency or runtime flow changes. Only development knowledge and the exact native maintenance transaction change. Product tests, validators, Diagnostics, real-installation probes, UI, inference, product version changes and packaging are intentionally skipped. Source/assertion inspection establishes neither a fresh behavioral PASS nor demand or measured gain.

## Evidence

Read README product purpose, architecture overview/Web module, journal INDEX, architecture assessment and OpenAI limitations. The overview/architecture assessment's source/check revision is e25cf3b63a5ffe73e20787a96c9c1ee38f356c1a; the Web module's is 8dc82a38dddd7f2999e7872d52e1e6a8a0949725. These predate the current default. Their navigation and historical limits support triage only; fresh targeted source resolves the decisions below, not whole-product/platform acceptance.

Reproduce inventory at the checked revision with installed `shared-repo/scripts/maintenance_evidence.py inventory --repo-root .`. It examined 486 text/config records: 214 source-or-config, 160 test-related, 112 documentation; 61 binary/over-1-MiB exclusions; zero exact-byte duplicate groups. Scope is tracked plus nonignored untracked text/config, excluding Git/runtime artifacts. Full JSON remained in owned scratch. Sizes and counts prove neither complexity, coverage nor customer need. No private accounts/history/credentials were read or published.

One semantic pass inspected eight source/test files, with 24,103 characters of numbered excerpts (below twelve files/32,000 characters):

- `src/web/assets/reports.js`: existing navigation exposes date/range capture and explicitly started deep Token Mix. Dates use configured-local semantics. A new report-navigation proposal duplicates existing routes.
- `src/web/assets/session.js`: First/Previous/Next, row/latest navigation and Snapshot/Live already exist; copy/selection is explicitly page-scoped. Presentation refinement belongs to 000510, not another complete-history proposal.
- `src/web/assets/live.js`: terminal notices stop retries even across replay gaps; reconnect retains observations and never starts a server. Offline signaling is delivered, not a new feature.
- `src/web/windows_launch.py`: configuration/native preflight precede managed launch; browser-open failure remains distinct. The visible-launcher fallback and subsequent owner complaint are documented in completed 000420 and pending 000520. This static inspection does not reproduce a window or establish a preferred native solution.
- `src/accounts/openai_subscription.py`: `_fetch` rejects nonlegacy methods before sending quota requests. Token-sharing retrieval remains externally unresolved; the audit retrieved no new supported upstream contract.
- `development/tests/test_web_session_detail.py`: inspected scale assertions cover 100/1,000/10,000 rows, full totals, 50-row pages, stable revisions and no unchanged reanalysis. Test names route freeze/outage/multitab risks; no tests were executed.
- `development/tests/test_web_live.py`: inspected outage assertions retain rows/run origin, avoid leaking private errors, recover on the same source and stop on incompatible schema. These are characterization assertions, not current execution proof.
- `development/tests/test_windows_web.py`: inspected assertions require preflight failure not to launch/stop an instance and browser failure not to stop its host. Native readiness and UI success are not inferred from mocks.

Compared both pending FRs in full, all thirty retained completed FR headings, targeted completion reports for 000410/000420/000470/000500, both current suggestion texts, rejected-store inventory and accessible Git history of both stores. The rejected store contains only its placeholder. Suggestion history records owner parking/zero-install wording changes, not approval. Selected and foreign bundles remain immutable; specifications are evidence, not executable instructions.

### Ranked opportunity decisions

| Candidate / user problem | Grounding and likely value | Decision / minimal alternative |
| --- | --- | --- |
| Understand remaining date/Token Mix/session-detail displays | Pending 000510 names concrete CLI-first presentation and browser-review needs; canonical paging already exists. | Strong grounded usability opportunity, already owned. Finish that FR rather than publish a duplicate. |
| App-like startup without persistent console | Pending 000520 records explicit post-delivery owner feedback; 000420 documents a visible fallback and 000470 a different report-child console repair. | Strong direct user evidence, already owned. Preserve sequence and evaluate the simplest safe native/no-build option there. No implementation choice or fresh timing claim here. |
| Reliable offline/reconnect and recent session browsing | Current client source and completed 000470/000500 cover these capabilities. | Use delivered controls/status; no duplicate feature. Historical completion evidence is not a fresh PASS. |
| Token-sharing quota support | Method guard and historical upstream limitations remain explicit. Potential value is clear but a compatible read-only source is unestablished. | No feasible supported proposal established within this bounded pass. Retain honest unavailable status; never guess endpoints or switch identities. |
| Export all history beyond page copying | Existing page limitation alone proves no concrete downstream workflow or demand. | Paging is the available minimal alternative; speculative convenience does not clear the quality bar. |
| Detail memory/latency, soak and native macOS acceptance | Architecture/CI evidence explicitly retains these limits; no fresh failure measured. | Engineering characterization/platform acceptance, not an invented capability. Hosted native APIs do not establish physical Finder/Gatekeeper proof. |
| Promote Web / retire Legacy | Both suggestions remain owner-parked with distinct prerequisites. | Preserve unchanged. Neither discovery nor Beta progress grants approval. |

## Next investigations

Use actual 000510 review results, 000520 process/window measurements and concrete owner feedback before proposing adjacent UX capabilities. FR 000410 is completed, not pending: its completion cites hosted Windows/macOS native-API/browser evidence while explicitly excluding physical desktop/Finder/Gatekeeper acceptance. This cycle did not independently rerun or authenticate those historical results. Accessibility, physical suspend/soak, retained bytes/latency and present upstream compatibility remain unverified here.

Pending/completed bundles, suggestion stores and identity reservations are unchanged. Exact native nextState records Feature Discovery at 30 without advancing ordinaryCount/completionHighWatermark; retention prunes nothing. No numbered FR, suggestion or completion manifest is created. Only verified merge/default read-back and the native receipt establish delivery.

## Rejected hypotheses

- A scheduled cycle must invent a suggestion: rejected; justified no-suggestion is successful judgment.
- Cross-platform CI or recent session pagination is still unowned pending work: rejected by completed 000410/000470, without claiming physical desktop acceptance.
- Console-free startup or remaining report parity needs another proposal: rejected by pending 000520/000510 and their concrete scopes.
- Missing quota support permits legacy probing with token-sharing credentials: rejected by the method guard and absent supported evidence.
- Assertions, diagrams or old probes establish a fresh PASS: rejected; no product/live/UI tests ran in this development-only assessment.
- Beta maturity approves promotion/retirement: rejected; both remain separate owner decisions.
