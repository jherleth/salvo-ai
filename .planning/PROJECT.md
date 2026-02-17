# Salvo

## What This Is

Salvo is a CLI testing framework for multi-step AI agents. Solo AI builders define test scenarios in YAML, run them N times against any model, and get reliability scores — pass rates, cost, latency, and failure breakdowns. When runs fail, recorded traces enable deterministic replay and re-evaluation without spending money re-running the agent.

## Core Value

When you change your agent, Salvo tells you whether it still works — across the full multi-step trajectory, not just single prompt-response pairs.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Define agent test scenarios in YAML (model, tools, assertions, thresholds)
- [ ] Run scenarios N times and compute reliability metrics
- [ ] Validate tool call sequences (order, arguments, outputs)
- [ ] Score runs with weighted assertions (required flags, thresholds)
- [ ] Evaluate with JMESPath queries on structured output
- [ ] Enforce cost and latency limits per run
- [ ] LLM judge evaluation with k-voting
- [ ] Custom Python evaluator support
- [ ] Record full agent traces for replay
- [ ] Replay recorded runs without API calls
- [ ] Re-evaluate recorded runs with updated assertions
- [ ] Rich CLI output with pass rates, failure breakdowns, run details
- [ ] OpenAI adapter (gpt-4o, gpt-4o-mini)
- [ ] Anthropic adapter (claude-sonnet-4-5, claude-haiku-4-5)
- [ ] Custom adapter support (subclass BaseAdapter)
- [ ] Scaffold new projects with `salvo init`
- [ ] JSON file storage (.salvo/ directory)

### Out of Scope

- Web dashboard (Streamlit or otherwise) — CLI-first, add later if needed
- Model comparison CLI — ship run/report/replay first
- Hallucination detectors — not core to trajectory validation
- Plugin marketplace — premature for v1
- Chain-of-thought storage — only safe trace events, no private reasoning
- Real-time streaming output — batch results are sufficient for v1

## Context

- **Gap being filled:** Promptfoo is the closest existing tool but is designed for single prompt→response evaluation. Multi-step agents need trajectory-level validation — tool call sequences, argument checking, and deterministic replay. Nothing does this well today.
- **First test scenario:** A "fix failing tests" coding agent that reads files, edits code, runs tests, and iterates. Salvo must validate the full trajectory (must call file_read before file_write, must run tests, must not spam tools).
- **Target user:** Solo AI builders who ship agents and need to know if changes break behavior.
- **Success looks like:** The author uses Salvo on their own agents and it catches real regressions. Battle-tested, not demo-ware.

## Constraints

- **Distribution**: Must be pip-installable (`salvo-ai` on PyPI)
- **Dependencies**: Minimal — avoid heavy frameworks. Pydantic for models, Click/Typer for CLI, Rich for terminal output.
- **Storage**: JSON files in `.salvo/` directory for MVP. Human-readable, git-friendly, zero driver dependencies.
- **Python**: 3.10+ (match modern agent ecosystem)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| JSON over SQLite for storage | Human-readable, git-friendly, no driver deps. Migrate later if perf matters. | — Pending |
| CLI-first, no web dashboard | Dev tools should be terminal-native. Dashboard is polish, not core. | — Pending |
| JMESPath for output queries | Standard, well-supported, familiar to devs who use AWS/jq. | — Pending |
| Pydantic for all models | Type safety, serialization, validation in one library. Standard in Python AI ecosystem. | — Pending |
| Name: Salvo | Distinctive, memorable, fits "fire a burst of runs" metaphor. Available namespace. | — Pending |

---
*Last updated: 2026-02-17 after initialization*
