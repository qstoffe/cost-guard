# Feature opportunity assessment

Source revision: b7d0b53c2470761a20f316bcbafb75f9345e1c67
Checked revision: b7d0b53c2470761a20f316bcbafb75f9345e1c67
Last checked: 2026-10-26
Status: current

## Summary

Feature Discovery at ordinary milestone 10: **no new suggestion**. The strongest grounded usability opportunity, navigable static/live Web reports with complete session history, is already approved in ten pending bundles (000290 through 000380). Promotion and Legacy retirement are separately parked in the human suggestion inbox; neither is authorized by Beta completion. Do not duplicate these capabilities or infer demand for unrelated features.

Journal assessment: retain this bounded opportunity map so later discovery can distinguish implemented behavior, approved work and external feasibility gaps. Architecture assessment: **no-update**; no ownership, dependency, module contract or runtime flow changes. This scheduled delivery changes only development documentation and exact native maintenance state. Product tests, validators, Diagnostics, live probes, paid inference, version changes and packaging are deliberately not run. No behavioral PASS or performance gain is claimed.

## Evidence

At the revision above, read README product purpose, architecture overview, Reports/Watch contracts, journal INDEX and routed architecture, Test Health and OpenAI limitations. Overview evidence is anchored at b2850feffd227ee5e502bd40d9a0266fdd49ba86, not the current HEAD; its broad audit supports navigation, not current execution proof. Reports/Watch module checks are older still. Fresh source sampling below independently resolves only the named opportunities, not the entire architecture or upstream compatibility.

Reproduce inventory with installed `shared-repo/scripts/maintenance_evidence.py inventory --repo-root .`. It examined 341 text files: 157 source/config, 120 test-related and 64 documentation; 17 binary/over-1-MiB exclusions, zero exact-byte duplicate groups. Git internals and ignored runtime material are excluded. Metadata/size is triage, not behavioral or customer-demand evidence. Full inventory stays in owner scratch; no private history or account exports were read or published.

One semantic assessment pass sampled seven actual source/test files, under the twelve-file / 32,000-character source-excerpt limit:

- `src/reports/service.py` (account scope and build/detail dispatch): report use cases already share analysis, but `build` closes accounts in `finally`. A persistent Web host needs the ownership seam already specified by 000290, not a second service per tab.
- `src/reports/prompt_rows.py` (projection setup and provisional metrics): active breakdowns require supported telemetry/attribution, with unknown values withheld. Reusing the shared projector is preferable to browser arithmetic.
- `development/tests/test_session_snapshot.py`: fixed expected Decimal metrics, missing-data cases, frozen duration/output and forbidden implicit Watch construction protect the already-delivered 000200 outcome. These assertions were read, not executed.
- `src/watch/observers.py` (`LiveEventPump`): live hints use an unbounded queue and explicit authoritative resync. This confirms the architecture journal's unmeasured robustness investigation, not a new product capability or demonstrated outage.
- `src/watch/coordinator.py` (V2 wait/advance): hints are coalesced into session IDs during waiting; resync triggers fresh polling. Future Web live subscriptions/slow consumers are already addressed by 000350, without proving current memory bounds.
- `development/tests/test_watch_source_recovery.py` (failure fixtures and first recovery case): synthetic sources, fixed clocks and forbidden subprocess construction establish a focused test seam for recovery; no fresh execution result follows.
- `src/accounts/openai_subscription.py` (method classification matches and `_fetch`): nonlegacy credentials return method-specific unavailable evidence without attempting a request. The retained token-sharing gap has no newly verified supported source here.

Compared all ten pending FR texts, all ten retained completed FR headings/scopes, both current suggestion texts, the rejected registry and accessible Git history of both suggestion stores. Completed 000120/000150/000160 cover identity/method guidance; 000190 covers Copilot unaccounted usage; 000200 covers static provisional running metrics. The rejected store contains only its placeholder, no retained rejection record. Suggestion history records owner-parking and subsequent zero-install wording changes; it is not approval. No attachment was treated as an instruction or newly published.

### Ranked opportunity decisions

| Candidate / user problem | Grounding and likely value | Decision / minimal alternative |
| --- | --- | --- |
| Navigable Web reports and complete live session history | Existing report/Watch projections support a coherent interface; long-history access, static/live distinction and independent observation scopes matter to correct interpretation. Impact is qualitative, not measured demand. | Strongest feasible capability, but already specified by 000290-000380. Keep existing staged work; publish no duplicate. |
| Provisional running metrics without implicit Watch | Actual projection and deterministic assertions support the requested one-shot experience. | Already implemented by 000200. Refresh the existing snapshot explicitly; no follow-up suggestion from stale docs. |
| Token-sharing subscription quotas | Real user-facing unknown remains documented; current method guard deliberately avoids incompatible WHAM requests. | Feasibility is unresolved without supported upstream evidence. Preserve honest unavailable status; no guessed endpoint, identity switch or speculative integration proposal. |
| Bounded hint handling during slow hydration | Fresh queue/wait source confirms an engineering investigation surface; no event-rate/memory measurement establishes user impact. | Code-health/robustness follow-up belongs to relevant maintenance or scoped live-engine work, not a feature-discovery suggestion. |
| Promote Web / retire CLI | Both capabilities are retained owner-parked proposals with explicit future decisions and prerequisites. | Do not republish, promote or assign priority. Preserve both inbox records unchanged. |

## Next investigations

After actual Web delivery and owner testing, compare concrete remaining user problems against the implemented views and both suggestion stores before proposing anything. No new research task is required to consume this cycle. Reassess token-sharing quotas only with a supported upstream read-only contract; this assessment performed no external service retrieval. Native macOS behavior, demand, latency, memory growth and current test execution remain unverified.

All ten pending bundles, both suggestions, completed bundles and identity reservations remain unchanged. Native transaction records Feature Discovery completed at 10 without increasing ordinaryCount; retention deletes nothing. No new completion manifest or numbered FR is created. Git-verified merge/default read-back and native delivery, not this note, establish completion.

## Rejected hypotheses

- A scheduled discovery must create a suggestion: rejected; no duplicate, speculative or weak capability is preferable.
- A Web diagram or approved FR proves Web already works: rejected; sampled runtime is still CLI/report/Watch and pending specifications are not implementation.
- Unknown token-sharing quota justifies probing legacy resources: rejected by the method guard and absence of newly supported evidence.
- An unbounded queue alone proves a user-visible outage or feature demand: rejected; load/recovery characterization is still needed.
- Reading test assertions or historical completion reports constitutes a fresh PASS: rejected; no product test was run in this development-only cycle.
