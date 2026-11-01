# Guidance trains the local model

Measured on the Auto Crawler project, 2026-10-19..21 (findings file `WRIGHTCREW_FINDINGS_20261021.md`; scorecard in `LOCAL_SCORECARD.md`).
A local model needed no fine-tuning to get better. What changed it was four written things, kept outside the model.

| Part | What it is | Why it works |
|---|---|---|
| **Lessons file** | One per role (`templates/lessons_file.md`). Every lesson = one real failure + the rule + how to check. Read first, every lane. | A lane has no memory between runs; the file is its memory. |
| **Recipe** | A written method plus one quality-bar example, made once by a strong model. | The strong model sets the bar; the local model repeats it at volume (L-36). |
| **Gates** | Automatic checks the lane runs on itself (the suite's summary line, palette/size rules, probes). | Cheap, tireless, and the lane sees the result before it stops. |
| **Scorecard** | One row per lane: kind, gates on the first try, checker findings, fix rounds, verdict. | The trend is the readiness measure; it tells you how much to trust the lane. |

## Results (sources: `LOCAL_SCORECARD.md` and the findings file; both are in the Auto Crawler repo, `scratch/_mentor_20261019/`, and not shipped here)
- Code cards: checker findings fell from 4 Important + 3 minor, then 3 small (card 3) to 1 minor (card 5, the first clean code pass).
- Art: hand-drawn screens mostly failed (dot grid, black trees, flat colour). Once a recipe existed, 5 of 5 zone screens passed all gates on the first try (findings file item 1). Separately, the local lanes then repeated one strong-model example for 7 zones, and one batch made 20 creature sprites in 31 min (item 2).
- These are one project and one model family. Treat them as an existence proof, not a rate.

## The loop
1. **Fail for real.** A checker or the user finds a defect in a landing.
2. **Write the lesson** (failure, rule, check) in the role's lessons file. Only the orchestrator edits it (L-42).
3. **Make or update the recipe** with a strong model when the lane needs a method rather than a rule. Include one example at the bar.
4. **Add or tighten a gate** so the same defect is caught automatically (see below).
5. **Score the next lane** and compare with the trend.

## Gates are necessary, not sufficient (L-37, L-38)
- Lanes passed every numeric gate while the art was flat, plaid, or had lost its signature features. A gate measures what you thought of.
- In the example project, every gate tried was eventually gamed or missed something: a "busy surface" metric was met by a perfect grid (plaid), a
  colour-connectivity check failed on rich art, and a halo gate read 0 while halos were visible.
- **Rule: when a human sees a defect the gate missed, first make the gate FAIL on it, then fix the work.** A gate that cannot go red on the known defect proves nothing.
- Close every batch with a taste check by a human or a strong model.

## The self-look step (vision models)
For any lane that produces something to be seen, add a mandatory step before it may stop: **open your own output and answer a fixed question list**,
writing the answers into its handoff entry, with a before/after comparison when it fixed something. The example project used 8 fixed questions
(its exact list is not in the findings file); this is a starting set to adapt:
1. Does it look like the brief's subject at the size it will really be shown (1x)?
2. Are the signature features visible at 1x?
3. Is any surface flat, patterned or gridded where it should vary?
4. Is anything cropped, missing or misplaced?
5. What did the last review say was wrong, and is it fixed?
6. What would a stranger name first, and is that right?
7. What changed since the previous version (before/after)?
8. What is still weak? List it; do not hide it.

## Scorecard format
| Lane | Kind | Gates first try | Checker / orchestrator findings | Fix rounds after | Verdict |
|---|---|---|---|---|---|

End with one line, "Trend: ...", that states the change in measured terms. Never write a number that is not in a source row.

## Limits
- It needs a strong model and a human in the loop: the lessons, the recipe and the taste check all come from them.
- The user's eye is the final gate; settle taste with side-by-side try-outs in the real view, not by argument (L-44).
