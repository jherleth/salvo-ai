---
phase: 02-adapter-layer-and-single-run-execution
plan: 01
subsystem: adapters
tags: [abc, dataclass, registry, importlib, cost-estimation, security-validation]

# Dependency graph
requires:
  - phase: 01-foundation-and-scenario-loading
    provides: "Project structure, Pydantic models (Scenario.adapter field), venv with pytest"
provides:
  - "BaseAdapter ABC with abstract send_turn() contract"
  - "Unified message/result dataclasses (Message, AdapterTurnResult, TokenUsage, ToolCallResult, AdapterConfig)"
  - "Adapter registry with builtin name lookup and custom dotted-path import"
  - "Cost estimation from token usage for 4 models"
  - "Extras validation with secret blocklist and size limits"
affects: [02-02, 02-03, 03-assertion-engine, 04-n-trial-runner-and-cli]

# Tech tracking
tech-stack:
  added: []
  patterns: [abc-abstractmethod, dataclass-not-pydantic, lazy-import-registry, frozenset-blocklist]

key-files:
  created:
    - src/salvo/adapters/__init__.py
    - src/salvo/adapters/base.py
    - src/salvo/adapters/registry.py
    - src/salvo/execution/__init__.py
    - src/salvo/execution/cost.py
    - src/salvo/execution/extras.py
    - tests/test_adapters_base.py
    - tests/test_adapters_registry.py
    - tests/test_execution_cost.py
    - tests/test_execution_extras.py
  modified: []

key-decisions:
  - "Plain dataclasses for adapter types (not Pydantic) to avoid overhead in hot path"
  - "Lazy imports via importlib for builtin adapters -- SDK not needed until first use"
  - "frozenset for BLOCKED_KEYS in extras validation for O(1) membership test"
  - "Model aliases dict for dated Claude versions mapping to base pricing"

patterns-established:
  - "ABC + abstractmethod for provider adapter contracts"
  - "Dataclass with field(default_factory=...) for mutable defaults"
  - "importlib.import_module + getattr for dynamic class loading"
  - "Case-insensitive blocklist validation via key.lower() in frozenset"

requirements-completed: [ADPT-03, EXEC-04]

# Metrics
duration: 3min
completed: 2026-02-17
---

# Phase 2 Plan 1: Adapter Foundation Summary

**BaseAdapter ABC with unified message types, adapter registry with lazy import, cost estimation for 4 models, and extras security validation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-18T01:41:34Z
- **Completed:** 2026-02-18T01:44:59Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- BaseAdapter ABC enforces send_turn() contract -- direct instantiation raises TypeError, conforming subclasses work
- Adapter registry resolves builtin names ("openai", "anthropic") with helpful ImportError messages including pip install hints
- Registry supports custom adapters via dotted-path import with issubclass validation
- Cost estimation returns correct USD for gpt-4o, gpt-4o-mini, claude-sonnet-4-5, claude-haiku-4-5 (with dated aliases)
- Extras validation blocks 9 secret-like key patterns, enforces 10 key max and 4096 byte size limit

## Task Commits

Each task was committed atomically (TDD: test then feat):

1. **Task 1: BaseAdapter ABC, message types, and adapter registry**
   - `591d087` (test) - Failing tests for BaseAdapter ABC and registry
   - `f237b49` (feat) - Implementation: BaseAdapter, dataclasses, registry
2. **Task 2: Cost estimation and extras validation**
   - `1a8c023` (test) - Failing tests for cost and extras
   - `07857a7` (feat) - Implementation: estimate_cost, validate_extras

## Files Created/Modified
- `src/salvo/adapters/base.py` - BaseAdapter ABC, ToolCallResult, TokenUsage, AdapterTurnResult, Message, AdapterConfig dataclasses
- `src/salvo/adapters/registry.py` - get_adapter() with BUILTIN_ADAPTERS dict and importlib dynamic loading
- `src/salvo/adapters/__init__.py` - Re-exports all public types and get_adapter
- `src/salvo/execution/cost.py` - ModelPricing dataclass, PRICING_TABLE, MODEL_ALIASES, estimate_cost()
- `src/salvo/execution/extras.py` - BLOCKED_KEYS frozenset, validate_extras() with size/count limits
- `src/salvo/execution/__init__.py` - Re-exports estimate_cost and validate_extras
- `tests/test_adapters_base.py` - 14 tests for ABC and dataclass behavior
- `tests/test_adapters_registry.py` - 6 tests for registry resolution and error handling
- `tests/test_execution_cost.py` - 9 tests for cost estimation across models
- `tests/test_execution_extras.py` - 16 tests for extras validation and security

## Decisions Made
- Used plain dataclasses instead of Pydantic for adapter types to avoid overhead in the hot path (adapter calls run many times per scenario)
- Lazy imports via importlib for builtin adapters so the OpenAI/Anthropic SDKs are not required until first use
- frozenset for blocked keys provides immutable O(1) membership testing
- Model aliases dict maps dated Claude versions to base model pricing rather than duplicating entries
- Round cost to 6 decimal places to avoid floating-point noise in comparisons

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- BaseAdapter ABC and message types ready for concrete OpenAI/Anthropic adapter implementations (02-02, 02-03)
- Registry ready for scenario runner to resolve adapter by name from YAML config
- Cost estimation ready for RunMetadata.cost_usd population
- Extras validation ready for AdapterConfig.extras sanitization before provider calls
- All 130 tests pass (85 existing + 45 new)

## Self-Check: PASSED

All 11 created files verified on disk. All 4 commit hashes verified in git log.

---
*Phase: 02-adapter-layer-and-single-run-execution*
*Completed: 2026-02-17*
