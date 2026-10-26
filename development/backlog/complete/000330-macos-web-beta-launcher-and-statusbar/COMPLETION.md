# FR 000330 — experimental macOS Web launcher implementation

Delivered as v80.84 on 2026-10-26. The owner explicitly requested best-effort implementation despite this session having only Windows, after the initial native-platform limitation was reported. **This is implementation delivery, not native macOS acceptance.** The immutable FR is preserved; its real-Mac checks remain outstanding and are not represented as PASS.

## Implemented

- `macos/Beta/Cost Guard Web.command`: checkout-relative, spaces/Unicode-safe discovery of already-installed Python 3.11+, no package/tool download, unchanged stable CLI/Watch/Diagnostics entrypoints. Git executable mode 100755 and scoped LF attributes are recorded; actual Finder/ZIP behavior is unverified.
- Same-process AppKit status item through a narrowly typed standard-library `ctypes`/Objective-C bridge. Main-thread default/tracking event loops, retained Open/Exit callbacks and a tracking-mode stop timer; one bounded asynchronous default-browser handoff. Readiness follows native install/pump; callback and worker faults reach the existing stop owner.
- The existing shared restart/private-state/source-change lifecycle is reused. Bounded isolated native preflight occurs before stopping a healthy old instance. Native failure does not fall back to an icon-free advertised server. Browser failure retains retryable Open. macOS's existing refusal of unsafe PID-based force-stop is unchanged.
- Optional first-launch Finder app creation from committed AppleScript using only `/usr/bin/osacompile`, in protected user-local checkout state outside Git. Source/product/OS/architecture/Python fingerprints, bounded artifact hash/mode checks, atomic publication, unchanged cache reuse and partial-build cleanup. A failed optional preparation reports the error and keeps the `.command` route; unverifiable caches are not overwritten. No compiled binary is committed.
- `docs/web-beta.md` documents the experimental status, generated-app location, security/Terminal limits and remaining native checklist. A separately approval-gated real-AppKit probe is supplied, not automatically run.

## Verification actually run

Windows workstation, installed Python, no implementation agents or model switches:

- `py -3 development/tools/run_tests.py --suite full`: PASS, all 101 registered test files, zero failures (final code run 41.3 seconds). New synthetic tests cover typed 64-bit dispatch, retained callbacks/fatal handoff, main-thread enforcement, preflight crash/timeout preserving the old host, readiness/partial cleanup, asynchronous Open/Exit/browser failure, quoting, source-change inclusion, app reuse/rebuild/tampering and compile failure/timeout cleanup. These tests do not load AppKit or execute a compiler.
- `py -3 development/tools/validate_package.py --working-tree`: PASS, zero failures. Four pre-existing design-budget warnings remain (README, analysis context, report service, Watch coordinator); no hard cap increased. Validator admits only the exact new Beta directory/files, not arbitrary uppercase directories or public launchers.
- `py -3 -B development/tests/integration/probe_web_lifecycle.py`: PASS on the real installation: HTTP ready, source acquired, report complete, authenticated stop passed, owned thread stopped, source guard unchanged, native GUI not run, model requests zero. Only the probe's own host was stopped; the shared OpenCode service was not stopped.
- Git whitespace check and tracked executable-mode inspection passed. No ZIP, tag or GitHub Release was created.

## Not verified / known limitations

No Mac was available. Real AppKit loading, Objective-C ABI/event-loop/menu tracking, Intel/Apple Silicon compatibility, Finder app execution, no-Terminal behavior, Gatekeeper/quarantine, physical double click, extracted ZIP executable metadata, native browser selection, native repeated restart/source-change/HTTP-fault/orphan cleanup, offline first launch and system osacompile output remain **NOT RUN**. A fake compiler and recorded Cocoa calls are not substitutes. The optional native probe also remains NOT RUN. No dependency or OS-protection constraint was relaxed; no package/compiler installation, quarantine removal, signing bypass, Terminal control or Automation/Accessibility request was added.

Generated apps bind their checkout/interpreter paths. After moving either, rerun the `.command`; old shortcuts can point to the old location. Old fingerprinted app caches are retained rather than broadly deleted. `.command` can leave a Terminal window depending on preferences. The generated app is the intended terminal-free route, not a demonstrated one. Ordinary provider/pricing network policies remain separate from offline GUI preparation.

## Knowledge and dependencies

Architecture updated only for the new macOS native ABI/status/launcher/app-cache owners, test routes and explicit proof limitations; the shared server/analysis boundaries are unchanged. Journal assessment: **no-update**—no new measured native macOS conclusion exists. Prerequisite FR 000310's lifecycle is reused; Windows-specific tray code is not imported. Later Web FRs can use the same owner without relying on unverified native success. No selected FR payload or attachment was edited and no recovery evidence for another FR is removed.
