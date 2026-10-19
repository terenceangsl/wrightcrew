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

## Pattern: draft while the window is full, launch after the reset
- Cheap work (briefs, prompts, reading via a small model) runs at any time.
- Heavy agents (the maker, the fresh checker) wait for the reset.
- Unused weekly allowance expires at the reset, so plan heavy waves for the days before it.

## Routing
| Model | Does |
|---|---|
| Small (Haiku) | bulk reading |
| Mid (Sonnet) | prompts, reviews, drafts |
| Top (Opus) | fresh checks |
| Local model | all building, suites and long runs (free, one lane at a time) |
