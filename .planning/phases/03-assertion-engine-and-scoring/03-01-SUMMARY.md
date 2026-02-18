---
phase: 03-assertion-engine-and-scoring
plan: 01
subsystem: evaluation
tags: [jmespath, assertion, scoring, evaluator, tdd]

requires:
  - phase: 02-adapter-layer-and-single-run-execution
    provides: "RunTrace model and execution pipeline"
provides:
  - "Assertion normalizer (operator-key shorthand to canonical form)"
  - "4 evaluators: JMESPath, tool sequence, cost limit, latency limit"
  - "Evaluator registry mapping type strings to classes"
  - "Weighted scorer with required-assertion hard-fail logic"
  - "evaluate_trace orchestration function"
affects: [03-02-integration, cli-eval-pipeline]

tech-stack:
  added: [jmespath]
  patterns: [evaluator-registry, canonical-assertion-form, weighted-scoring]

key-files:
  created:
    - src/salvo/evaluation/__init__.py
    - src/salvo/evaluation/normalizer.py
    - src/salvo/evaluation/evaluators/__init__.py
    - src/salvo/evaluation/evaluators/base.py
    - src/salvo/evaluation/evaluators/jmespath_eval.py
    - src/salvo/evaluation/evaluators/tool_sequence.py
    - src/salvo/evaluation/evaluators/cost_limit.py
    - src/salvo/evaluation/evaluators/latency_limit.py
    - src/salvo/evaluation/scorer.py
    - tests/test_evaluation_normalizer.py
    - tests/test_evaluation_jmespath.py
    - tests/test_evaluation_tool_sequence.py
    - tests/test_evaluation_limits.py
    - tests/test_evaluation_scorer.py
  modified:
    - pyproject.toml

key-decisions:
  - "EVALUATOR_REGISTRY dict pattern for type-string to evaluator-class dispatch"
  - "Canonical assertion form: {type, expression, operator, value, weight, required}"
  - "build_trace_data flattens RunTrace into JMESPath-queryable dict with response/turns/tool_calls/metadata keys"
  - "Tool sequence match functions return tuple[bool, str] with divergence-pinpointing failure messages"
  - "compute_score uses sum(score*weight)/sum(weight) formula with zero-weight guard"

patterns-established:
  - "Evaluator pattern: BaseEvaluator ABC with evaluate(trace, assertion) -> EvalResult"
  - "Registry pattern: EVALUATOR_REGISTRY dict with get_evaluator() factory function"
  - "Normalizer pattern: shorthand detection via operator-key set intersection"

requirements-completed: [EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06]

duration: 6min
completed: 2026-02-18
---

# Phase 3 Plan 1: Assertion Engine Core Summary

**JMESPath/tool-sequence/cost/latency evaluators with weighted scorer, normalizer, and registry -- 91 tests covering all 8 operators, 3 sequence modes, edge cases, and scoring math**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-18T19:41:58Z
- **Completed:** 2026-02-18T19:48:06Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments
- Normalizer converts all 8 operator-key shorthand forms (eq, ne, gt, gte, lt, lte, contains, regex) to canonical jmespath assertion format
- JMESPath evaluator queries trace data via jmespath.search() with 8 comparison operators, type coercion, and error handling
- Tool sequence evaluator validates EXACT, IN_ORDER, ANY_ORDER modes with divergence-pinpointing failure messages
- Cost and latency limit evaluators check thresholds with None-safe cost handling
- Weighted scorer computes sum(score*weight)/sum(weight) with required-assertion hard-fail override
- evaluate_trace orchestrates full pipeline from trace + assertions to scored results
- 91 new tests (78 Task 1 + 13 Task 2), total suite at 292, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Assertion normalizer, BaseEvaluator, registry, and all four evaluators** - `016ad38` (feat)
2. **Task 2: Weighted scorer with required-assertion hard-fail logic** - `3693b96` (feat)

## Files Created/Modified
- `src/salvo/evaluation/__init__.py` - Package init with re-exports for normalizer, evaluators, scorer
- `src/salvo/evaluation/normalizer.py` - Operator-key shorthand to canonical form conversion with OPERATOR_KEYS set
- `src/salvo/evaluation/evaluators/__init__.py` - EVALUATOR_REGISTRY dict and get_evaluator() factory
- `src/salvo/evaluation/evaluators/base.py` - BaseEvaluator ABC with evaluate() abstract method
- `src/salvo/evaluation/evaluators/jmespath_eval.py` - JMESPath query evaluator with build_trace_data and compare functions
- `src/salvo/evaluation/evaluators/tool_sequence.py` - Tool sequence validation with match_exact/match_in_order/match_any_order
- `src/salvo/evaluation/evaluators/cost_limit.py` - Cost threshold evaluator with None-safe handling
- `src/salvo/evaluation/evaluators/latency_limit.py` - Latency threshold evaluator
- `src/salvo/evaluation/scorer.py` - Weighted scoring with compute_score and evaluate_trace
- `tests/test_evaluation_normalizer.py` - 16 tests for normalizer (8 operators, passthrough, errors)
- `tests/test_evaluation_jmespath.py` - 33 tests for JMESPath evaluator (operators, coercion, errors)
- `tests/test_evaluation_tool_sequence.py` - 17 tests for tool sequence (3 modes, zero calls, dispatch)
- `tests/test_evaluation_limits.py` - 12 tests for cost/latency limits (thresholds, None, weight/required)
- `tests/test_evaluation_scorer.py` - 13 tests for scorer (weighted math, threshold, hard-fail, E2E)
- `pyproject.toml` - Added jmespath>=1.1.0 dependency

## Decisions Made
- EVALUATOR_REGISTRY dict pattern for O(1) type-string to evaluator-class dispatch
- Canonical assertion form {type, expression, operator, value, weight, required} enables uniform processing
- build_trace_data creates flat dict with response/turns/tool_calls/metadata top-level keys for JMESPath querying
- Tool sequence match functions return tuple[bool, str] where string provides human-readable divergence details
- compute_score guards against zero total weight with early return (0.0, False, hard_fail)
- evaluate_trace takes already-normalized assertions -- normalization responsibility is upstream (03-02)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All evaluation primitives are built and tested -- ready for 03-02 integration plan
- evaluate_trace provides the orchestration entry point for CLI pipeline wiring
- Normalizer will be called upstream when loading scenario assertions
- EVALUATOR_REGISTRY is extensible for future evaluator types (e.g., LLM judge in Phase 5)

## Self-Check: PASSED

- All 15 files verified present on disk
- Commit 016ad38 verified in git log
- Commit 3693b96 verified in git log
- 292 tests pass (201 pre-existing + 91 new), zero regressions

---
*Phase: 03-assertion-engine-and-scoring*
*Completed: 2026-02-18*
