# Software errors and crash reports

Unexpected Python defects show **`COST GUARD FAILED`**, return non-zero and name a standalone report under `diagnostics/crashes/cost-guard-crash-YYYYMMDD-HHMMSS-PID[-N].txt`. Send that individual file to a maintainer; normal full Diagnostics is **not** run automatically. Windows still returns to the usable PowerShell prompt.

Explicitly isolated worker/account faults show **ERROR** while unaffected results continue. Software incidents append to `diagnostics/errors/cost-guard-errors-YYYY-MM-DD.log`; repeated polling faults are summarized rather than logged every refresh. Healthy runs create no error log. Expected timeout/auth/source-unavailable/config/CLI conditions and intentional Ctrl+C use their normal handling, not crash reporting.

Reports include version/runtime metadata and full chained stack structure (file/function/line), but never locals, source-code lines, arbitrary exception messages, prompts, credentials or raw payloads. Review a file before sharing. Only Cost Guard-owned error/crash files older than **30 days** are removed best-effort at startup; unrelated files are untouched.

If reporting itself fails, minimal stderr still identifies the original exception and the process fails. Force-kill, power loss and native/interpreter corruption cannot be recovered this way. Terminal rendering is independent of normal report/Watch renderers, with plain stderr as fallback.
