# Web Settings and appearance

Source revision: 9ba5faa68788a85ec96e685d72d8e1c5f00788f9
Checked revision: 9ba5faa68788a85ec96e685d72d8e1c5f00788f9
Last checked: 2026-11-01
Status: current

## Summary

### Compact Settings and native option help — 2026-11-06

FR 000597 (v80.181) replaces the old framed Settings page with aligned compact
rows. Separate label/current-choice help uses ContextHelp; native customizable
selects own keyboard/touch/focus/commit/cancel. A stable description column belongs
to the popup itself, not an overlapping competing tooltip. Narrow/touch pickers
show inline descriptions; unsupported browsers retain native controls with a
Choice help disclosure. Never use an option `label` attribute for rich choices:
the tested Chromium rendered the label but suppressed the rich description.
Nonzero DOM layout plus real pointer/AX assertions and an inspected screenshot
distinguish actual help from an invisible string. Description IDs stay outside
selectedcontent's cloned subtree.

Final Full passed 149 files, validator passed 11 checks (six advisory warnings),
and installed Chrome/Edge passed option-hover, keyboard/touch, rollback/reload,
default-change, theme/width/CSS zoom and actual browser-zoom matrices. The short
real V2 probe failed its owned-worker assertion during a pending quota request;
the account-aware probe waited for publication and passed with one owner, two
streams, three accounts and zero owned threads/processes after close. Neither
probe is complete history or real-source visual coverage. Shared OpenCode was
untouched. No waiver; physical OS/screen-reader use and non-Chromium engines
remain unverified. [Detailed evidence](../architecture/governance/verification/web-settings-597.json).

### Historical appearance implementation

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

### PR CI repair

Run 41356409265 passed Windows Full/package and native API checks but failed
`test_web_theme.py` on both macOS architectures; all browser checks stopped at the
old adaptive-dark-default assertion (`ci_browser_web.py:99`). Trusted disposable
fixture roots now resolve macOS's `/var` alias, without relaxing production ancestor
guards; deterministic read/write tests also reject a linked ancestor above the root.
The hosted browser uses disposable canonical config and exercises actual Settings
saves, both Classic preferences, adaptive Web, persistence/reload/new tab and no
Settings report acquisition. It remains hosted-only, not workstation UI permission.

GitHub Actions job-log retrieval returned HTTP 401; PR/jobs/Checks annotations were
available. Detailed original macOS traces were not retrieved, so canonicalization
was a hypothesis, not an observed traceback diagnosis. Fresh run 41357257423 then
passed both macOS Full/package phases (1,456 passing cases, seven platform skips),
supporting that fixture repair. Its browser test exposed a locator distinction:
the wrapping label text includes option text, but Chromium's accessibility tree
names the combobox exactly `Theme`; use the accessible role/name, not raw label text.
The integrated browser confirmed this without external UI. Windows had one bounded
batch-status fixture assertion failure in that run; it remains a failed run, not PASS.
The **Decision Delegate** authorized this narrow repair/evidence path, with local
Full/validator and all fresh required hosted checks still mandatory before merge.
No alternate identity/access route or additional test waiver was authorized.
After these test-only repairs, local Full passed all 120 files (zero failures,
55.2s); the validator passed all 11 checks with the same four design warnings.
After the locator correction, local Full again passed (120 files, 51.2s), and
run [41358018350](https://github.com/qstoffe/cost-guard/actions/runs/41358018350)
passed all three platform jobs: Windows 2025, macOS 15 ARM and macOS 15 Intel.
Full/package, isolated native and rendered Chromium phases passed, including actual
Settings writes/reloads and no JavaScript errors. The intermediate Windows fixture
failure did not recur; no launcher assertion, deadline or production code changed.
This is focused hosted smoke coverage, not the waived complete visual matrix,
physical/native-desktop, assistive-technology or real-source visual acceptance.

If separately requested, inspect final appearance with Review visible and collect
native/assistive-technology and cold first-paint evidence. No automatic external
browser fallback, OS-setting change or paid inference is authorized by this note.
Concurrent tabs intentionally read the file on entry/reload rather than polling.

## Rejected hypotheses

A successful HTTP shell or source probe does not prove browser painting or quota
freshness. A 100%-ready report waiting for an animation frame while Review is not
visible is not a completed visual matrix. Readonly rejection must not be presented
as Saved, and whole-row `.new` inheritance is not the intended selective lime accent.
