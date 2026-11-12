# FR000681 completion — installed Python and readable startup failures

Implemented for v81.29 (2026-11-12), delivered through
[PR #286](https://github.com/qstoffe/cost-guard/pull/286).

- Shared pre-Python resolvers cover bounded, deterministic installed-runtime
  discovery for each OS's Web, Legacy report/Watch and Diagnostics launchers.
  Old, broken, hanging and Store-alias candidates cannot mask a usable candidate.
  No installs, downloads or PATH/registry/config/profile/security changes occur.
- Fixed, spaced, sanitized startup reasons distinguish Python and Web failures;
  browser-only failure preserves running-host guidance. Interactive feedback is
  cleared before failures; redirected output remains plain and nonblocking.
- Generated Finder commands re-enter discovery instead of pinning an interpreter.
  Native lifecycle, private cache/logging and ownership boundaries are retained.
- Full local verification passed 184 groups (2297 tests, 4 named skips); Windows
  native-focused checks and the package validator passed. Actual workstation
  PEP 514-only lookup/invocation and authenticated real-source generation passed.
  Protected common and Windows/macOS ARM/Intel checks at `8d06cef` passed;
  the final PR head's checks are required before normal protected merge.

The initial generic live probe **FAILED** its immediate quota-worker retirement
assertion; it is not relabeled. The scoped follow-up observed zero final owned
workers/processes with normal providers retained. Decision Delegate authorized
journal-only residual exclusions after core non-PATH real-runtime startup,
stale-command recovery and native lifecycle proof: physical Finder/Gatekeeper/
Explorer, visual dialog/tray/browser and actual consumer-installed distribution
acceptance remain **NOT RUN / UNVERIFIED**. The reported user's root cause is not
established. No model calls or shared OpenCode service stop occurred.

See the [verification and scoped-decision ledger](../../../journal/python-discovery.md)
for real-versus-synthetic coverage, repaired CI causes, receipts and limitations.
