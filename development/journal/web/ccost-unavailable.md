# Unavailable reference CCost explanations — FR000628

2026-11-08, v80.208. Scoped explanatory change, not a repair of upstream model
selection or historical Claude Agent pricing. Existing amounts, rate resolution,
billing, quotas and defaults remain authoritative and unchanged.

## Classification boundary

`domain/reference_cost.py` carries at most six distinct, sorted reason facts per
scope; omitted causes add a neutral unknown fact. `pricing/reference_diagnostics.py`
diagnoses already-unpriced canonical requests from the current catalog and token
evidence. It does not alter valuation or acquire sources. Contributors include
linked children, not just the visible main model.

- Missing known token categories produce usage wording with bounded category names.
- Missing acquisition proof or a failed/stale catalog produces qualified catalog
  wording, never a definitive list-absence claim.
- Only recognized explicit version identities with no corresponding catalog
  candidate can establish available-list absence. This includes the owner-observed
  Claude Sonnet 4 identity. No new pricing alias or speculative retired rate exists.
- Unknown, ambiguous and unrecognized variants retain identity wording. A matched
  model with no selected tier or required rate gets rate wording. Existing
  cache-write fallback remains unchanged.
- Unproven causes use neutral available-model-pricing/usage wording. Token Mix's
  aggregate cells intentionally use this fallback instead of inventing request
  attribution. No raw provider error, private ID or prompt is added to reasons.

Catalog `analysis_signature` remains rate-semantic. Separate `diagnostic_signature`
invalidates explanatory session/detail caches when evidence freshness changes,
without repricing unchanged requests. Session reconciliation rebuilds bounded
reasons ephemerally, including on unchanged-source cache reuse; no persisted
per-request diagnostic ledger is added. Existing disposable scalar row caches
validate the allowlisted facts. A failed forced fetch's process-local stale marker
survives metadata-only refresh until a verified price observation supersedes it.

## Interaction boundary

Shared `ContextHelp` retains its 600ms hover, focus/tap, Escape, selection and
document ownership. Actual N/A amounts own the target, not a whole row/cell or
generic noncost N/A. Full Watch merges reason and rich breakdown. Mini keeps
stable separate prompt and parenthesized session spans with existing compact
prompt details; each unavailable component explains only its own scope. Its daily
target is active only for N/A, not an ordinary positive partial amount. Empty
dynamic content closes help without moving focus. Pending acquisition stays
Loading; known partial subtotal, true zero and known cost retain their display.

## Verification and limits

- Final product Full suite: all 172 files passed, four workers, 120.9 seconds,
  including the new deterministic file and failed-price/metadata regression.
  Working-tree validation passed all 11 checks with seven existing advisory
  prose/design warnings; no budget, structure baseline or exception was raised.
- Canonical deterministic fixtures cover Sonnet absence, identity/ambiguity,
  missing rate/usage, unverified/stale catalog, multiple contributing models,
  positive partial, zero, known cost, retained cache/reason refresh and bounded
  privacy-safe export. The stale-marker metadata regression was observed failing
  before the fix and passing afterwards.
- `probe_web_help.cjs --ccost-unavailable` passed in hidden Chromium with actual
  Document PiP, real CDP keyboard/Escape/hover/touch, text-sized Full/Mini targets,
  independent Mini pairs/day, unit/focus/node identity, production Sessions
  catalog/detail/footer and retained history reason correction; no JavaScript
  exceptions. N/A-to-known daily updates preserve node/focus, close empty help
  and remove its help styling/tab stop. Sanitized local artifact:
  `scratch:/ccost-browser.json`.
- Earlier expanded probe attempts failed because the headless opener remained
  unfocused after PiP. The final Sessions phase closes PiP and explicitly uses CDP
  focus emulation; it still asserts in-place DOM/focus/open-help reason refresh.
  This is not proof of physical OS focus restoration.
- The existing rich-help probe's Credits goldens had relied on the former default;
  it now explicitly selects Credits. The product default remains USD.
  `probe_web_help.cjs --watch-only` passed with Chrome 156.0.8078.80: both Full
  tables and real Mini PiP, Classic/Web light/dark, narrow/150% zoom, rich groups,
  delayed hover, flyover cancellation, pointer transfer, touch/Escape, long titles,
  241 virtual seconds of stable totals and pending Loading. Artifact:
  `scratch:/existing-help-browser.json`. Its missed window-blur fallback is
  synthetic, not physical OS focus evidence.
- An earlier combined real-installation probe independently passed Sessions but
  failed later with a connection reset during unrelated whole-Earlier proof.
  Concurrent source edits were a possible cause, not established root cause.
  Final relevant verification freezes product source and omits `--watch-cards`;
  no new universal history/performance gate is introduced here.
- The source-frozen `--sessions --prompt-cost --session-cost --daily` attempt
  passed Sessions (2,974 roots, visible indexed 0→50, two detail rows) but then
  reached `probe_prompt_cost_timeout` without an eligible fully priced Earlier
  row. It did not reach session-cost/daily parity phases. HTTP/Live remained
  active; cleanup left zero owned threads/processes and no cleanup failures.
  This does not prove prompt/session raw parity and is not recorded as PASS.
  Those older probes require eligible fully-priced certified Earlier cards;
  focused Sessions reason-wire and daily observation are independent evidence.
- Final focused `probe_web_live.py --sessions --daily`: PASS on the real V2
  installation. Of 53 exported Sessions/detail cost values checked, three were
  N/A with allowlisted identity reasons and nonzero-cost clarification. Visible
  index 0→49 (49 ready, one retained), two detail rows; 2,974 available roots.
  Daily 3,278 requests/109 prompts reconciled category costs; partial pricing and
  prompt coverage remained qualified. One Live owner, two verified SSE streams,
  advancing publication, zero model calls started, no shared-service stop and
  zero owned workers/cleanup failures at close. The exact Sonnet owner incident
  remains unestablished; synthetic canonical evidence proves that classification.

Synthetic browser evidence does not reconstruct the historical owner incident or
prove physical desktop, screen-reader or other-engine behavior. No paid model
test, service stop, alternative rates or provider/model-selection repair occurred.
No requirement exception was requested or granted by this worker.
