# Installed contract revision 2 adoption

## Identity and outcome

2026-10-25; source base [df44c06](https://github.com/qstoffe/cost-guard/commit/df44c06a97244278abd8d0dc9ed90ea12c368e47). Native selection: `contract-sync/2/df44c06a97244278abd8d0dc9ed90ea12c368e47`. Installed schema SHA-256: `547e9d73f34cb3997f826d4c62c0fd9d55719c57aeef6c7568d15c73b06f4fcb`.

Migration candidate, not a claim of merge. This report travels with its delivery PR; Git/native delivery receipts establish actual publication.

## Publication dependency

Canonical installed `verify-release` currently rejects the immutable base history with `HISTORY_INVALID: Earlier active minors need one exact rolling consolidation range.` The base uses `## Earlier v80 history`; the helper requires a `### Earlier minors (v80.1-v80.65) — consolidated` range even before first adoption. Its documented first-adoption exception allows legacy excess bullets, not this heading format. The candidate uses the strict current range and older-version heading, but cannot rewrite the Git base. Native Contract Sync verification passed; no PR, push, merge, delivery or cleanup is claimed. An authorized Toolkit helper compatibility fix and manual installation/reload are required before publication can proceed; no local verifier fallback or installed-runtime edit is permitted.

## Changes and deliberate exclusions

- Relocated architecture contracts into six owner leaves, with owner/test routes, failure/privacy facts, unchanged file-budget facts and historical performance evidence in their current categories. Added the bounded overview Mermaid and journal routes. Consolidated the legacy development-root README/router into the overview, preserving its authority/data facts while meeting the installed manifest's two-file development root; installed Toolkit remains the only workflow authority.
- Used the installed source-bound priority migration: 90, 120, 130 and 140 keep their numerical identities, bodies and order, now in six-digit bundles. No ordinary FR is completed by this maintenance selection; all four remain todo. There were no completed records to backfill or prune and no attachments to transfer.
- Moved all 28 fixture files under tests, updated package imports/resource roots, and retained Quick/Full/profile membership exactly. Updated the AST inventory to count nested fixtures once, with a deterministic regression.
- Moved both human Diagnostics launchers, corrected their root traversal, and changed only the shipped Diagnostics path literals in `cost-guard.py` and `src/runtime_errors.py`. These source changes qualify one functional minor, v80.71 dated 2026-10-25; release adapter facts bind runtime, README and separate root history. Consolidated the legacy rolling history to ten bullets without rewriting retained published minor entries.
- No Watch/account/usage/pricing semantics, dependencies, source credentials, shared-service lifecycle, user configuration, native protections or GitHub Release/tag/ZIP policy changed. No installation/restart or UI automation occurred.

## Verification

- `python development/tools/run_tests.py --suite full`: PASS, 90 files, zero failures (49.5 seconds on this Windows workstation). Initial relocation failures exposed old resource paths/launcher expectations, a fixture-copy parent and README cap; repaired causally, all 64 affected tests passed before the final Full run. Assertions and caps were not relaxed.
- `python development/tools/validate_package.py --working-tree`: PASS, 11 checks, zero failures. Four design-budget warnings remain (README and unchanged context/report-service/Watch-coordinator owners); hard caps preserved.
- Source-bound migration checks: PASS, 77 local Markdown links resolve, suite/profile membership unchanged, budget JSON unchanged, all 28 fixtures present and non-Python fixture bytes unchanged modulo checkout line endings.
- `python development/tools/macos_compatibility.py`: PASS, 14 simulated cases. Native macOS execution NOT RUN.
- Read-only Diagnostics collection (`collect(network=True, snapshots=1, test_service_start=False)`): healthy installed V2 2.1.4; report build succeeded; headless Watch initialized in 550.61 ms and polled in 374.97 ms, with three rows/accounts and no flowing-text overflow at 80/120/160 columns. Today progressed from pending to populated. These are single-run observations, not before/after performance claims or upstream quota freshness proof. No raw output, private identities, account labels or payloads are included here.
- Interactive launchers, native terminal visuals, Ctrl+C, sleep/wake and native macOS NOT RUN. Static path assertions and simulated launcher tests do not prove those UI behaviors.

## Knowledge assessment and follow-ups

No runtime architecture boundary changed. Existing performance/source evidence and limitations were retained and rerouted; no new general runtime/performance journal conclusion is warranted. The new journal INDEX is navigation, not a session log. The pending bootstrap FR must independently reconcile its retained historical requirements; the OpenAI subscription and two Watch requests are unimplemented and remain pending.
