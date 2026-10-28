# FR 000524 — Rename Windows and macOS launchers to whitespace-free filenames

## User problem and objective

Users launching Cost Guard from an existing terminal must quote or escape everyday launcher filenames containing spaces. The owner requests replacing spaces with hyphens across Windows .cmd and macOS .command entrypoints, including Beta and Diagnostics. Keep double-click use just as straightforward.

## Required changes

Rename all eight currently shipped user-facing launchers, preserving their current directories and extensions:
- windows/Cost Guard.cmd -> windows/Cost-Guard.cmd
- windows/Cost Guard Watch.cmd -> windows/Cost-Guard-Watch.cmd
- windows/Beta/Cost Guard Web.cmd -> windows/Beta/Cost-Guard-Web.cmd
- development/user-tools/diagnostics/windows/Cost Guard Diagnostics.cmd -> development/user-tools/diagnostics/windows/Cost-Guard-Diagnostics.cmd
- macos/Cost Guard.command -> macos/Cost-Guard.command
- macos/Cost Guard Watch.command -> macos/Cost-Guard-Watch.command
- macos/Beta/Cost Guard Web.command -> macos/Beta/Cost-Guard-Web.command
- development/user-tools/diagnostics/macos/Cost Guard Diagnostics.command -> development/user-tools/diagnostics/macos/Cost-Guard-Diagnostics.command

Update all documentation, README quick starts, troubleshooting/crash/Diagnostics paths, launcher references inside PowerShell/Python/AppleScript/embedded source and tests/fixtures, as well as package/source distribution rules and any macOS Finder helper cache-input identity depending on filenames. Do not leave accidental references to non-existing paths or duplicate competing launcher entrypoints.

## Boundaries and dependencies

- This FR changes path/entrypoint naming, not analysis, UI, shell ownership or Web lifecycle. Coordinate ordering with FR000522 and **before FR000520's native Web launcher build**, so only current names are used in later implementation.
- Preserve Windows scripts' checkout-relative arguments, code signing/trust story, macOS executable permission bits, Finder-open behavior, no-extra-dependency contract and paths containing spaces elsewhere in the user's checkout. Only shipped launcher basenames become hyphenated.
- Document that previously bookmarked/shortcut-linked old names need updating. Do not silently ship aliases that retain the space-named UX unless a compatibility reason is explicitly accepted.

## Acceptance

All eight names are present and executable through terminal invocation (without quoting the filename itself) and their OS double-click/Finder paths. Search/test fixtures and user documentation reference the new filenames, including Diagnostics error guidance. Windows terminal/Watch Ctrl+C and Beta launch handoff, macOS launcher parity and native helper behavior retain their separate safety checks. Verify source ZIP/clone and no broken modes. No product runtime changes are made by publishing this FR.

**Priority:** High / after FR000523 and before existing pending FR000520.
