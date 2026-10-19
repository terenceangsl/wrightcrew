TASK (checker role, read-only review of ONE landing): review the commit range {commit} (commits: {commits}) for card {id}; write the report, then STOP.

You did not build this. Edit nothing except the report file.

1. `git log --stat {commit}` and `git diff {commit}` on the product paths (the range covers the code commit and its record commits). Read the card it names.
2. Check:
   - (a) flag-OFF behaviour is unchanged;
   - (b) save and load compatibility;
   - (c) correctness: units at the live tick, off-by-one, undefined reads;
   - (d) interactions with recent landings in the same functions;
   - (e) card fidelity: it did what the card says, and nothing extra;
   - (f) test honesty: the new asserts actually exercise the change.
3. Write `{report_path}`. **Its first line must be exactly `CLEAN` or `FINDINGS (n)`**; the driver reads it, and a CLEAN review marks the card `reviewed`. Then:
   - for each finding: severity, file:line, the defect, a failure scenario, and a one-line fix.
   Mark each finding CONFIRMED or PLAUSIBLE.
4. If there is an IMPORTANT or CRITICAL finding: also write `{fix_draft_path}`, a fix card draft (`templates/card.md` shape). The mentor checks it before it is queued.
