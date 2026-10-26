# FR 000490 — Accounts page: structured CLI-equivalent quota and billing information

## Problem

Web Accounts currently reads as a dense mixture of disconnected paragraphs, raw numbers and quota tables. The owner wants recognizable CLI account information, but with a much clearer and more modern web layout. The current `render.js` outputs provider/account identity, availability, billing, CCost scopes, Pace, remaining fraction and each quota as numerous paragraphs plus a table, including raw decimal strings for `remaining_fraction`, pace and amounts.

## Required behavior

- Inventory the CLI Normal Account blocks and Watch account display. The Accounts page should match the **Normal report's scope** by default and retain the identities, provider/plan status, quota names/windows, native money or credits, Remaining, reset, Pace, billed today/month, local-month/Today CCost, Copilot Unaccounted usage and error/warning notes as applicable. Do not silently substitute Watch rolling account data for the Normal report's comparison period.
- Group information in clearly separated provider/account sections with concise heading, recognizable main quota/remaining visual, reset and status, contextual breakdown and expandable secondary details when valuable. Do not lose account-specific exceptions or important notes merely to reduce prose. Existing provider-normalized terms and CLI distinctions should lead the design.
- Format fractional quotas as percentages/progress semantics, native amounts with correct unit/precision, billed USD as currency, times/reset in the configured timezone and CCost with CLI-equivalent display. No visible long unrounded `Decimal` or low-level `window_active`/error-code dumps as primary UI. Unavailable vs zero vs unlimited vs blocked vs stale/recovering remains explicit.
- Accessible red/amber/status/fading equivalents apply to warning and critical account states; unknown values are not rendered as misleading empty progress bars. Preserve private-source restrictions, no account credential/token exposure or in-browser editing.
- Reuse shared FR000430 display and FR000440 visual components. Keep account acquisition/freshness and cached shared Normal observation independent of tab navigation; no duplicated provider requests.

## Acceptance

- Use equivalent synthetic account fixtures to verify CLI and Web displayed values/units/periods for blocked, unlimited, missing, partial, rate-limited, recovering and fully available providers; check reset and Pace format. No raw unsupported fraction or dollar digits.
- Owner can scan each account's key state without scrolling through a wall of diagnostic paragraphs; actual browser light/dark/narrow/keyboard checks are reported.
- Source/account report scopes, formulas, refresh ownership and privacy remain unchanged.

Relevant owners: `src/presentation/accounts.py`, `src/web/assets/render.js`, `app.css`, `src/application/projection.py`, `src/accounts/`, Web and quota presentation tests.