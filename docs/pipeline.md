# The pipeline

```
 draft ──check──▶ checked ──release──▶ queued ──driver──▶ running ──▶ landed ──review──▶ reviewed
   ▲                │                                        │
   └──must-fixes────┘                                        ├──▶ stopped  (CARD-CONFLICT: card flaw, 0 files changed)
                                                             ├──▶ failed   (lane error / timeout / dirty tree)
 hold  (paused by the mentor)        parked (set aside for the user)
```

All state lives in **one file**, `.cadre/run/queue.json`, and it is changed only through `cadre/driver.py`
(`add`, `set-state`, `status`). Nobody renames files to signal state. (L-16: renaming a running item would have crashed the driver.)

## 1. Make (planner)
- Write the card (`templates/card.md`): what, why, write set, and decisions taken (or "needs user").
- Write the builder prompt (`templates/builder_prompt.md`), with every anchor re-measured.
- Add it as `draft`:
  ```
  driver.py add <ID> builder <prompt.md> --state draft --maker sonnet
  ```

## 2. Check (a fresh session, never the maker)
- Produce `templates/check_report.md`, with a verdict per item.
- **RELEASE**: `driver.py set-state <ID> queued --checker opus`.
- **MUST-FIXES**: they go back to the *maker*, who applies them, then a re-check of the changed lines.
- **HOLD**: the item stays `draft` or goes to `hold`, with a note.

## 3. Build (the driver plus a local lane)
- The driver takes the first `queued` item in `order`, writes a launch file (the task line first, plus a shell-safety
  block), and runs the runner with the role's tool set and a timeout.
- **Preconditions** for builder items: the guarded paths are clean, and the builder-failure streak is below the limit.
- **Outcome** is decided from `git log` since the lane started, matched on the card id in commit subjects:
  - a commit with the id and no `CARD-CONFLICT` in it → `landed` (with the commit hash recorded);
  - a commit with the id and `CARD-CONFLICT` → `stopped`;
  - no commit, or a non-zero exit → `failed`.

## 4. Review (per landing, automatic)
- If `review_after_builder` is on, every `landed` item gets a **review item** queued at the front: a read-only
  checker lane, or a Claude reviewer, that looks at exactly that commit (`templates/review_prompt.md`).
- A review finding becomes a fix card at the front of the queue. Fixing within the hour beats an end-of-week audit
  of 20 stacked landings. (L-19)

## 5. Refill (when the queue is empty)
- The driver runs the planner refill lane (`templates/refill_prompt.md`). It writes new cards as **`draft`**,
  priority-ordered by the project's plan, and obeys the park rule and the never-overwrite rule.
- Drafts still need a checker before they are `queued`. If no checker is available unattended, the project decides
  in `cadre.config.json` (`refill_autoqueue`) whether unchecked refills may run. The default is false. (L-12)

## 6. Park rule
A card family (same id stem) with **2 CARD-CONFLICT stops** in a row is `parked` for the user, not re-issued. (L-11)

## Priorities
Keep the refill's priority list tied to the project's **actual goal** (for example, the v1 scope list). When it was
missing, the refill drifted to low-value items: 11 lanes, 1 landing. (L-20)
