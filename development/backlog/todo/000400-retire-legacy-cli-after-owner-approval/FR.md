# FR 000400 — Retire Legacy CLI after owner-approved coexistence

## Blocking owner checkpoint

Depends on FR000390 AND a separate later explicit owner decision that the Web product is sufficiently established and Legacy fallback is no longer needed. Promotion approval does not authorize retirement. No automatic date, release count or completed test can satisfy this prerequisite. Until then, retain the Legacy entry points and implementation.

## Outcome

Remove the temporary terminal-report/Watch user interface once Web is the accepted product, without removing any shared analysis, source, report, account, cache, error or diagnostic functionality that the Web application still uses. Follow the migration contract in FR000290/PLAN.md.

## Required behavior after approval

- Inventory consumers before removal. Delete `windows/Legacy/`, `macos/Legacy/`, the explicit Legacy CLI entry and only terminal-specific presentation/bootstrap code and obsolete aliases that no longer have supported consumers. Do not equate directory names such as `watch`, `reports` or `presentation` with disposable code: Watch acquisition/tracking and shared formatters may still be essential to Web. Move genuinely shared formatting/definitions to their existing appropriate owner before deleting a wrapper.
- Keep the canonical Python application/report layer, all analysis formulas and accounting evidence, source adapters, provider integrations, cache generations, runtime-error boundary and Diagnostics functional. Remove terminal-specific tests only alongside their retired surface; retain semantic fixtures/parity tests and replace obsolete entry-point coverage with current supported flows. Do not use retirement to bypass failing accounting tests or delete inconvenient historical evidence.
- Preserve a small operational Python entry for Web startup/control, help/version, actionable startup errors and diagnostics. Retiring the CLI report UI does not mean eliminating all terminal error output or headless development/test access to the application services. An old removed report/Watch argument must fail clearly with migration guidance rather than silently starting a different operation.
- Update navigation, docs, package manifests, default launchers, optional-runtime setup and implementation ownership maps. Remove stale Legacy links and misleading claims of fallback availability. Retain historical completed FR bundles/COMPLETION evidence; do not rewrite history to imply Web had always been the default.
- Never delete user configuration, OpenCode data, runtime logs or historical records as a side effect. Any cleanup is restricted to demonstrably owned obsolete code/artifacts, not general application-data directories. Keep process identity/security, simple source-change shutdown, current menu actions and browser launch behavior intact.
- Do not introduce unrelated UI redesign, provider rewrites, pricing migrations, telemetry, OS services or an updater. This is the final removal of a temporary interface, not permission to rework the protected engine.

## Acceptance

Fresh clone/ZIP and an upgraded promoted installation start the same Web application on Windows/macOS, including first setup and installed offline launch, tray/menu actions, restart and diagnostics failures. All supported report and live views remain available with unchanged numeric/unknown/partial semantics. No runtime import or packaged launcher references deleted terminal-only modules. Existing semantic test coverage remains meaningful and former CLI arguments fail with a useful explanation.

Record the explicit retirement approval and removal inventory in the normal completion evidence. Verify preserved user/runtime data and explain how users start/stop and troubleshoot the Web product after retirement. This specification alone authorizes neither premature deletion nor a new permanent release gate.
