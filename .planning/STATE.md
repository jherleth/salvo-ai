# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** When you change your agent, Salvo tells you whether it still works -- across the full multi-step trajectory.
**Current focus:** Phase 1: Foundation and Scenario Loading

## Current Position

Phase: 1 of 6 (Foundation and Scenario Loading) -- COMPLETE
Plan: 3 of 3 in current phase
Status: Phase Complete
Last activity: 2026-02-17 -- Completed 01-03-PLAN.md (Phase 1 done)

Progress: [####......] 17%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 4.3min
- Total execution time: 0.22 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation-and-scenario-loading | 3/3 | 13min | 4.3min |

**Recent Trend:**
- Last 5 plans: 01-01 (4min), 01-02 (5min), 01-03 (4min)
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

### Pending Todos

None yet.

### Blockers/Concerns

- Research flagged LiteLLM-vs-direct-adapters decision -- resolve during Phase 2 planning
- Research flagged judge-in-replay conflict -- resolve during Phase 5-6 planning
- Research flagged async execution model -- resolve during Phase 2 planning

## Session Continuity

Last session: 2026-02-17
Stopped at: Completed 01-03-PLAN.md -- Phase 1 complete
Resume file: .planning/phases/01-foundation-and-scenario-loading/01-03-SUMMARY.md
