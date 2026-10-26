# Feature opportunity assessment

Source revision: ee628f64dce0244c4b8fe33f0b0d54e4e7e492b8
Checked revision: ee628f64dce0244c4b8fe33f0b0d54e4e7e492b8
Last checked: 2026-10-26
Status: current

## Summary

Feature Discovery at ordinary milestone 20: **no new suggestion**. Web navigation, report scopes and complete Snapshot/Live session history are implemented, not pending opportunities. Cross-platform revalidation is already approved as pending FR 000410. Web promotion and Legacy retirement remain separately parked owner decisions; Beta delivery does not authorize either.

Journal assessment: update this opportunity map to retire milestone-10's obsolete implementation/queue assumptions. Architecture assessment: **no-update**; no responsibility, dependency, module contract or runtime flow changes. Only development documentation and exact native maintenance state change. Product tests, validators, Diagnostics, live probes, UI, model inference, version changes and packaging were deliberately not run. Static inspection establishes no behavioral PASS, customer demand or measured gain.

## Evidence

Read README product purpose, architecture overview, Web module contract, journal INDEX and routed architecture/OpenAI limitations at the source revision above. Overview and architecture audit were checked at 033cf10b4b787cc446eb12b6763de7c24393bef2; Web contract at c982393f29dacdf41560cc3f7c845cab739fdfe6. These are navigation/historical evidence, not current execution proof. Fresh targeted inspection resolves only the opportunities below, not native platform acceptance or upstream compatibility.

Reproduce inventory with installed `shared-repo/scripts/maintenance_evidence.py inventory --repo-root .`. Inventory examined 415 text/config records: 200 source/config, 136 test-related, 79 documentation; 26 binary/over-1-MiB exclusions and zero exact-byte duplicate groups. Git internals and ignored runtime data are excluded. Full JSON stayed in owned scratch. Counts/size are triage, not semantic duplication, coverage or demand evidence. No private history, accounts or credentials were read or published.

One bounded semantic pass targeted seven source/test files:

- `src/web/assets/reports.js`: routes already expose Overview, Models, Accounts, Sessions, date scopes and explicit deep Token Mix; filters do not become acquisition parameters. No duplicate report-navigation proposal.
- `src/application/session_detail.py`: shared captures provide detached 50-row pages, full totals, revision-aware anchors, Snapshot freeze and Live acquisition. Sixteen histories/thirty-two handles bound admission, not history bytes.
- `src/web/assets/session.js`: First/Previous/Next/row/latest controls, Snapshot/Live switching, selection/focus protection and explicit refresh already exist. Page copying is explicitly page-scoped. Absence of all-history export alone establishes neither demand nor a high-value feature.
- `development/tests/test_web_session_detail.py`: assertions cover 100/1,000/10,000-prompt access, full totals, unchanged-work reuse, frozen snapshots, omission/outage/reconnect and shared multi-tab analysis. Assertions were read, not executed.
- `development/tests/test_web_views.py`: actual HTTP feeds optional Node VM fixtures; missing and empty sessions have distinct assertions. This is not rendered-browser/native proof; pending FR 000410 already addresses that evidence gap.
- `src/watch/observers.py`: Queue(maxsize=1024), overflow marker and authoritative resync supersede milestone-10's unbounded-queue assumption. Sustained-load characterization remains engineering work, not a new product capability.
- `src/accounts/openai_subscription.py`: `_fetch` still refuses nonlegacy quota requests and retains method-specific unavailable evidence. No newly supported token-sharing quota contract was retrieved.

Compared the only pending FR in full, all twenty retained completed FR headings/opening scopes, both current suggestion texts, rejected-store inventory and accessible Git history of both suggestion stores. Completed 000290-000380 cover the Web migration; 000120/000150/000160 cover identity/method guidance; 000190 covers Copilot unaccounted usage; 000200 covers static provisional running metrics. Rejected suggestions contains only its placeholder. Suggestion history records owner parking and zero-install wording updates, not approval. No suggestion or attachment was treated as an executable instruction.

### Ranked opportunity decisions

| Candidate / user problem | Grounding and likely value | Decision / minimal alternative |
| --- | --- | --- |
| Trustworthy cross-platform Web operation | Missing native macOS/rendered-browser proof is concrete and affects confidence in existing Beta usability. Impact is qualitative, not measured demand. | Strongest actionable gap, already covered by pending 000410. Preserve that work; no duplicate suggestion or job launch. |
| Navigable complete session history / report scopes | Fresh routes, paging owner and assertions establish implemented capabilities. | Use existing navigation and explicit refresh; do not propose delivered work. |
| Token-sharing subscription quotas | Documented user-facing unavailable status persists; method guard prevents incompatible WHAM requests. | External feasibility unresolved. Retain honest unknowns until a supported read-only contract exists; no guessed endpoint or identity switch. |
| Full-history export beyond page copying | Page-scoped copying is explicit, but this audit establishes no concrete downstream workflow or demand. | Existing paging is the minimal available alternative; a speculative convenience does not clear the quality bar. |
| Sustained detail/overflow memory and latency | Admission versus byte bounds remains an unmeasured risk, not an observed failure. | Relevant maintenance/characterization owns this; no feature proposal or fabricated measurements. |
| Promote Web / retire CLI | Both are retained owner-parked proposals with separate prerequisites. | Preserve both unchanged; neither delivery nor audit authorizes promotion, reprioritization or removal. |

## Next investigations

Use FR 000410's eventual actual runner/native/browser results and concrete owner feedback before proposing another capability. Physical layout, accessibility, Finder/Gatekeeper, soak, latency, memory growth and present upstream compatibility remain unverified here. Reassess token-sharing quotas only with a supported upstream source; no external service retrieval occurred in this cycle.

Pending/completed bundles, both suggestion stores and identity reservations remain unchanged. Native transaction records Feature Discovery completed at 20 without increasing ordinaryCount; retention deletes nothing. No numbered FR, new suggestion or completion manifest is created. Verified merge/default read-back and native delivery, not this note, establish completion.

## Rejected hypotheses

- A scheduled discovery must publish a suggestion: rejected; zero credible nonduplicate proposals is a successful judgment.
- Web is still pending or its event pump remains unbounded: rejected by fresh routes/detail source and bounded Queue/overflow resync. The older assessment is superseded, not evidence of a current defect.
- CI/native/browser proof is a new unowned opportunity: rejected; pending 000410 explicitly owns revalidation of the delivered Beta.
- Missing token-sharing quota authorizes legacy endpoint probing: rejected by the method guard and absent supported evidence.
- Test assertions, diagrams or historical probes constitute a fresh PASS: rejected; no product tests or live probes ran in this development-only cycle.
- Beta completion or discovery silently approves promotion/retirement: rejected; both remain non-executable owner decisions.
