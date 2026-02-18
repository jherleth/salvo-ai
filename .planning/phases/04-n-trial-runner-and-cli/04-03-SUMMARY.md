---
phase: 04-n-trial-runner-and-cli
plan: 03
subsystem: cli
tags: [typer, rich, report, history, trend, filtering]

requires:
  - phase: 04-n-trial-runner-and-cli
    provides: "TrialSuiteResult, Verdict for N-trial results display"
  - phase: 04-n-trial-runner-and-cli
    provides: "RunStore with save_suite_result, load_suite_result, load_latest_suite, list_runs"
provides:
  - "salvo report command showing latest run detail with verdict, metrics, per-trial breakdown"
  - "salvo report --history trend table of recent runs with pass rate, score, cost"
  - "Failure filtering (--failures) and scenario filtering (--scenario) for report views"
affects: [05-llm-as-judge, 06-record-and-replay]

tech-stack:
  added: []
  patterns: [verdict-display-reuse, project-root-discovery, typer-cli-runner-testing]

key-files:
  created:
    - src/salvo/cli/report_cmd.py
    - tests/test_report_cmd.py
  modified:
    - src/salvo/cli/main.py

key-decisions:
  - "Report command imports Rich directly (Table, Console, box) since report layout differs from live output.py rendering"
  - "Verdict styling duplicated from output.py _VERDICT_STYLES rather than cross-importing to keep modules independent"
  - "_find_project_root walks up from cwd (not scenario file) since report has no scenario file argument"
  - "History mode loads runs via list_runs then load_suite_result per run with skip-on-error for resilience"
  - "Typer CliRunner with patch on _find_project_root for test isolation using tmp_path"

patterns-established:
  - "Report rendering pattern: separate _render_run_detail and _render_history for detail vs trend views"
  - "CliRunner + patch for project root: enables fully isolated testing without real .salvo directory"

requirements-completed: [CLI-03]

duration: 2min
completed: 2026-02-18
---

# Phase 4 Plan 3: Report Command Summary

**salvo report command with Rich-rendered latest run detail, --history trend table, --failures assertion filter, and --scenario filter using RunStore persistence**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-18T21:03:09Z
- **Completed:** 2026-02-18T21:05:31Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- report_cmd.py module with full report command: latest run detail view, --history trend table, --failures filter, --scenario filter, --limit control
- Rich-rendered per-trial breakdown table with Trial#, Status, Score, Latency, Cost, Retries columns
- History trend table with Run ID, Scenario, Verdict, Score, Trials, Cost and pass rate trend summary
- Graceful error handling: empty store, missing run IDs, corrupted files, no matching scenario
- Report command registered in main.py as `salvo report` subcommand
- 11 tests covering all modes and edge cases, full suite at 438 tests with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: salvo report command with latest detail, history trend, and failure filtering** - `8c43db5` (feat)

## Files Created/Modified
- `src/salvo/cli/report_cmd.py` - Report command with _render_run_detail, _render_history, verdict display, project root discovery
- `src/salvo/cli/main.py` - Added report command registration via `app.command(name="report")(report_cmd)`
- `tests/test_report_cmd.py` - 11 tests: latest, by-run-id, no-runs, run-id-not-found, history, history-limit, history-no-runs, scenario-filter, scenario-no-match, failures-detail, failures-history

## Decisions Made
- Report command has its own _VERDICT_STYLES copy rather than importing from output.py -- keeps report_cmd and output.py as independent modules that can evolve separately
- _find_project_root walks up from cwd (not scenario file path) since report command has no scenario file argument
- History mode uses list_runs then individual load_suite_result calls with try/except skip for corrupted entries
- Tests use typer.testing.CliRunner with patch on _find_project_root for clean tmp_path isolation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Phase 4 CLI commands complete: init, validate, run, report
- Report command ready for LLM judge results (Phase 5) -- same TrialSuiteResult format
- History trend view ready for record/replay comparisons (Phase 6)

## Self-Check: PASSED

All 3 created/modified files verified on disk. Task commit (8c43db5) verified in git log.

---
*Phase: 04-n-trial-runner-and-cli*
*Completed: 2026-02-18*
