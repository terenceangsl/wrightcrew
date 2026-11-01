# The pipeline

```
 draft ──check──▶ checked ──release──▶ queued ──driver──▶ running ──▶ landed ──review──▶ reviewed
   ▲                │                                        │
   └──must-fixes────┘                                        ├──▶ stopped  (CARD-CONFLICT: card flaw, 0 files changed)
                                                             ├──▶ failed   (lane error / timeout / dirty tree)
 hold  (paused by the mentor)        parked (set aside for the user)
```

All state lives in **one file**, `.wrightcrew/run/queue.json`, and it is changed only through `wrightcrew/driver.py`
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
- **Outcome** is decided from the commits made during the lane (`<HEAD at start>..HEAD`) whose subject **starts with** `[ID]`:

  | lane result | state |
  |---|---|
  | a `[ID] CARD-CONFLICT...` commit | `stopped` |
  | exit 0, at least one `[ID]` commit, guarded paths clean | `landed` (all its commit hashes recorded) |
  | no `[ID]` commit, non-zero exit, dirty guarded paths, a driver error, or ended by STOP / deadline / backstop | `failed`, with the reason in `note` |
  | review/docs lane that changed guarded paths | `failed`: READ-ONLY VIOLATION, and builders pause |
  | review lane with no report file | `failed` |

- An item never stays `running` after an error. A driver that crashed mid-lane is reconciled at the next start: a dead lane → `failed`;
  a live lane PID → the driver refuses to start until you deal with that PID. `driver.py recover` does the same by hand.

## 4. Review (per landing, automatic)
- If `review_after_builder` is on, every `landed` item gets a **review item** queued at the front: a read-only
  checker lane, or a Claude reviewer, that looks at that card's commits (`templates/review_prompt.md`).
- The review covers the card's **whole commit range** (code plus record commits). A report whose first line is `CLEAN` marks
  the card `reviewed`; `FINDINGS (n)` leaves it `landed` with a note pointing at the report.
- Turning a finding into a fix card is done **by hand** (mentor or planner, then a checker). Fixing within the hour beats an
  end-of-week audit of 20 stacked landings. (L-19)

## 5. Refill (when the queue is empty)
- The driver runs the planner refill lane (`templates/refill_prompt.md`) **once per idle period**, and only while fewer than
  `max_open_drafts` (default 6) drafts are open. It writes new cards as **`draft`**,
  priority-ordered by the project's plan, and obeys the park rule and the never-overwrite rule.
- Drafts still need a checker before they are `queued`. If no checker is available unattended, the project decides
  in `wrightcrew.config.json` (`refill_autoqueue`) whether unchecked refills may run. The default is false. (L-12)

## 6. Pauses and stops
- After `max_builder_fail_streak` failed builder lanes in a row, builder items are skipped (the log names them as BLOCKED) until
  `driver.py reset-streak`. Docs and review lanes keep running.
- A STOP file, `USER_BACK` or the deadline also **ends the running lane** (its process tree, by PID), unless
  `stop_kills_running_lane` is false. Sleeps check for them every 10 s.

### Recovering after a lane is ended mid-edit
STOP, `USER_BACK`, the deadline or a timeout can kill a builder lane mid-edit. Before the next run:
1. `git status`: if the guarded paths are dirty, inspect the changes, then restore from the card's backup or run `git checkout -- <paths>`.
2. If `.git/index.lock` exists and no git process is running, delete it.
3. `driver.py status`: the item is `failed`, with the reason in its note. Re-queue it (`set-state <ID> queued`) once the tree is clean.

**One driver per repo** is enforced by the `driver.pid` lock: the pid is written atomically, and only its owner deletes it. An empty, unparsable or dead `driver.pid` counts as LOCKED and `run` aborts. If no driver is alive, `driver.py recover` is the only way to clear it. (L-26)

## 6b. Lane hygiene (L-40, L-42)
- **Log format.** Run `pi` with `--mode json` and a closed stdin. The log then shows progress while the lane runs, keeps partial work
  after a timeout, and says why a run ended (`stopReason`, `agent_settled`). Measured on one model: a run cut at 25 s kept 354,378 B in
  JSON mode and 0 B in text mode (`pi_mode_test_20261020.md`, findings file item 6).
- **Never read a lane log whole.** `python tools/lane_summary.py <lane.log>` prints event counts, whether the run settled, the last
  stopReason, tool calls by name, errors and the tail of the final text. Exit code 0 = settled, 2 = not settled, 1 = unreadable file.
- **Cap each lane.** Set `lane_timeout_s` well below the 14400 s default for a local lane (the author's cap is 90 min = 5400 s). One lane looped
  424 turns over 2.5 h (findings file item 8).
- **Fix cycles.** The driver does not count them: the cap of 3 per card is the builder's in-lane rule (`AGENTS.md` §4), with no "it is a new failure" exception; across lanes only `max_builder_fail_streak` applies.
- **Lanes do not edit the orchestrator's files.** The lessons file, state file and queue belong to the orchestrator (L-42); a lane proposes a lesson in its handoff entry. Listing them in `guarded_paths` makes a docs or review lane that touches them fail (READ-ONLY VIOLATION), but does not stop a builder lane, and an uncommitted orchestrator edit there blocks all builder lanes until it is committed. Keep them outside the builder's clone, or check every builder diff for them.

## 7. Park rule
A card family (same id stem) with **2 CARD-CONFLICT stops** in a row is `parked` for the user, not re-issued. (L-11)

## 8. Priorities
Keep the refill's priority list tied to the project's **actual goal** (for example, the v1 scope list). When it was
missing, the refill drifted to low-value items. (L-20)
