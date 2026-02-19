# Roadmap: Salvo

## Overview

Salvo is a CLI testing framework for multi-step AI agents. The roadmap delivers it in six phases: first, the data models and scenario loading (so users can write and validate YAML); then a working adapter layer (so scenarios can run against real models); then the assertion engine (so runs produce scored results); then the N-trial runner and CLI (so users get reliability metrics from the terminal); then LLM judge evaluation (so users can define rubric-based assertions); and finally record/replay (so users can debug deterministically without API calls). Each phase produces a testable, standalone increment.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation and Scenario Loading** - Data models, YAML parsing, validation, project scaffolding, and storage layer (completed 2026-02-17)
- [ ] **Phase 2: Adapter Layer and Single-Run Execution** - Provider adapters (OpenAI, Anthropic, custom) and single-scenario execution
- [x] **Phase 3: Assertion Engine and Scoring** - All evaluator types, weighted scoring, tool call validation, and JMESPath queries (completed 2026-02-18)
- [ ] **Phase 4: N-Trial Runner and CLI** - Run N times with isolation/concurrency, Rich CLI output, reporting, and CI exit codes
- [ ] **Phase 5: LLM Judge Evaluation** - Rubric-based LLM judge assertions with k-voting
- [ ] **Phase 6: Record and Replay** - Trace recording, deterministic replay, and re-evaluation with updated assertions

## Phase Details

### Phase 1: Foundation and Scenario Loading
**Goal**: Users can write YAML test scenarios and Salvo validates them with clear error messages
**Depends on**: Nothing (first phase)
**Requirements**: SCEN-01, SCEN-02, SCEN-03, CLI-01, CLI-05
**Success Criteria** (what must be TRUE):
  1. User can run `salvo init` and get a working project with an example scenario file
  2. User can write a YAML scenario specifying adapter, model, tools, assertions, and threshold, and Salvo parses it into validated internal models
  3. User gets specific, helpful error messages when YAML is invalid (wrong types, missing fields, unknown keys)
  4. Run data can be written to and read from `.salvo/` directory as JSON files
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md -- Project setup and Pydantic data models (Scenario, RunResult, ProjectConfig)
- [ ] 01-02-PLAN.md -- YAML parsing pipeline, validation, rich error formatting, `salvo validate` command
- [ ] 01-03-PLAN.md -- `salvo init` scaffolding with templates and `.salvo/` JSON storage layer

### Phase 2: Adapter Layer and Single-Run Execution
**Goal**: Users can execute a scenario once against a real LLM and get back a structured trace with cost and latency metadata
**Depends on**: Phase 1
**Requirements**: ADPT-01, ADPT-02, ADPT-03, EXEC-04
**Success Criteria** (what must be TRUE):
  1. User can run a scenario against OpenAI models (gpt-4o, gpt-4o-mini) and get a complete trace
  2. User can run a scenario against Anthropic models (claude-sonnet-4-5, claude-haiku-4-5) and get a complete trace
  3. User can create a custom adapter by subclassing BaseAdapter and use it in a scenario
  4. Each run produces reproducibility metadata (model, provider, timestamp, cost, latency, scenario version hash)
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md -- BaseAdapter ABC, unified message types, adapter registry, cost estimation, extras validation (TDD)
- [ ] 02-02-PLAN.md -- Scenario model extensions (max_turns, temperature, seed, extras), OpenAI and Anthropic adapter implementations
- [ ] 02-03-PLAN.md -- ScenarioRunner execution loop, trace models, redaction, `salvo run` CLI command

### Phase 3: Assertion Engine and Scoring
**Goal**: Users get detailed, per-assertion scored results after a run, with weighted scoring and threshold-based pass/fail
**Depends on**: Phase 2
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06, EVAL-07
**Success Criteria** (what must be TRUE):
  1. User can query structured output with JMESPath expressions and eight comparison operators (eq, ne, gt, gte, lt, lte, contains, regex)
  2. User can validate tool call sequences using three matching modes (EXACT, IN_ORDER, ANY_ORDER)
  3. User can set cost and latency limits that fail the run when exceeded
  4. User sees per-assertion results (not just aggregate), with weighted scores computed as sum(score * weight) / sum(weight), and the run passes when score >= threshold
  5. Required assertions cause hard failure regardless of overall score
**Plans**: 2 plans

Plans:
- [ ] 03-01-PLAN.md -- Assertion normalizer, evaluator infrastructure (BaseEvaluator, registry), JMESPath/tool-sequence/cost/latency evaluators, weighted scorer (TDD)
- [ ] 03-02-PLAN.md -- Assertion model update, YAML pipeline normalization, evaluate_trace integration into `salvo run`, per-assertion output formatting

### Phase 4: N-Trial Runner and CLI
**Goal**: Users run `salvo run` from the terminal, execute scenarios N times with reliability scoring, and see rich failure breakdowns
**Depends on**: Phase 3
**Requirements**: EXEC-01, EXEC-02, EXEC-03, CLI-02, CLI-03, CLI-06, EVAL-08
**Success Criteria** (what must be TRUE):
  1. User can run a scenario N times and see aggregated pass rate, cost totals, and latency percentiles in the terminal
  2. Each trial runs with isolated state -- no cross-trial contamination of files or environment
  3. Trials can run concurrently for faster execution (configurable parallelism)
  4. `salvo report` shows historical run summaries with failure filtering
  5. Failure breakdowns show which assertions fail most often across trials, and CLI exits with non-zero code on failure (for CI/CD)
**Plans**: 3 plans

Plans:
- [ ] 04-01-PLAN.md -- TrialRunner engine, trial data models, retry logic, aggregate metrics, cross-trial failure ranking (TDD)
- [ ] 04-02-PLAN.md -- Rich CLI output (verdict table, progress bar, detail sections), refactored run command with N-trial integration, suite persistence, exit codes
- [ ] 04-03-PLAN.md -- `salvo report` command with latest run detail, history trend view, and failure filtering

### Phase 5: LLM Judge Evaluation
**Goal**: Users can define rubric-based LLM judge assertions that produce reliable verdicts through majority voting
**Depends on**: Phase 4
**Requirements**: JUDG-01, JUDG-02
**Success Criteria** (what must be TRUE):
  1. User can define a rubric-based LLM judge assertion in their scenario YAML and it evaluates the agent's output against that rubric
  2. LLM judge runs k times (default 3) with majority-vote pass/fail, and the individual verdicts are visible in output
**Plans**: 2 plans

Plans:
- [ ] 05-01-PLAN.md -- Judge config models, prompt builder, context builder, structured extraction, k-vote aggregation, JudgeEvaluator with registry integration (TDD)
- [ ] 05-02-PLAN.md -- Async evaluation pipeline, trial runner integration, judge cost tracking, CLI output with judge model/k/cost breakdown and per-criterion details

### Phase 6: Record and Replay
**Goal**: Users can record agent traces and replay them deterministically without spending money on API calls
**Depends on**: Phase 4
**Requirements**: RECD-01, RECD-02, RECD-03, CLI-04
**Success Criteria** (what must be TRUE):
  1. User can record full agent traces (with sensitive data redacted) during runs, stored as JSON
  2. User can run `salvo replay` on a recorded run and see results without any API calls being made
  3. User can re-evaluate a recorded run with updated assertions and see new scores against the same trace
**Plans**: TBD

Plans:
- [ ] 06-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6
Note: Phases 5 and 6 depend on Phase 4 but not on each other.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation and Scenario Loading | 3/3 | Complete    | 2026-02-17 |
| 2. Adapter Layer and Single-Run Execution | 3/3 | Complete    | 2026-02-17 |
| 3. Assertion Engine and Scoring | 0/2 | Complete    | 2026-02-18 |
| 4. N-Trial Runner and CLI | 0/3 | Not started | - |
| 5. LLM Judge Evaluation | 0/2 | Not started | - |
| 6. Record and Replay | 0/? | Not started | - |
