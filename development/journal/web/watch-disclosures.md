# Full Watch disclosure stability — FR 000709

2026-11-14 · v81.53 · base `91148bb08dab562504184af4a58806ce5a699b19`.
Scoped causal investigation, not proof of the owner's uncaptured browser incident.

## Reproduction and ownership

The original `watch.js` deletes Running call controls whenever a publication omits
their details. Failed groups switch between `details` and plain text based on the
current detail list, even with the same nonzero outcome aggregate. Skills rebuild
their entire child list when one count changes. The backend intentionally withholds
private invocation evidence during partial/retrying/reverification states; an
observed card can also await a newer catalog revision. Previously the export lost
the distinction between temporary withholding and authoritative empty membership.

`fixtures/watch_tool_outcomes.py::disclosure_publications()` constructs 48
synthetic canonical-source observations and projects them through the actual Python
Live exporter: four failures, an arriving fifth, independent successful tools,
foreground 1→2→1, two background calls, skill counts, safe input/reason corrections
and four partial publications followed by recovery. Partial exports contain the
same aggregate activity but no invocation inputs/lists.

`probe_watch_disclosures.cjs` renders those actual DTOs through Full Watch in hidden
Chromium. Against the base revision's actual Watch asset, it fails: stability,
surviving focus/selection, no-remount and established-arrow assertions are false.
The comparison uses the new producer's explicit availability field, which the old
asset ignores; the old list omissions/aggregate shape are unchanged. This is a
synthetic before/after reproduction, not the owner's private runtime trace.
The probe's combined private-clearing/availability-note assertion also fails on the
old asset; this is not evidence that the old asset retained private text.

## Change and security lifetime

- `ToolObservation.detail_state` carries observed/pending/invalidated separately
  from counts, safe revisions and native UI choice. The card owner sets pending
  during source revision verification even if the visible card state is observed.
  The application exporter independently suppresses all non-observed detail.
- `WatchCard.activity_scope` is a SHA-256 digest of source type/generation/instance.
  It exposes no locator and does not change on normal revisions. Full Watch keys
  cards by this scope, owning session and focal prompt; real replacement/removal
  clears obsolete controls and their detached input nodes.
- Pending publications retain only existing bounded call-node identities and
  native open/closed choices. Input and failure reasons are cleared immediately,
  including under focus/selection, and replaced with neutral availability notes.
  Recovery reconciles real source-owned identities into those same nodes. No old
  DTO/private input is cached for recovery. New unrelated siblings remain private.
- An established nonzero failure group stays the same native disclosure when its
  detail list is omitted, including authoritative count-only updates. An observed
  missing call is removed; a never-detailed aggregate stays plain text, not invented
  call records. Real success corrections/removal discard the old group.
- Skills rows key by skill ID. Summary fragments and unchanged text update
  incrementally. Actual reorder uses the existing atomic-move/selection restoration
  path. Colors, logical indentation, canonical counts, physical deduplication,
  privacy allowlists, five-per-running-mode/ten-failure limits and shared input/
  event/replay budgets remain unchanged.

No source reads, expansion requests, model calls, polling loops, persisted private
input or service owners were added. Pending UI maps do not accumulate identities:
only the previous bounded population survives, then authoritative membership
reconciles/removes it. Aggregate and Skills maps delete absent groups.

## Verification

- Full suite: **199/199 groups passed**, zero failures (173.4s and 174.1s runs).
  Final focused invocation/tool/Watch/card/V1 coverage: **95 tests passed** after
  the final projection privacy guard. Strengthened source-scope and full-size scope/
  100-card budget assertions then passed in **50 invocation/card tests**.
- Working-tree validator: **11 passes, zero failures**; eight existing advisory
  prose/design-size warnings. No cap or baseline raised. Final documentation
  validation is included in the delivery output.
- Hidden Edge **157.0.4341.46**: **six cases**, Classic/Web light/Web dark ×
  1366/360, on final production assets and Python DTOs. Each executes the 48-frame
  sequence twice (open, then explicitly closed) and asserts unchanged surviving
  node objects, no incidental subtree remount, focus/selection endpoints, immediate
  private-input clearing, stable arrow, sibling independence, source-scope reset,
  authoritative failure removal, safe reason correction and reorder. Resource
  counts do not change on disclosure/refresh.
- Existing FR000701/FR000688 probes also pass mouse/keyboard/touch, 125% zoom,
  narrow wrapping, no injected markup, indentation/colors, unchanged timer-frame
  scroll and security clearing. Classic narrow/Web dark screenshots inspected;
  final scalar results/images are in `scratch:/browser-delivery/`.
- Read-only real-installation `probe_web_live.py --tool-outcomes --tool-invocations`
  passes on V2 via the authenticated owned host: one activity card, six evidenced
  failures/six failed details, two active invocation details, one preserved native
  command and one labeled timeout in the final observation. Zero model calls;
  shared OpenCode untouched; owned probe threads/processes close successfully.
  Global history/daily coverage is not claimed.

## Limits

The exact owner-reported refresh incident remains **not captured/not verified**.
Partial gaps and authoritative corrections are synthetic; real observed invocation
and failure DTOs are complementary installation evidence, not that incident's
reproduction. The browser tests prove native DOM/input semantics in hidden Edge,
not physical desktop, assistive-technology, other-engine or non-Windows operation.
No paid inference, shared-service interruption, release ZIP, Git tag or GitHub
Release. No acceptance waiver or scope deferral was needed.
