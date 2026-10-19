# AGENTS.md: ground rules for every agent in this repo

> Every agent reads this file first, every session. It holds **rules only**. Each rule's backstory lives in
> `docs/lessons.md` (cite it by id, e.g. L-07). Keep this file short: every session and every lane pays
> for its length in context.
> Fill in the `<<...>>` parts for your project.

## 1. Roles
See `docs/roles.md`. The short form:
- **The builder is the only writer of product code** (`<<game/, src/, ...>>`). Exactly one builder at a time.
- **A maker never checks its own work.** Every prompt, card, fix and landing is verified by a *different, fresh*
  session before it runs or is trusted. (L-12)
- **An auditor is never the builder**, in the same session or on the same work.
- If your dispatch does not name your role and task, **ask before touching files**.

## 2. Startup (bounded)
1. Read this file.
2. Read the state file `<<docs/STATE.md>>`, which must stay small.
3. Read the **last N entries** of the handoff log through a window tool, never the whole file. (L-01)
4. Read the card or spec named in your dispatch.
5. If your task appears nowhere: write a question entry and stop.

## 3. Single writer
- One agent edits one file at a time. Corrections are new versions or new entries, never overwrites of
  another agent's file. **Before writing, `ls` the path; if it exists and is not yours, choose a new name.** (L-17)
- Never rename, move or delete a queue item the driver may be running. Change state with
  `cadre/driver.py set-state` only. (L-16)

## 4. Build discipline (builder)
1. **Backup → edit → verify → log**, in that order. The backup is taken *before* the first touch and is proven to
   differ from live afterwards. (L-08)
2. **Restore only from your own card's snapshot**, taken after GREEN, fingerprinted (md5), and re-checked before
   every restore. Never restore from an older card's folder or kit. (L-09)
3. **Green gate or no claim.** The gate is the suite's own summary line (`N failing; allowlist = M`, N==M),
   never a grep count. (L-10)
4. **Card-conflict = stop.** If the card cannot be satisfied as written, stop with zero product files changed and
   report why. Do not bend the card. At most 3 fix cycles; the same FAIL twice = hard stop and restore.
5. **New features ship OFF** behind a flag unless the card says otherwise. (L-14)
6. **Every commit subject starts with the card id**: `[FIX-S02] ...`. The driver reads it. (P-02)

## 5. Writing cards and prompts (planner)
- **Re-measure every anchor** on the current disk, with line numbers, immediately before handing over. Code moves.
- **Every exit criterion must be satisfiable and visible to the named instrument.** If the change must move an
  existing assert, the card names and licenses that edit. (L-11)
- **No exact counts the work itself changes**; use measured pairs (AFTER == BEFORE + k) with the command that
  measures them.
- **Mutations must turn red for the stated reason**, not vacuously.
- **Unit and live parity:** every timer states its unit and the live caller's tick.

## 6. Common discipline (all roles)
1. **Premise check.** A claim you were handed is a hypothesis until you measure it.
2. **Act → measure → write.** Write "landed", "committed" or "N fails" only after the command that proves it ran.
   A query that returns nothing is reported as "query failed", never as "found none".
3. **Host safety.** Close every process you start, by PID, and report leftovers (expected 0). Never kill by
   image name. Never touch files or processes you did not create. (L-04)
4. **Shell safety.** In Git Bash never put `$` code inside a double-quoted PowerShell string. Always pass
   `-NonInteractive`. Wrap anything that can hang in `timeout`. (L-18)
5. **Loop prevention.** Reading the same thing 3 times without writing = write. Stuck 5 turns = log the block and stop.

## 7. Decisions
- **The user's words outrank every recommendation.** Record them verbatim, with their scope.
- Locked decisions live in `<<docs/adr/>>`. Never relitigate one; log evidence and defer. (L-13)
- A mentor decision made under delegation is **provisional**, recorded as such, and vetoable in one line.

## 8. Unattended runs
- The user starts the driver; agents never start their own unattended loops. (L-15)
- Permissions: see `docs/permissions.md`. Use scoped rules or auto mode for the run. **Revert on return.**
- Stop files: `<<.cadre/run/STOP>>` (any agent may create it on a real defect) and `<<.cadre/run/USER_BACK>>`.
- When the user is present and interacting, no lanes run. Their remote check-ins do not count as present;
  only the `USER_BACK` file does. (L-06)
