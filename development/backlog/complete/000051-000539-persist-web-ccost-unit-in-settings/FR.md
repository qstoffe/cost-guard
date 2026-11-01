# FR 000539 — Organize Web-only Settings and persist CCost Credits/USD

## Goal and dependency

Extend the **Settings** page delivered by **FR 000538**. Move the existing **CCost: Credits / USD** control out of **Models → More information** into a named **Web settings** section alongside the already implemented **Theme** control. Save Web CCost in the actual `config/user-config.jsonc` and immediately update CCost display throughout Web without reload or report reacquisition.

Establish a clear, **reusable per-setting separation rule**: an existing setting remains shared by CLI and Web while Web merely consumes it and does not provide an editable Web preference. **When a setting is promoted to an editable Web Settings control, give it an independent Web-only value under `webSettings` and leave the existing shared/CLI setting untouched.** Once promoted, changing the Web setting cannot alter CLI behavior, and later changes to the shared/CLI setting cannot silently override the Web preference. This is a convention for future separate FRs, **not** authorization to migrate every existing configuration field or build a generic settings editor now.

FR 000538 owns the initial `#/settings` route, standalone `webTheme` key and narrowly authenticated settings-file mutation. **Implement this FR after FR 000538 is delivered**, without changing that already-running FR or inventing a second settings backend. FR 000526 owns canonical CCost Credits/reference-USD formatting; FR 000528 owns immediate display-token switching in Web. Preserve their pricing/display contracts and change only Web preference location, persistence, and appropriately scoped configuration ownership.

## 1. Web settings grouping and controls

1. Under the existing `#/settings` page title, show one simple, discoverable **Web settings** section. All preferences directly editable in Web belong in this section; **for now it contains exactly two controls**:
   - **Theme:** Classic / Web, retaining FR 000538's current effective behavior and default.
   - **CCost display:** Credits / USD, default **Credits**, with the established brief explanation that USD is **reference token valuation, not billed spending**.
2. Do not add or duplicate generic/shared CLI configuration fields to this section unless a separate approved FR explicitly promotes each one to an independent Web-only preference. Future Web-editable preferences join this same section and configuration namespace instead of ad hoc controls across report pages.
3. Remove the **interactive** CCost selector from Models → More information and any other previous toolbar/shell location. Retain explanatory CCost prose where still helpful, but ensure there is **one authoritative CCost control** and **one authoritative Theme control** under Web settings.
4. Keep the settings page minimal, accessible, keyboard/mobile friendly and immediately saved (no separate Apply/Save). Merely opening Settings, or changing either preference, must not acquire reports, history, pricing or accounts, restart the host/OpenCode, clear frozen observations or disrupt Watch/Live.

## 2. One Web-only configuration namespace, with backward compatibility

Use the existing default config and the same Git-ignored per-user override file; organize Web-only preferences within **one `webSettings` object**, rather than accumulating unrelated new top-level `web*` keys:

```json
{
  "webSettings": {
    "theme": "classic",
    "ccostDisplayUnit": "credits"
  }
}
```

1. The validated `webSettings.theme` enum is `"classic" | "web"`, with default `"classic"`. The validated `webSettings.ccostDisplayUnit` enum is `"credits" | "usd"`, with default `"credits"`. This grouping concerns **configuration**, not a separate settings file or frontend storage store. Shipped defaults belong in `config/default-config.jsonc`; user changes belong **only** in `config/user-config.jsonc`.
2. **FR 000538 compatibility:** That earlier FR introduced top-level `webTheme`. Honor any existing user override for `webTheme` when the user has not explicitly set `webSettings.theme`; do not reset existing Web/Classic choices during upgrade. Effective precedence: **explicit user `webSettings.theme` → existing user `webTheme` → shipped Classic default**. Implement this in the canonical config normalization/validation or equivalent source-aware read so a new shipped default does not mistakenly mask legacy overrides. A future **Theme UI change writes `webSettings.theme`**. The old `webTheme` key can remain accepted as a legacy fallback (no automatic destructive JSONC rewrite); the new nested key wins when both are present. Keep tests for older configs and both-key precedence.
3. **CCost promotion:** Existing `ccostDisplayUnit` remains the **shared/CLI key** used by the CLI (including its unchanged `--ccost-unit` override). Before this promotion, Web follows that existing configured value as today. **Once this FR is delivered, Web uses its own `webSettings.ccostDisplayUnit`, independently defaulting to Credits when absent**, including if the old CLI/shared `ccostDisplayUnit` is USD. This intentional boundary establishes independent defaults; do not overwrite, delete, silently copy or continue following the old setting after promotion. Existing CLI behavior and option precedence must remain unchanged.
4. A missing user file or missing nested override inherits the appropriate default without creating the file during read. A real selection change may create a minimal valid `webSettings` override object. Existing unknown/valid unrelated user settings, nested structures and JSONC comments remain intact.
5. Web-only values must be loaded from the confirmed effective config on a new tab, browser reload or later host launch; valid external edits are recognized at next settings read/launch. No `localStorage`, `sessionStorage`, browser cookie preference, URL setting or continuous file polling. The new schema is a **small organization step for Theme and CCost**, not a general-purpose migration of other settings.

## 3. Immediate, cross-view CCost display switching

1. On each actual user selection change to **CCost display**, persist only `webSettings.ccostDisplayUnit` through the narrow authenticated Settings write mechanism. **After confirmed success**, immediately apply it to the currently visible view and previously retained Web views, without reload, new acquisition or an additional action. On failure, retain/revert to the last confirmed value, show truthful accessible error/status, allow retry and never falsely claim the choice was saved.
2. Keep the selected unit in effect in **Models, Watch, Sessions, session Snapshot/Live detail, Accounts, Reports, Token Mix, Cost per Active Hour** and every other existing Web CCost surface. Route changes, refreshed reports, streaming Watch/Live publications, historical observations, stale/offline content and later selected pages must consistently reflect the effective Web preference. Avoid wrong-unit first render while awaiting analytics when the setting can be fetched independently at startup.
3. Reuse FR 000528's existing Python-prepared `display_units.credits/usd` and shared Web display-token binding. JavaScript must not reprice models, convert/round monetary values, request new history or alter raw numbers, totals, sorting, thresholds, report identity, focus, scroll or pagination. FR 000526's USD uses **$ and two decimals** and is clearly reference USD, not provider billing.
4. Do not convert provider-reported **Billed** money, provider-native AI credits/quotas, **Unaccounted** residual credits, native rate catalogs or dimensionless **Relative CCost** multipliers. A Web preference must not change CLI/Watch reports, pricing, model selection, user credentials or OpenCode state.

## 4. Reuse FR 000538's secure settings read/write

- Extend the existing fixed Settings API and JSONC-edit mechanism to read/write the **two explicitly allowed nested Web fields** `webSettings.theme` and `webSettings.ccostDisplayUnit`, including safe legacy `webTheme` read fallback. Either two narrowly typed fixed endpoints or a strictly allowlisted fixed API is acceptable. **No generic write endpoint, path/key parameter that permits arbitrary config edits, arbitrary JSON bodies or file browser.**
- Preserve FR 000538's loopback-only Host/Origin restrictions, authenticated HttpOnly session, CSRF, lifecycle/shutdown guards, request size/type limits, safe owner/path checks, validated enum/config, bounded atomic replacement, concurrent-change detection and sanitized errors. Never send raw config, paths or secrets to browser/storage/logs.
- When writing one Web preference, preserve the **other** Web preference, legacy `webTheme`, shared `ccostDisplayUnit`, unrelated keys, comments, nested objects, ordering and feasible formatting. Minimal syntax-aware JSONC edits are preferable. Do not serialize merged defaults back over user overrides; malformed, unsupported or unsafe input fails without modifying the file. If a legacy `webTheme` entry cannot safely be removed while preserving comments, **keep it**; documented nested-key precedence prevents ambiguity in effective settings.
- Changes from concurrent tabs or an external editor must not silently overwrite unrelated values; reuse the proportional conflict handling in FR 000538. Valid changes to `user-config.jsonc` must not trigger source-change shutdown, server/browser restart or CLI theme/color changes.
- Update documentation that currently says Web CCost is page-memory-only, and clearly distinguish shared legacy/CLI values from the editable Web-only namespace.

## Acceptance criteria

1. After FR 000538, Settings has one **Web settings** section with **Theme** and **CCost display** dropdowns. No interactive CCost choice remains in Models → More information or other reports. The controls are accessible at 360px/mobile and desktop, and do not trigger acquisition.
2. With no overrides, **Classic** and **Credits** are active in Web. `webTheme: "web"` saved by FR 000538 still produces the **Web** theme after upgrading, despite the new nested defaults. Explicit `webSettings.theme` wins over the legacy value. Editing Theme subsequently saves the nested value without changing CLI color settings.
3. With `ccostDisplayUnit: "usd"` set for CLI but no `webSettings.ccostDisplayUnit`, Web **still defaults to Credits** after promotion, while CLI remains USD. Selecting USD on Web writes `webSettings.ccostDisplayUnit: "usd"` to `config/user-config.jsonc`, updates CCost on the **current page immediately**, and does not affect CLI; selecting Credits reverses it. Later CLI config changes cannot override the Web choice.
4. Navigate all Web report routes, refresh, receive Live/Watch updates, reopen frozen session detail, reload, open a new tab and relaunch: all CCost views use the saved Web-only unit with existing Python display semantics and without unrelated acquisitions or changed ordering.
5. A user JSONC file containing comments, nested account/source values, customized CLI colors, original `ccostDisplayUnit`, legacy `webTheme` and new `webSettings` survives **Theme and CCost** changes independently, without lost or rewritten unrelated values. Concurrent changes, malformed JSONC, invalid enums, read-only file, symlink/reparse/path hazards and lost authorization fail safely with no false success.
6. Confirm shared non-Web-editable settings continue to govern CLI and Web until individually promoted by a future approved FR; **only** Theme and CCost are organized here. CLI flags, reports, legacy settings, quota/billing/rates, exact CCost calculations, rounding, warning thresholds and actual data acquisition remain unchanged.
7. Focused deterministic validation/config/API/security/Web DOM tests and actual-browser checks cover nested grouping, legacy theme precedence, default/override isolation, direct-page updates, reload/new tab, multiple routes, Live/Snapshot, concurrent and failed writes. Update user docs and any verification references that describe the previous page-memory-only behavior.

## Boundaries and queue

This is **one cohesive follow-up FR** to the existing Settings implementation, not a separate generic settings-framework feature. No broad migration of arbitrary configuration keys, second config file, generic editor, new frontend framework, browser storage, new pricing logic, report redesign, CLI display change or edits to the in-progress FR 000538. Future settings promotions require their own separately approved FRs; they reuse the **Web settings** group and `webSettings` namespace.

**Permanent identity:** `000539`. **Queue priority:** `000300`, following FR 000538 (`000200`). Backlog-only change, no product runtime implementation or version bump.
