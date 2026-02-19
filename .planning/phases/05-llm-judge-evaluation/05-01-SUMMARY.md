---
phase: 05-llm-judge-evaluation
plan: 01
subsystem: evaluation
tags: [llm-judge, k-vote, structured-output, pydantic, tdd]

# Dependency graph
requires:
  - phase: 03-assertion-engine-and-scoring
    provides: "BaseEvaluator ABC, EVALUATOR_REGISTRY, EvalResult model, scorer pipeline"
  - phase: 02-adapter-layer-and-single-run-execution
    provides: "BaseAdapter ABC, adapter registry, AdapterTurnResult, cost estimation"
provides:
  - "JudgeConfig model for project-level judge defaults"
  - "Assertion model extended with criteria/judge_model/k/include_system_prompt/custom_prompt/threshold"
  - "Judge prompt builder with 5-point anchoring and scoring tool schema"
  - "Context builder with trace summary and opt-in system prompt"
  - "Structured extraction with tool_call parsing, score clamping, and text-JSON fallback"
  - "k-vote aggregation with median per-criterion scores and majority verdict"
  - "JudgeEvaluator registered as 'judge' in EVALUATOR_REGISTRY"
  - "resolve_judge_config for config merging (assertion > project > defaults)"
affects: [05-02-llm-judge-evaluation, 06-record-replay-and-regression]

# Tech tracking
tech-stack:
  added: [statistics.median]
  patterns: [judge-subpackage-modules, structured-tool-output-extraction, k-vote-aggregation, text-json-fallback]

key-files:
  created:
    - src/salvo/evaluation/judge/__init__.py
    - src/salvo/evaluation/judge/prompt.py
    - src/salvo/evaluation/judge/context.py
    - src/salvo/evaluation/judge/extraction.py
    - src/salvo/evaluation/judge/aggregation.py
    - src/salvo/evaluation/evaluators/judge.py
    - tests/test_judge_prompt.py
    - tests/test_judge_context.py
    - tests/test_judge_extraction.py
    - tests/test_judge_aggregation.py
    - tests/test_judge_evaluator.py
  modified:
    - src/salvo/models/config.py
    - src/salvo/models/scenario.py
    - src/salvo/evaluation/evaluators/__init__.py

key-decisions:
  - "judge_model field name avoids Pydantic model_* namespace collision"
  - "Judge subpackage (evaluation/judge/) isolates all judge modules from existing evaluators"
  - "format_tool_choice detects provider via string contains for flexible naming"
  - "Threshold field added to Assertion model for per-assertion judge threshold override"

patterns-established:
  - "Judge prompt templates use named placeholders (criteria_block, context_block)"
  - "Structured extraction prefers tool_call, falls back to text-JSON, validates criterion names"
  - "k-vote aggregation uses statistics.median for outlier robustness"
  - "resolve_judge_config three-tier merge: assertion > project > hard-coded defaults"

requirements-completed: [JUDG-01, JUDG-02]

# Metrics
duration: 5min
completed: 2026-02-19
---

# Phase 5 Plan 01: LLM Judge Evaluator Summary

**Complete LLM judge pipeline with 4 submodules: prompt builder with 5-point anchoring scale, context builder, structured extraction with text-JSON fallback, and k-vote aggregation with median scores and majority verdict**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-19T16:13:14Z
- **Completed:** 2026-02-19T16:18:22Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- JudgeConfig model and Assertion model extended with all judge-specific fields
- Judge prompt builder with 5-point anchoring (0.0-1.0), scoring tool schema, and provider-specific tool_choice
- Trace context builder with opt-in system prompt inclusion and argument truncation
- Structured extraction with tool_call preference, score clamping, and three-strategy text-JSON fallback
- k-vote aggregation using statistics.median for outlier robustness and majority-vote pass/fail
- JudgeEvaluator class orchestrating the full pipeline with cost tracking
- resolve_judge_config merging assertion > project > hard-coded defaults
- 41 TDD tests covering all modules with full edge case coverage (479 total suite passes)

## Task Commits

Each task was committed atomically:

1. **Task 1: Judge config models, prompt builder, context builder, and extraction** - `e6f785a` (feat)
2. **Task 2: JudgeEvaluator with k-vote aggregation and registry integration** - `1fb9240` (feat)

## Files Created/Modified
- `src/salvo/models/config.py` - Added JudgeConfig model with adapter/model/k/temperature/max_tokens defaults; added judge field to ProjectConfig
- `src/salvo/models/scenario.py` - Extended Assertion model with criteria/judge_model/k/include_system_prompt/custom_prompt/threshold
- `src/salvo/evaluation/judge/__init__.py` - Judge subpackage init
- `src/salvo/evaluation/judge/prompt.py` - System/user templates, criteria block builder, scoring tool schema, provider-specific tool_choice
- `src/salvo/evaluation/judge/context.py` - Trace context builder with tool call summary and opt-in system prompt
- `src/salvo/evaluation/judge/extraction.py` - Structured extraction: tool_call parsing with score clamping, text-JSON fallback (direct/brace/code-block)
- `src/salvo/evaluation/judge/aggregation.py` - k-vote aggregation with median per-criterion scores and majority-vote pass/fail
- `src/salvo/evaluation/evaluators/judge.py` - JudgeEvaluator class with async pipeline and resolve_judge_config helper
- `src/salvo/evaluation/evaluators/__init__.py` - Added "judge": JudgeEvaluator to EVALUATOR_REGISTRY
- `tests/test_judge_prompt.py` - 7 tests for prompt builder, scoring tool, tool_choice formatting
- `tests/test_judge_context.py` - 6 tests for context builder with truncation and empty response
- `tests/test_judge_extraction.py` - 10 tests for extraction with clamping, fallback, and validation
- `tests/test_judge_aggregation.py` - 9 tests for aggregation edge cases (outliers, zero weight, missing criteria)
- `tests/test_judge_evaluator.py` - 9 tests for evaluator pipeline, registry, and config resolution

## Decisions Made
- Used `judge_model` field name (not `model`) to avoid shadowing Pydantic's internal `model_*` namespace
- Judge subpackage `evaluation/judge/` isolates all judge-specific modules from existing evaluators
- `format_tool_choice` uses string-contains check (`"openai" in lower`) for flexible provider naming
- Added `threshold` field to Assertion model for per-assertion judge threshold override (not in original plan but needed for judge evaluation flow)
- Context builder gracefully skips system prompt sections when scenario is None even if include_system_prompt=True

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added threshold field to Assertion model**
- **Found during:** Task 1 (Config models)
- **Issue:** Assertion model needed a threshold field for per-assertion judge threshold override; the JudgeEvaluator reads `assertion.get("threshold", 0.8)` but this wouldn't pass Pydantic validation with extra="forbid"
- **Fix:** Added `threshold: float | None = None` to Assertion model
- **Files modified:** src/salvo/models/scenario.py
- **Verification:** All 479 tests pass, existing scenario tests unaffected
- **Committed in:** e6f785a (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Essential for correctness -- without the threshold field, judge assertions would fail Pydantic validation. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Judge evaluator fully implemented and registered in EVALUATOR_REGISTRY
- Ready for Plan 05-02: YAML integration, scorer pipeline wiring, and end-to-end judge flow
- All existing tests (479) pass with no regressions

## Self-Check: PASSED

All 11 created files verified on disk. Both commit hashes (e6f785a, 1fb9240) verified in git log.

---
*Phase: 05-llm-judge-evaluation*
*Completed: 2026-02-19*
