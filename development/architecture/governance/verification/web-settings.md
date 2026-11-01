# Persisted Web settings verification

FR 000539; v80.120; Windows workstation / Python 3.14; 2026-11-01–02.

## Ownership and implementation

Settings contains one Web settings group with exactly Theme and CCost display.
`src/web/settings.py` extends/replaces the former theme owner, not its security
model: the same bounded canonical validation, preserving JSONC offsets, owner/path
checks, serialized writes, last-moment identity/byte comparison and private atomic
replacement apply. Only two fixed nested leaves are writable. Legacy `webTheme`
stays untouched; source-aware normalization precedes shipped-default merging.
The original `ccostDisplayUnit` and `--ccost-unit` remain CLI-owned. Unpromoted
settings remain shared; this feature does not migrate other fields.

Authenticated startup reads Web preferences before report/Live presentation. A
confirmed save updates CSS and existing Python-prepared CCost text bindings,
including detached retained detail roots. Report numbers, identity, sorting,
pagination, billing/native quota/rates and acquisition are unchanged. Settings
reads on entry, not by polling or browser persistence. Other tabs converge on
their next read, not an automatic broadcast.

## Deterministic and package checks

- Full: all 120 files passed. After final test strengthening, the five focused
  config/settings/views/remaining/CLI-unit targets passed all 38 tests.
- `validate_package.py --working-tree`: 11 passes, zero failures, four existing
  design warnings (README, analysis/context, reports/service, Watch coordinator).
  Hard caps were retained; README/history wording was condensed, not caps raised.
- Configuration/store cases cover missing-file reads, minimal nested creation,
  both-key theme precedence, legacy theme with partial nested overrides, independent
  Web Credits despite CLI USD, external edits and fresh store instances.
- Byte-preserving tests include comments/CRLF/order/escaped keys, nested objects,
  both Web preferences, CLI color/source/account overrides and legacy keys.
  Invalid/duplicate config/enums, readonly/oversize/hardlink/reparse/symlink hazards,
  failed replacement, concurrent editor changes and permission loss immediately
  before commit remain non-destructive with no temporary leftovers.
- Real HTTP tests exercise authentication, Host/Origin/CSRF/type/exact-body/enum
  guards on both writes, sanitized failures, conflict status, early theme and no
  report jobs or source-guard shutdown. Common HTTP framing/bounds retain their
  existing tests. The VM checks confirmed-only application, rollback/retry,
  unchanged-selection suppression, native-focus recovery and external reads.
- Real HTTP plus the served app VM exercises actual persisted CCost writes,
  retained Models and detached detail bindings without acquisition. Numeric
  goldens, Session/Watch updates, native values and reversible raw-order-preserving
  token selection remain in the existing display/remaining/live/detail tests.

The first Full run found an obsolete test expecting CLI USD to initialize Web;
its replacement explicitly proves the new independent default plus saved-unit
application. A subsequent run failed only README/history hard caps; concise
documentation resolved them. Neither failed run is recorded as PASS.

## Actual integrated-browser checks

The built-in Chromium Review browser used `serve_web_remaining.py`: shipped assets,
real canonical DTOs and the real settings writer with disposable config. Synthetic
HTTP/source transport is not product security or real-source visual proof.

- `web_theme_browser.js` measured 108 combinations: Classic/Web × light/dark ×
  360/1366/1920 CSS pixels × nine views. No document overflow or preference-signal
  mismatch; exactly two Settings selects throughout. Classic stayed dark; Web
  followed the actual child-frame preference. Mobile Classic and desktop Web
  Settings screenshots were inspected.
- `checkWebCCost` exercised both units across Models, Accounts, Sessions,
  date/range, captured Token Mix, captured Cost per Active Hour, Watch, session
  Snapshot and Follow live. No old interactive CCost controls remained. USD cells
  used `$`/two decimals; credits reversed them. Models retains dimensionless
  Relative CCost; Billed money remains USD when CCost returns to credits.
- Initial Settings entry submitted no reports; an actual native CCost selection
  issued only its fixed settings POST. Reload/new tabs read saved Web values.
  A fixed external legacy file (`webTheme:web`, CLI `ccostDisplayUnit:usd`) yielded
  Web theme and independent Credits, including the early HTML theme.
- A readonly disposable file produced a truthful error and retained confirmed
  Credits; restoring permissions and retrying saved USD. New-tab startup read USD.
  Native keyboard Home then saved Credits, restoring `ccost-unit` focus with a
  solid keyboard outline; reload retained Credits. Final fresh-tab console had
  no JavaScript errors.

Browser inspection used genuine iframe CSS widths, not physical devices. It does
not prove screen-reader behavior, native OS menus, physical mobile input, macOS or
real-source visual parity. No such proof or requirement exception is claimed.

## Separate read-only real-installation probe

`probe_web_live.py --detail --reports` passed against installed V2: one acquisition
owner, two streams, three Watch rows and three account rows, preserved run origin
and advancing sequence. Shell 0.013s; first source view 13.982s. Detail first/latest
access and freeze were consistent (one observed row). Normal/all-models/sessions/date
completed in 7.824/2.801/1.019/28.733s; explicit deep history cancelled. Owned Live/HTTP
workers closed; shared OpenCode was untouched. This does not modify real user
preferences or prove real-source visual parity.

No model calls, credential changes, real user config mutation, install/reload,
shared-service stop, ZIP or GitHub Release was performed. No requirement/test
waiver was requested or granted. Architecture owner/navigation docs were updated;
journal no-update: these current owner/evidence facts are sufficient.
