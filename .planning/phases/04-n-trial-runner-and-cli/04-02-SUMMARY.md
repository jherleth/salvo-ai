---
phase: 04-n-trial-runner-and-cli
plan: 02
subsystem: cli
tags: [rich, typer, progress-bar, verdict-table, json-output, symlink, exit-codes]

requires:
  - phase: 04-n-trial-runner-and-cli
    provides: "TrialRunner, TrialSuiteResult, Verdict for N-trial execution and results"
  - phase: 02-adapter-layer-and-single-run-execution
    provides: "BaseAdapter ABC, get_adapter registry, ScenarioRunner for execution"
  - phase: 03-assertion-engine-and-scoring
    provides: "evaluate_trace, EvalResult for per-trial evaluation"
provides:
  - "Rich verdict rendering: headline table, detail sections, progress bar, JSON output"
  - "Refactored salvo run with N-trial integration and full CLI flag support"
  - "RunStore suite persistence with save_suite_result, load_suite_result, latest symlink"
  - "Exit codes 0/1/2/3 mapping to PASS/FAIL/HARD FAIL/INFRA_ERROR verdicts"
affects: [04-03, 05-llm-as-judge, 06-record-and-replay]

tech-stack:
  added: [rich.progress, rich.table, rich.box]
  patterns: [verdict-styling-map, atomic-symlink-with-fallback, adapter-factory-per-trial-in-cli]

key-files:
  created:
    - src/salvo/cli/output.py
    - tests/test_output.py
    - tests/test_run_cmd_ntrial.py
  modified:
    - src/salvo/cli/run_cmd.py
    - src/salvo/storage/json_store.py
    - tests/test_cli_run.py

key-decisions:
  - "Verdict styling via _VERDICT_STYLES dict mapping verdict value to (symbol, Rich style) tuples"
  - "create_trial_progress returns None for non-TTY -- caller handles skip, not the progress bar"
  - "render_details filters infra_error trials from score breakdown for accurate distribution display"
  - "adapter_factory closure in run_cmd calls get_adapter per trial for fresh adapter instances"
  - "Latest symlink uses atomic os.symlink+os.replace with .latest text file fallback for Windows"
  - "Updated test_cli_run.py to use side_effect factory pattern (not return_value) for N-trial compatibility"

patterns-established:
  - "Verdict styling map: static dict of (symbol, style) tuples for consistent verdict display"
  - "Non-TTY detection: console.is_terminal guard with None return for optional features"
  - "Atomic symlink pattern: create tmp symlink then os.replace for safe concurrent access"
  - "Fresh mock adapter factory: side_effect returning new instances for N-trial test isolation"

requirements-completed: [CLI-02, CLI-06]

duration: 6min
completed: 2026-02-18
---

# Phase 4 Plan 2: CLI Output and N-Trial Integration Summary

**Rich verdict rendering with headline table and detail sections, refactored salvo run using TrialRunner with -n/--parallel/--json/--early-stop flags, suite persistence with latest symlink, and exit codes 0/1/2/3**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-18T20:47:51Z
- **Completed:** 2026-02-18T20:53:50Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Rich verdict rendering module (output.py) with headline table, detail sections, progress bar, and pure JSON output mode
- Refactored run_cmd.py to use TrialRunner for N-trial execution with 10 CLI flags (-n, --parallel, --json, --verbose, --report, --diagnose, --early-stop, --allow-infra, --threshold)
- RunStore extended with save_suite_result, update_latest_symlink, load_suite_result, load_latest_suite for TrialSuiteResult persistence
- Exit codes mapped: 0=PASS, 1=FAIL/PARTIAL, 2=HARD FAIL, 3=INFRA_ERROR with --allow-infra override
- Non-TTY/CI mode: progress bar suppressed, ANSI codes stripped automatically by Rich
- 42 new tests across output.py and run_cmd_ntrial.py, plus 8 updated tests in test_cli_run.py
- Full test suite (427 tests) passes with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Rich verdict rendering module (output.py)** - `036ba45` (feat)
2. **Task 2: Refactor run_cmd.py with TrialRunner integration and suite persistence** - `2a1b44d` (feat)

## Files Created/Modified
- `src/salvo/cli/output.py` - Rich rendering: create_trial_progress, render_headline, render_details, output_json
- `src/salvo/cli/run_cmd.py` - Refactored run command with TrialRunner, 10 CLI flags, exit code mapping
- `src/salvo/storage/json_store.py` - Extended with save_suite_result, update_latest_symlink, load_suite_result, load_latest_suite
- `tests/test_output.py` - 26 tests for verdict rendering, details, JSON output, non-TTY mode
- `tests/test_run_cmd_ntrial.py` - 16 tests for suite persistence, exit codes, allow-infra, latest symlink
- `tests/test_cli_run.py` - Updated 8 tests for N-trial architecture (fresh adapter per trial via side_effect)

## Decisions Made
- Verdict styling uses a static dict mapping verdict value to (symbol, Rich style) tuples for maintainable display
- create_trial_progress returns None for non-TTY -- caller checks and skips, avoiding conditional logic inside progress bar
- render_details filters infra_error trials from score breakdown so distributions only show meaningful scores
- adapter_factory closure in run_cmd calls get_adapter per trial to ensure fresh adapter instances (matches TrialRunner contract)
- Latest symlink uses atomic os.symlink + os.replace pattern with .latest text file fallback for Windows compatibility
- Updated test_cli_run.py from return_value to side_effect factory pattern because N-trial architecture creates fresh adapters per trial

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_cli_run.py for N-trial adapter factory pattern**
- **Found during:** Task 2 (run_cmd refactoring)
- **Issue:** Old tests used `patch("...get_adapter", return_value=mock_adapter)` which returns the same mock instance for all N trials. With TrialRunner, each trial consumes the mock's single response, causing trials 2+ to fail with "exhausted responses" (INFRA_ERROR).
- **Fix:** Changed to `side_effect=_mock_adapter_factory()` which creates a fresh CLIMockAdapter per call. Also updated exit code assertions (HARD FAIL now exits 2 instead of 1) and adapted output assertions for verdict table format.
- **Files modified:** tests/test_cli_run.py
- **Verification:** All 427 tests pass including all 11 test_cli_run.py tests
- **Committed in:** 2a1b44d (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test adaptation was necessary for compatibility with refactored architecture. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- output.py rendering functions ready for report command (04-03) to reuse for historical run display
- RunStore.load_latest_suite() ready for `salvo report` to show most recent results
- All CLI flags established and tested for pipeline integration documentation

## Self-Check: PASSED

All 6 created/modified files verified on disk. Both task commits (036ba45, 2a1b44d) verified in git log.

---
*Phase: 04-n-trial-runner-and-cli*
*Completed: 2026-02-18*
