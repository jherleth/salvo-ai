---
phase: 02-adapter-layer-and-single-run-execution
plan: 02
subsystem: adapters
tags: [openai, anthropic, async-client, message-conversion, tool-calls, mock-testing]

# Dependency graph
requires:
  - phase: 02-adapter-layer-and-single-run-execution
    provides: "BaseAdapter ABC, unified Message/AdapterTurnResult types, adapter registry"
provides:
  - "OpenAIAdapter with chat completion format conversion, tool_call extraction, usage mapping"
  - "AnthropicAdapter with system-as-param, input_schema tools, tool_use extraction, usage computation"
  - "Extended Scenario model with max_turns, temperature, seed, extras fields"
  - "Optional SDK dependencies (openai, anthropic) in pyproject.toml"
affects: [02-03, 03-assertion-engine, 04-n-trial-runner-and-cli]

# Tech tracking
tech-stack:
  added: [openai-sdk, anthropic-sdk, pytest-asyncio]
  patterns: [lazy-client-init, mock-async-client, provider-format-normalization]

key-files:
  created:
    - src/salvo/adapters/openai_adapter.py
    - src/salvo/adapters/anthropic_adapter.py
    - tests/test_adapters_openai.py
    - tests/test_adapters_anthropic.py
  modified:
    - src/salvo/models/scenario.py
    - src/salvo/adapters/__init__.py
    - pyproject.toml
    - tests/test_models_scenario.py
    - tests/test_adapters_registry.py

key-decisions:
  - "Lazy-initialized AsyncOpenAI/AsyncAnthropic clients -- SDK not loaded until first send_turn()"
  - "OpenAI tool_call arguments parsed via json.loads; Anthropic tool_use input already a dict"
  - "Anthropic max_tokens defaults to 4096 when config.max_tokens is None (required param)"

patterns-established:
  - "Mock SDK response objects with MagicMock matching real response structure"
  - "AsyncMock for async client methods enabling zero-network test execution"
  - "Provider extras passed through via kwargs.update(config.extras)"

requirements-completed: [ADPT-01, ADPT-02]

# Metrics
duration: 4min
completed: 2026-02-17
---

# Phase 2 Plan 2: Scenario Model Extensions and Provider Adapters Summary

**OpenAI and Anthropic adapters normalizing provider-specific message/tool formats into unified BaseAdapter interface, with extended Scenario model for execution parameters**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-18T01:48:22Z
- **Completed:** 2026-02-18T01:53:12Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Extended Scenario model with max_turns (default 10, validated 1-100), temperature, seed, and extras fields
- OpenAI adapter converts unified messages to chat completion format, extracts tool_calls via json.loads, maps prompt/completion tokens to unified usage
- Anthropic adapter extracts system as separate param, uses input_schema (not parameters), wraps tool_result in user role, computes total from input+output tokens
- Both adapters lazy-init async clients reading API keys from env, pass extras through to API calls
- Optional SDK dependencies declared in pyproject.toml with openai, anthropic, and all extras groups
- 176 total tests pass (46 new in this plan)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Scenario model and add optional SDK dependencies** - `893393c` (feat)
2. **Task 2: OpenAI and Anthropic adapter implementations** - `8561ca6` (feat)
3. **Deviation fix: Registry tests updated for installed SDKs** - `3630a7b` (fix)

## Files Created/Modified
- `src/salvo/adapters/openai_adapter.py` - OpenAIAdapter with message/tool conversion, tool_call extraction, usage mapping
- `src/salvo/adapters/anthropic_adapter.py` - AnthropicAdapter with system extraction, input_schema tools, tool_use parsing
- `src/salvo/adapters/__init__.py` - Updated with try/except re-exports for optional adapter classes
- `src/salvo/models/scenario.py` - Added max_turns, temperature, seed, extras fields to Scenario
- `pyproject.toml` - Added openai, anthropic, all optional dependency groups and pytest-asyncio
- `tests/test_adapters_openai.py` - 14 tests with mocked AsyncOpenAI client
- `tests/test_adapters_anthropic.py` - 18 tests with mocked AsyncAnthropic client
- `tests/test_models_scenario.py` - 12 new tests for Phase 2 Scenario fields
- `tests/test_adapters_registry.py` - Updated to mock missing SDKs and added positive resolution tests

## Decisions Made
- Lazy-initialized async clients so the SDK modules are not imported until the adapter is actually used in a send_turn() call
- OpenAI tool_call arguments are JSON strings that need json.loads; Anthropic tool_use input is already a Python dict -- handled differently in each adapter
- Anthropic max_tokens defaults to 4096 when config.max_tokens is None, since it is a required parameter for the Anthropic API
- Provider-specific extras are passed through via kwargs.update() so users can set top_p, presence_penalty, top_k, etc.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Registry tests assumed SDKs not installed**
- **Found during:** Post-Task 2 full test suite verification
- **Issue:** Two registry tests expected get_adapter('openai') and get_adapter('anthropic') to raise ImportError, but now that SDKs are installed as optional deps, the imports succeed
- **Fix:** Updated tests to mock importlib.import_module for the error path, added positive tests verifying adapters resolve correctly with SDKs installed
- **Files modified:** tests/test_adapters_registry.py
- **Verification:** All 8 registry tests pass
- **Committed in:** `3630a7b`

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential fix for test correctness after SDK installation. No scope creep.

## Issues Encountered

None.

## User Setup Required

None for unit tests (all use mocked clients). For integration testing, users will need:
- `OPENAI_API_KEY` from https://platform.openai.com/api-keys
- `ANTHROPIC_API_KEY` from https://console.anthropic.com/settings/keys

## Next Phase Readiness
- Both concrete adapters ready for use in the scenario execution runner (02-03)
- Registry resolves "openai" and "anthropic" to working adapter instances
- Scenario model carries all execution parameters needed by the runner (max_turns, temperature, seed, extras)
- All 176 tests pass

## Self-Check: PASSED

All 9 created/modified files verified on disk. All 3 commit hashes verified in git log.

---
*Phase: 02-adapter-layer-and-single-run-execution*
*Completed: 2026-02-17*
