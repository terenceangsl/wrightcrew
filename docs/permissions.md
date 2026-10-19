# Permissions for unattended runs

Goal: **no stalls, and no blanket bypass.** Everything here is set by the **user**; agents cannot and should not change their own permissions (L-07, L-15).

## Before an unattended window

1. **One shell tool.** Tell scheduled runs to use only the Bash tool (or only PowerShell) and write rules for that tool. Rules for one don't cover the other. (L-05c)
2. **A fixed health script** instead of ad-hoc commands, e.g. `bash .cadre/checks.sh`, with one exact allow rule for it. Every new command string is a new prompt. (L-05a)
3. **File-write rules use `Edit(...)`.** Scope them to the run's working folders:
   ```json
   "Edit(.cadre/run/**)", "Edit(reports/**)", "Edit(prompts/**)"
   ```
4. **Lane launches are started by the driver**, which the user starts; agents need no "start process" rule.
5. For the scheduled run session itself, choose **one** of:
   - `"defaultMode": "auto"` in the project `.claude/settings.local.json`. A safety classifier blocks risky actions and the run continues without hanging (recommended).
   - `"defaultMode": "bypassPermissions"`. Nothing asks, and nothing is blocked. The app may also need its bypass opt-in.

   A mode toggled inside one session does **not** carry over to the next scheduled run. (L-05d)

## After the window: revert

- Remove `defaultMode` from the project settings.
- Remove the away-window allow rules. Keep a backup of the file.
- Disable the scheduled task.
- Turn off any app-level bypass opt-in.
- Remove the stop files, or leave `USER_BACK` until the next run.

## Diagnosing a stalled scheduled run

- The session shows "running", last activity is old, and **no child process** is running under it → it is waiting on an approval.
- Look at the last tool *name* in its transcript: Bash, PowerShell, Write. That tells you which rule family is missing.
- A scheduler won't start a new run while one is open, so one stuck run blocks all later ones.
