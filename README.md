# Wrightcrew

**A small crew of AI agents with fixed roles, building a project together, with a checker on every maker.**

Wrightcrew is the operating kit distilled from running the *Auto Crawler* game project with a mixed crew: Claude (Opus / Sonnet / Haiku) for planning, checking and reading, and a **local LLM** for unattended building. It came out of one hard week in October 2026, in which an away-week of autonomous work went from about 1 hour of model work per 7.5 hours to 44-69 lanes a day. Every rule in it comes from something that actually broke.

## Why Wrightcrew

A *wright* is a maker: a shipwright, a playwright, a wheelwright. Wrightcrew is a crew of makers, where **every maker has a checker**.

**The story.** Most multi-agent kits assume the agents are good. Ours were not. A small local model built a game unattended for a week, and it got things wrong in every way a weak model can. Cards were unsatisfiable. Restores went stale. Lanes hung. Approval prompts stalled overnight. Instead of a smarter agent, we built a stricter crew around it. By the end of the week the local model ran **44–69 lanes a day**, the paid models spent their tokens only on planning and checking, and every mistake that got through was caught by a checker before it shipped.

**What makes it different:**
1. **Made from incidents, not theory.** Every rule names the failure that caused it (`docs/lessons.md`, L-01..L-22).
2. **The maker never checks itself, and the code enforces it.** The queue refuses an unchecked builder card.
3. **Cheap hands, expensive eyes.** A free local model does the grinding; Claude spends its tokens where a mistake is costliest, on plans and checks.
4. **Failing safely counts as success.** A weak model that can't meet a card stops cleanly (CARD-CONFLICT) with nothing changed, instead of bending the work.
5. **No server, no database.** One JSON file plus git is the whole state; a `[CARD-ID]` in a commit subject *is* the status update.
6. **Honest about permissions.** Agents never start their own loops or widen their own access; the user does, and reverts.

## Runs on Strata

Wrightcrew is the crew; **Strata** is the ground it builds on, the local model server that does the work. They meet at two points in `wrightcrew.config.json`:
- `health_url`: Strata's model endpoint (e.g. `http://127.0.0.1:8080/v1/models`). The driver waits while it is down and never starts a lane against a dead server.
- `runner`: the agent harness command that talks to Strata (e.g. `pi -p --provider local --model <strata model>`), wrapped by `tools/run_lane.example.py` for the timeout and the process-tree kill.

Strata serves one request at a time, so Wrightcrew runs **one lane at a time** and keeps Claude out of the lane loop. Interactive Claude sessions and Strata lanes don't compete: when the user is present, no lanes run.

## What's in the box

It is not a framework or a server. It is:

- **A role charter.** Who plans, who builds, who checks, who reads, and what each role never does.
- **A pipeline.** Maker → checker → (maker fixes) → queue → build → review → landed or stopped.
- **A driver** (`wrightcrew/driver.py`). It runs queued lanes one at a time with no Claude in the loop: one state file, stop files, a deadline, and a post-landing review.
- **Templates** for cards, builder prompts, check reports, handoff entries and the planner refill.
- **A lessons file**, which records each incident and the rule it produced.

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

1. Copy `wrightcrew/`, `templates/` and `AGENTS.md` into your project. Fill in the `<<like this>>` parts of `AGENTS.md`, and
   start `docs/STATE.md` and `docs/goals.md` from `templates/STATE.md` and `templates/goals.md`.
2. Copy `wrightcrew.config.example.json` to `wrightcrew.config.json`. Set `guarded_paths` (your product code), the `runner` command
   (start from `tools/run_lane.example.py`) and `health_url`.
3. Write cards with `templates/card.md` and builder prompts with `templates/builder_prompt.md`. Get each one checked by a
   fresh session (`templates/check_report.md`).
4. Queue a checked prompt (a builder item can't be queued without a named checker):
   ```
   python wrightcrew/driver.py add FIX-S02 builder prompts/fix_s02.md --state queued --maker sonnet --checker opus
   ```
   Unchecked work goes in as `--state draft`, and is promoted later with `set-state FIX-S02 queued --checker opus`.
5. Remove any leftover `.wrightcrew/run/STOP` or `USER_BACK`, then start the driver yourself, in your own terminal (never an agent):
   ```
   python wrightcrew/driver.py run
   ```
6. Watch it with `driver.py status`. End it with `driver.py stop`, which also ends the running lane. After a crash:
   `driver.py recover`. After a builder failure streak: `driver.py reset-streak`.
7. Before trusting a change to the driver, run `python tests/smoke_test.py` (no model needed).

## Read next

- `docs/pipeline.md`: the lifecycle of a piece of work, the queue states, and what moves an item between them.
- `docs/roles.md`: each role's charter in detail.
- `docs/permissions.md`: setting up an unattended run without stalls and without a blanket bypass, then reverting it.
- `docs/lessons.md`: every incident and the rule it produced. **Read this before your first unattended run.**

## Status

v0.3, 2026-10-19. The driver generalises the one that ran the Auto Crawler away-week.
- **Checked.** A fresh Opus checker reviewed v0.1 (2 critical, 10 important) and v0.2 (1 new critical, 1 important); all are fixed in v0.3.
- **Tested.** `tests/smoke_test.py` covers the checker's reproductions (v0.1 and v0.2 rounds) plus the core paths: 11 cases.
- **Not yet run for real.** It has not driven a real model lane in this generic form, so point it at a throwaway repo first.
- **Limits:**
  - The `--checker` guard is free text, so any lane with a shell could self-queue. Lanes are isolated by OS means instead (`docs/permissions.md`).
  - Review findings become fix cards by hand (mentor or planner); this is not automated.

**Planned next:**
- Resume the lane's agent session when retrying a stopped card, instead of a cold start (L-22).
- A small HTML dashboard over `queue.json`.
