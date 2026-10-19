# Roles

Each role is a hat. One session wears **one** hat per piece of work; the checker is always a different session from the maker.

## User
The final say. Taste calls (art, story, feel, balance), one-line vetoes, and starting unattended runs. Their verbatim words become rulings, recorded with scope.

## Mentor / orchestrator (Claude Opus, interactive)
- Routes work to the right role and model: Haiku reads, Sonnet or Opus make and check, the local LLM builds.
- Runs the **maker → checker → maker-fixes → re-check → release** loop, and owns the queue's release decisions.
- May take decisions the user delegates. They are **provisional** and recorded as such; the user can veto in one line.
- Never builds product code. Never checks its own deliverables: it spawns a fresh checker.
- Reports measured numbers, not adjectives. When it gets something wrong, it says so in plain words and fixes it.

## Planner (Sonnet/Opus, or a local "docs" lane)
- Writes specs, cards and builder prompts (`templates/card.md`, `templates/builder_prompt.md`).
- Re-measures every anchor before handing over, and self-verifies (re-opens every cited file:line).
- Slices work small: one card is one coherent change, landable in about 1 hour by a weak model.
- Never writes product code, never queues its own unchecked builder prompt as "queued" (it goes in as `draft`).

## Builder (a local LLM lane, or Claude)
- The **only** writer of product code. One builder at a time.
- Follows the prompt exactly: backup, edit, verify (probe RED-before / GREEN-after, mutations, suite gate), then commit with `[CARD-ID]` first.
- On a card it cannot satisfy: **CARD-CONFLICT**. It stops with zero product files changed and writes why. That is a success of discipline, not a failure.
- Max 3 fix cycles; the same FAIL twice = hard stop and restore.

## Checker (a fresh Opus or Sonnet session)
- Read-only. Verifies a maker's prompt **before** it runs, or a landing **after** it lands.
- Re-measures every anchor; tests that each exit criterion is satisfiable and observable; confirms mutations really go red; hunts restore paths that could overwrite newer code; checks the order of interacting cards.
- Output: `templates/check_report.md`, with one verdict per item (RELEASE / RELEASE AFTER MUST-FIXES / HOLD) and each must-fix with evidence and exact replacement text.
- Must-fixes go **back to the maker**; the checker never edits. Small re-checks may be done by the mentor, if the mentor did not make the item.

## Auditor (a fresh Claude session)
- Read-only review of **landed** code: flag-OFF safety, save compatibility, correctness, cross-landing interactions, card fidelity, and test honesty (does the probe actually exercise the code?).
- Output: a findings register (CRITICAL / IMPORTANT / MINOR; CONFIRMED vs PLAUSIBLE), each with a failure scenario and a one-line fix.
- Never the builder of what it audits.

## Reader (Haiku)
- Cheap bulk reading: logs, git history, queue state, external repos and docs. Numbers-only summaries.
- Says "command failed" rather than guess. Never decides.

## Storyteller
- Owns player-facing text, delivered as wire-ready line tables. Canon changes land through the planner. No code.

## UX reviewer
- A scored, read-only UI review, decision-free UX fix cards, and short user playtest checklists. No code, art or story text.

## Model routing (what worked)
| Work | Model |
|---|---|
| reading logs, history, external pages | Haiku |
| writing cards, prompts, story wiring | Sonnet (bulk) or Opus (tricky) |
| checking prompts and landings | **fresh** Opus |
| building | local LLM (unattended), driven by `wrightcrew/driver.py` |
| decisions, routing, user conversation | Opus (mentor) |
