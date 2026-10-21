# Changelog

## v0.4.0 (draft, 2026-10-21, branch `v0.4-findings`, not yet checked)
Folds in the ten findings from the Auto Crawler work of 2026-10-19..21 (source: `WRIGHTCREW_FINDINGS_20261021.md`).
- **Lessons:** L-35..L-44 in `docs/lessons.md`, one per finding.
- **New doc:** `docs/guidance.md`: lessons-as-memory, recipe from a strong model, gates, the self-look step for vision models, the scorecard.
- **Docs:** `docs/pipeline.md` §6b lane hygiene (JSON logs, lane cap, fix-cycle cap, lanes never edit the orchestrator's files);
  `docs/roles.md` (art director, maker/checker evidence); `docs/budget.md` (watch the 5-hour window first).
- **Tools:** `tools/lane_summary.py` (JSONL lane-log summariser), `templates/lessons_file.md` (lessons-file template).
- **Config:** the example runner now uses `pi -p --mode json` (L-40).
- **Tests:** `tests/test_lane_summary.py`.
- Not part of this entry: the uncommitted v0.3.2 work (V-05, V-06, V-10) that was in the working tree when this branch was cut; it stays uncommitted.
- **Needs a fresh checker** before release (L-12, L-23): every number must be traced to the findings file.

## v0.3.1 (2026-10-19)
Fixes from the v0.3 re-check (W-01..W-14, V-01..V-11). See `git log` and the README status section.
