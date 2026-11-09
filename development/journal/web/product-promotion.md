# Web as the default product — FR000650

2026-11-09, v81.0. Entry-point and branding migration only: no new Web host,
accounting/source/pricing engine, dependency, user-data migration or Legacy retirement.

## Ownership and compatibility

- `src/product_entry.py` routes desktop default intent to the existing Windows
  PowerShell handoff or macOS managed launcher; help/version stay local. Every
  explicit legacy argument is forwarded unchanged to bootstrap, including unknown
  option errors. Unsupported no-argument platforms fail with actionable alternatives.
- `cost-guard-cli.py` retains the independent guarded bootstrap. Platform CLI pairs
  moved intact to `Legacy/` with corrected parent traversal and this explicit entry.
  The macOS report's exit variable avoids zsh's read-only `status` parameter.
- Web launchers/template moved out of Beta. SourceGuard covers real native trees
  and all three entries, with unchanged link/reparse and metadata-only safeguards.
  The owned content-addressed Finder cache now emits `Cost Guard.app` with canonical
  display/version metadata; old generated outputs are not deleted or overwritten.
- The authenticated header uses the serving `/api/status` version; per-route titles
  and tray/menu branding drop Beta. The existing guide URL is intentionally retained.
- Redirected/noninteractive Windows startup failures print recovery/Legacy guidance
  without attempting a blocking desktop dialog; ordinary interactive errors retain it.

## Evidence so far

- Native-Web profile: 14/14 files passed on Windows. Actual moved CMD/status plumbing
  and PS discovery/exit behavior use non-UI fixtures with spaces/Unicode paths.
- Full: all 179 registered files executed; initial failures were four causal stale
  launcher-path/version-whitespace test owners. Repairs and focused reruns are pending
  final consolidation; the initial Full is not recorded as PASS.
- Working-tree package validation passed; seven existing advisory/design warnings,
  no hard-cap or structure-policy relaxation. No source/release ZIP was generated.
- Hidden Chrome 156 rendered the authenticated shipped shell: `Cost Guard v81.0`
  and correct Models/Watch/Accounts/Sessions/AI Stats/Settings tab titles; no duplicate
  branding or page errors. Private one-use launch credentials remained in memory.
  Evidence: `scratch:/branding.json`, `scratch:/branding.png`.
- Real read-only V2 installation probe completed Normal (29 catalog/25 selectable)
  and All Models (29) reports with the same Live owner, authenticated HTTP/SSE, and
  owned cleanup; shared OpenCode was untouched. It does not prove full history
  acquisition or private account correctness. Evidence: `scratch:/live-models.json`.

## Native verification decision and remaining scope

Decision Delegate rejected disruptive workstation reassurance and requested a bounded
improvement to the existing hosted native case: moved shell → production `main()` →
production launch wrapper, including config/native preflight and macOS app preparation;
one existing OS browser handoff only, then restart/owned cleanup with unchanged
preferences and checkout identity. The old offline shim bypassed those wrappers.
The case now isolates acquisition/private test state, not the launcher path. An
unavailable opener is exit 4 and is distinct from successful browser launch/rendering.
Actual hosted results and the final physical-only exception are still pending.

Integrated browser was unavailable (`browser.disconnected`); hidden Chromium was used
without changing identity, security or desktop permissions. The workstation native UI
probe is NOT RUN. Physical Windows appearance/input, macOS Finder/Gatekeeper, quarantine,
consumer-desktop launch and accessibility remain unverified, never inferred from mocks,
hidden DOM or hosted APIs. The Delegate agrees v81 promotion may retain explicit
physical macOS limits, but has not yet waived an unresolved native integration failure.
