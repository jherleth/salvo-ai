---
phase: 06-record-and-replay
plan: 02
subsystem: recording
tags: [replay, reeval, cli, trace, pydantic]

# Dependency graph
requires:
  - phase: 06-record-and-replay
    provides: "RecordedTrace model, RunStore recording methods, --record CLI flag"
  - phase: 04-n-trial-runner-and-cli
    provides: "CLI structure, Typer app, Rich output patterns"
  - phase: 03-assertion-engine-and-scoring
    provides: "evaluate_trace_async, assertion normalization, scoring pipeline"
provides:
  - "salvo replay CLI command for read-only trace display"
  - "salvo reeval CLI command for re-evaluating traces with updated assertions"
  - "TraceReplayer class for loading recorded traces"
  - "RevalResult Pydantic model for re-evaluation output"
  - "RunStore.save_reeval_result saving to .salvo/revals/ directory"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [replay-banner-format, reeval-linked-results, revals-directory-separation]

key-files:
  created:
    - src/salvo/cli/replay_cmd.py
    - src/salvo/cli/reeval_cmd.py
    - src/salvo/recording/replayer.py
    - tests/test_replay_cmd.py
    - tests/test_reeval_cmd.py
  modified:
    - src/salvo/recording/models.py
    - src/salvo/recording/__init__.py
    - src/salvo/cli/main.py
    - src/salvo/storage/json_store.py

key-decisions:
  - "RevalResult stored in .salvo/revals/ directory to avoid contaminating list_runs() which globs .salvo/runs/"
  - "metadata_only traces filter out content-dependent assertion types (jmespath, judge, custom) during reeval"
  - "Replay shows (recorded) suffix on latency and cost values to distinguish from live runs"
  - "Reeval exit code mirrors run: 0 on pass, 1 on fail"

patterns-established:
  - "Replay banner pattern: [REPLAY] / [RE-EVAL] banners distinguish replayed output from live output"
  - "Revals directory: .salvo/revals/ stores re-evaluation results separate from runs"
  - "Content-dependent assertion filtering: metadata_only mode skips jmespath/judge/custom types"

requirements-completed: [RECD-02, RECD-03, CLI-04]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 6 Plan 2: Replay and Re-evaluation Commands Summary

**salvo replay for zero-cost trace inspection with [REPLAY] banner and (recorded) timing, salvo reeval for re-evaluating traces against updated assertions with linked RevalResult output**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T17:18:59Z
- **Completed:** 2026-02-19T17:24:09Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- salvo replay command renders recorded traces read-only with [REPLAY] banner, (recorded) timing labels, and message summary -- zero API calls
- salvo reeval command runs evaluation pipeline against recorded traces with original snapshot or updated scenario file
- RevalResult model links re-evaluation output to original trace via original_trace_id
- .salvo/revals/ directory keeps reeval results isolated from run results (no list_runs contamination)
- metadata_only mode handled gracefully: replay shows content excluded warning, reeval skips content-dependent assertions
- Both commands registered in CLI entry point (salvo --help shows replay and reeval)
- 18 tests covering all replay and reeval scenarios

## Task Commits

Each task was committed atomically:

1. **Task 1: TraceReplayer, RevalResult model, and salvo replay command** - `470fab9` (feat)
2. **Task 2: salvo reeval command with updated assertions and linked results** - `d6fdc63` (feat)

## Files Created/Modified
- `src/salvo/cli/replay_cmd.py` - salvo replay CLI command with [REPLAY] banner and trace display
- `src/salvo/cli/reeval_cmd.py` - salvo reeval CLI command with evaluation pipeline and linked results
- `src/salvo/recording/replayer.py` - TraceReplayer class for loading recorded traces
- `src/salvo/recording/models.py` - Added RevalResult Pydantic model for re-evaluation output
- `src/salvo/recording/__init__.py` - Added re-exports for RevalResult and TraceReplayer
- `src/salvo/cli/main.py` - Registered replay and reeval commands
- `src/salvo/storage/json_store.py` - Added save_reeval_result and .salvo/revals/ directory support
- `tests/test_replay_cmd.py` - 8 tests for replay command
- `tests/test_reeval_cmd.py` - 10 tests for reeval command

## Decisions Made
- RevalResult stored in .salvo/revals/ directory (not .salvo/runs/) to prevent contaminating list_runs() which globs runs_dir/*.json
- metadata_only traces filter out content-dependent assertion types (jmespath, judge, custom) during reeval; non-content types (tool_sequence, cost_limit, latency_limit) still evaluable
- Replay displays (recorded) suffix on latency and cost values per locked decision from research
- Reeval exit code mirrors salvo run: 0 on pass, 1 on fail for CI compatibility

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mock target path for evaluate_trace_async in tests**
- **Found during:** Task 2 (test_reeval_cmd.py)
- **Issue:** Mock patch targeted `salvo.cli.reeval_cmd.evaluate_trace_async` but the function is imported lazily inside `_reeval_async`, so the attribute doesn't exist on the module at patch time
- **Fix:** Changed mock target to `salvo.evaluation.scorer.evaluate_trace_async` which is the actual source module
- **Files modified:** tests/test_reeval_cmd.py
- **Verification:** All 10 reeval tests pass
- **Committed in:** d6fdc63 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test mock path correction. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 6 (Record and Replay) is complete
- Full recording pipeline: --record flag captures traces, replay displays them, reeval re-evaluates them
- All 534 tests pass across the entire codebase

## Self-Check: PASSED

All 9 files verified present. Both task commits (470fab9, d6fdc63) verified in git log.

---
*Phase: 06-record-and-replay*
*Completed: 2026-02-19*
