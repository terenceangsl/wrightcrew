TASK (planner role, docs only, refill): the queue is empty. Write the next builder cards and prompts as DRAFTS, then STOP.

1. Read:
   - `python cadre/driver.py status`;
   - the last 40 lines of `.cadre/run/driver.log`;
   - `git log --oneline -30`;
   - the goal list `<<docs/goals.md>>`.
   Never read the handoff log whole.
2. For each `stopped` or `failed` item: read its lane log tail and stop entry. If a card flaw caused it, write a corrected card
   (`<ID>_r2`). **Park rule:** if a family has 2 stops, do not re-issue it; `set-state <ID> parked` with the reason.
3. Pick the next 2 cards **in goal-list order**. Skip anything that landed, or that needs a user taste call.
4. Write each card (`templates/card.md`) and builder prompt (`templates/builder_prompt.md`):
   - re-measure every anchor on the current disk;
   - self-verify by re-opening every file:line you cite.
5. **Never overwrite:** `ls` every path before writing; on a collision, use a new name.
6. Register each one as a draft:
   `python cadre/driver.py add <ID> builder <prompt path> --state draft --maker <you>`
7. Write a 5-line summary to `.cadre/run/refill_<MMDD_HHMM>.md`. No product code, no commits.
