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

## Runs on a local model server

Wrightcrew works with any local model server that exposes an OpenAI-style endpoint (for example llama.cpp's server, Ollama, LM Studio or vLLM; these are examples, not a tested list). The author runs it on [Strata](https://github.com/niko1221/strata). The two meet at two points in `wrightcrew.config.json`:
- `health_url`: the server's model endpoint (e.g. `http://127.0.0.1:8080/v1/models`). The driver waits while it is down and never starts a lane against a dead server.
- `runner`: the agent harness command that talks to the server (e.g. `pi -p --mode json --provider local --model <your model>`), wrapped by `tools/run_lane.example.py` for the timeout and the process-tree kill.

Many local servers serve one request at a time; Wrightcrew runs **one lane at a time** either way, and keeps Claude out of the lane loop. One driver per repo is enforced by a lock (`driver.pid`, written atomically and deleted only by its owner). A `driver.pid` whose pid is dead, or alive but not a Wrightcrew driver (a reused pid), counts as stale; `driver.py recover` is the only way to clear it, and it deletes the file only if it still holds the value it read. If the process command line cannot be read, the pid is treated as a driver, and the refusal message and `status` say which file to delete by hand (they say it only in that case; a readable driver gets "use `driver.py stop`"). Interactive Claude sessions and local lanes don't compete: no lanes run once you create `.wrightcrew/run/USER_BACK`.

## What's in the box

It is not a framework or a server. It is:

- **A role charter.** Who plans, who builds, who checks, who reads, and what each role never does.
- **A pipeline.** Maker → checker → (maker fixes) → queue → build → review → landed or stopped.
- **A driver** (`wrightcrew/driver.py`). It runs queued lanes one at a time with no Claude in the loop: one state file, stop files, a deadline, and a post-landing review.
- **Templates** for cards, builder prompts, check reports, handoff entries and the planner refill.
- **A lessons file**, which records each incident and the rule it produced.
- **A lane-log summariser and a template** (v0.4 draft): `tools/lane_summary.py` summarises a JSONL lane log, and `templates/lessons_file.md` is a per-role lessons-file template.
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
   Unchecked work goes in as a draft, e.g. `python wrightcrew/driver.py add FIX-S02 builder prompts/fix_s02.md --state draft --maker sonnet`, and is promoted later with `set-state FIX-S02 queued --checker opus`. A draft added without a maker can get one later: `set-state FIX-S02 queued --maker sonnet --checker opus`.
5. **Isolate the lanes.** Builder lanes get read/edit/write/bash. Run them in a separate clone or under a low-privilege account with no secrets (`docs/permissions.md` §A), not in your real working repo.
6. Remove any leftover `.wrightcrew/run/STOP` or `USER_BACK`, then start the driver yourself, in your own terminal (never an agent):
   ```
   python wrightcrew/driver.py run
   ```
7. Watch it with `driver.py status`. End it with `driver.py stop`, which also ends the running lane (unless `stop_kills_running_lane` is false in the config, in which case the current lane finishes first). After a crash:
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

v0.3.3 plus the v0.4 draft docs and tools (CHANGELOG), 2026-10-21. The driver generalises the one that ran the Auto Crawler away-week.
- **Changed since v0.3.2.** D-1: the `queue.lock` stale breaker claims the stale file by atomic rename, re-reads it, and puts a live lock back instead of deleting it (L-26); D-2: L-30 now describes what the driver does; D-3: the README stop note names `stop_kills_running_lane`. Smoke tests: 25 cases.
- **Changed in v0.3.2.** V-05: a live pid in `driver.pid` counts as a driver only if its command line contains `driver.py` (a reused pid is stale); V-06: `recover` reads `driver.pid` once and deletes it only if the value is unchanged; V-10: `set-state --maker`; W2-02: the driver.py check ignores case (Windows); W2-05: the delete-by-hand hint appears only when the command line cannot be read; the "Runs on" section now describes any OpenAI-style local server. Smoke tests: 23 cases.
- **Changed since v0.3.** Checker equal to maker is refused; the driver lock is written atomically and deleted only by its owner (an empty or dead `driver.pid` is LOCKED until `recover`); a WARNING is logged for each missing `guarded_paths` entry; `status` prints ASCII and flags a stale lock; a queued builder card needs a named maker; the health script reports MODEL DOWN correctly; the README claims are now measured and the quick start covers the runner, isolation and gitignore; lessons L-23..L-34 and `docs/budget.md` are new; MIT license.
- **Checked.** A fresh Opus checker reviewed v0.1 (2 critical, 10 important) and v0.2 (1 new critical, 1 important); all are fixed in v0.3. The v0.3 rename and README were re-checked by a fresh checker (14 findings W-01..W-14, fixed in v0.3.1). Re-checked 2026-10-19 by a fresh checker in two rounds: final verdict RELEASE (round 1 findings V-01..V-09 and round 2 findings V-10..V-11; V-05, V-06 and V-10 fixed in v0.3.2). v0.3.2 was then checked by a fresh Opus checker in two rounds: final verdict RELEASE.
- **Tested.** `tests/smoke_test.py` covers the checker's reproductions plus the core paths: 25 cases (plus 4 in `tests/test_lane_summary.py`).
- **Not yet run for real.** It has not driven a real model lane in this generic form, so point it at a throwaway repo first.
- **Limits:**
  - The `--checker` guard is free text: it refuses a queued builder card with no maker, no checker, or checker == maker, but any lane with a shell could still self-queue under another name. Lanes are isolated by OS means instead (`docs/permissions.md`).
  - Review findings become fix cards by hand (mentor or planner); this is not automated.

**Planned next:**
- Resume the lane's agent session when retrying a stopped card, instead of a cold start (L-22).
- A small HTML dashboard over `queue.json`.

## License

MIT, see LICENSE.
