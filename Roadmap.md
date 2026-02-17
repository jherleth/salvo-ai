SALVO MVP SPECIFICATION
=======================

ONE-LINER
---------
Salvo — Pytest for multi-step AI agents.
Define scenarios in YAML, run them N times, compute reliability scores,
store artifacts, and reproduce failures via replay.


GOALS
-----
- Execute multi-step agent workflows with tool use.
- Produce repeatable metrics: pass rate, score, cost, latency, failures.
- Support record/replay for deterministic debugging.
- Enable model comparison on identical scenarios.


NON-GOALS (MVP)
---------------
- No hallucination detectors or simulators.
- No plugin marketplace.
- No web dashboard (CLI-first with rich terminal output).
- No chain-of-thought storage — only safe trace events.
- No model comparison CLI — ship run/report/replay first.


QUICK DEMO (30-SECOND PITCH)
-----------------------------
A user writes this YAML:

  scenario: book_flight
  adapter: openai
  model: gpt-4o
  runs: 10
  timeout: 30
  threshold: 0.8

  system_prompt: |
    You are a travel assistant with access to flight search
    and booking tools.

  user_message: |
    Book the cheapest round-trip flight from SFO to JFK
    on March 15, returning March 20.

  tools:
    - search_flights
    - book_flight
    - get_booking_confirmation

  assertions:
    - type: tool_sequence
      expected: [search_flights, book_flight, get_booking_confirmation]
      required: true
      weight: 2

    - type: jmespath
      path: final_output.confirmation_id
      operator: regex
      value: "^[A-Z]{6}$"
      weight: 1

    - type: cost_limit
      max_usd: 0.05
      weight: 1

    - type: latency_limit
      max_seconds: 15
      weight: 1

Then runs:

  $ salvo run scenarios/book_flight.yaml --runs 10 --record

  book_flight  10/10 runs  pass-rate: 80%  avg-score: 0.84
  ─────────────────────────────────────────────────────────
  tool_sequence      10/10 passed   (required)
  confirmation_id     8/10 passed
  cost_limit         10/10 passed   avg: $0.032
  latency_limit       9/10 passed   avg: 8.2s
  ─────────────────────────────────────────────────────────
  2 failures recorded. Replay with:
    salvo replay <run_id>


CORE CONTRACT (AgentRunResult)
------------------------------
Each run produces a single structured result containing:

Identity
- run_id
- scenario_id
- provider
- model
- timestamp
- seed (optional)

Execution Output
- final_output (any structured or text result)
- tool_calls (ordered list)
- trace (safe events only, no private reasoning)

Performance
- metrics: latency, tokens, cost, tool count

Evaluation
- eval_results (per assertion)
- weighted_score (0-1)
- passed (boolean)
- error (optional message)


SCENARIO YAML RULES
-------------------
A scenario defines:

- adapter + model to run
- system_prompt and user_message
- tools available to the agent
- number of runs
- timeout
- pass threshold
- structured assertions

Key design rules:
- JMESPath is the default query language.
- Assertions support:
  - required flag
  - weight
- Scenario passes when:
  weighted_score >= threshold


EVALUATOR TYPES (MVP)
---------------------
Each evaluator is a function:

evaluate(scenario, assertion, result) -> EvalResult

Supported evaluators:

1. jmespath
   - Queries structured output via JMESPath expressions
   - Operators: eq, ne, gt, gte, lt, lte, contains, regex

2. tool_sequence
   - Validates tool call order (exact or subset match)

3. cost_limit
   - Pass if cost <= max_usd

4. latency_limit
   - Pass if runtime <= max_seconds

5. llm_judge
   - Cheap model grades output against a rubric
   - Strict JSON output
   - k voting (default = 3)
   - Majority pass

6. custom
   - User-provided Python function
   - Signature: (scenario, assertion, result) -> EvalResult
   - Loaded via dotted path, e.g. "my_evals.check_format"


SCORING RULES (EXACT)
---------------------
Step 1:
Evaluate all assertions -> scores in [0,1].

Step 2:
If ANY required assertion fails:
- passed = false
- weighted_score = 0.0

Step 3:
Otherwise compute weighted score:

weighted_score =
sum(score * weight) / sum(weight)

Step 4:
Scenario passes if:

weighted_score >= threshold


RUNNER & ADAPTER INTERFACE
--------------------------
An adapter is a Python class implementing:

  class BaseAdapter:
      async def run(self, request: AdapterRequest) -> AdapterResponse:
          ...

AdapterRequest contains:
- model: str
- system_prompt: str
- user_message: str
- tools: list[ToolDefinition]
- timeout_seconds: int
- seed: int | None

AdapterResponse contains:
- final_output: Any
- tool_calls: list[ToolCall]
- trace: list[TraceEvent]
- metrics: RunMetrics (latency, tokens, cost, tool_count)

MVP adapters:
- OpenAI (gpt-4o, gpt-4o-mini)
- Anthropic (claude-sonnet-4-5, claude-haiku-4-5)
- Custom user adapter (subclass BaseAdapter)


RECORD / REPLAY (KEY FEATURE)
-----------------------------
Record mode stores:
- Redacted API requests/responses
- Full AgentRunResult
- Judge outputs

Security defaults:
- Strip secrets from headers/env
- Cap large blobs (configurable max size)
- Optional content hashing

Replay mode:
- Reconstructs run WITHOUT API calls
- Enables deterministic debugging

Re-evaluation:
- Re-runs evaluators on stored results
- No extra cost


STORAGE (JSON FILES)
--------------------
All data stored in .salvo/ directory:

.salvo/
  runs/
    {run_id}.json          # AgentRunResult
  recordings/
    {run_id}/
      request.json         # Redacted API request
      response.json        # API response
      judge.json           # LLM judge outputs
  history.jsonl            # Append-only run index

Why JSON over SQLite for MVP:
- Human-readable, easy to debug
- Git-friendly (can commit recordings)
- No driver dependencies
- Migrate to SQLite later if perf matters


CLI COMMANDS (MVP)
------------------
salvo init
  - Scaffolds .salvo/ directory
  - Creates example scenario YAML
  - Creates example custom adapter

salvo run [PATH] --runs N --record
  - Runs scenario(s) N times
  - Prints rich terminal table with results
  - Optionally records for replay

salvo report [--last N] [--failures]
  - Shows historical run summaries
  - Filter to recent or failures only

salvo replay RUN_ID [--re-eval]
  - Replays a recorded run without API calls
  - Optionally re-runs evaluators


CLI COMMANDS (POST-MVP)
-----------------------
salvo compare --a MODEL --b MODEL
  - Pass-rate deltas per scenario
  - Largest failing assertion differences

salvo dashboard
  - Streamlit web UI (post-MVP, not in initial build)


REPOSITORY LAYOUT
-----------------
salvo/
  core/
    models.py           # Pydantic models (AgentRunResult, etc.)
    scenario.py         # YAML loader + validation
    evaluators/
      __init__.py
      jmespath_eval.py
      tool_sequence.py
      cost_limit.py
      latency_limit.py
      llm_judge.py
      custom.py
    scoring.py          # Weighted score computation
    runner.py           # Orchestrates runs
    recorder.py         # Record/replay logic
    storage.py          # JSON file persistence
  adapters/
    base.py             # BaseAdapter ABC
    openai_adapter.py
    anthropic_adapter.py
  cli.py                # Click/Typer CLI entry point
scenarios/
  examples/
    book_flight.yaml
tests/
  test_scoring.py
  test_evaluators.py
  test_scenario_loader.py
pyproject.toml
README.md


BUILD PHASES
------------
Phase 1 — Foundation
- Pydantic models (AgentRunResult, AdapterRequest, etc.)
- Scenario YAML loader with validation
- BaseAdapter ABC
- Single adapter (OpenAI)

Phase 2 — Evaluators & Scoring
- All 6 evaluator types
- Weighted scoring engine
- Unit tests for scoring edge cases

Phase 3 — Runner & CLI
- Run orchestrator (N runs, parallel optional)
- JSON storage layer
- CLI: init, run, report
- Rich terminal output (tables, colors)

Phase 4 — Record/Replay
- Recording interceptor
- Replay engine
- Secret stripping
- CLI: replay --re-eval

Phase 5 — Second Adapter & Polish
- Anthropic adapter
- Example scenarios that actually work
- README with GIF demo
- PyPI-ready packaging (pyproject.toml, entry points)

Phase 6 (Post-MVP)
- Model compare CLI
- Streamlit dashboard
- GitHub Actions integration


SHIP CHECKLIST (RESUME IMPACT)
------------------------------
These are what make it portfolio-worthy:

- [ ] pip install salvo-ai works
- [ ] Running the example scenario produces output in under 60 seconds
- [ ] README has a GIF showing a real run
- [ ] Project has its own test suite (tests for the test framework)
- [ ] At least 2 non-trivial example scenarios included
- [ ] Clean GitHub repo with proper .gitignore, LICENSE, pyproject.toml
