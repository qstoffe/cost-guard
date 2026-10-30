# Completion — FR 000536

Date: 2026-10-30
Version: v80.117
Branch: `fr-000536`, targeting actual default `main`.
Product/test source: `61088f210250f41e2f28f2a5d1da74794995915c`.

## Implemented scope

- Restored real intended-account OpenAI quota on the affected Windows machine,
  not merely a renamed error. OpenSSL's failed built chain had substituted an
  expired local `CA` intermediate for the peer's valid chain. Windows OpenAI
  HTTPS now trusts server-authentication `ROOT` anchors plus configured OpenSSL
  CA paths, without importing that intermediate cache as trust anchors.
- Certificate/hostname checks and default verification flags remain enabled.
  Empty eligible Windows roots fail closed; other platforms retain Python
  defaults. No certificate installation, trust-store/clock/proxy change,
  credential renewal, account switch, sign-in or new runtime dependency.
- Real urllib certificate, other TLS, DNS, connection and timeout failures retain
  safe typed causes through normalization, Diagnostics and report/Watch rendering.
  HTTP status stays zero without a response; 401/403/429 remain distinct.
  Exports allowlist TLS categories and integer verification codes in 0..255,
  never arbitrary exception text, certificate subjects or response bodies.
- Certificate validation does not receive fast retries. Normal bounded failed
  checks, successful recovery, independent provider lanes, current identity,
  failed-capacity clearing and separate CCost remain protected.
- Added ten transport regressions and synthetic localhost certificates/key;
  none is a workstation/provider credential. User support/version documentation
  and relevant provider/presentation/code-map contracts were updated. The latest
  history prose was shortened to retain the unchanged file cap.

The original specification and diagnostic attachment were moved intact as one
bundle. New reusable evidence is outside that payload in
[the OpenAI journal](../../../journal/openai-identity.md).

## Actual functional verification

On 2026-10-30, CPython 3.14.8 / OpenSSL 3.5.9 on Windows:

- Credential-free, still-verifying comparisons reproduced code 10 expiry with
  Python defaults and with PARTIAL_CHAIN removed; ROOT-only trust reached HTTP
  401. Peer/built-chain role comparisons isolated the expired local intermediate.
  This 401 was causal transport evidence, not authenticated quota acceptance.
- Bounded read-only OpenCode V2 2.2.4 metadata matched the sole selected active
  canonical quota record to an integration connection and token-account/header
  identity, comparing identifiers only in memory. Actual method was
  `chatgpt-browser`; no auth-file override or inactive-account fallback.
- The production provider returned HTTP 200, native weekly quota **75% remaining**
  and reset `1793807183000` UTC milliseconds. It returned no five-hour window.
  Credentials were equal before/after. Existing connection/provider-route
  preservation was checked read-only; no paid inference was issued and no newly
  tested model-call success is claimed. Another legacy sign-in was unnecessary.
- Two unmodified production CLI Watch runs, 75s and a fresh 40s start, rendered
  weekly **25% USED** with reset text and no OpenAI quota-error blocks. Five
  successful run-local observations included ordinary approximately 30s scheduled
  refreshes. Final main-thread publications followed retrieval by 0.409s and
  1.013s. Unchanged provider percentages were observed honestly, not synthesized.

Exact sanitized timestamps, reproduction commands, chain-comparison setup and
privacy bounds are consolidated in the journal linked above. This is native
production CLI output captured through pipes, not desktop pixels, a launcher
double-click, a diagnostic rerender or mocked acquisition.

## Actual local tests and package validation

- `py -3 -B development/tools/run_tests.py --suite full --json-report ../full-tests-final.json`:
  **119 files: 118 PASS, one FAIL; 1,448 registered tests; two skips; no errors**.
  All ten new transport tests, 17 existing identity/method tests and applicable
  OpenAI, Watch, HTTP, recovery and privacy files passed. This is **not an overall
  Full PASS**: four subcase assertions failed in the unchanged launcher file.
- The two skips were
  `MacAppTests.test_linked_cache_destination_is_refused` and
  `LifecycleTests.test_guard_does_not_follow_runtime_symlinks`, because this
  Windows host cannot create the required test symlinks.
- `py -3 -B development/tools/validate_package.py --working-tree`: **PASS**,
  11 checks, zero failures, four nonblocking design-budget warnings for README,
  analysis/context, reports/service and watch/coordinator. The initial history
  hard-cap failure was repaired and revalidated; no budget was raised.
- Real loopback TLS regressions reproduce expired-intermediate shadowing and
  reject expired leaves, untrusted chains and hostname mismatch. Additional tests
  exercise actual urllib exceptions through normalization/export/both renderers,
  safe evidence filtering, ordinary Watch publication/failure/recovery with a
  healthy neighbor, empty roots/purpose filtering and retained platform defaults.

## Decision Delegate exception and remaining limits

The **Decision Delegate**, not the user, authorized only four execution-policy-
blocked local Windows PowerShell 5.1 subcases in
`development/tests/test_launcher_feedback.py`:

- `test_windows_missing_python_is_clear_in_both_shells_without_starting_app`,
  `shell=powershell.exe`: expected 9009, actual 1.
- `test_windows_skips_duplicate_failures_finds_next_python_and_preserves_mode_exit`,
  `shell=powershell.exe`, separately report/watch/diagnostics: expected 17, actual 1.

The host refused `probe.ps1` with `SecurityError/UnauthorizedAccess` because
scripts are disabled. The conditional decision required history-cap repair,
normal investigation of any other failures, actual intended-account quota and
scheduled/fresh-start Watch acceptance, unchanged TLS/account/privacy scope, and
passing normal hosted PR checks/protections. No hosted failure or functional
requirement was waived. The delegate could not inspect the clone because of
enforced scratch boundaries and relied on supplied evidence. No execution-policy
change, bypass flag or weakened test was used. Corresponding `pwsh` coverage
passed but is not equivalent PowerShell 5.1 proof; those local behaviors remain
unverified. Final local evidence confirms only that precise failure boundary.

Each bounded Watch child was ended with CTRL_BREAK and reaped, exiting
`0xC000013A` with nonempty stderr. The harness kept stdout/stderr only in memory,
did not retain the stderr content or establish its cause, and did not separately
inspect helper-process state. A graceful/no-error shutdown is **not** claimed.
No physical desktop, assistive-input or consumer launcher acceptance was run.
Success is specific to the measured machine/current credential generation and
does not establish token-sharing quota or future upstream/account behavior.

## Knowledge and delivery assessment

Updated the existing OpenAI identity/TLS journal, its route and affected provider,
presentation/Diagnostics and code-map contracts. No system-layer dependency,
validation trigger, permanent release gate or workflow diagram change was needed.
Product source delivery does not install/reload or restart the existing runtime.

Hosted verification and canonical PR/merge evidence will be recorded after the
ordinary PR checks complete; local results above do not substitute for them.
