# Models first-entry focus stripe — FR000668

2026-11-10, v81.18; baseline `cb5670b5089e01b0da83cda88b267c9760cb28e7`.
This is a scoped browser presentation correction, not a dispatcher/performance change.

## Confirmed cause

The authenticated shipped UI over the controlled first-Live fixture reproduced the
stripe in headless Chrome before production edits. Initial focus was `main#content`,
matching `:focus-visible`, with a solid 3px accent outline and 3px offset. At 1366px,
main occupied x=0, y=123.25, width=1366; its top outline painted at y=117.25–120.25,
immediately below/over the navigation's lower edge. After the valid Normal result,
the table appeared and **zero progress elements remained**, but that outline persisted
through later updates. The regression assertion failed on this state. This confirms
a focus outline, not an orphaned progress node, scrollbar or second loader.

The fixture also captures source waiting, manually stepped determinate work, first
complete paint, a later **new source-observed timestamp**, Watch and cached Models
return, keyboard/mouse/touch entry and authenticated direct Models reload. Screenshots
and computed outline/box/progress facts are retained in [models-focus/](models-focus/).
These are synthetic report values over real authentication/HTTP/assets/LiveRuntime,
not screenshots of the owner's original private incident.

## Correction and boundaries

- Only the full-width main focus outline is suppressed. Automatic focus, preventScroll
  and new-route top scrolling are retained; same-route sorts/filters do not refocus.
- A focus-visible interactive origin transfers the keyboard cue to the named Report
  content landmark. An inset 4px leading edge replaces the misleading horizontal rule.
  Already-focused main is not itself evidence of intentional keyboard navigation.
- Skip to report still exposes the target and moves focus. Native Tab proceeds into
  controls, whose existing outlines remain. Forced-colors uses an inset system outline
  because that mode suppresses box shadows; unattended startup still has no outline.
- No report-loading, acquisition, retries, prices, valuation or model requests changed.
  Unknown source waits retain their existing indeterminate state; actual measured
  work retains determinate percentages and successful completion removes the loader.

## Executed verification

- Full: 181 registered groups executed, 180 passed initially. The new focus call exposed
  an incomplete lifetime-VM DOM stub (`classList`, then `getAttribute` after tracking
  activeElement); repairing that stub and adding explicit automatic/keyboard/already-
  focused assertions made the remaining `test_web_loading.py` group pass. Thus all
  181 groups have passing results across the Full run and focused repair rerun, not
  a claim that the initial Full run passed. No passed groups were redundantly rerun.
- Eight Chrome startup cases: Classic/Web × light/dark media × 360/1366px. All pass
  first-Live waiting, centered determinate work, single shared Normal job, loader
  removal, startup/cached and mouse/keyboard/touch navigation, control/Skip focus,
  same-route focus/scroll and deep-link reuse. A final narrow Web-dark run adds
  explicit newer-source timestamp, deep-link computed styles and forced-colors proof.
- Models-only `probe_report_loading.cjs --models-only`: PASS, 3 lifecycle checks and
  6 layouts; stable monotonic progress, inactive completion/Back, quiet refresh,
  terminal error→Retry and source-wait recovery. The fixture's completed Normal/Token
  Mix results lacked their source-observed timestamp, so the browser correctly withheld
  them; the fixture now supplies the same real observation timestamp in both fields.
- `probe_models_refresh.cjs`: PASS; real shipped DOM, controlled canonical reports,
  explicit refresh/failure/recovery, retained focus/filters/sorts, toolbar/help/layout
  and parity probes. No private data or paid model calls.
- Read-only real-installation `probe_web_live.py --models`: PASS on V2, one Live owner,
  Normal complete (98.031s, 30 catalog rows), all-models complete (1.887s), shared
  origin preserved and owned workers closed. Shared OpenCode was not stopped.
- Working-tree validator: PASS, 11 checks, zero failures, 7 existing advisory warnings
  (prose/module sizes); no budget changes, dependencies, ZIP, tag or Release.
- Hosted Chromium routing probe now asserts no initial landmark outline/loader and
  intentional Skip cue; its actual execution is owned by the delivery PR's CI.

## Limits and failed exploratory checks

The integrated browser skill was permission-denied/unavailable here; all browser work
used owned hidden Chrome profiles and loopback fixtures, with no visible desktop effects.
An optional Edge run timed out creating its CDP target and provides **no Edge PASS**.
The broad all-report loading smoke first exposed the missing fixture timestamp above;
after that repair it reached an unrelated AI Stats fixture/loading condition and failed.
The explicit Models-only run covers this FR's required lifecycle; this entry does not
claim all-report browser success or change AI Stats behavior. An initial screenshot
attempt also timed out on a background headless target; activating the owned target
fixed capture. No exception, exclusion of Models acceptance, or Delegate waiver was
required. Physical screen-reader speech, other engines and the original private
incident are not certified by these controlled tests.
