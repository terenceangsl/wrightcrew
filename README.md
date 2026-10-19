# Cadre

**A small crew of AI agents with fixed roles, building a project together, with a checker on every maker.**

Cadre is the operating kit distilled from running the *Auto Crawler* game project with a mixed crew: Claude (Opus / Sonnet / Haiku) for planning, checking and reading, and a **local LLM** for unattended building. It came out of one hard week in October 2026, in which an away-week of autonomous work went from about 1 hour of model work per 7.5 hours to 44-69 lanes a day. Every rule in it comes from something that actually broke.

It is not a framework or a server. It is:

- **A role charter.** Who plans, who builds, who checks, who reads, and what each role never does.
- **A pipeline.** Maker → checker → (maker fixes) → queue → build → review → landed or stopped.
- **A driver** (`cadre/driver.py`). It runs queued lanes one at a time with no Claude in the loop: one state file, stop files, a deadline, and a post-landing review.
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

1. Copy `cadre/`, `templates/` and `AGENTS.md` into your project. Fill in the `<<like this>>` parts of `AGENTS.md`, and
   start `docs/STATE.md` and `docs/goals.md` from `templates/STATE.md` and `templates/goals.md`.
2. Copy `cadre.config.example.json` to `cadre.config.json`. Set `guarded_paths` (your product code), the `runner` command
   (start from `tools/run_lane.example.py`) and `health_url`.
3. Write cards with `templates/card.md` and builder prompts with `templates/builder_prompt.md`. Get each one checked by a
   fresh session (`templates/check_report.md`).
4. Queue a checked prompt (a builder item can't be queued without a named checker):
   ```
   python cadre/driver.py add FIX-S02 builder prompts/fix_s02.md --state queued --maker sonnet --checker opus
   ```
   Unchecked work goes in as `--state draft`, and is promoted later with `set-state FIX-S02 queued --checker opus`.
5. Remove any leftover `.cadre/run/STOP` or `USER_BACK`, then start the driver yourself, in your own terminal (never an agent):
   ```
   python cadre/driver.py run
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

v0.2, 2026-10-19. The driver generalises the one that ran the Auto Crawler away-week.
- **Checked.** A fresh Opus checker reviewed v0.1 and found 2 critical and 10 important defects. The driver changes are fixed; the docs changes are fixed in v0.2.
- **Tested.** `tests/smoke_test.py` covers the checker's reproductions plus the core paths: 9 cases.
- **Not yet run for real.** It has not driven a real model lane in this generic form, so point it at a throwaway repo first.
- **Limits:**
  - The `--checker` guard is free text, so any lane with a shell could self-queue. Lanes are isolated by OS means instead (`docs/permissions.md`).
  - Review findings become fix cards by hand (mentor or planner); this is not automated.

**Planned next:**
- Resume the lane's agent session when retrying a stopped card, instead of a cold start (L-22).
- A small HTML dashboard over `queue.json`.
