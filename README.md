# Cadre

**A small crew of AI agents with fixed roles, building a project together, with a checker on every maker.**

Cadre is the operating kit distilled from running the *Auto Crawler* game project with a mixed crew: Claude (Opus / Sonnet / Haiku) for planning, checking and reading, and a **local LLM** for unattended building. It came out of one hard week in October 2026, in which an away-week of autonomous work went from 1 hour of work per 7 hours to roughly 30 lanes a day. Every rule in it comes from something that actually broke.

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

1. Copy `AGENTS.md` into your project root and fill in the project-specific sections, marked `<<like this>>`.
2. Copy `cadre.config.example.json` to `cadre.config.json` and point it at your repo, your runner and your guarded paths.
3. Write cards with `templates/card.md` and builder prompts with `templates/builder_prompt.md`. Get each one checked (`templates/check_report.md`).
4. Queue checked prompts:
   ```
   python cadre/driver.py add FIX-S02 builder prompts/fix_s02.md --maker opus --checker opus
   ```
5. Start the driver yourself, in your own terminal; it is never started by an agent:
   ```
   python cadre/driver.py run
   ```
6. Watch it with `python cadre/driver.py status`. Stop it with `python cadre/driver.py stop`, or by creating the stop file.

## Read next

- `docs/pipeline.md`: the lifecycle of a piece of work, the queue states, and what moves an item between them.
- `docs/roles.md`: each role's charter in detail.
- `docs/permissions.md`: setting up an unattended run without stalls and without a blanket bypass, then reverting it.
- `docs/lessons.md`: every incident and the rule it produced. **Read this before your first unattended run.**

## Status

v0.1, extracted 2026-10-19. The driver generalises the one that ran the Auto Crawler away-week. It was smoke-tested against a throwaway git repo with a fake runner, covering:
- the queue checker guard and duplicate refusal;
- a builder lane detected as landed from its `[ID]` commit;
- the review queued at the front and run;
- drafts not running;
- a clean stop on the stop file.

It has **not** yet driven a real model lane in this generic form, so point it at a throwaway repo first.

**Planned next:**
- Resume the lane's agent session when retrying a stopped card, instead of a cold start (L-22).
- A small HTML dashboard over `queue.json`.
