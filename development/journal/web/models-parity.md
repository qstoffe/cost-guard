# Models visual parity — FR000659

2026-11-10; v81.9, based on `7fc76c401b0a4ecae2f44e8a5853b54146c5c85d`.
Scoped presentation evidence, not a new pricing or acquisition audit.

## Ownership and invariants

- `render.js::modelHeading` supplies both h2/source structures: a common heading,
  small muted parenthesized source and one safe official link. Refresh/date/status
  are the common toolbar's left group; the independent filters stay at the right.
- `app.css` includes both Models tables in the existing semantic table-shell/cell
  skin. Shared grid structure and sort controls replace partial duplicate rules;
  only column tracks, reference ratio typography and numeric alignment differ.
  The benchmark section stays unboxed; its table gets the same thin rounded shell.
- The effort details control uses Settings' control tokens at Models button size.
  Its popup has one full-width checkbox row per source value, bounded vertical
  scrolling and no horizontal flow. Coarse-pointer targets remain at least 44px.
- `benchmark.js` sorts a deduplicated copy of source options by conceptual rank,
  then case-insensitive alphabetical extras with deterministic case-sensitive ties.
  Exact source strings remain selected-state keys; aliases are never merged and
  missing effort is never invented. Custom subsets, empty selection and All retain
  their existing refresh reconciliation. Solved stays elastic and aligns left;
  task cost stays right-aligned. FR000658's Solved-descending default is unchanged.
- No backend, data contract, model matching, benchmark denominator, price, API,
  Settings behavior, dependency or architectural boundary changed.

## Executed verification

- Local Full: **181 isolated file entries**; 179 initially passed. The two failures
  were the old heading/source-toolbar assertions in `test_web_views.py` and
  `test_web_overview.py`. Both causal assertion updates passed their focused reruns.
  The original Full invocation was not all-green. Models tests separately pass
  exact source-key ordering, aliases/extras, no invented missing option, deduplication,
  source non-mutation, High-only/none/All and refresh reconciliation.
- Hidden Chrome **156.0.8078.80**, authenticated shipped application with controlled
  synthetic source: **PASS**, 13 interaction checks and 284 layout records. The new
  36-case matrix covers 360/768/1366/1920px, Classic/Web light/dark and 100/125/150%
  text size. Computed headings, links, shells, headers, ordinary cells, sort buttons,
  refresh buttons and status match on the same page. Solved/cost alignment, right-edge
  groups, no document overflow, popup bounds/one-column rows, native touch and a
  long-list native wheel scroll pass. Existing 240 toolbar stress cases also pass,
  including long errors, 200% text and separate coarse-pointer checks. Keyboard
  Enter/Space/Escape, mouse/outside dismissal, help, selection and refresh recovery pass.
  Evidence: `scratch:/models-chrome.json`; both full tables and the open picker are
  captured together in `scratch:/models-chrome-parity-1366-{classic,light,dark}.png`,
  with additional 360px captures. Values in these screenshots are synthetic, not
  published benchmark evidence. The emulation matrix runs after the pre-existing
  input sequence to avoid contaminating its touch state; stale pre-FR000658 initial
  sort expectations were updated to match the already-shipped default.
- Frozen-report layout probe: **six cases PASS**, 360/1366/1920px, light/dark plus
  Classic/Web and 100/125% zoom in each page. `scratch:/models-layout.json`.
- Real read-only workstation `probe_web_live.py --models --benchmark`: **PASS**.
  35 Harbor rows, 27 exact matches, 30 reference rows; actual 100-prompt comparison
  help sums correctly. Full-source denominator and independent retained pricing
  verified. Normal/full Models reports both complete; one V2 Live owner, two streams,
  no model calls, owned workers closed, shared OpenCode untouched.
  `scratch:/real-models.log`. An earlier run was interrupted during the version edit;
  the repeat against stable source completed normally.
- Package validator: **0 failures, 11 passes**, v81.9 consistency; seven existing
  advisory size warnings. No hard cap or exception baseline was raised.

## Limits

Integrated Browser was disconnected. Hidden Chromium supplied actual rendering and
native protocol input without visible desktop effects. No physical desktop,
assistive screen-reader, Safari/Firefox or macOS acceptance is claimed. Real-source
HTTP evidence is separate from controlled-source browser geometry. No waiver,
model inference, ZIP, tag or GitHub Release. Remote check and merge truth belongs
to the delivery PR.
