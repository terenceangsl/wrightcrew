# Pacing paid models

Facts from the Auto Crawler week (see L-31, L-33, L-34 in `docs/lessons.md`).

## The two windows
- Subscription limits have a short window (5 hours) and a long one (weekly).
- Paid overflow happens when the short window overflows, even when the weekly figure is low.
  Measured: paid extra usage grew from SGD 1.16 to 18.56 while the weekly figure was 53% (L-31).

## Guards
- Check usage before every wave.
- Waves stop at 60-80% of the short window.
- Scheduled checks only review above 60%.
- A hard tripwire on paid spend.

## Watch both windows (L-43)
Extra paid usage also grew when the weekly figure reached 98-100 % (findings file item 9). Read the short window and the weekly figure before every wave.
When either is high: draft, don't launch. Whenever the local model is idle, give it the work (it costs no paid usage, L-34).

## Pattern: draft while the window is full, launch after the reset
- Cheap work (briefs, prompts, reading via a small model) runs at any time.
- Heavy agents (the maker, the fresh checker) wait for the reset.
- Unused weekly allowance expires at the reset, so plan heavy waves for the days before it.

## Routing
| Model | Does |
|---|---|
| Small (Haiku) | bulk reading |
| Mid (Sonnet) | prompts, reviews, drafts, routine fresh checks (L-39) |
| Top (Opus) | the orchestrator; fresh checks of tricky items |
| Local model | all building, suites and long runs (free, one lane at a time) |
