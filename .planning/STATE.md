# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** When you change your agent, Salvo tells you whether it still works -- across the full multi-step trajectory.
**Current focus:** Phase 2 Complete -- Ready for Phase 3: Assertion Engine

## Current Position

Phase: 2 of 6 (Adapter Layer and Single-Run Execution) -- COMPLETE
Plan: 3 of 3 in current phase (all complete)
Status: Phase Complete
Last activity: 2026-02-17 -- Completed 02-03-PLAN.md

Progress: [######....] 40%

## Performance Metrics

**Velocity:**
- Total plans completed: 6
- Average duration: 3.8min
- Total execution time: 0.38 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation-and-scenario-loading | 3/3 | 13min | 4.3min |
| 02-adapter-layer-and-single-run-execution | 3/3 | 11min | 3.7min |

**Recent Trend:**
- Last 5 plans: 01-03 (4min), 02-01 (3min), 02-02 (4min), 02-03 (4min)
- Trend: stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Compressed research's 8 phases into 6 for standard depth -- merged Foundation+Scenario Loading, merged N-Trial Runner+CLI
- [Roadmap]: Phases 5 (LLM Judge) and 6 (Record/Replay) are independent -- both depend on Phase 4 but not each other
- [01-01]: Used hatchling build backend with src/ layout for clean package structure
- [01-01]: All Pydantic models use extra='forbid' to reject unknown YAML keys early
- [01-01]: Created venv for isolated development (Python 3.14 externally-managed)
- [01-02]: Dotted path format for line_map keys (e.g. tools.0.name) for nested YAML position tracking
- [01-02]: Error codes E001-E007 mapped from Pydantic error types for consistent identification
- [01-02]: CI mode auto-detects from CI env var when --ci flag not provided
- [01-03]: Include path in example.yaml uses ../tools/ since !include resolves relative to scenario file directory
- [01-03]: Template files located via __file__ path for reliable package-relative resolution
- [01-03]: RunStore uses atomic write-to-tmp-then-rename for both run files and index
- [02-01]: Plain dataclasses for adapter types (not Pydantic) to avoid overhead in hot path
- [02-01]: Lazy imports via importlib for builtin adapters -- SDK not needed until first use
- [02-01]: frozenset for BLOCKED_KEYS in extras validation for O(1) membership test
- [02-01]: Model aliases dict for dated Claude versions mapping to base pricing
- [02-02]: Lazy-initialized AsyncOpenAI/AsyncAnthropic clients -- SDK not loaded until first send_turn()
- [02-02]: OpenAI tool_call arguments parsed via json.loads; Anthropic tool_use input already a dict
- [02-02]: Anthropic max_tokens defaults to 4096 when config.max_tokens is None (required param)
- [02-03]: Pydantic for trace models (not dataclasses) for JSON serialization with model_dump/model_validate
- [02-03]: Bearer token redaction pattern applied first to prevent partial matches from general auth pattern
- [02-03]: RunStore.save_trace() uses separate .salvo/traces/ directory from runs for clean separation
- [02-03]: _find_project_root() walks up from scenario file looking for .salvo/ or falls back to cwd

### Pending Todos

None yet.

### Blockers/Concerns

- Research flagged LiteLLM-vs-direct-adapters decision -- resolve during Phase 2 planning
- Research flagged judge-in-replay conflict -- resolve during Phase 5-6 planning
- Research flagged async execution model -- resolve during Phase 2 planning

## Session Continuity

Last session: 2026-02-17
Stopped at: Completed 02-03-PLAN.md (Phase 2 complete)
Resume file: .planning/phases/02-adapter-layer-and-single-run-execution/02-03-SUMMARY.md
