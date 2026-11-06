# Models pricing refresh and compact Mini help

Source revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Checked revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Last checked: 2026-11-06
Status: current

## Summary

FR 000598 / v80.182 changes the checked base with this delivery's source/tests.
An explicit Models action must distinguish a real successful upstream observation
from a cached fallback. `GitHubCopilotPricingProvider.get_catalog(force=True)` is
deliberately fail-soft for existing consumers, so its return alone cannot prove a
fresh fetch. The new locked `refresh_catalog()` requires a validated upstream
document and raises without replacing the prior cached payload/date on failure.
Unchanged rates may acquire a new factual observation time without a new revision.

`src/web/jobs.py::ModelsPriceRefresh` distinguishes explicit actions from ordinary
TTL captures while reusing in-flight equality coalescing and the existing four-job,
one-process, sixteen-result, 8 MiB and 120-second bounds. Authenticated, CSRF/Origin/
Host-protected `POST /api/models/refresh` accepts only `{}`. Composition constructs
no account providers and pins the new catalog on one fresh canonical ReportService;
prices, ratios, sample valuation, revision and timestamp are projected together.
The separate Live/Watch catalog is not replaced mid-publication.

The browser retains its old report during refresh/failure, disables duplicate
clicks and preserves filters, multi-sort, units and practicable focus/pan. It never
revalues tokens. Navigation/SSE do not force retrieval. Semantic label-only heading
help replaces the Models disclosure/cards, including actual sample count, token
categories, hidden 2/96/1/1 fallback and source tier thresholds. Mini subscription
help now contains exactly primary-window Capacity and Next reset, using canonical
unit/provenance/reset tokens. Rich Full Watch/Accounts help and visible warnings
are unchanged.

## Evidence

Observed on Windows, 2026-11-06; no model inference or shared OpenCode stop.

- Final frozen-source Full suite: 150 files, zero failures, 92.9 seconds;
  `scratch:/full-tests-delivery.json`. The new provider/composition/job tests are
  registered in `development/tools/run_tests.py`. Initial failures were stale
  removed-card expectations, repaired causally rather than waived.
- `development/tests/test_web_price_refresh.py` covers warm-cache bypass, unchanged
  source provenance, offline/invalid rejection without cache replacement, coherent
  changed ratios/sample valuation, no accounts or pinned-Watch repricing, distinct
  coalescing, multiprocessing marker serialization and truthful account readiness.
  `test_web_runtime.py` exercises real HTTP auth/CSRF/Origin/body/admission guards;
  existing runtime tests independently exercise spawned process lifecycle/bounds.
- `node development/tests/integration/probe_models_refresh.cjs <Chrome> <output>`:
  PASS in Chrome 156.0.8078.80. Production HTTP/auth/assets and canonical Python
  reports with synthetic source/upstream and controlled in-memory jobs cover warm
  cache, changed/unchanged retrieval, exact old table/date on offline/invalid failure,
  retry, double-click, preferences/navigation, semantic focus help and bounded
  Classic/Web light/Web dark layouts at 360/1280. This fixture is not production
  concurrency/process proof. `scratch:/models-refresh.json` and six associated PNGs;
  360-light and 1280-dark screenshots were visually inspected.
- `py -3 development/tests/integration/probe_web_models.py --browser <Chrome>
  --output <output>`: six light/dark 360/1366/1920 cases PASS, including exact tier
  sorting, Shift keyboard/mouse actions, filters and overflow;
  `scratch:/models-layout.json`.
- `node development/tests/integration/probe_web_help.cjs <Chrome> <output>
  --watch-only`: PASS, actual Document PiP and Full Watch, Classic/Web light/dark,
  narrow/150% zoom, 600ms hover, focus/touch/Escape/panel transfer/rapid-exit cleanup.
  The two-line Mini help and richer Full Watch help coexist;
  `scratch:/mini-help.json` and associated images. VM tests separately cover
  exact/inferred/unknown Capacity in Credits/USD and reset/unstarted/unknown states.
- Real installation `py -3 development/tests/integration/probe_web_live.py --models
  --accounts`: PASS. V2, one owner/two streams, three account cards, publication
  advanced, run origin preserved. Normal 64.791s, 29 catalog rows/25 selectable/14
  selectable-latest with verified availability; all-models 4.080s, 29 rows/16 latest,
  no accounts. Total 76.9594s; zero owned threads/processes and no cleanup failures.
- Real installation `py -3 development/tests/integration/probe_web_live.py
  --refresh-prices`: PASS, authenticated HTTP through actual spawned report process,
  real upstream and canonical projection. Action 3.856s, 29 rows, genuine retrieval
  at/after request time, same pinned Watch catalog object; total 5.1102s. Zero owned
  threads/processes, no cleanup failures. Scalars retained here from observed output,
  not private source/session/account payloads.

Final working-tree package validation had 11 passes, zero failures and six existing
advisory prose/design warnings; hard caps were not raised. The task's COMPLETION.md
retains the delivery summary. No ZIP or release was built.

## Next investigations

The original combined Node-hosted synthetic browser-to-spawn fixture stalled before
target entry: job running without progress after more than 20 seconds, zero fixture
fetches and no entry marker. Direct Python execution of that target worked. The
pre-target cause remains unknown. **Decision Delegate** authorized the split browser
fixture plus independent provider/composition/security/serialization/process tests,
with Full/package/live checks still required. No equivalent synthetic retry, visible
desktop work or product requirement waiver was authorized or needed. The later real
HTTP/spawn/upstream success narrows, but does not explain, that original failure.

Integrated Review browsing was disconnected; hidden Chrome used no personal profile.
Physical OS pointer/window behavior, a real screen reader, macOS and other engines
were not tested by this task and are not claimed. Browser fixture concurrency alone
does not establish production concurrency; backend coalescing tests own that proof.

## Rejected hypotheses

- A returned forced legacy catalog proves fresh prices: false; cached fallback is
  supported legacy behavior. Strict upstream validation is the explicit action's seam.
- A new timestamp alone proves coherent repricing: false; canonical changed-price
  tests assert relative ratios and sample valuation against the same new catalog.
- The synthetic pre-entry stall proves production process startup is broken: not
  established. Existing process tests and the later real authenticated spawned action
  passed; retain the failed experiment and its unresolved cause without a false PASS.
- Browser-local arithmetic or replacing Watch's catalog is necessary: rejected;
  isolated canonical report composition preserves existing valuation ownership.
