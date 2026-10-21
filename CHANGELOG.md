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
- Not part of this entry: the v0.3.2 work (V-05, V-06, V-10); it is its own entry below.
- **Needs a fresh checker** before release (L-12, L-23): every number must be traced to the findings file.

## v0.3.3 (2026-10-21)
Three defects found by challenging seven outside reviews against the code.
- **D-1 (important):** the `queue.lock` stale breaker could delete a live lock another waiter had just created. It now claims the stale file by atomic rename, re-reads it, and restores a live lock with `os.link`; any put-back failure (lock already present, or no hard links) logs `LOCK ALARM`, keeps the claimed file and aborts. One window remains (rename to put-back): a third waiter can take the lock there, and it is detected only if the put-back finds `queue.lock` present, so two writers may briefly overlap (round 2: C3-01 any link error, C3-02 stale-claim cleanup and 0.1 s pause).
- **D-2 (docs):** L-30 now says what the driver does: no `[ID]` commit means `failed`; a lane that leaves guarded files dirty blocks all builder lanes until a human cleans up.
- **D-3 (docs):** the README stop note names `stop_kills_running_lane`.
- **Tests:** `tests/smoke_test.py` now has 25 cases (the D-1 case fails on v0.3.2; the C3-01 link-error case fails on 2c01ac6; a no-re-check mutant turns D-1 RED).

## v0.3.2 (2026-10-21)
Driver lock owner checks and `set-state --maker` (re-check findings V-05, V-06, V-10).
- **V-05:** a live pid in `driver.pid` counts as a driver only if its command line contains `driver.py` (case-insensitive); a reused pid is stale.
- **V-06:** `recover` reads `driver.pid` once and deletes it only if the value is unchanged after reconcile.
- **V-10:** `set-state --maker`.
- **README:** new "Runs on a local model server" section (any OpenAI-style endpoint; the author runs Strata); v0.3.2 status.
- **Tests:** `tests/smoke_test.py` now has 23 cases (4 new; 3 fail on v0.3.1, 1 kills an always-False `driver_alive` mutant).
- **Checked** by a fresh Opus checker in two rounds; final verdict RELEASE.

## v0.3.1 (2026-10-19)
Fixes from the v0.3 re-check (W-01..W-14, V-01..V-11). See `git log` and the README status section.
