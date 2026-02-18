---
phase: 03-assertion-engine-and-scoring
plan: 02
subsystem: evaluation
tags: [formatting, cli-integration, normalization, scoring, pipeline]

requires:
  - phase: 03-assertion-engine-and-scoring
    provides: "Evaluator registry, normalizer, scorer, evaluate_trace"
  - phase: 02-adapter-layer-and-single-run-execution
    provides: "run_cmd.py CLI, RunTrace, RunResult models"
provides:
  - "Assertion normalization in YAML validation pipeline"
  - "Per-assertion CLI output with severity ordering (HARD FAIL/FAILED/PASS)"
  - "Score breakdown formatting with weighted calculation display"
  - "Real evaluation replacing Phase 2 stubs in run_cmd.py"
  - "CI-compatible exit codes (0 pass, 1 fail)"
affects: [04-n-trial-runner-and-cli, 05-llm-judge, 06-record-replay]

tech-stack:
  added: []
  patterns: [normalization-before-validation, severity-ordered-output, format-eval-results]

key-files:
  created:
    - src/salvo/evaluation/formatting.py
    - tests/test_evaluation_formatting.py
  modified:
    - src/salvo/models/scenario.py
    - src/salvo/loader/validator.py
    - src/salvo/cli/run_cmd.py
    - src/salvo/evaluation/__init__.py
    - tests/test_models_scenario.py
    - tests/test_loader_validator.py
    - tests/test_cli_run.py

key-decisions:
  - "normalize_assertions inserted before Pydantic validation in validate_scenario to convert operator-key shorthand"
  - "max_usd and max_seconds added to Assertion model for cost_limit/latency_limit types"
  - "format_eval_results returns plain text with indentation -- Rich markup applied only in CLI layer"
  - "model_dump(exclude_none=True) converts Assertion objects to clean dicts for evaluators"
  - "Exit code 1 on evaluation failure for CI pipeline compatibility"

patterns-established:
  - "Normalization-before-validation: raw dicts normalized to canonical form before Pydantic model_validate"
  - "Severity-ordered output: hard failures first, soft failures second, passes last"
  - "Formatter separation: formatting.py produces plain text, CLI applies Rich styling"

requirements-completed: [EVAL-05, EVAL-06, EVAL-07]

duration: 4min
completed: 2026-02-18
---

# Phase 3 Plan 2: Evaluation Pipeline Integration Summary

**Operator-key assertion normalization in YAML pipeline, evaluate_trace wired into CLI replacing stubs, per-assertion PASS/FAILED/HARD FAIL output with severity ordering and score breakdowns**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-18T19:51:50Z
- **Completed:** 2026-02-18T19:56:07Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Assertion normalization step inserted in validate_scenario() converts operator-key shorthand ({path, contains, ...}) to canonical form before Pydantic validation
- Assertion model extended with max_usd and max_seconds fields for cost_limit/latency_limit types
- evaluate_trace replaces Phase 2 stubs (passed=True, score=0.0) with real weighted scoring in run_cmd.py
- Per-assertion output formatter with severity ordering: HARD FAIL first, FAILED second, PASS last
- Score breakdown with weighted calculation shown on fail; minimal single-line output on pass
- RunResult persisted with real eval_results, score, and passed values
- Exit code 1 on failure for CI pipeline integration
- 26 new tests (10 Task 1 + 16 Task 2), total suite at 318, zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Assertion model update and YAML pipeline normalization** - `8cc0ba8` (feat)
2. **Task 2: Evaluation integration into run_cmd.py and per-assertion output formatting** - `fc60187` (feat)

## Files Created/Modified
- `src/salvo/evaluation/formatting.py` - Per-assertion result formatter with severity ordering and score breakdowns
- `src/salvo/models/scenario.py` - Added max_usd and max_seconds fields to Assertion model
- `src/salvo/loader/validator.py` - Inserted normalize_assertions step before Pydantic validation
- `src/salvo/cli/run_cmd.py` - Wired evaluate_trace replacing Phase 2 stubs, added formatted output and exit codes
- `src/salvo/evaluation/__init__.py` - Added format_eval_results re-export
- `tests/test_models_scenario.py` - 4 new tests for canonical form, cost_limit, latency_limit, extra forbid
- `tests/test_loader_validator.py` - 6 new tests for normalization pipeline (shorthand, explicit, errors, mixed)
- `tests/test_evaluation_formatting.py` - 12 new tests for formatting (pass, verbose, severity, breakdown)
- `tests/test_cli_run.py` - 4 new tests for CLI evaluation (pass, fail, hard fail, persistence)

## Decisions Made
- normalize_assertions inserted before Pydantic validation in validate_scenario to convert operator-key shorthand -- normalization errors wrapped as ValidationErrorDetail with assertion index
- max_usd and max_seconds fields added to Assertion model because extra='forbid' requires declaring all fields used by evaluators
- format_eval_results returns plain text with indentation -- Rich markup applied only in CLI layer for clean separation
- model_dump(exclude_none=True) used to convert Assertion Pydantic objects to clean dicts for evaluator consumption
- Exit code 1 on evaluation failure (not passed) for CI pipeline compatibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Complete evaluation pipeline from YAML loading through scoring to CLI output
- Phase 3 fully complete -- all assertion engine and scoring functionality delivered
- Ready for Phase 4 (N-Trial Runner and CLI) which will call evaluate_trace per trial
- format_eval_results can be reused for per-trial output in batch runs
- EVALUATOR_REGISTRY extensible for Phase 5 (LLM Judge evaluator)

## Self-Check: PASSED

- All 9 files verified present on disk
- Commit 8cc0ba8 verified in git log
- Commit fc60187 verified in git log
- 318 tests pass (292 pre-existing + 26 new), zero regressions

---
*Phase: 03-assertion-engine-and-scoring*
*Completed: 2026-02-18*
