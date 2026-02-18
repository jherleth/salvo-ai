---
phase: 04-n-trial-runner-and-cli
plan: 01
subsystem: execution
tags: [async, trial-runner, retry, aggregation, pydantic, percentiles]

requires:
  - phase: 02-adapter-layer-and-single-run-execution
    provides: "BaseAdapter ABC, AdapterConfig, ScenarioRunner for single-run execution"
  - phase: 03-assertion-engine-and-scoring
    provides: "evaluate_trace, compute_score, EvalResult for per-trial evaluation"
provides:
  - "TrialResult, TrialSuiteResult, Verdict, TrialStatus Pydantic models"
  - "TrialRunner class for N-trial orchestration with isolation, concurrency, and early-stop"
  - "retry_with_backoff for transient error handling with exponential backoff + jitter"
  - "compute_aggregate_metrics, determine_verdict, aggregate_failures for cross-trial analysis"
affects: [04-02, 04-03, 05-llm-as-judge, 06-record-and-replay]

tech-stack:
  added: [uuid7, statistics.quantiles, asyncio.TaskGroup, asyncio.Semaphore]
  patterns: [adapter-factory-per-trial, tmpdir-isolation, hand-rolled-retry]

key-files:
  created:
    - src/salvo/models/trial.py
    - src/salvo/execution/retry.py
    - src/salvo/execution/trial_runner.py
    - src/salvo/evaluation/aggregation.py
    - tests/test_trial_models.py
    - tests/test_aggregation.py
    - tests/test_retry.py
    - tests/test_trial_runner.py
  modified: []

key-decisions:
  - "Hand-rolled retry (~20 lines) instead of tenacity dependency for transient error handling"
  - "adapter_factory callable (not shared instance) ensures fresh adapter per trial for state isolation"
  - "uuid7() for run_id since Python 3.14 provides it natively (monotonically sortable)"
  - "statistics.quantiles(n=100) for percentiles with guard for single-trial edge case"
  - "aggregate_failures ranks by frequency * average weight lost for balanced impact ranking"

patterns-established:
  - "adapter_factory pattern: Callable[[], BaseAdapter] creates fresh instances to prevent shared state"
  - "TemporaryDirectory per trial for filesystem isolation (no os.chdir)"
  - "Semaphore-bounded TaskGroup for concurrent execution with early-stop via asyncio.Event"

requirements-completed: [EXEC-01, EXEC-02, EXEC-03, EVAL-08]

duration: 5min
completed: 2026-02-18
---

# Phase 4 Plan 1: N-Trial Execution Engine Summary

**TrialRunner with per-trial adapter isolation, Semaphore-bounded concurrency, exponential-backoff retry, early-stop, and cross-trial failure aggregation ranked by frequency * weighted impact**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-18T20:39:33Z
- **Completed:** 2026-02-18T20:45:02Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- TrialResult, TrialSuiteResult, Verdict, TrialStatus Pydantic models with extra='forbid' and JSON round-trip serialization
- compute_aggregate_metrics using statistics.quantiles for p50/p95 with 0-trial and 1-trial edge case guards
- determine_verdict mapping all 5 states (PASS, FAIL, HARD FAIL, PARTIAL, INFRA_ERROR) with allow_infra option
- aggregate_failures ranking by frequency * avg_weight_lost with sample capping at 3
- retry_with_backoff: hand-rolled exponential backoff + full jitter, detects transient via isinstance + status_code attrs
- TrialRunner orchestrating N isolated trials with fresh adapter + tmpdir per trial
- Concurrent mode via asyncio.Semaphore + TaskGroup with asyncio.Event for early-stop cancellation
- Early-stop on hard fail or mathematical impossibility (pessimistic best-possible-avg check)
- 67 tests covering all models, aggregation, retry, and runner behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Trial data models and aggregate metrics computation** - `e32295a` (feat)
2. **Task 2: TrialRunner with isolation, concurrency, retry, and early-stop** - `747f4e8` (feat)

## Files Created/Modified
- `src/salvo/models/trial.py` - TrialResult, TrialSuiteResult, Verdict, TrialStatus Pydantic models
- `src/salvo/evaluation/aggregation.py` - compute_aggregate_metrics, determine_verdict, aggregate_failures
- `src/salvo/execution/retry.py` - retry_with_backoff with transient error detection
- `src/salvo/execution/trial_runner.py` - TrialRunner class with isolation, concurrency, early-stop
- `tests/test_trial_models.py` - 16 tests for trial models and serialization
- `tests/test_aggregation.py` - 20 tests for metrics, verdict, and failure ranking
- `tests/test_retry.py` - 17 tests for retry logic and transient detection
- `tests/test_trial_runner.py` - 14 tests for runner orchestration, concurrency, and early-stop

## Decisions Made
- Hand-rolled retry (~20 lines) avoids tenacity dependency -- project preference for minimal deps
- adapter_factory callable pattern (not shared instance) prevents shared client state across trials
- uuid7() used natively from Python 3.14 stdlib for sortable run IDs
- statistics.quantiles(n=100) with guard for n<2 (returns scalar value for single trial)
- Failure aggregation ranks by freq * avg_weight_lost to balance frequency and severity

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed str(Enum) test assertion for Python 3.14**
- **Found during:** Task 1 (trial model tests)
- **Issue:** Python 3.14 changed str(StrEnum) to return "ClassName.value" instead of "value"
- **Fix:** Changed test to use .value property instead of str()
- **Files modified:** tests/test_trial_models.py
- **Verification:** All 36 Task 1 tests pass
- **Committed in:** e32295a (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test adjustment for Python 3.14 enum behavior. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- TrialSuiteResult is the core data contract consumed by CLI output (04-02) and report command (04-03)
- TrialRunner.run_all() ready for CLI integration with progress_callback for real-time output
- All modules importable: salvo.models.trial, salvo.execution.trial_runner, salvo.evaluation.aggregation

## Self-Check: PASSED

All 9 created files verified on disk. Both task commits (e32295a, 747f4e8) verified in git log.

---
*Phase: 04-n-trial-runner-and-cli*
*Completed: 2026-02-18*
