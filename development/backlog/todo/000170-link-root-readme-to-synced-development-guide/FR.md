# FR 000170 — Link CostGuard root README to the Toolkit-synced development guide

## Goal and intended user experience

A human or cloud AI that has access **only to qstoffe/cost-guard** should be able to open the repository's existing root README.md, follow one clear link to **development/README.md**, understand the purpose/structure of development/, and find a **lightweight Feature Request writing guideline** without having to know, install or browse OpenCode Toolkit. The product owner has approved a **single small documentation change**, not a new policy, validation process or release gate.

This follows the separately approved **OpenCode Toolkit FR000030 — One shared-repo skill and Toolkit-owned development README**:
https://github.com/qstoffe/opencode-toolkit/blob/b39b671d6803c802004ad42cd5d65c6e491d5027/development/backlog/todo/000030-unified-shared-repo-skill-and-portable-development-readme/FR.md

The Toolkit FR owns the new one-skill identity, the master README and the compatible existing Contract Sync mechanism. **CostGuard does not implement any of those contracts**.

## Required smallest change

1. **Dependency/order:** Wait for the compatible Toolkit implementation to be published, the user to install/reload it as needed, and **CostGuard's own normal Repo Backlog Contract Sync** to copy the Toolkit-owned master into **development/README.md**, with the normal applied-contract receipt. The existing native Contract Sync has precedence over ordinary FRs, so a subsequently eligible FR000170 should see the guide already present. Never copy master text manually, edit another repo, impersonate a completed sync or start another sync engine. If the dependency is not genuinely installed/available, retain the pending FR rather than inventing the document or incorrectly claiming completion.
2. Edit only the **existing root README.md** in CostGuard, preferably under its existing **## Development** section. Add **one concise visible Markdown sentence**, e.g.:

   Development workflow and Feature Request guidelines: [development/README.md](development/README.md).

   This link should work on GitHub and in a local Markdown reader; retain all other CostGuard README explanations, links, commands and product facts. Avoid repeated links, a new standalone guide, AGENTS/FR_GUIDE, or duplicated skill/README prose.
3. Treat **development/README.md as an exact Toolkit-owned mirror** and **do not change it** from the CostGuard FR. It is published by Contract Sync, not authored or maintained by CostGuard. Root README remains a CostGuard-owned introduction; Toolkit's future Contract Sync only updates the generated development README, never CostGuard's root.
4. The README guide is **friendly, optional advice**, not a mandatory FR template, minimum content standard, permanent product test/release gate, file-size budget or new command to execute. Do not add a schema check, CI test or root README linter just to enforce this sentence. Existing user/Git/privacy/selected-work protections remain.

## Acceptance and proportional delivery

- After an authoritative CostGuard Contract Sync, the committed source contains **development/README.md**, whose Toolkit provenance and normal applied receipt are verified by that sync; root README contains one valid relative link to it under Development.
- From the *CostGuard repository alone*, a reader can reach the locally present writing advice and understand how to describe a Feature Request without loading Toolkit skills. No extra navigation assumptions, dead link, changed FR template or duplicate content.
- This is a **documentation-only root README edit**. Unless a repository-owned rule demonstrably requires something more, perform only source read/edit, simple link read-back and the normal authorized Git publication/merge/receipt/cleanup. No paid model evaluation, full Python suite, package validation, product behavior change, version/history bump or new permanent approval/verification gate **merely for this one-link change**. Affected files and checks should remain proportional and honest.
- Never touch a selected/paused FR, other Checkout's uncommitted work, authentication, Watch/CCost logic or FR000160 completion. No new release target.

## Priority and implementation independence

**Normal next available FR000170**, after CostGuard's existing high-watermark 160. Its implementation depends on Toolkit FR000030 and the resulting **CostGuard Contract Sync**; publication of this specification itself does not perform either task. If CostGuard is launched before a compatible Toolkit is installed, do not attempt to implement the cross-repository prerequisite by hand. Keep this FR self-contained for later authorized execution.

Creating this FR is direct-main FR-only authoring: change only its FR.md and the exact identity-state watermark to 170. No product release, PR, tests or Toolkit installation occurs during specification publication.
