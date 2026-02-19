# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** When you change your agent, Salvo tells you whether it still works -- across the full multi-step trajectory.
**Current focus:** Phase 5 In Progress -- LLM Judge Evaluation

## Current Position

Phase: 5 of 6 (LLM Judge Evaluation)
Plan: 1 of 2 in current phase (05-01 complete)
Status: Phase 5 In Progress
Last activity: 2026-02-19 -- Completed 05-01-PLAN.md

Progress: [###########-] 86%

## Performance Metrics

**Velocity:**
- Total plans completed: 12
- Average duration: 4.3min
- Total execution time: 0.85 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation-and-scenario-loading | 3/3 | 13min | 4.3min |
| 02-adapter-layer-and-single-run-execution | 3/3 | 11min | 3.7min |
| 03-assertion-engine-and-scoring | 2/2 | 10min | 5.0min |
| 04-n-trial-runner-and-cli | 3/3 | 13min | 4.3min |
| 05-llm-judge-evaluation | 1/2 | 5min | 5.0min |

**Recent Trend:**
- Last 5 plans: 04-01 (5min), 04-02 (6min), 04-03 (2min), 05-01 (5min)
- Trend: stable

*Updated after each plan completion*
| Phase 04 P01 | 5min | 2 tasks | 8 files |
| Phase 04 P02 | 6min | 2 tasks | 6 files |
| Phase 04 P03 | 2min | 1 tasks | 3 files |
| Phase 05 P01 | 5min | 2 tasks | 14 files |

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
- [03-01]: EVALUATOR_REGISTRY dict pattern for O(1) type-string to evaluator-class dispatch
- [03-01]: Canonical assertion form {type, expression, operator, value, weight, required} enables uniform processing
- [03-01]: build_trace_data creates flat dict with response/turns/tool_calls/metadata keys for JMESPath querying
- [03-01]: Tool sequence match functions return tuple[bool, str] with divergence-pinpointing failure messages
- [03-01]: compute_score uses sum(score*weight)/sum(weight) with zero-weight guard and hard-fail override
- [03-02]: normalize_assertions inserted before Pydantic validation in validate_scenario to convert operator-key shorthand
- [03-02]: max_usd and max_seconds added to Assertion model for cost_limit/latency_limit types
- [03-02]: format_eval_results returns plain text -- Rich markup applied only in CLI layer
- [03-02]: model_dump(exclude_none=True) converts Assertion objects to clean dicts for evaluators
- [03-02]: Exit code 1 on evaluation failure for CI pipeline compatibility
- [04-01]: Hand-rolled retry (~20 lines) instead of tenacity dependency for transient error handling
- [04-01]: adapter_factory callable (not shared instance) ensures fresh adapter per trial for state isolation
- [04-01]: uuid7() for run_id since Python 3.14 provides it natively (monotonically sortable)
- [04-01]: statistics.quantiles(n=100) for percentiles with guard for single-trial edge case
- [04-01]: aggregate_failures ranks by frequency * avg_weight_lost for balanced impact ranking
- [04-02]: Verdict styling via _VERDICT_STYLES dict mapping verdict value to (symbol, Rich style) tuples
- [04-02]: create_trial_progress returns None for non-TTY -- caller handles skip, not the progress bar
- [04-02]: render_details filters infra_error trials from score breakdown for accurate distribution display
- [04-02]: adapter_factory closure in run_cmd calls get_adapter per trial for fresh adapter instances
- [04-02]: Latest symlink uses atomic os.symlink+os.replace with .latest text file fallback for Windows
- [04-02]: Updated test_cli_run.py to use side_effect factory pattern (not return_value) for N-trial compatibility
- [04-03]: Report command imports Rich directly -- independent from output.py rendering module
- [04-03]: _find_project_root walks up from cwd (not scenario file) since report has no scenario argument
- [04-03]: History mode loads runs individually with skip-on-error for corrupted/incompatible entries
- [04-03]: Verdict styling duplicated from output.py to keep report_cmd and output.py as independent modules
- [05-01]: judge_model field name avoids Pydantic model_* namespace collision
- [05-01]: Judge subpackage (evaluation/judge/) isolates all judge modules from existing evaluators
- [05-01]: format_tool_choice detects provider via string contains for flexible naming
- [05-01]: Threshold field added to Assertion model for per-assertion judge threshold override

### Pending Todos

None yet.

### Blockers/Concerns

- Research flagged LiteLLM-vs-direct-adapters decision -- resolve during Phase 2 planning
- Research flagged judge-in-replay conflict -- resolve during Phase 5-6 planning
- Research flagged async execution model -- resolve during Phase 2 planning

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 05-01-PLAN.md
Resume file: .planning/phases/05-llm-judge-evaluation/05-02-PLAN.md
