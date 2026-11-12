# FR000689 completion — v81.34, 2026-11-12

Every unready AI Stats card now contains exactly one `Loading…` text node,
including failed/interrupted/queued attempts. Real blockers appear outside cards;
ready values commit atomically and same-source/same-period last-good content stays.

Unready exhaustion/checkpoint failure no longer earns a successful cached cadence.
BUSY checkpoints retain the logical scan; supervised retries, old-policy regeneration
and attempt-qualified browser application preserve automatic acquisition/recovery.
No source/history writes, schema/security relaxation, inference or service restart.

## Verification

- Full executed all 185 groups: 184 passed initially. A version-edit race failed
  foundation; reruns passed the affected assertions, including a subsequent
  validator-subprocess timeout in isolation. This was not one wholly green Full run.
- Focused resume/dispatch 74 tests and report-lifetime VM passed. Validator:
  11 passes, seven existing advisory warnings; final delivery validation repeated.
- Headless Edge Loading matrix: 19 checks, 160 pending combinations. Enhanced
  operational-error checks completed before a combined-probe deadline during slices;
  separate production slices passed with 24 total hydrations/12 children, narrow
  readiness at 2/24 roots, broad completion and clean ownership teardown.
- Frozen real managed replay: visible interest/90s lease → queued/running → complete;
  3164/3164 roots, `fun-3-responses`, strict validation, all five scopes ready and
  12 cards. Warm Stats/Token Mix: 47.759/20.791s; preceding warm pass: 48.045/16.152s.
  Simulated browser transport faults automatically recovered over real results;
  retained DOM, cold Loading/page notices, units/themes/layout and clean exits passed.

## Explicit evidence exception

**Decision Delegate** authorized the minor historical-attribution exception to
acceptance 7 after two successful frozen managed runs. The owner's exact prior
failure/cache state and cold-upgrade causal replay/timing remain **NOT VERIFIED**:
the exact checkout-keyed instance/diagnostics/lifecycle records were absent.
The initial source-edited baseline was invalid; the later frozen 540s timeout
**FAILED**, cause unresolved. Warm successes do not relabel either result or prove
the historical cause. Further new-state probing cannot recover missing records.
No cold/schema, readiness/recovery, security or worker-bound requirement was waived;
no Suggestion or On Hold was required. Live injected faults were simulated browser
faults, not observed source outages or backend-child recovery.

See the [AI Stats journal](../../../journal/web/ai-stats.md#loading-only-and-supervised-recovery--fr000689)
for evidence paths, limitations and the separately authorized direct consolidation
after the journal helper's pre-write `KNOWLEDGE_LIMIT` rejection.
