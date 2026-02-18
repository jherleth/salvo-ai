---
phase: 02-adapter-layer-and-single-run-execution
plan: 03
subsystem: execution
tags: [scenario-runner, multi-turn, mock-tools, trace, redaction, cli-run, rich-summary, json-storage]

# Dependency graph
requires:
  - phase: 02-adapter-layer-and-single-run-execution
    provides: "BaseAdapter ABC, unified Message/AdapterTurnResult types, adapter registry, cost estimation, extras validation, OpenAI/Anthropic adapters"
provides:
  - "ScenarioRunner with async run() driving multi-turn conversation loop with mock tool injection"
  - "RunTrace and TraceMessage Pydantic models for replay-ready trace storage"
  - "Redaction utilities (redact_content, truncate_content, apply_trace_limits) for trace safety"
  - "ToolMockNotFoundError for missing mock response detection"
  - "salvo run CLI command with structured Rich summary output"
  - "RunStore.save_trace() and load_trace() for .salvo/traces/ persistence"
affects: [03-assertion-engine, 04-n-trial-runner-and-cli, 06-record-replay]

# Tech tracking
tech-stack:
  added: []
  patterns: [multi-turn-loop, mock-tool-injection, trace-redaction, cli-async-bridge]

key-files:
  created:
    - src/salvo/execution/trace.py
    - src/salvo/execution/redaction.py
    - src/salvo/execution/runner.py
    - src/salvo/cli/run_cmd.py
    - tests/test_execution_trace.py
    - tests/test_execution_redaction.py
    - tests/test_execution_runner.py
    - tests/test_cli_run.py
  modified:
    - src/salvo/execution/__init__.py
    - src/salvo/storage/json_store.py
    - src/salvo/cli/main.py

key-decisions:
  - "Pydantic for trace models (not dataclasses) for JSON serialization with model_dump/model_validate"
  - "Bearer token redaction pattern applied first to prevent partial matches from general auth pattern"
  - "RunStore.save_trace() uses separate .salvo/traces/ directory from runs for clean separation"
  - "_find_project_root() walks up from scenario file looking for .salvo/ or falls back to cwd"

patterns-established:
  - "MockAdapter pattern for runner tests: list of pre-configured AdapterTurnResults popped per turn"
  - "asyncio.run() bridge in CLI for async runner execution"
  - "Rich console for structured CLI output with stderr for errors, stdout for summary"
  - "Atomic trace writes matching existing RunStore pattern"

requirements-completed: [EXEC-04]

# Metrics
duration: 4min
completed: 2026-02-17
---

# Phase 2 Plan 3: Execution Pipeline and CLI Run Command Summary

**ScenarioRunner multi-turn loop with mock tool injection, replay-ready trace models with secret redaction, and `salvo run` CLI printing structured summary with cost/latency/hash and persisting results + traces to .salvo/**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-18T01:56:05Z
- **Completed:** 2026-02-18T02:00:45Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- ScenarioRunner drives multi-turn conversation loop: sends to adapter, checks for tool calls, injects mock responses, repeats until final answer or max turns safety net
- Runner handles parallel tool calls (all tool calls from one response get mocked), accumulates usage across turns, computes scenario hash and cost estimate
- ToolMockNotFoundError raised immediately when model calls a tool with no mock_response defined
- RunTrace and TraceMessage Pydantic models capture all messages, tool calls, turn count, usage, latency, cost, hash, provider metadata, and max_turns_hit flag
- Redaction removes API keys, OpenAI sk-... patterns, and Bearer tokens; truncation enforces 50KB/message and 100KB/response limits
- `salvo run scenario.yaml` end-to-end: load, validate extras, resolve adapter, execute, print Rich summary, save RunResult to .salvo/runs/ and redacted RunTrace to .salvo/traces/
- Error cases (invalid YAML, missing SDK, blocked extras, missing mock, API errors) produce clear messages and exit code 1
- All 201 tests pass (25 new, zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Trace models, redaction utilities, and ScenarioRunner** - `a0654d5` (feat)
2. **Task 2: salvo run CLI command with summary output and RunStore persistence** - `f3478d6` (feat)

## Files Created/Modified
- `src/salvo/execution/trace.py` - RunTrace and TraceMessage Pydantic models for replay-ready storage
- `src/salvo/execution/redaction.py` - redact_content(), truncate_content(), apply_trace_limits() with compiled regex patterns
- `src/salvo/execution/runner.py` - ScenarioRunner class with async run() multi-turn loop, ToolMockNotFoundError exception
- `src/salvo/execution/__init__.py` - Updated exports for all new execution modules
- `src/salvo/cli/run_cmd.py` - `salvo run` command: async execution bridge, Rich summary output, RunStore persistence
- `src/salvo/cli/main.py` - Registered run command in Typer app
- `src/salvo/storage/json_store.py` - Added save_trace() and load_trace() methods with .salvo/traces/ directory
- `tests/test_execution_trace.py` - 3 tests for TraceMessage serialization, RunTrace round-trip, defaults
- `tests/test_execution_redaction.py` - 7 tests for all redaction patterns, truncation, and apply_trace_limits
- `tests/test_execution_runner.py` - 8 tests with MockAdapter covering single/multi-turn, parallel tools, max turns, usage accumulation, hash, cost
- `tests/test_cli_run.py` - 7 tests with CLIMockAdapter covering success, invalid YAML, missing SDK, missing mock, store persistence, extras validation, trace persistence

## Decisions Made
- Used Pydantic for trace models (not dataclasses) because traces are serialized to JSON for storage and Pydantic provides model_dump/model_validate for free
- Reordered redaction patterns so Bearer token pattern runs before the general auth pattern, preventing partial matches where `Authorization: Bearer` was consumed as a key-value pair
- Separate .salvo/traces/ directory from .salvo/runs/ for clean separation of run results vs full traces
- _find_project_root() walks up from scenario file directory looking for existing .salvo/ directory, falls back to cwd

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed bearer token redaction pattern ordering**
- **Found during:** Task 1 (redaction tests)
- **Issue:** The general auth pattern `(authorization)\s*[:=]\s*\S+` consumed "Authorization: Bearer" before the bearer-specific pattern could match the full JWT token
- **Fix:** Reordered REDACTION_PATTERNS to apply bearer token pattern first
- **Files modified:** src/salvo/execution/redaction.py
- **Verification:** test_redact_bearer_token passes, JWT fully redacted
- **Committed in:** `a0654d5` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential ordering fix for correct bearer token redaction. No scope creep.

## Issues Encountered

None.

## User Setup Required

None - all tests use mocked adapters. For real execution, users need API keys (OPENAI_API_KEY or ANTHROPIC_API_KEY) as documented in 02-02-SUMMARY.md.

## Next Phase Readiness
- Phase 2 complete: full execution pipeline from scenario YAML to stored results + traces
- ScenarioRunner ready for N-trial execution (Phase 4) by wrapping in a loop
- RunTrace ready for assertion evaluation (Phase 3) -- contains all messages and tool calls
- Trace persistence ready for record/replay (Phase 6)
- All 201 tests pass across Phase 1 and Phase 2

## Self-Check: PASSED

All 11 created/modified files verified on disk. Both commit hashes verified in git log.

---
*Phase: 02-adapter-layer-and-single-run-execution*
*Completed: 2026-02-17*
