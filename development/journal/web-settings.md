# Web Settings and appearance

Source revision: 9ba5faa68788a85ec96e685d72d8e1c5f00788f9
Checked revision: 9ba5faa68788a85ec96e685d72d8e1c5f00788f9
Last checked: 2026-11-01
Status: current

## Summary

FR 000538's candidate on this base introduces one deliberately narrow write owner,
`src/web/theme.py`, not a generic configuration editor or preferences store.
`config.validated_values` shares startup validation before minimal JSONC mutation;
CLI palettes/legacy normalization and acquisition semantics remain independent.
Atomic replacement must compare current bytes and identity after preparing the
private temporary, not only before parsing. Ordinary editor-conflict protection is
not a hostile same-user transaction guarantee. Windows CRT fstat and Path.lstat
ctime differ: compare file identity/size/mtime plus original bytes, not ctime.

Native selects lose focus when disabled during immediate saving. Restore it only
when the connected control previously had focus and the user has not moved to
another control/route. Never optimistically apply or claim a persisted theme.
Theme styling must exclude `tr.new` when preserving ordinary new-row text; mark
the actual cells/notices instead. Web's adaptive tokens stay independent.

## Evidence

Full: 120 files, zero failures, 1,462 cases passed and one ordinary Windows-host
macOS zsh/PTY skip. Working-tree validator passed with four pre-existing design
warnings. Actual integrated Chromium measured 108 route/width/theme/preference
combinations with no document overflow; readonly save failure/retry, native select
keyboard/focus, early shell, reload/new-tab and zero Settings report requests were
observed against disposable configuration and synthetic transport/data. A separate
read-only V2 probe completed Normal/all-models with one owner/two streams and owned
shutdown; it was not real-source visual proof.

After the final Classic-only `.new:not(tr)` refinement, fresh full visual reruns
timed out and Review screenshot access reported a nonvisible desktop window. Those
attempts are not PASS. The **Decision Delegate** authorized only omission of a fresh
post-refinement full visual matrix/screenshots: prior comprehensive browser evidence
and a focused final computed-style check were adequate relative to disruption from
external automation/owner interruption. That final check passed (ordinary row text
grey, marked cells/notices/running lime; Web colors retained). No implementation,
backend-test or delivery gate was waived; no external desktop use was authorized.
Final post-change appearance was not freshly visually inspected. Native OS/physical
input, screen-reader/assistive technology and real-source visual behavior remain
unverified. This was the delegate's decision, not a new user prompt.

Reproduction, measurements, safe file/HTTP cases, failed attempts and uncertainty:
[theme verification](../architecture/governance/verification/web-theme.md).

## Next investigations

If separately requested, inspect final appearance with Review visible and collect
native/assistive-technology and cold first-paint evidence. No automatic external
browser fallback, OS-setting change or paid inference is authorized by this note.
Concurrent tabs intentionally read the file on entry/reload rather than polling.

## Rejected hypotheses

A successful HTTP shell or source probe does not prove browser painting or quota
freshness. A 100%-ready report waiting for an animation frame while Review is not
visible is not a completed visual matrix. Readonly rejection must not be presented
as Saved, and whole-row `.new` inheritance is not the intended selective lime accent.
