---
phase: 08-config-wiring-and-defensive-hardening
plan: 01
subsystem: config
tags: [salvo-yaml, project-config, judge-config, storage-dir, normalization, cli-wiring]

# Dependency graph
requires:
  - phase: 05-llm-judge-evaluation
    provides: JudgeEvaluator, resolve_judge_config
  - phase: 06-record-and-replay
    provides: TraceRecorder, RunStore, reeval_cmd
  - phase: 07-wire-trace-pipeline
    provides: trace_id generation, manifest methods, store passthrough
provides:
  - Shared find_project_root() and load_project_config() in models/config.py
  - JudgeConfig.default_threshold field for project-level threshold defaults
  - _project_judge_config injection pattern from TrialRunner to JudgeEvaluator
  - Defensive normalize_assertions() call in TrialRunner before evaluation
  - storage_dir parameter on RunStore wired from ProjectConfig in all CLI commands
  - k=1 verbose-only warning in JudgeEvaluator
  - recorder.py backward-compatible re-export of load_project_config
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_project_judge_config injection pattern: TrialRunner injects project judge config dict into assertion dicts, JudgeEvaluator pops and passes to resolve_judge_config"
    - "Shared find_project_root/load_project_config promoted from scattered CLI definitions to models/config.py"
    - "Defensive normalization: normalize_assertions wrapped in try/except before evaluate_trace_async"

key-files:
  created: []
  modified:
    - src/salvo/models/config.py
    - src/salvo/recording/recorder.py
    - src/salvo/execution/trial_runner.py
    - src/salvo/evaluation/evaluators/judge.py
    - src/salvo/cli/run_cmd.py
    - src/salvo/cli/report_cmd.py
    - src/salvo/cli/replay_cmd.py
    - src/salvo/cli/reeval_cmd.py
    - src/salvo/storage/json_store.py
    - src/salvo/scaffold/templates/salvo.yaml
    - tests/test_models_config.py
    - tests/test_trial_runner.py
    - tests/test_judge_evaluator.py
    - tests/test_cli_run.py
    - tests/test_report_cmd.py
    - tests/test_reeval_cmd.py
    - tests/test_replay_cmd.py

key-decisions:
  - "Config import at module level in run_cmd.py for patchability in tests (not local import inside async function)"
  - "recorder.py load_project_config kept as thin re-export wrapper for backward compat"
  - "_verbose flag injected via assertion dict alongside _scenario and _project_judge_config (consistent injection pattern)"

patterns-established:
  - "Config injection via assertion dict: TrialRunner enriches assertion dicts with _ prefixed metadata keys that evaluators pop before use"
  - "Shared project root discovery: all CLI commands import find_project_root from models/config.py (no local definitions)"

requirements-completed: [JUDG-01, JUDG-02, EVAL-01, SCEN-02, CLI-05]

# Metrics
duration: 6min
completed: 2026-02-19
---

# Phase 8 Plan 01: Config Wiring and Defensive Hardening Summary

**salvo.yaml judge/storage settings wired through TrialRunner, JudgeEvaluator, and all 4 CLI commands via shared config loading and _project_judge_config injection**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-19T20:21:52Z
- **Completed:** 2026-02-19T20:28:28Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments
- Promoted find_project_root() and load_project_config() to models/config.py as the single canonical location, eliminating 4 duplicate _find_project_root definitions across CLI commands
- Wired project-level judge config (model, k, temperature, default_threshold) through TrialRunner into JudgeEvaluator via _project_judge_config injection pattern
- Added defensive normalize_assertions() call in TrialRunner before evaluation to handle shorthand assertion formats
- Wired ProjectConfig.storage_dir to RunStore in all 4 CLI commands (run, report, replay, reeval)
- Added k=1 verbose-only warning for judge assertions where majority voting is disabled

## Task Commits

Each task was committed atomically:

1. **Task 1: Promote config loading, add default_threshold, wire RunStore storage_dir** - `95eb399` (feat)
2. **Task 2: Wire config through TrialRunner, JudgeEvaluator, and all CLI commands** - `e994461` (feat)

## Files Created/Modified
- `src/salvo/models/config.py` - Added find_project_root(), load_project_config(), JudgeConfig.default_threshold
- `src/salvo/recording/recorder.py` - Thin re-export wrapper for load_project_config backward compat
- `src/salvo/storage/json_store.py` - Added optional storage_dir parameter to RunStore.__init__
- `src/salvo/scaffold/templates/salvo.yaml` - Updated template with all configurable fields including judge section
- `src/salvo/execution/trial_runner.py` - Added project_config/verbose params, defensive normalization, _project_judge_config/_verbose injection
- `src/salvo/evaluation/evaluators/judge.py` - Extract _project_judge_config, wire default_threshold, k=1 verbose warning
- `src/salvo/cli/run_cmd.py` - Shared config imports, storage_dir wiring, project_config to TrialRunner, removed _find_project_root
- `src/salvo/cli/report_cmd.py` - Shared config imports, storage_dir wiring, removed _find_project_root
- `src/salvo/cli/replay_cmd.py` - Shared config imports, storage_dir wiring, removed _find_project_root
- `src/salvo/cli/reeval_cmd.py` - Shared config imports, storage_dir wiring, _project_judge_config injection, removed _find_project_root
- `tests/test_models_config.py` - Tests for find_project_root, load_project_config, default_threshold, RunStore storage_dir
- `tests/test_trial_runner.py` - Tests for project_config param, normalize_assertions call, _project_judge_config injection
- `tests/test_judge_evaluator.py` - Tests for project config override, default_threshold, assertion threshold precedence, k=1 warning
- `tests/test_cli_run.py` - Updated patches from _find_project_root to find_project_root
- `tests/test_report_cmd.py` - Updated patches from _find_project_root to find_project_root
- `tests/test_reeval_cmd.py` - Updated patches from _find_project_root to find_project_root
- `tests/test_replay_cmd.py` - Updated patches from _find_project_root to find_project_root

## Decisions Made
- Moved find_project_root/load_project_config import to module level in run_cmd.py for test patchability (local imports inside async functions cannot be patched at the module level)
- Kept recorder.py load_project_config as a thin re-export wrapper to avoid breaking existing import paths
- Used _verbose flag injection via assertion dict (consistent with _scenario and _project_judge_config injection pattern)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Module-level import for find_project_root in run_cmd.py**
- **Found during:** Task 2 (test_cli_run.py failures)
- **Issue:** Plan specified local import inside _run_async, but tests patching `salvo.cli.run_cmd.find_project_root` failed because the name wasn't at module level
- **Fix:** Moved import to module level alongside other imports
- **Files modified:** src/salvo/cli/run_cmd.py
- **Verification:** All 11 test_cli_run.py tests pass
- **Committed in:** e994461 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Trivial import placement change. No scope creep.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All config wiring complete; salvo.yaml settings flow through the full pipeline
- 555 tests pass with no regressions
- Project ready for any remaining gap closure work

## Self-Check: PASSED

All 17 files verified present. Both task commits (95eb399, e994461) verified in git log. 555 tests pass.

---
*Phase: 08-config-wiring-and-defensive-hardening*
*Completed: 2026-02-19*
