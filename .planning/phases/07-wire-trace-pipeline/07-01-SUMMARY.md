---
phase: 07-wire-trace-pipeline
plan: 01
subsystem: execution, storage, cli
tags: [uuid7, trace-pipeline, manifest, replay, reeval, judge-assertions]

# Dependency graph
requires:
  - phase: 06-record-and-replay
    provides: "RecordedTrace, TraceRecorder, TraceReplayer, RevalResult models and CLI commands"
  - phase: 04-n-trial-runner-and-cli
    provides: "TrialRunner, TrialResult, TrialSuiteResult, run_cmd"
provides:
  - "trace_id always populated (never None) on every TrialResult via uuid7()"
  - "Immediate per-trial trace persistence when store is provided"
  - "Trace manifest at .salvo/traces/manifest.json mapping run_id to trace_ids"
  - "_scenario injection for judge assertions in reeval_cmd"
  - "--allow-partial, --allow-partial-reeval, --strict-scenario CLI flags"
  - "Scenario drift detection in reeval_cmd"
affects: [08-gap-closure-testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Manifest file pattern for run_id-to-trace_id mapping with atomic writes"
    - "Upfront trace_id generation before try/except for availability in both success and error paths"
    - "asyncio.Lock for serializing manifest writes in concurrent execution"

key-files:
  created: []
  modified:
    - "src/salvo/execution/trial_runner.py"
    - "src/salvo/storage/json_store.py"
    - "src/salvo/cli/run_cmd.py"
    - "src/salvo/cli/replay_cmd.py"
    - "src/salvo/cli/reeval_cmd.py"
    - "tests/test_reeval_cmd.py"

key-decisions:
  - "trace_id generated as first line of _execute_single_trial, before start_time and try/except"
  - "Partial traces with finish_reason=error persisted for failed trials"
  - "reeval strict by default on metadata_only with content-dependent assertions; --allow-partial-reeval opts in"
  - "Scenario drift detection only when --scenario flag is provided (original snapshot hashes match by definition)"
  - "replay exits 1 on missing run_id without --allow-partial (was exit 0)"

patterns-established:
  - "Manifest-based trace tracking: manifest.json stores run_id -> [{trace_id, trial_index, status}] mappings"
  - "Store injection pattern: TrialRunner accepts optional store for immediate persistence"

requirements-completed: [RECD-01, RECD-02, RECD-03, CLI-04, JUDG-01]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 7 Plan 1: Wire Trace Pipeline Summary

**End-to-end trace pipeline wired: trace_id via uuid7() on every trial, immediate per-trial persistence, manifest tracking, _scenario injection for judge reeval, and --allow-partial/--strict-scenario CLI flags**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T18:09:00Z
- **Completed:** 2026-02-19T18:13:48Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Closed INT-01: trace_id is a valid uuid7 string on every TrialResult (never None)
- Closed INT-03: _scenario injected into judge assertion dicts in reeval_cmd
- Immediate per-trial trace persistence to .salvo/traces/{trace_id}.json when store provided
- Manifest file at .salvo/traces/manifest.json tracks run_id -> trace_id mappings
- Dead trace-save loop in run_cmd.py removed; store passed to TrialRunner
- New CLI flags: --allow-partial (replay), --allow-partial-reeval (reeval), --strict-scenario (reeval)
- Scenario drift detection warns/fails on hash mismatch

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire trace_id generation, manifest methods, store passthrough** - `3d69f54` (feat)
2. **Task 2: _scenario injection, CLI flags, scenario drift detection** - `a8fe6c6` (feat)

## Files Created/Modified
- `src/salvo/execution/trial_runner.py` - trace_id generation, optional store, manifest lock, partial trace persistence
- `src/salvo/storage/json_store.py` - Manifest methods: load/update/mark_run_recorded/get_trace_ids/get_latest_recorded
- `src/salvo/cli/run_cmd.py` - Store passed to TrialRunner, dead loop removed, mark_run_recorded, trace_id display
- `src/salvo/cli/replay_cmd.py` - --allow-partial flag, error handling for corrupt/missing traces
- `src/salvo/cli/reeval_cmd.py` - _scenario injection, --allow-partial-reeval, --strict-scenario, drift detection
- `tests/test_reeval_cmd.py` - Updated test for strict default, added test for permissive flag

## Decisions Made
- trace_id generated as first line of _execute_single_trial (before try/except) so it is available in both success and error paths
- Partial traces persisted for infra_error trials with finish_reason="error" and minimal message content
- reeval_cmd defaults to strict on metadata_only traces; --allow-partial-reeval required to skip incompatible assertions
- Scenario drift detection only runs when --scenario is explicitly provided (original snapshot always matches)
- replay_cmd changed from exit 0 to exit 1 when specific run_id not found (without --allow-partial)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test for new strict metadata_only default**
- **Found during:** Task 2 (reeval_cmd CLI flags)
- **Issue:** test_reeval_metadata_only_skips_content_assertions expected exit 0 (old permissive behavior) but new default is strict (exit 1)
- **Fix:** Split test into two: one verifying strict default (exit 1), one verifying --allow-partial-reeval flag (exit 0)
- **Files modified:** tests/test_reeval_cmd.py
- **Verification:** All 535 tests pass
- **Committed in:** a8fe6c6 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Test aligned with new intentional behavior. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full trace pipeline operational end-to-end
- Ready for Phase 8 gap closure testing
- All 535 tests pass (534 original + 1 new)

## Self-Check: PASSED

All files found. All commits verified.

---
*Phase: 07-wire-trace-pipeline*
*Completed: 2026-02-19*
