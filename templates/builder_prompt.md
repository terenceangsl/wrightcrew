TASK (builder role, <LOCAL lane | Claude>, <attended | unattended until <date>>): implement card <ID> exactly as written below; that card only, then STOP.

# Builder prompt <ID> (card: <path>) · maker <who> · checked by <who>, <date>

## 0. Read first
- `AGENTS.md` §3-§6. The last 3 handoff entries via the window tool (never the whole log).
- Never read <big files> whole.

## 1. Preconditions (if any fails: CARD-CONFLICT, zero product files changed, report why)
- [ ] The guarded paths are clean: `git status --short <paths>` = 0 lines
- [ ] The previous card landed (if ordered): `git log --oneline -30 | grep -F "[<PREV-ID>]"` ≥ 1
- [ ] Each anchor occurs exactly once (count with `grep -c -F '<anchor text>' <file>`):
  | file | anchor (exact text) | expected count | measured at <commit> line |
  |---|---|---|---|

## 2. Baseline
- Run the suite once **before** the first write; record its summary line and failing set.

## 3. Backup (before the first touch)
- `mkdir -p backups/<id>_<date>/` and copy every write-set file there; record the md5s.

## 4. Edits
For each edit: file, anchor (exact), replacement (exact), and how the lander verifies it (count after == 1).
Prefer an anchor-guarded script that refuses non-unique anchors and preserves line endings.

## 5. Proof
- The new or changed probe: RED on the old code (show it), GREEN on the new (3 standalone runs).
- **Snapshot:** right after GREEN, copy the live write-set files to `<work>/<id>/landed/`, record LANDED_MD5, and prove
  each one differs from its backup.
- **Mutations M1..Mn:** apply each to a COPY, or to live and then restore **only from this card's `landed/`** after re-checking
  LANDED_MD5. Each must turn the named assert RED.
- **Gate:** the suite's own line, N == M, with the same failing set as the baseline.
- Flag-OFF parity: <digest / probe>.

## 6. Commit (only after the gate is green)
- Subject: `[<ID>] <what landed>, ships <ON|OFF>, probe <n/n>, gate <N==M>`
- Commit exactly the write set, plus generated files the suite rebuilt, plus the green stamp. Never `git add -A`.

## 7. Stops
- CARD-CONFLICT: restore from the backup, run `git checkout --` on generated files, prove the guarded status = 0 lines,
  then commit only a report entry: `[<ID>] CARD-CONFLICT: <reason>`.
- Max 3 fix cycles. The same FAIL twice = HARD STOP and restore.

## 8. Shell safety
In Git Bash, never put `$` code inside a double-quoted PowerShell string. Always pass `-NonInteractive`.
Use `timeout 600` on anything that can hang. Close every process you start.
