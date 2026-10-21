# Wrightcrew

**A small crew of AI agents with fixed roles, building a project together, with a checker on every maker.**

Wrightcrew is the operating kit distilled from running the *Auto Crawler* game project with a mixed crew: Claude (Opus / Sonnet / Haiku) for planning, checking and reading, and a **local LLM** for unattended building. It came out of one hard week in October 2026, in which an away-week of autonomous work went from about 1 hour of model work per 7.5 hours to 19–69 lane starts a day (250 over the week; about 30% were refill/docs lanes). Every rule in it comes from something that actually broke.

## Why Wrightcrew

A *wright* is a maker: a shipwright, a playwright, a wheelwright. Wrightcrew is a crew of makers, where **every maker has a checker**.

**The story.** Most multi-agent kits assume the agents are good. Ours were not. A small local model built a game unattended for a week, and it got things wrong in every way a weak model can. Cards were unsatisfiable. Restores went stale. Lanes hung. Approval prompts stalled overnight. Instead of a smarter agent, we built a stricter crew around it. By the end of the week the local model ran **19–69 lane starts a day** (250 over the week; about 30% were refill/docs lanes), and the paid models spent their tokens only on planning and checking. Most mistakes were stopped by a checker before a lane ran. Some slipped through and were found by post-landing review or audit (L-19).

**What makes it different:**
1. **Made from incidents, not theory.** Every rule names the failure that caused it (`docs/lessons.md`, L-01..L-34).
2. **The maker never checks itself.** Queueing a builder card needs both a named maker and a named checker, and the checker must not be the maker (case-insensitive). The names are still a text field, so OS isolation is the real guard (`docs/permissions.md`).
3. **Cheap hands, expensive eyes.** A free local model does the grinding; Claude spends its tokens where a mistake is costliest, on plans and checks.
4. **Failing safely counts as success.** A weak model that can't meet a card stops cleanly (CARD-CONFLICT) with nothing changed, instead of bending the work.
5. **No server, no database.** One JSON file plus git is the whole state; a `[CARD-ID]` in a commit subject *is* the status update.
6. **Honest about permissions.** Agents never start their own loops or widen their own access; the user does, and reverts.

## Runs on Strata

Wrightcrew is the crew; **Strata** is the ground it builds on, the local model server that does the work. They meet at two points in `wrightcrew.config.json`:
- `health_url`: Strata's model endpoint (e.g. `http://127.0.0.1:8080/v1/models`). The driver waits while it is down and never starts a lane against a dead server.
- `runner`: the agent harness command that talks to Strata (e.g. `pi -p --mode json --provider local --model <strata model>`), wrapped by `tools/run_lane.example.py` for the timeout and the process-tree kill.

Strata serves one request at a time, so Wrightcrew runs **one lane at a time** and keeps Claude out of the lane loop. One driver per repo is enforced by a lock (`driver.pid`, written atomically and deleted only by its owner); `driver.py recover` is the only way to clear a stale lock. Interactive Claude sessions and Strata lanes don't compete: no lanes run once you create `.wrightcrew/run/USER_BACK`.

## What's in the box

It is not a framework or a server. It is:

- **A role charter.** Who plans, who builds, who checks, who reads, and what each role never does.
- **A pipeline.** Maker → checker → (maker fixes) → queue → build → review → landed or stopped.
- **A driver** (`wrightcrew/driver.py`). It runs queued lanes one at a time with no Claude in the loop: one state file, stop files, a deadline, and a post-landing review.
- **Templates** for cards, builder prompts, check reports, handoff entries and the planner refill.
- **A lessons file**, which records each incident and the rule it produced.
- **Two small tools** (v0.4 draft): `tools/lane_summary.py`, a JSONL lane-log summariser, and `templates/lessons_file.md`, a per-role lessons-file template.
- **A guidance guide** (`docs/guidance.md`): how lessons, a recipe, gates and a scorecard trained a local model without fine-tuning.

## The crew

| Role | Usually played by | Does | Never does |
|---|---|---|---|
| **User** | you | taste calls, final say, one-line vetoes | (nothing is off-limits) |
| **Mentor / orchestrator** | Claude Opus (interactive) | routes work, makes or approves decisions, runs the maker/checker loop | builds game code; self-checks its own deliverables |
| **Planner** | Claude Sonnet/Opus, or a local docs lane | writes specs, cards and builder prompts | writes code |
| **Builder** | local LLM lane (or Claude) | the ONLY writer of product code; backup → edit → verify → commit | adds features with no card; relitigates locked decisions |
| **Checker** | a *fresh* Claude Opus/Sonnet | read-only verification of a maker's prompt or landing | edits what it checks; checks its own work |
| **Auditor** | a *fresh* Claude session | read-only review of landed code → findings register | builds (an auditor is never the builder) |
| **Reader** | Claude Haiku | cheap bulk reading → numbers-only summaries | judges or decides |
| **Storyteller** | Claude | player-facing text, as wire-ready line tables | code, gates, balance numbers |
| **UX reviewer** | a fresh Claude | scored UI review plus decision-free UX cards | code, art, story text |

The one rule above all: **if you are the maker, you need a checker.** Nothing a maker writes runs until a different session has verified it.

## Quick start

Requires Python 3.9+ and git. Run every command from **your project's root**.

1. Copy `wrightcrew/`, `templates/`, `tools/`, `scripts/`, `tests/` and `AGENTS.md` into your project. Fill in the `<<like this>>` parts of `AGENTS.md`, and
   start `docs/STATE.md` and `docs/goals.md` from `templates/STATE.md` and `templates/goals.md`.
2. Copy `wrightcrew.config.example.json` to `wrightcrew.config.json`. Set `guarded_paths` (your product code), the `runner` command
   (start from `tools/run_lane.example.py`) and `health_url`. Add `.wrightcrew/` and `wrightcrew.config.json` to your `.gitignore`.
   *Upgrading from Cadre:* move `.cadre/run` to `.wrightcrew/run`, or the driver starts with an empty queue.
3. Write cards with `templates/card.md` and builder prompts with `templates/builder_prompt.md`. Get each one checked by a
   fresh session (`templates/check_report.md`).
4. Queue a checked prompt. A builder card needs a named maker AND a different named checker to be queued:
   ```
   python wrightcrew/driver.py add FIX-S02 builder prompts/fix_s02.md --state queued --maker sonnet --checker opus
   ```
   Unchecked work goes in as a draft, e.g. `python wrightcrew/driver.py add FIX-S02 builder prompts/fix_s02.md --state draft --maker sonnet`, and is promoted later with `set-state FIX-S02 queued --checker opus`. Set the maker when you add a draft: `set-state` cannot add it later.
5. **Isolate the lanes.** Builder lanes get read/edit/write/bash. Run them in a separate clone or under a low-privilege account with no secrets (`docs/permissions.md` §A), not in your real working repo.
6. Remove any leftover `.wrightcrew/run/STOP` or `USER_BACK`, then start the driver yourself, in your own terminal (never an agent):
   ```
   python wrightcrew/driver.py run
   ```
7. Watch it with `driver.py status`. End it with `driver.py stop`, which also ends the running lane. After a crash:
   `driver.py recover`. After a builder failure streak: `driver.py reset-streak`.
8. Before trusting a change to the driver, run `python tests/smoke_test.py` (no model needed).

## Read next

- `docs/pipeline.md`: the lifecycle of a piece of work, the queue states, and what moves an item between them.
- `docs/roles.md`: each role's charter in detail.
- `docs/permissions.md`: setting up an unattended run without stalls and without a blanket bypass, then reverting it.
- `docs/lessons.md`: every incident and the rule it produced. **Read this before your first unattended run.**
- `docs/budget.md`: pacing paid models, so the short usage window does not overflow into paid spend.
- `docs/guidance.md`: training a local model with guidance (lessons, recipe, gates, self-look, scorecard).
- `CHANGELOG.md`: what changed in each version.

## Status

v0.3.1, 2026-10-19. The driver generalises the one that ran the Auto Crawler away-week.
- **Changed since v0.3.** Checker equal to maker is refused; the driver lock is written atomically and deleted only by its owner (an empty or dead `driver.pid` is LOCKED until `recover`); a WARNING is logged for each missing `guarded_paths` entry; `status` prints ASCII and flags a stale lock; a queued builder card needs a named maker; the health script reports MODEL DOWN correctly; the README claims are now measured and the quick start covers the runner, isolation and gitignore; lessons L-23..L-34 and `docs/budget.md` are new; MIT license.
- **Checked.** A fresh Opus checker reviewed v0.1 (2 critical, 10 important) and v0.2 (1 new critical, 1 important); all are fixed in v0.3. The v0.3 rename and README were re-checked by a fresh checker (14 findings W-01..W-14, fixed in v0.3.1). Re-checked 2026-10-19 by a fresh checker in two rounds: final verdict RELEASE (round 1 findings V-01..V-09 and round 2 findings V-10..V-11 fixed, except V-05/V-06, planned for v0.3.2).
- **Tested.** `tests/smoke_test.py` covers the checker's reproductions plus the core paths: 19 cases.
- **Not yet run for real.** It has not driven a real model lane in this generic form, so point it at a throwaway repo first.
- **Limits:**
  - The `--checker` guard is free text: it refuses a queued builder card with no maker, no checker, or checker == maker, but any lane with a shell could still self-queue under another name. Lanes are isolated by OS means instead (`docs/permissions.md`).
  - Review findings become fix cards by hand (mentor or planner); this is not automated.

**Planned next:**
- `set-state --maker` so a draft added without a maker can still be queued (V-10).
- V-05: a reused pid can make a stale `driver.pid` look alive; check the process command line, not just the pid.
- V-06: `recover` deletes `driver.pid` without an owner check; delete only if it still holds the same dead value.
- Resume the lane's agent session when retrying a stopped card, instead of a cold start (L-22).
- A small HTML dashboard over `queue.json`.

## License

MIT, see LICENSE.
