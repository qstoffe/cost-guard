# Software errors and crash reports

Unexpected Python defects show **`COST GUARD FAILED`**, return non-zero and name a standalone report under `logs/crashes/cost-guard-crash-YYYYMMDD-HHMMSS-PID[-N].txt`. The message, and any other error that stops Cost Guard (not Ctrl+C or self-healing outages), ends with **Need help? Run Cost Guard Diagnostics:** and the absolute path of `development/user-tools/diagnostics/windows/Cost Guard Diagnostics.cmd` (Windows) or `development/user-tools/diagnostics/macos/Cost Guard Diagnostics.command` (macOS) in this installation. Diagnostics is **not** run automatically. Windows still returns to the usable PowerShell prompt.

Explicitly isolated worker/account faults show **ERROR** while unaffected results continue. Software incidents append to `logs/errors/cost-guard-errors-YYYY-MM-DD.log`; repeated polling faults are summarized rather than logged every refresh. Healthy runs create no error log. Expected timeout/auth/source-unavailable/config/CLI conditions and intentional Ctrl+C use their normal handling, not crash reporting.

Reports include version/runtime metadata and full chained stack structure (file/function/line), but never locals, source-code lines, arbitrary exception messages, prompts, credentials or raw payloads. Review a file before sharing. Only Cost Guard-owned error/crash files older than **30 days** are removed best-effort at startup; unrelated files are untouched.

If reporting itself fails, minimal stderr still identifies the original exception and the process fails. Force-kill, power loss and native/interpreter corruption cannot be recovered this way. Terminal rendering is independent of normal report/Watch renderers, with plain stderr as fallback.

Release-date metadata failures are not software defects: classified failures (DNS, connection, TLS, HTTP status, timeout, parse/schema, matches) go to `logs/errors/cost-guard-metadata-YYYY-MM-DD.log` once per failure period (start, change, bounded summaries). Real recoveries go to the matching log in `logs/recovery/`. Live retry/health state lives in `cache/state/model-metadata.json`; a healthy state is not an error. Legacy `logs/recovery/model-metadata.json` is copied atomically without deletion; current state wins, with the valid legacy copy as read/write fallback when cache state is unavailable. Verified dates remain in the pricing catalog cache.

Diagnostics bundles include owned errors/crashes/recovery under `logs/` and live metadata under `state/model-metadata.json`, plus relevant metadata summaries. Verified archives remove only unchanged logs idle at least 60 seconds; active files and both current/legacy state are retained. Recovery events include the version. Event logs follow 30-day retention; persistent state is excluded from log cleanup. Runtime state/logs never ship in product ZIPs.

## Expected connectivity conditions

**OpenCode unavailable** means the V2 background service is not reachable, not an
unexpected crash or proof of an uninstalled application. Start Desktop V2 once
after starting the computer, then retry the report; Watch waits/reconnects,
including unfinished initialization. Unsupported schemas, authorization failures
and invalid registration are distinct terminal conditions. Main guidance omits
legacy table details. See [connectivity and safe environmental checks](connectivity.md).
Source incidents retain bounded sanitized categories/phases and recovery timing
in `logs/recovery/watch-recovery.json`; Diagnostics archives but does not prune
that live history. Certificate-verification errors remain distinct from other TLS.
