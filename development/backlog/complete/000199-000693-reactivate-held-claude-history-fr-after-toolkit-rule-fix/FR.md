# FR 000693 — Restore held Claude model-history FR000692 to Ready after Toolkit rule is correctly fixed

**Owner-approved Ready Feature Request — 2026-11-13. Permanent identity 000693, queue priority 000001.**

**FR AUTHORING AND ROLLBACK ONLY.** The owner explicitly requires **changes to the OpenCode Toolkit worker instruction and a renewed approval of held FR000692 to happen via their respective feature-request workflows**, not by direct assistant edits to the product or installed Toolkit commands. This FR publication **does not implement** FR000692, change Cost Guard's model resolver, or directly release the held FR. A separate, explicit rollback in the same documentation commit restores FR000692 from the assistant's unauthorized direct Ready move to its last authentic **On Hold** state and restores the original `HOLD.md`; that reversal is not implementation of this new FR.

## Actual problem and prior state

- The user's own Cost Guard Web → Sessions still shows many historical **2026-11-12 Europe/Stockholm** entries as **`Claude Sonnet (version unverified)`** and similarly affected newly generated Claude Agent model-test sessions. The user wants the **exact local affected records**, not a synthetic substitute, diagnosed and resolved correctly.
- **FR000687** shipped tooltip/raw-model help but **did not** run the required historical-session inspection or deliver the historical version/CCost repair. See `development/backlog/complete/000194-000687-claude-agent-identity-recovery-and-raw-provider-model-help/COMPLETION.md`.
- **FR000692** was then explicitly created to require either a fix verified against the **real 2026-11-12 sessions after Cost Guard restart**, or On Hold with a genuine blocker. Its implementing worker put it **On Hold immediately** based on `commands/repo-backlog.md` in the separate OpenCode Toolkit repo:
  ```text
  Never inspect another session's scratch, processes, stashes or private records/storage.
  ```
  `development/backlog/on-hold/000692-hard-gate-repair-exact-2026-11-12-claude-unverified-sessions/HOLD.md` confirms **zero target sessions read, zero local database queries, zero Claude SDK transcript checks and no product repair**. The hold was due to a permission-interpretation conflict, **not** a demonstrated irrecoverable Claude-model technical limitation.
- The user objected that **a saved OpenCode session export is not another agent's scratch**. These should remain separate. User-authorized analysis may read previous sessions, including those originally created by other coding agents, while other implementation workers' scratch, processes, stashes and private task workspace stay isolated.
- The assistant then **directly** edited OpenCode Toolkit's rule and **directly** moved FR000692 out of On Hold. The owner explicitly disapproved this shortcut. Both direct actions are rolled back; **the change of worker rule must instead be implemented through OpenCode Toolkit FR000471**, and **the later release of held FR000692 must happen through this Cost Guard FR000693**.

## Required prerequisite in the other repository

**OpenCode Toolkit FR000471**, [Distinguish saved OpenCode session exports from worker-private scratch](https://github.com/qstoffe/opencode-toolkit/blob/main/development/backlog/ready-to-develop/000001-000471-distinguish-saved-opencode-sessions-from-worker-private-scratch/FR.md), is a separate high-priority owner-approved task.

**Do not reactivate FR000692 until BOTH conditions hold:**

1. OpenCode Toolkit FR000471 has been implemented through its **normal reviewed repository PR/merge** and the authoritative command/rule now distinguishes **explicitly permitted read-only OpenCode session history** from prohibited **other-worker scratch/private state**. Keep the rest of the worker isolation and native security restrictions intact.
2. The owner's **actually installed and loaded** Toolkit command/skill version reflects that reviewed rule. GitHub main being updated alone does not prove this. Follow normal supported Toolkit sync/install/reload procedures and confirm the loaded instructions with an ordinary new session; do not silently mutate active installed configuration or bypass `ask`/`deny`.

If either prerequisite is absent, FR000692 **stays On Hold**; this new FR000693 is **NOT complete**. Record the exact missing prerequisite and use the established task status/dependency workflow, without moving FR000692 prematurely or pretending a blocked read is possible.

## Actions after the prerequisite has truly been verified

1. Read original `FR000692` and `HOLD.md` from the On Hold directory. Preserve the permanent identity **000692**, its original two-outcome hard gate and full historical-case acceptance. This is **reactivation of the existing task**, not implementation, a replacement task or new permanent ID for the historical bug.
2. Move `development/backlog/on-hold/000692-hard-gate-repair-exact-2026-11-12-claude-unverified-sessions/FR.md` to `development/backlog/ready-to-develop/000001-000692-hard-gate-repair-exact-2026-11-12-claude-unverified-sessions/FR.md` with **priority 000001**, the highest of ordinary Ready FRs when it returns. Keep the hold rationale in an appropriate historical attachment (e.g. `PRIOR-HOLD.md`), explicitly marked superseded by verified Toolkit rule correction. Remove the active On Hold entry only when the Ready move is committed; do not leave duplicate executable FRs.
3. Add the owner's latest clarification to FR000692 **in the normal FR implementation/change process, not through direct author edits**: Owner authorizes **read-only inspection/export of all relevant saved OpenCode session records**, including sessions created by other agents, and relevant SQLite, provider plugin records and native Claude SDK transcripts, where normal installed access permits. **This does not authorize reading other agents' scratch, stashes, checkpoints or live processes**, which are unrelated to the intended source analysis. These saved session records are Cost Guard's legitimate product input.
4. Retain the original **binary final acceptance** for the subsequent FR000692 worker: (a) all exact affected November 12 and owned native test sessions are individually diagnosed, correctly resolved and verified after genuine Cost Guard cold/warm restart, or (b) move the same FR000692 back **On Hold with the first demonstrated, specific remaining technical/access blocker**. No P2-only/tooltip-only closure, synthetic PASS, new Suggestion in place of repair, or delegate waiver of the affected-records gate.
5. Preserve the user's request for deep, sustained troubleshooting **up to 48 hours of real work** before declaring the technical problem insoluble where the environment reasonably supports it. Use supported Checkpoint/Resume across sessions when necessary and an evidence ledger; 48 hours is not idle clock waiting, a requirement to generate paid model tokens, or a permission to bypass an explicit native tool denial. Report actual attempted avenues and time honestly, never claim a 48-hour effort that was not performed.
6. Merge/publish the documentation-only backlog transition through the ordinary Cost Guard FR000693 workflow, verify that FR000692 appears **once** under Ready with the correct priority and its former On Hold entry is gone, then mark **FR000693** complete separately. At that point the actual FR000692 bug-fixing implementation becomes executable through ordinary Repo Backlog selection.

## Why sequence matters

The prior FR000692 implementation did **not** fail after exhausting technical model-resolution approaches. It never reached the database. Repeating its execution before the Toolkit rule is merged **and loaded** would simply recreate the same hold. Conversely, rewording only Cost Guard's FR without the actual Toolkit interpretation fixed would change nothing.

This FR explicitly divides two independent authorizations:

- **Toolkit FR000471:** implement the general-purpose instruction distinction in the source that owns the worker rules.
- **Cost Guard FR000693:** **only after that instruction is actually loaded**, release existing Cost Guard FR000692 from On Hold into Ready at highest priority, preserving its hard fix-or-hold gate.

The owner expects the implementing worker to keep working on real technical alternatives, not end after one lookup, but no FR can override host-enforced filesystem rules, credentials, native `deny` or safety limits. The correct way to address a genuine access blocker is its supported approval mechanism or a targeted owner decision, not guessing the model version or claiming a completed fix.

## Acceptance

- The author's direct Toolkit rule edit is visibly reverted; FR000471 exists as a normal executable Ready FR, and **the Toolkit worker rule is changed only by its later implementing worker/approved PR**.
- This Cost Guard authoring rollback leaves **FR000692 exactly in On Hold with the original original FR and HOLD reason**, and only **FR000693** is newly Ready. A prior direct activation is not misrepresented as an implemented bug fix.
- A later worker demonstrates actual merged **and installed** Toolkit FR000471 rule before changing FR000692's stage.
- After that verified dependency, FR000692 is the same original task with priority 000001 and the explicit user permission/effort clarification; the On Hold rationale is retained as history, not mistaken for a technical model-identity determination.
- No Cost Guard product code, OpenCode native database or third-party sessions were changed as part of the administrative transition, and no original 2026-11-12 request was rerun for paid inference.
- FR000693 completion includes GitHub links showing the reviewed Toolkit rule and Cost Guard hold→Ready migration. FR000692 itself cannot later close without its **actual historical-session** acceptance.

**Non-goals:** resolving the Claude version/CCost bug within FR000693, manually reopening 000692 before Toolkit FR000471 is installed, globally permitting another worker's scratch access, or using direct assistant edits instead of the requested FR process.
