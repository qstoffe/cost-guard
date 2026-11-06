# FR 000605 — Web Watch: rename Earlier Prompts to Earlier Sessions

**Owner-approved Ready Feature Request, 2026-11-06.** Permanent identity **000605**; priority **000230**, after the current Ready FR000603 (000220). This request is for backlog authoring only, not implementation now.

## Request

On the full Web **Watch** page, the collapsible historical section is called **Earlier Prompts**. Mini Watch already calls the corresponding section **Earlier Sessions**, which better describes that the history groups distinct sessions. Use the same, clearer terminology on both surfaces.

## Scope and acceptance

1. Rename the full Watch disclosure heading from **Earlier Prompts** to exactly **Earlier Sessions**. Use session terminology for the same section's visible empty/unavailable messages as well (e.g. **No earlier sessions** / **Earlier sessions unavailable**).
2. Keep **Running Prompts** and labels for actual individual prompts unchanged. Do not change history membership, counts, ordering, rows, calculations, collapsed/expanded behavior, accessibility, or Mini Watch.
3. Adjust current Web Watch documentation and focused UI/test expectations that describe this visible heading; do not rewrite historical FRs, journals, or text that correctly refers to prompts.
4. Verify that the full Watch heading and relevant empty states say **Earlier Sessions**, matching Mini Watch, with otherwise unchanged behavior.

**Publication boundary:** add only this Ready FR and advance `development/backlog/identity-state.json` from 604 to 605. No product code, tests, documentation, version, release, or completion changes in this authoring step.
