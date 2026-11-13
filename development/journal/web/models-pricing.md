# Models pricing refresh, toolbar presentation and compact Mini help

Source revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Checked revision: 50d88a4bcfba6c1f853607ce0ee84a5c9663c0a3
Last checked: 2026-11-06
Status: current

## Summary

### Source-owned DOM and input modality — FR000695 / v81.39

Price publication now retains its Models root and benchmark sibling; equal
records keep physical row identity. Pointer activation no longer triggers
keyboard-only price focus recovery. [RED/after browser and real-source evidence,
including the precise unverified PiP focus-transfer boundary](models-isolation.md).
Earlier transport, valuation and platform proof below retains its original scope.

### Toolbar alignment — FR 000618 / v80.198, 2026-11-07

Scoped delta on `a80b5128ea18f40d07d1d89708e0d5ae7159efb6`; the earlier
pricing/transport findings below keep their original evidence and limits.

The rendered pre-fix toolbar confirmed the `.model-prices` collision: Refresh and
date both used `ui-monospace, monospace`, with a 40.25px / 15px-font button and
12.75px date. `.model-relative` correctly used monospace too. Separating
`.model-price-controls` restores the normal system-UI family for action/date/status,
uses Watch's exact 30px height / 12px font / 3.75px 9.75px padding at the default
15px root, and leaves numeric table styles unchanged. Centered native filter labels
and wrapping groups avoid overflow without another card/frame. Coarse-pointer action
and label targets measure 44.25px. Feedback may naturally add rows rather than clip.

Keyboard proof also exposed the disabled-button focus loss that preceded result
replacement. The explicit action now restores that focus only while its own view
remains current and the user has not focused/clicked elsewhere. Listener cleanup is
limited to listeners actually registered by that action. No backend, pricing,
report scheduling, checkbox meaning, sort or other page style changes were made.

Observed checks on Windows / Chrome 156.0.8078.80:

- `scratch:/models-toolbar-before.json`: actual pre-fix computed styles.
- `scratch:/models-toolbar-after.json`: PASS, 240 real-DOM cases at
  360/800/1280/1366/1920px, Classic/Web light/Web dark, 100/125/150/200% root-font
  scaling and normal/refreshing/long-date-error/unavailable states. Checks inspect
  actual control bounds, overlap, clipping, page overflow, checkbox text/box centers,
  desktop shared axis, UI-vs-monospace computed fonts and coarse-pointer targets.
  Long synthetic localized labels and unbroken error text are stress inputs, not
  observed upstream messages. Native Enter/Space, native touch, disabled duplicate
  guard, failure/retry, retained factual time/table, sorting/filter choices and
  deliberate focus movement pass. Watch's actual toggle computed metrics match.
  The 360-light and 1280-dark screenshots were visually inspected.
- `scratch:/models-layout.json`: all six existing light/dark 360/1366/1920
  canonical tier/filter/sort/panning browser cases PASS.
- `scratch:/full-tests-final.json`: final supported Full suite, 155 isolated files,
  zero failures, 111.0s. A broad focused-pattern experiment incorrectly grouped Web
  tests into one subprocess and timed out; its focus-listener failure was repaired.
  The final bounded Full run supersedes that experiment, not a timeout waiver.
- `scratch:/models-live.log`: real V2 installation, authenticated HTTP and actual
  spawned price refresh PASS: new upstream observation, 29 catalog rows, Watch's
  catalog remains pinned, 103.150s. Normal 61.448s / 25 selectable / 14 latest;
  all-models 6.087s / 29 rows / 16 latest. One Live owner, two streams, run origin
  and advancing publications preserved; 173.2222s overall. No inference/shared
  service stop; zero remaining owned threads/processes, no cleanup failures.
  One history-batch observation recorded an error; this was not a whole-history
  health audit and does not establish that unrelated history work was error-free.

Integrated Review was disconnected; hidden Chromium used an owned temporary
profile, not a personal browser. Font scaling is not a physical OS/browser-zoom
claim. Upstream failure proof is controlled offline/invalid provider evidence;
the real upstream check succeeded. Other engines, a real screen reader and
physical desktop/touch hardware were not tested. No current requirement/test
exception was requested or granted. User instructions did not change, so
`docs/web-beta.md` needs no update; architecture and code-map notes were updated.

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
