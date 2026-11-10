# FR000668 completion

Implemented in v81.18, 2026-11-10. Original specification moved intact.

## Outcome

Authenticated browser reproduction confirmed that the persistent blue stripe was
`main#content`'s 3px focus-visible outline, not a residual loading bar. Automatic
Models entry keeps focus and new-route top scrolling without that outline. Keyboard
entry/Skip use an inset leading-edge cue on the named Report content landmark, with
a system-outline fallback in forced-colors mode. Interactive focus rings, same-route
scroll/focus, the centered loader and all acquisition/report semantics are preserved.

## Verification and evidence

- All 181 test groups passed across Full (180 passes, one VM-stub failure) and the
  repaired `test_web_loading.py` rerun. The initial Full was not a PASS.
- Eight Chrome startup configurations: Classic/Web, light/dark, 360/1366px; actual
  mouse/keyboard/emulated touch, centered measured progress, complete DOM/no loader,
  cached route return, control/Skip focus, same-route sort/filter and deep links.
- Additional final narrow run: newer source publication, deep-link computed styles,
  forced-colors keyboard fallback. Models-only loading: 3 checks/6 layouts including
  error→Retry, source waits, quiet refresh and inactive completion.
- Models pricing/layout/parity browser probe passed. Read-only real V2 Normal and
  all-models captures passed, retaining one Live owner and closing owned workers.
- Working-tree package validator passed (11 checks, zero failures, 7 advisory warnings).
- Shared hosted routing/browser assertions extended; GitHub's actual checks own CI truth.

[Journal, reproducible probes, retained screenshots/geometry and failed exploratory
checks](../../../journal/web/models-focus.md). Architecture owners and Web guide updated.
No approved exceptions or Models acceptance exclusions. No paid requests, visible
desktop interaction, new dependencies, source mutations, ZIP, tag or Release.
Optional Edge target creation failed; other engines, physical screen-reader speech
and the owner's original private incident are not certified. The unrelated broad
AI Stats fixture smoke is not claimed as passing.
