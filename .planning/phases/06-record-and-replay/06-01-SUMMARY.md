---
phase: 06-record-and-replay
plan: 01
subsystem: recording
tags: [trace, redaction, replay, pydantic, cli]

# Dependency graph
requires:
  - phase: 02-adapter-layer-and-single-run-execution
    provides: "RunTrace model, execution/redaction module, RunStore persistence"
  - phase: 04-n-trial-runner-and-cli
    provides: "TrialSuiteResult, TrialRunner, salvo run CLI command"
provides:
  - "RecordedTrace and TraceMetadata Pydantic models with schema versioning"
  - "Extended redaction pipeline with custom pattern support"
  - "metadata_only recording mode for sensitive environments"
  - "TraceRecorder orchestrating record pipeline"
  - "RunStore extensions for .recorded.json persistence and symlinks"
  - "--record CLI flag on salvo run"
affects: [06-02-replay-engine]

# Tech tracking
tech-stack:
  added: []
  patterns: [recorded-trace-wrapper, additive-redaction-pipeline, metadata-only-stripping]

key-files:
  created:
    - src/salvo/recording/__init__.py
    - src/salvo/recording/models.py
    - src/salvo/recording/redaction.py
    - src/salvo/recording/recorder.py
    - tests/test_recording.py
  modified:
    - src/salvo/execution/redaction.py
    - src/salvo/models/config.py
    - src/salvo/storage/json_store.py
    - src/salvo/cli/run_cmd.py

key-decisions:
  - "RecordedTrace wraps RunTrace (not extends) to keep recording metadata separate from execution trace"
  - "Custom redaction patterns are additive-only; built-in patterns cannot be disabled"
  - "metadata_only strips content to [CONTENT_EXCLUDED] while preserving roles, tool names, turn counts, usage"
  - "Each trial trace is individually recorded as {trace_id}.recorded.json (not one file per suite)"
  - "Recording happens after normal suite persistence (step 12b) to avoid disrupting existing flow"

patterns-established:
  - "Recorded trace schema versioning via CURRENT_TRACE_SCHEMA_VERSION with forward-compat validation"
  - "Additive redaction pipeline: build_redaction_pipeline combines built-in + custom patterns at build time"
  - "Atomic .recorded.json file naming convention alongside raw .json traces"

requirements-completed: [RECD-01]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 6 Plan 1: Trace Recording Infrastructure Summary

**Recording subpackage with schema-versioned RecordedTrace models, additive custom redaction pipeline, metadata_only mode, and --record CLI flag writing .recorded.json per trial**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T17:12:52Z
- **Completed:** 2026-02-19T17:16:52Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Recording subpackage (models, redaction, recorder) providing full trace capture with automatic secret redaction
- Extended built-in redaction patterns to cover cookies, Anthropic keys, GitHub PATs/OAuth tokens
- Custom redaction patterns from salvo.yaml extend (never replace) built-in patterns
- metadata_only mode strips message content and tool arguments while preserving structural metadata
- TraceRecorder orchestrates redaction pipeline, mode handling, and per-trial persistence
- RunStore extended with save/load/list for .recorded.json files and latest-recorded symlink
- `salvo run --record` flag wired as opt-in step after normal suite persistence
- 31 tests covering the full recording pipeline

## Task Commits

Each task was committed atomically:

1. **Task 1: Recording models, extended redaction, and project config** - `9904468` (feat)
2. **Task 2: TraceRecorder, RunStore extensions, and --record flag** - `d00d290` (feat)

## Files Created/Modified
- `src/salvo/recording/__init__.py` - Package re-exports for recording subpackage
- `src/salvo/recording/models.py` - RecordedTrace, TraceMetadata, schema versioning
- `src/salvo/recording/redaction.py` - Extended redaction pipeline, custom patterns, metadata_only stripping
- `src/salvo/recording/recorder.py` - TraceRecorder class and load_project_config helper
- `src/salvo/execution/redaction.py` - Added cookie, Anthropic key, GitHub token patterns
- `src/salvo/models/config.py` - RecordingConfig added to ProjectConfig
- `src/salvo/storage/json_store.py` - save/load/list recorded traces and latest-recorded symlink
- `src/salvo/cli/run_cmd.py` - --record flag and recording step after suite persistence
- `tests/test_recording.py` - 31 tests for full recording pipeline

## Decisions Made
- RecordedTrace wraps RunTrace (not extends) to keep recording metadata separate from execution trace
- Custom redaction patterns are additive-only; built-in patterns cannot be disabled
- metadata_only strips content to [CONTENT_EXCLUDED] while preserving roles, tool names, turn counts, usage
- Each trial trace is individually recorded as {trace_id}.recorded.json (not one file per suite)
- Recording happens after normal suite persistence (step 12b) to avoid disrupting existing flow

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Recording infrastructure complete, ready for replay engine (06-02)
- RecordedTrace model provides the input format for trace replay
- latest-recorded symlink enables `salvo replay` to find most recent recording

---
*Phase: 06-record-and-replay*
*Completed: 2026-02-19*
