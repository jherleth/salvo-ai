# Requirements: Salvo

**Defined:** 2026-02-17
**Core Value:** When you change your agent, Salvo tells you whether it still works -- across the full multi-step trajectory.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Scenario Definition

- [x] **SCEN-01**: User can define test scenarios in YAML (adapter, model, tools, assertions, threshold)
- [x] **SCEN-02**: Scenario YAML is validated against schema with helpful error messages on invalid input
- [x] **SCEN-03**: User can specify system prompt and user message per scenario

### Execution

- [x] **EXEC-01**: User can run a scenario N times and see aggregated reliability metrics
- [x] **EXEC-02**: Each trial runs with isolated state (no cross-trial contamination)
- [x] **EXEC-03**: Trials can run concurrently for faster execution
- [x] **EXEC-04**: Each run logs reproducibility metadata (model, provider, timestamp, seed, cost, latency, scenario version hash)

### Provider Adapters

- [x] **ADPT-01**: User can run scenarios against OpenAI models (gpt-4o, gpt-4o-mini)
- [x] **ADPT-02**: User can run scenarios against Anthropic models (claude-sonnet-4-5, claude-haiku-4-5)
- [x] **ADPT-03**: User can create custom adapters by subclassing BaseAdapter

### Assertion & Scoring

- [x] **EVAL-01**: User can query structured output with JMESPath expressions (eq, ne, gt, gte, lt, lte, contains, regex)
- [x] **EVAL-02**: User can validate tool call sequences with three modes (EXACT, IN_ORDER, ANY_ORDER)
- [x] **EVAL-03**: User can set cost limits per run (pass if cost <= max_usd)
- [x] **EVAL-04**: User can set latency limits per run (pass if runtime <= max_seconds)
- [x] **EVAL-05**: User can mark assertions as required (hard fail if any required assertion fails)
- [x] **EVAL-06**: Weighted score is computed as sum(score * weight) / sum(weight), scenario passes when score >= threshold
- [x] **EVAL-07**: Output shows per-assertion results, not just aggregate scores
- [x] **EVAL-08**: Output aggregates failure counts per assertion across trials so users can see which assertions fail most often

### LLM Judge

- [x] **JUDG-01**: User can define rubric-based LLM judge assertions
- [x] **JUDG-02**: LLM judge runs k times (default 3) with majority-vote pass/fail

### Record/Replay

- [x] **RECD-01**: User can record full agent traces (redacted) during runs
- [x] **RECD-02**: User can replay recorded runs without making API calls
- [x] **RECD-03**: User can re-evaluate recorded runs with updated assertions

### CLI & Storage

- [x] **CLI-01**: `salvo init` scaffolds a new project with example scenario
- [x] **CLI-02**: `salvo run` executes scenarios with rich terminal output (tables, colors, pass rates)
- [x] **CLI-03**: `salvo report` shows historical run summaries with failure filtering
- [x] **CLI-04**: `salvo replay` replays a recorded run with optional re-evaluation
- [x] **CLI-05**: All run data stored as JSON files in `.salvo/` directory
- [x] **CLI-06**: CLI exits with non-zero code on failure for CI/CD integration

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Extended Providers

- **ADPT-04**: LiteLLM-based universal provider support (100+ models via one interface)

### Scenario Composition

- **SCEN-04**: Scenario inheritance and shared configs to reduce YAML duplication

### Model Comparison

- **COMP-01**: Compare pass-rate deltas between two models on identical scenarios
- **COMP-02**: Show largest failing assertion differences between models

### Seed Reproducibility

- **EXEC-05**: Seed parameter passed to providers for reproducibility hints

### Dashboard

- **DASH-01**: Streamlit web UI with reliability over time, failure breakdowns, model comparison, run explorer

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web dashboard | CLI-first. Dev tools should be terminal-native. Defer to v2. |
| Hallucination detectors | Not core to trajectory validation |
| Plugin marketplace | Premature for v1 |
| Chain-of-thought storage | Privacy risk. Only safe trace events. |
| Real-time streaming output | Batch results sufficient for v1 |
| Framework integrations (LangChain, CrewAI) | Couples to specific agent frameworks. Salvo is framework-agnostic. |
| Production monitoring/observability | Different product category (Braintrust/LangSmith territory) |
| Synthetic dataset generation | Out of scope -- user provides scenarios |
| Containerized execution sandbox | User's responsibility to sandbox their agents |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCEN-01 | Phase 1 | Complete |
| SCEN-02 | Phase 1, Phase 8 | Pending |
| SCEN-03 | Phase 1 | Complete |
| EXEC-01 | Phase 4 | Complete |
| EXEC-02 | Phase 4 | Complete |
| EXEC-03 | Phase 4 | Complete |
| EXEC-04 | Phase 2 | Complete |
| ADPT-01 | Phase 2 | Complete |
| ADPT-02 | Phase 2 | Complete |
| ADPT-03 | Phase 2 | Complete |
| EVAL-01 | Phase 3, Phase 8 | Pending |
| EVAL-02 | Phase 3 | Complete |
| EVAL-03 | Phase 3 | Complete |
| EVAL-04 | Phase 3 | Complete |
| EVAL-05 | Phase 3 | Complete |
| EVAL-06 | Phase 3 | Complete |
| EVAL-07 | Phase 3 | Complete |
| EVAL-08 | Phase 4 | Complete |
| JUDG-01 | Phase 5, Phase 7, Phase 8 | Complete |
| JUDG-02 | Phase 5, Phase 8 | Pending |
| RECD-01 | Phase 6, Phase 7 | Complete |
| RECD-02 | Phase 6, Phase 7 | Complete |
| RECD-03 | Phase 6, Phase 7 | Complete |
| CLI-01 | Phase 1 | Complete |
| CLI-02 | Phase 4 | Complete |
| CLI-03 | Phase 4 | Complete |
| CLI-04 | Phase 6, Phase 7 | Complete |
| CLI-05 | Phase 1, Phase 8 | Pending |
| CLI-06 | Phase 4 | Complete |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 29
- Unmapped: 0
- Pending (gap closure): 9

---
*Requirements defined: 2026-02-17*
*Last updated: 2026-02-19 after gap closure phase creation*
