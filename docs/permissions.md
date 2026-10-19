# Permissions for unattended runs

Goal: **no stalls, and no blanket bypass.** Everything here is set by the **user**; agents cannot and should not change their own permissions (L-07, L-15).

There are two different things to secure:

## A. The local-LLM lanes (the builder, docs and review lanes the driver starts)

These run a coding agent with a **shell, as your user account, for days**. The permission settings of your Claude app do **not** apply to them. Contain them by OS means:

- **A separate clone** of the repo for unattended runs. Lanes work there; you pull their commits into your main clone after review.
- **A low-privilege account or a VM/container** if you can. At minimum, no admin rights.
- **No secrets in reach:** no `.env` with real keys, no cloud credentials, no SSH or signing keys, and no logged-in browser profiles in that account.
- **Network:** ideally only the model endpoint (for example `127.0.0.1:8080`). If the agent can reach the internet, a malicious page it reads can steer it.
- **Timeouts and process-tree kill:** the runner must kill the whole tree on timeout (`tools/run_lane.example.py` does), and the driver ends the lane on STOP or the deadline.
- **Reviewer and docs lanes are told they are read-only;** the driver marks them `failed` if they change guarded paths. That is detection, not prevention: isolation is the real control.

## B. Claude sessions that run unattended (for example an hourly scheduled check)

1. **One shell tool.** Tell the scheduled run to use only the Bash tool (or only PowerShell), and write rules for that tool. Rules for one don't cover the other. (L-05c)
2. **A fixed health script** instead of ad-hoc commands (start from `scripts/checks.example.sh`), with one exact allow rule for it. Every new command string is a new prompt. (L-05a)
3. **File-write rules use `Edit(...)`,** scoped to the run's working folders:
   ```json
   "Edit(.wrightcrew/run/**)", "Edit(reports/**)", "Edit(prompts/**)"
   ```
4. **Lane launches come from the driver,** which the user starts. Agents need no "start process" rule; don't grant one.
5. **A default mode for the window,** set in the project `.claude/settings.local.json`. A mode toggled inside one session does **not** carry over to the next scheduled run (L-05d). Prefer the first option:
   - `"defaultMode": "auto"`: a safety classifier reviews actions and blocks risky ones. In our runs, blocked actions were denied rather than left waiting. Check your Claude Code version's docs for current behaviour.
   - `"defaultMode": "bypassPermissions"`: **not recommended.** Nothing is checked at all, so a mistaken or manipulated agent can do anything your account can. If you use it anyway: only in an isolated clone or account (as in A), only for the window, and revert immediately after. The app may also require a separate bypass opt-in.

## After the window: revert

- Remove `defaultMode` from the project settings.
- Remove the away-window allow rules. Keep a backup of the file.
- Disable the scheduled task.
- Turn off any app-level bypass opt-in.
- Rotate anything the lanes could reach that you're unsure about.

## Diagnosing a stalled scheduled run

- The session shows "running", last activity is old, and **no child process** is running under it → it is waiting on an approval.
- Look at the last tool *name* in its transcript (Bash, PowerShell, Write). That tells you which rule family is missing.
- A scheduler won't start a new run while one is open, so one stuck run blocks all later ones.
