# Token category presentation

## FR 000533 — 2026-10-30

The visible sequence is **Input / Cached input / Cache write / Output**. Input
is uncached, Cached input is cache read, Cache write is cache creation, and
Output includes reasoning. Keep these mutually exclusive. Python's existing
`src/display.py` boundary now owns labels and the explicit I/C/W/O legend;
presentation reuses them and the immutable application export supplies additive
display metadata to Web. Existing raw keys/order, token acquisition, price
fallbacks, valuation, samples, sorting and stored schemas are unchanged.

Observed zero, absent Cache write telemetry, a published price without usage,
and a catalog Not applicable rate have separate deterministic regression cases.
A price is not evidence of metered tokens. Missing shares remain unavailable;
any existing known-cost subtotal is not a manufactured token observation.

## Verification and limits

`test_token_category_names.py` checks CLI/DTO numeric correspondence, model and
publisher cells, telemetry distinctions and 80/120/160-column rendering. Shipped
JS deterministic DOM tests cover Overview, Models/all catalog, historical model
and publisher tables, date/range, Watch and Snapshot/Live session detail, with
plain-text legends, semantic headings and unchanged numeric cells/unit switching.
`integration/capture_token_categories.py` captures synthetic CLI text into
`development/tests/fixtures/token-categories/`; these are not OS screenshots or
browser evidence. Numeric prompt/Watch grids retain existing minimum widths;
their 80-column captures document this rather than clipping numeric fields.

Real-browser checks could not start: the configured Python runtime reported
`ModuleNotFoundError: No module named 'playwright'`. No browser was launched,
installed, attached to or discovered by a wider route. Static CSS inspection
confirmed existing scrollable table regions, untruncated headers, wrapping prose
and the narrow-layout breakpoint; this is not rendered-layout proof. Actual
1280px/360px light/dark wrapping, browser accessibility and visual clipping remain
unverified. Decision Delegate authorized the runtime-unavailability exception for
this display-only change, conditional on applicable deterministic checks passing.

The full suite exposed four `powershell.exe` launcher subcase failures:
`SecurityError` / `UnauthorizedAccess` because script execution was disabled,
exit 1 rather than 9009/17. These remain **FAIL—execution-policy blocked**; their
intended Windows PowerShell behavior is unverified. Corresponding `pwsh` cases
passed. Decision Delegate authorized only this unrelated exception, conditional
on all other required checks and package validation passing; no policy change,
weakened assertion or launcher edit was authorized or made.

Final full run: 117 files, 116 passed, one failed file; 1424 test cases reported
and two built-in symlink-privilege skips. The overall suite is not PASS.
Package validation passed with zero failures and four design-budget warnings.
See `development/tests/evidence/fr000533-full-final.json` and
`fr000533-package.json`; earlier failed runs remain separate evidence.

Decision Delegate separately permitted minimal, meaning-preserving recent
product-changelog compaction to keep the unchanged byte cap, with every release
version/date and behavior/limitation retained. README uses current synthetic CLI
text examples instead of stale embedded v78 screenshots; binary assets remain
historical. This documentation-format substitution was also explicitly delegated.
No backlog history cleanup or product architecture-boundary change was needed.
