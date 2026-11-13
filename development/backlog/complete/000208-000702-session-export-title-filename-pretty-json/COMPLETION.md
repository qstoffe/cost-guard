# FR 000702 — completion

Implemented 2026-11-14 in v81.46.

- Native Save As and browser fallback use the observed selected-session title plus
  `.json`, deleting unsafe characters, preserving valid Unicode/spaces, bounding
  long names and falling back safely for empty/reserved names.
- Names are prepared before trusted activation and captured with the selected
  token. Source/token/navigation retirement prevents stale saves; strict ID-shaped
  transport validation remains unchanged.
- Native sanitized JSON has two-space indentation and a final newline. Incremental
  encoding enforces the original 16 MiB on final UTF-8 bytes, with no partial or
  minified substitute. Native content, string whitespace and safety boundaries stay.

## Verification

- Full local suite: **193 file targets passed**, zero failures, 166.7 s.
- Focused export/view tests: **10 passed**, including real-limit pretty expansion,
  filename safety/lifecycle and attachment-response rejection.
- Working-tree validator: **11 passes**, zero failures, seven existing advisory
  warnings; no cap/baseline changes.
- Hidden owned Edge: **PASS** across 24 layout/input configurations; actual
  authenticated title-derived fallback file, pretty/native semantic equality,
  browser collision suffix without overwrite, malformed export rejection,
  trusted-click ordering, cancellation/commit doubles and navigation/focus cleanup.
- Installed V2 own-session read-only export: **PASS**, 107,127 pretty UTF-8 bytes,
  30 messages, 3,712 lines; only scalar evidence retained.

## Explicit evidence caveat

**Decision Delegate, 2026-11-14, FR000702-only:** fresh Windows filename-field
presentation/editing, destination selection/completed native Save, real Cancel and
native modality/focus/tooltip observations remain **NOT RUN / UNVERIFIED**.
Rebuilding a missing isolated-desktop/UIA harness was judged disproportionate for
this narrow delta without a demonstrated native defect, not impossible.
OS filename adjustments/native focus sequences remain uncertain. This is no
functionality/security/test waiver; no visible desktop authority was granted.
Historical predecessor evidence/waivers are not a new native PASS.

The [export journal](../../../journal/web/session-export.md#fr000702--title-filenames-and-pretty-native-json-2026-11-14)
records actual checks, harness correction, exception attribution and limitations.
The Web guide and architecture module are updated; no layer/diagram change.
No inference, other-session export, shared OpenCode mutation, dependency or ZIP.
