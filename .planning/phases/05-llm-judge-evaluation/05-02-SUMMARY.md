---
phase: 05-llm-judge-evaluation
plan: 02
subsystem: evaluation
tags: [llm-judge, async-evaluation, trial-runner, cli-output, cost-tracking]

# Dependency graph
requires:
  - phase: 05-llm-judge-evaluation
    plan: 01
    provides: "JudgeEvaluator with k-vote aggregation, prompt/context/extraction/aggregation submodules"
  - phase: 04-n-trial-runner-and-cli
    provides: "TrialRunner N-trial execution engine, CLI output rendering, TrialSuiteResult model"
provides:
  - "BaseEvaluator.evaluate_async default method for async evaluation support"
  - "evaluate_trace_async async evaluation pipeline in scorer.py"
  - "Trial runner integrated with async evaluation and _scenario injection for judge context"
  - "EvalResult.metadata dict for structured judge data (model, k, cost, per_criterion)"
  - "TrialSuiteResult.judge_cost_total for separate judge cost tracking"
  - "CLI headline Judge row with model and k value"
  - "CLI cost breakdown showing agent + judge cost separation"
  - "CLI Judge Criteria section with color-coded per-criterion median scores"
affects: [06-record-replay-and-regression]

# Tech tracking
tech-stack:
  added: []
  patterns: [async-evaluation-pipeline, metadata-on-eval-result, judge-cost-aggregation, cli-judge-display]

key-files:
  created:
    - tests/test_judge_integration.py
  modified:
    - src/salvo/evaluation/evaluators/base.py
    - src/salvo/evaluation/evaluators/judge.py
    - src/salvo/evaluation/scorer.py
    - src/salvo/execution/trial_runner.py
    - src/salvo/models/result.py
    - src/salvo/models/trial.py
    - src/salvo/cli/output.py
    - tests/test_evaluation_scorer.py

key-decisions:
  - "evaluate_async default delegates to sync evaluate() -- no changes needed for existing evaluators"
  - "EvalResult.metadata stores structured judge data alongside human-readable details string"
  - "Judge cost tracked separately from agent cost (suite.cost_total is agent-only, judge_cost_total is additional)"
  - "CLI shows combined total = agent + judge in cost row when judge assertions present"

patterns-established:
  - "Async evaluation via evaluate_trace_async for evaluators needing LLM calls"
  - "EvalResult metadata dict for evaluator-specific structured data"
  - "Trial runner injects _scenario into judge assertion dicts for context building"
  - "Color-coded criteria display: green >= 0.7, yellow >= 0.4, red < 0.4"

requirements-completed: [JUDG-01, JUDG-02]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 5 Plan 02: Judge Integration Pipeline Summary

**Async evaluation pipeline wiring JudgeEvaluator into trial runner with separate cost tracking and CLI display of judge model, k-vote count, and per-criterion scores**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T16:21:33Z
- **Completed:** 2026-02-19T16:26:14Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- BaseEvaluator extended with evaluate_async default that delegates to sync evaluate()
- Async evaluation pipeline (evaluate_trace_async) enabling JudgeEvaluator LLM calls without event loop conflicts
- Trial runner uses async evaluation with _scenario injection for judge context building
- EvalResult extended with metadata dict for structured judge data (model, k, cost, per_criterion)
- TrialSuiteResult extended with judge_cost_total aggregated from eval result metadata
- JudgeEvaluator updated to populate metadata on EvalResult for cost aggregation
- CLI headline shows Judge row (model, k) and cost breakdown (agent + judge)
- CLI detail section shows Judge Criteria with color-coded per-criterion median scores
- 6 new tests (3 async scorer, 3 integration) -- 485 total suite passes

## Task Commits

Each task was committed atomically:

1. **Task 1: Async evaluation pipeline and trial runner integration** - `0ada078` (feat)
2. **Task 2: CLI output for judge model, cost breakdown, and per-criterion details** - `9016df7` (feat)

## Files Created/Modified
- `src/salvo/evaluation/evaluators/base.py` - Added evaluate_async default method delegating to sync evaluate()
- `src/salvo/evaluation/evaluators/judge.py` - Added metadata dict to EvalResult with judge_model, judge_k, judge_cost_usd, per_criterion
- `src/salvo/evaluation/scorer.py` - Added evaluate_trace_async for async evaluator support
- `src/salvo/execution/trial_runner.py` - Uses evaluate_trace_async, injects _scenario for judge, aggregates judge costs
- `src/salvo/models/result.py` - Added optional metadata dict field to EvalResult
- `src/salvo/models/trial.py` - Added judge_cost_total field to TrialSuiteResult
- `src/salvo/cli/output.py` - Judge row in headline, cost breakdown, Judge Criteria detail section
- `tests/test_evaluation_scorer.py` - Added 3 async scorer tests
- `tests/test_judge_integration.py` - 3 end-to-end integration tests for judge in trial runner

## Decisions Made
- evaluate_async default delegates to sync evaluate() -- existing evaluators work unchanged without any modifications
- EvalResult.metadata stores structured judge data (model, k, cost, per_criterion) alongside human-readable details string
- Judge cost tracked separately: suite.cost_total is agent-only cost, judge_cost_total is additional judge LLM cost
- CLI combined total = agent_cost + judge_cost displayed when judge assertions present
- Color-coded criteria display in CLI details: green for median >= 0.7, yellow >= 0.4, red < 0.4

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added metadata to JudgeEvaluator EvalResult returns**
- **Found during:** Task 1 (Trial runner integration)
- **Issue:** JudgeEvaluator returned EvalResult without metadata field -- cost aggregation in trial runner requires metadata["judge_cost_usd"] to be present
- **Fix:** Added metadata dict with judge_model, judge_k, judge_cost_usd, and per_criterion to both success and failure EvalResult returns in JudgeEvaluator
- **Files modified:** src/salvo/evaluation/evaluators/judge.py
- **Verification:** Integration tests verify metadata populated and judge_cost_total aggregated correctly
- **Committed in:** 0ada078 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for correctness -- without metadata on EvalResult, judge costs cannot be aggregated in trial runner. No scope creep.

## Issues Encountered
- Integration test mock patching: ScenarioRunner is lazy-imported inside _execute_single_trial, so patching `salvo.execution.trial_runner.ScenarioRunner` fails. Fixed by patching at the source module `salvo.execution.runner.ScenarioRunner` instead.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Complete LLM judge pipeline working end-to-end from scenario YAML through evaluation to terminal output
- Judge assertions evaluated asynchronously within async trial runner pipeline
- Judge cost tracked separately and visible in CLI
- Phase 5 complete -- ready for Phase 6 (Record/Replay and Regression)
- All 485 tests pass with zero regressions

---
*Phase: 05-llm-judge-evaluation*
*Completed: 2026-02-19*
