# FR 000567 — evidence inventory

The [branding journal](../../../../journal/web/branding.md) owns interpretation and
the explicit Decision Delegate verification exception. No PNG is brightened or
rescaled. JSON physical scratch prefixes in the native Chrome failure stack are
normalized to logical `scratch:/`; error/status text is otherwise retained.

- `dpi-baseline.json`: hidden installed-pythonw original-resource DPI/monitor probe.
- `python-manifests.json`: installed interpreter CreateProcess-manifest inventory,
  read through PE data-resource APIs; neither declares DPI awareness.
- `full-tests-summary.json`: final Full runner summary (136 units, 1,617 tests,
  one platform-specific skip); measured elapsed time and validator result are in
  the journal.
- `native-hicon.json`, `native-hicon-{light,dark}.png`: actual production 24px HICON,
  offscreen DrawIconEx; **not taskbar screenshots or physical theme tests**.
- `native-lifecycle.json`: targeted real-native host commands, exact own-entry
  simulated taskbar loss/re-add and cleanup; **not mouse/Explorer restart proof**.
- `menu-before-capture*`: original unaware popup; `menu-stock-reference*`: original
  implementation under external PMv2; `menu-candidate-capture*`: candidate PMv2.
  JSON includes physical rectangles and exact contexts. `-menu.png` is the bounded
  screen BitBlt CAPTUREBLT capture; `-menu-print.png` is supplemental PrintWindow.
  Both have fidelity limitations described in the journal.
- `native-{before,after}-icon.png`: failed physical notification-area proof; the
  shell-reported icon rectangle yielded no recognizable icon. Not a visual PASS.
- `chrome-branding.json`, `edge-branding.json`: independently passing real headless
  browser route/decoding/title/reload/reopen/server-restart checks.
- `chrome-native-branding.json`: **FAIL**, CDP timeout after partial checks/capture.
  `chrome-native-branding.png` is its bounded native tab strip at DPI 144; it is not
  a CDP page screenshot or proof of the later failed restart sequence.

Source artwork and the generator are maintained in runtime/tests, not these images.
The disposable stdio/CDP/native probes used synthetic reports and owned handles;
no credential-bearing bootstrap URL, cookies or private source payload was retained.
