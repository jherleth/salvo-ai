---
phase: 02-adapter-layer-and-single-run-execution
verified: 2026-02-17T02:10:00Z
status: passed
score: 15/15 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Run salvo run scenario.yaml against a real LLM"
    expected: "Rich summary printed with turn count, cost, latency, hash; .salvo/runs/ and .salvo/traces/ populated"
    why_human: "All tests use mocked adapters; real API call requires OPENAI_API_KEY or ANTHROPIC_API_KEY and cannot be verified statically"
---

# Phase 2: Adapter Layer and Single-Run Execution Verification Report

**Phase Goal:** Users can execute a scenario once against a real LLM and get back a structured trace with cost and latency metadata
**Verified:** 2026-02-17T02:10:00Z
**Status:** passed
**Re-verification:** No -- initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A custom adapter subclassing BaseAdapter and implementing send_turn() can be instantiated | VERIFIED | `src/salvo/adapters/base.py`: `class BaseAdapter(ABC)` with `@abstractmethod async def send_turn()`; test `test_subclass_with_send_turn_instantiates` passes |
| 2 | A custom adapter missing send_turn() cannot be instantiated (TypeError) | VERIFIED | ABC enforcement confirmed; test `test_subclass_without_send_turn_raises` passes |
| 3 | get_adapter('openai') resolves to correct dotted path via lazy import | VERIFIED | `registry.py` BUILTIN_ADAPTERS maps "openai" -> "salvo.adapters.openai_adapter.OpenAIAdapter"; `importlib.import_module` used; all registry tests pass |
| 4 | get_adapter('my.module.MyAdapter') loads a custom adapter by dotted path | VERIFIED | `registry.py` rpartition + importlib.import_module path; `test_get_adapter_custom_dotted_path` passes |
| 5 | estimate_cost returns a float for known models and None for unknown models | VERIFIED | `execution/cost.py` PRICING_TABLE covers gpt-4o, gpt-4o-mini, claude-sonnet-4-5, claude-haiku-4-5 with MODEL_ALIASES; all 9 cost tests pass |
| 6 | Extras validation rejects dicts containing secret-like keys and oversized payloads | VERIFIED | `execution/extras.py` BLOCKED_KEYS frozenset with case-insensitive check, MAX_EXTRAS_KEYS=10, MAX_EXTRAS_SIZE=4096; all 16 extras tests pass |
| 7 | OpenAI adapter converts unified Messages to OpenAI chat format and back | VERIFIED | `openai_adapter.py` _convert_messages() handles system/user/assistant/tool_result; 14 tests pass |
| 8 | Anthropic adapter converts unified Messages to Anthropic format (system as param, input_schema) | VERIFIED | `anthropic_adapter.py` _extract_system() + _convert_tools() uses input_schema not parameters; 18 tests pass |
| 9 | Both adapters extract tool calls and report TokenUsage in AdapterTurnResult | VERIFIED | OpenAI uses json.loads on arguments; Anthropic uses block.input directly (already dict); usage mapped in both |
| 10 | Both adapters lazy-init async clients reading API keys from environment | VERIFIED | `_get_client()` pattern in both adapters; lazy_client_init tests pass |
| 11 | Scenario model accepts max_turns, temperature, seed, and extras fields | VERIFIED | `models/scenario.py`: max_turns=Field(default=10, ge=1, le=100), temperature/seed optional, extras dict |
| 12 | ScenarioRunner drives multi-turn loop, stops on final answer or max turns | VERIFIED | `execution/runner.py`: for-loop up to max_turns, breaks when result.tool_calls empty; 8 runner tests pass including parallel tool calls, usage accumulation, hash, cost |
| 13 | Runner fails immediately if model calls a tool with no mock_response | VERIFIED | `ToolMockNotFoundError` raised with tool_name and available_mocks attributes; test_runner_tool_mock_not_found passes |
| 14 | Run trace contains messages, tool_calls, usage, latency, cost, hash, provider metadata | VERIFIED | `execution/trace.py` RunTrace Pydantic model has all required fields; round-trip test passes |
| 15 | salvo run command loads scenario, resolves adapter, executes, prints summary, stores result + trace | VERIFIED | `cli/run_cmd.py` full pipeline: validate -> get_adapter -> validate_extras -> ScenarioRunner -> apply_trace_limits -> Rich output -> RunStore.save_run + save_trace; all 7 CLI tests pass |

**Score:** 15/15 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/salvo/adapters/base.py` | BaseAdapter ABC, Message, AdapterTurnResult, TokenUsage, ToolCallResult, AdapterConfig | VERIFIED | 114 lines; all 6 dataclasses and ABC present; `class BaseAdapter(ABC)` at line 80 |
| `src/salvo/adapters/registry.py` | get_adapter() with builtin name lookup and dotted-path import | VERIFIED | 98 lines; BUILTIN_ADAPTERS dict + importlib.import_module + issubclass check present |
| `src/salvo/execution/cost.py` | estimate_cost() with static pricing table | VERIFIED | 70 lines; ModelPricing dataclass, PRICING_TABLE, MODEL_ALIASES, estimate_cost() all present |
| `src/salvo/execution/extras.py` | validate_extras() with blocklist and size limits | VERIFIED | 75 lines; BLOCKED_KEYS frozenset, MAX_EXTRAS_KEYS=10, MAX_EXTRAS_SIZE=4096, validate_extras() present |
| `src/salvo/adapters/openai_adapter.py` | OpenAIAdapter with message/tool format conversion and usage extraction | VERIFIED | 182 lines; `class OpenAIAdapter(BaseAdapter)`, send_turn(), _convert_messages(), _convert_tools() all present |
| `src/salvo/adapters/anthropic_adapter.py` | AnthropicAdapter with system-as-param, input_schema tools, usage computation | VERIFIED | 216 lines; `class AnthropicAdapter(BaseAdapter)`, _extract_system(), input_schema in _convert_tools() present |
| `src/salvo/models/scenario.py` | Extended Scenario with max_turns, temperature, seed, extras | VERIFIED | max_turns=Field(default=10, ge=1, le=100), temperature/seed/extras all present at lines 70-73 |
| `pyproject.toml` | Optional dependencies for openai and anthropic SDKs | VERIFIED | Contains "openai" and "anthropic" optional dependency groups |
| `src/salvo/execution/runner.py` | ScenarioRunner with async run() multi-turn loop | VERIFIED | 223 lines; `class ScenarioRunner`, `ToolMockNotFoundError`, async run() with full multi-turn logic |
| `src/salvo/execution/trace.py` | RunTrace and TraceMessage Pydantic models | VERIFIED | 53 lines; TraceMessage and RunTrace BaseModel classes with all required fields |
| `src/salvo/execution/redaction.py` | redact_content(), truncate_content(), apply_trace_limits() | VERIFIED | 127 lines; all three functions implemented with compiled regex patterns |
| `src/salvo/cli/run_cmd.py` | salvo run CLI command end-to-end | VERIFIED | 171 lines; `def run()`, `async _run_async()` with full pipeline wiring |
| `src/salvo/storage/json_store.py` | RunStore with save_trace() and load_trace() | VERIFIED | save_trace() at line 127, load_trace() at line 144, atomic writes to .salvo/traces/ |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `adapters/registry.py` | `adapters/base.py` | issubclass check against BaseAdapter | WIRED | `issubclass(cls, BaseAdapter)` at line 91 |
| `adapters/registry.py` | importlib | dynamic module import | WIRED | `importlib.import_module(module_path)` at line 72 |
| `adapters/openai_adapter.py` | `adapters/base.py` | subclass of BaseAdapter | WIRED | `class OpenAIAdapter(BaseAdapter)` at line 22 |
| `adapters/anthropic_adapter.py` | `adapters/base.py` | subclass of BaseAdapter | WIRED | `class AnthropicAdapter(BaseAdapter)` at line 21 |
| `adapters/openai_adapter.py` | `openai.AsyncOpenAI` | lazy-initialized async client | WIRED | `from openai import AsyncOpenAI` in `_get_client()` at line 35 |
| `adapters/anthropic_adapter.py` | `anthropic.AsyncAnthropic` | lazy-initialized async client | WIRED | `from anthropic import AsyncAnthropic` in `_get_client()` at line 34 |
| `execution/runner.py` | `adapters/base.py` | calls adapter.send_turn() in loop | WIRED | `result = await self.adapter.send_turn(messages, tool_defs, config)` at line 126 |
| `execution/runner.py` | `execution/cost.py` | estimate_cost() on accumulated usage | WIRED | `cost_usd = estimate_cost(model=config.model, ...)` at line 192 |
| `cli/run_cmd.py` | `execution/extras.py` | validate_extras() before building config | WIRED | `validate_extras(scenario.extras)` at line 67 |
| `cli/run_cmd.py` | `execution/runner.py` | ScenarioRunner.run() call | WIRED | `runner = ScenarioRunner(adapter)` + `trace = await runner.run(scenario, config)` at lines 83-84 |
| `cli/run_cmd.py` | `storage/json_store.py` | save_run() and save_trace() persistence | WIRED | `store.save_run(run_result)` at line 144, `store.save_trace(run_id, trace)` at line 145 |
| `cli/run_cmd.py` | `adapters/registry.py` | get_adapter() for adapter resolution | WIRED | `adapter = get_adapter(scenario.adapter)` at line 57 |
| `cli/main.py` | `cli/run_cmd.py` | run command registered in Typer app | WIRED | `from salvo.cli.run_cmd import run` + `app.command()(run)` at lines 8, 18 |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| ADPT-01 | 02-02-PLAN.md | User can run scenarios against OpenAI models | SATISFIED | `openai_adapter.py` implements BaseAdapter; supports gpt-4o and gpt-4o-mini via PRICING_TABLE |
| ADPT-02 | 02-02-PLAN.md | User can run scenarios against Anthropic models | SATISFIED | `anthropic_adapter.py` implements BaseAdapter; supports claude-sonnet-4-5 and claude-haiku-4-5 |
| ADPT-03 | 02-01-PLAN.md | User can create custom adapters by subclassing BaseAdapter | SATISFIED | BaseAdapter ABC defined; registry supports dotted-path custom adapter loading with issubclass validation |
| EXEC-04 | 02-01-PLAN.md, 02-03-PLAN.md | Each run logs reproducibility metadata (model, provider, timestamp, seed, cost, latency, scenario version hash) | SATISFIED | RunTrace contains all required fields: model, provider, timestamp, cost_usd, latency_seconds, scenario_hash; RunMetadata in RunResult also includes salvo_version, adapter, seed |

All 4 requirement IDs (ADPT-01, ADPT-02, ADPT-03, EXEC-04) are fully satisfied by Phase 2 implementation.

No orphaned requirements detected: REQUIREMENTS.md Phase 2 column maps exactly these 4 IDs.

---

### Anti-Patterns Found

No blockers or warnings found.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `adapters/__init__.py` | 33-34, 40-41 | `pass` in except blocks | Info | Correct pattern for optional SDK imports; not a stub |
| `storage/json_store.py` | 106, 168 | `return []` / `return {}` | Info | Correct empty-collection returns for missing data (no runs dir, no index file); not a stub |
| `execution/redaction.py` | 29 | `REDACTED_PLACEHOLDER = "[REDACTED]"` | Info | Literal placeholder string for redaction output; not an implementation stub |

---

### Human Verification Required

#### 1. End-to-End Real LLM Execution

**Test:** Set OPENAI_API_KEY environment variable, create a minimal scenario YAML (adapter: openai, model: gpt-4o-mini, prompt: "Say hello"), run `salvo run scenario.yaml`
**Expected:** Rich summary printed to stdout with model name, turn count (1), cost (~$0.000X estimated), latency in seconds, hash (first 12 chars); .salvo/runs/ and .salvo/traces/ directories created with JSON files
**Why human:** All tests use mocked adapters; real HTTP call to OpenAI API cannot be verified statically

#### 2. Bearer Token Redaction in Practice

**Test:** Run a scenario where mock tool responses contain a Bearer token string; inspect the saved trace file in .salvo/traces/
**Expected:** Bearer token value replaced with [REDACTED] in stored trace
**Why human:** Redaction tests pass with mock content, but verifying the full pipeline (runner -> apply_trace_limits -> save_trace) with realistic content requires execution

---

### Test Suite Results

```
Phase 2 tests:  104 passed in 0.20s (all Phase 2 test files)
Full suite:     201 passed in 0.27s (no regressions in Phase 1 tests)
```

Test files verified:
- `tests/test_adapters_base.py` -- 14 tests
- `tests/test_adapters_registry.py` -- 8 tests (updated for installed SDKs)
- `tests/test_execution_cost.py` -- 9 tests
- `tests/test_execution_extras.py` -- 16 tests
- `tests/test_adapters_openai.py` -- 14 tests
- `tests/test_adapters_anthropic.py` -- 18 tests
- `tests/test_execution_trace.py` -- 3 tests
- `tests/test_execution_redaction.py` -- 7 tests
- `tests/test_execution_runner.py` -- 8 tests
- `tests/test_cli_run.py` -- 7 tests

---

### Summary

Phase 2 goal is achieved. All 15 observable truths verified against actual code (not SUMMARY claims). All 13 required artifacts exist, are substantive, and are wired into the execution pipeline. All 6 key links from plan frontmatter confirmed with pattern matching in the actual source. All 4 requirement IDs (ADPT-01, ADPT-02, ADPT-03, EXEC-04) are satisfied by concrete implementation.

The full execution path from `salvo run scenario.yaml` to stored trace is wired: `cli/run_cmd.py` calls `validate_scenario_file -> get_adapter -> validate_extras -> ScenarioRunner.run -> apply_trace_limits -> RunStore.save_run + save_trace`. Each link in this chain exists and is connected.

The only caveat is that all tests use mocked adapters -- real LLM execution against the OpenAI or Anthropic APIs requires human verification with actual API keys.

---

_Verified: 2026-02-17T02:10:00Z_
_Verifier: Claude (gsd-verifier)_
