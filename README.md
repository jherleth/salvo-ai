<div align="center">

# SALVO

**Test your AI agents like you test your code.**

Define scenarios in YAML. Run them N times. Get pass rates, costs, and failure breakdowns.
When runs fail, replay recorded traces without spending another cent.

[![PyPI version](https://img.shields.io/pypi/v/salvo-ai?style=for-the-badge&logo=python&logoColor=white&color=3776AB)](https://pypi.org/project/salvo-ai/)
[![Tests](https://img.shields.io/badge/tests-555_passing-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://github.com/)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue?style=for-the-badge)](LICENSE)

<br>

```bash
pip install salvo-ai[openai]
```

<br>

*Your agent passes once. Does it pass 50 times in a row?*

<br>

[Why Salvo](#why-salvo) · [Quick Start](#quick-start) · [How It Works](#how-it-works) · [Assertions](#assertions) · [Commands](#commands) · [Adapters](#adapters)

</div>

---

## Why Salvo

You changed a system prompt. You tweaked the tools. You swapped models. **Does your agent still work?**

Single prompt-response evals don't catch multi-step failures. Your agent might call tools in the wrong order, hallucinate arguments, or bail out after one turn. You won't know until a user hits it.

Salvo fixes that. Write a YAML scenario, give it tools with mock responses, define what "correct" looks like with assertions, and run it 50 times. Get a pass rate. Sleep at night.

```
$ salvo run scenarios/ -n 10

  coding-assistant   gpt-4o   10/10 passed   score: 1.00   $0.12   avg 2.3s
  search-agent       gpt-4o    8/10 passed   score: 0.85   $0.08   avg 1.8s
  data-pipeline      gpt-4o    9/10 passed   score: 0.94   $0.15   avg 3.1s

  3 scenarios | 27/30 passed | avg score: 0.93
```

When something breaks, don't re-run and re-pay. **Replay the recorded trace** and re-evaluate with updated assertions. Zero API calls. Zero cost.

---

## Quick Start

### 1. Install

```bash
pip install salvo-ai[openai]       # For OpenAI models
pip install salvo-ai[anthropic]    # For Anthropic models
pip install salvo-ai[all]          # Both
```

### 2. Initialize

```bash
salvo init
```

Creates a starter project:
```
my-project/
  salvo.yaml              # Project config
  scenarios/
    example.yaml          # Example scenario with tools and assertions
  tools/
    example_tool.yaml     # Reusable tool definition
```

### 3. Write a Scenario

```yaml
description: "Agent fixes a bug by reading source, finding the issue, and applying a fix"

adapter: openai
model: gpt-4o

system_prompt: |
  You are a senior software engineer. Read the failing test,
  inspect the source, write a fix, then run tests to verify.

prompt: |
  The test in tests/test_math.py is failing. Please investigate and fix the bug.

tools:
  - name: file_read
    description: "Read the contents of a file"
    parameters:
      type: object
      properties:
        path:
          type: string
      required: [path]
    mock_response: |
      def add(a, b):
          return a - b  # BUG: should be a + b

  - name: file_write
    description: "Write contents to a file"
    parameters:
      type: object
      properties:
        path: { type: string }
        content: { type: string }
      required: [path, content]
    mock_response: "File written successfully"

  - name: run_tests
    description: "Run the test suite"
    parameters:
      type: object
      properties:
        test_path: { type: string }
    mock_response: "1 passed, 0 failed"

assertions:
  - type: tool_called
    tool: file_read
    required: true

  - type: tool_sequence
    mode: in_order
    sequence: [file_read, file_write, run_tests]
    weight: 2.0

  - type: output_contains
    value: "+"

threshold: 0.8
```

### 4. Run

```bash
# Run once
salvo run scenarios/example.yaml

# Run 10 times for reliability stats
salvo run scenarios/ -n 10

# Record traces for replay
salvo run scenarios/ -n 10 --record
```

---

## How It Works

```
 YAML Scenario          Adapter            N-Trial Runner
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│ system_prompt │───>│   OpenAI /   │───>│  Run scenario N  │
│ prompt        │    │  Anthropic   │    │  times, collect  │
│ tools + mocks │    │              │    │  traces + usage  │
│ assertions    │    └──────────────┘    └────────┬─────────┘
└──────────────┘                                  │
                                                  v
                    ┌──────────────┐    ┌──────────────────┐
                    │   Results    │<───│  Assertion Engine │
                    │              │    │                   │
                    │ pass rates   │    │ tool_sequence     │
                    │ scores       │    │ jmespath queries  │
                    │ cost / time  │    │ LLM judge (k=3)  │
                    │ breakdowns   │    │ cost/latency caps │
                    └──────────────┘    └──────────────────┘
```

**Scenarios** define what to test: a system prompt, user prompt, available tools with mock responses, and assertions that define "correct."

**Adapters** send the conversation to your model. Tools are presented to the model, and mock responses are returned when the model calls them. Multi-turn loops continue until the model stops calling tools or hits the safety limit.

**Assertions** evaluate the trace: Did it call the right tools? In the right order? Did the output contain what we expected? Did it stay under budget?

**Traces** capture everything: every message, every tool call, token counts, latency, cost. Record them to replay later without API calls.

---

## Assertions

Salvo ships with 7 assertion types that cover the full evaluation spectrum.

### Quick Assertions

The simplest way to check common things:

```yaml
# Did the agent call a specific tool?
- type: tool_called
  tool: file_read
  required: true          # Hard fail if not called

# Does the output contain a string?
- type: output_contains
  value: "fixed"
```

### Tool Sequence

Verify your agent follows the correct workflow:

```yaml
- type: tool_sequence
  mode: in_order          # exact | in_order | any_order
  sequence:
    - file_read
    - file_write
    - run_tests
  weight: 2.0             # Count this assertion double
```

| Mode | Behavior |
|------|----------|
| `exact` | Actual calls must match expected exactly |
| `in_order` | Expected tools appear in order (extra calls OK) |
| `any_order` | All expected tools called (any order, extras OK) |

### JMESPath Queries

Query the full trace data structure with [JMESPath](https://jmespath.org/):

```yaml
# Check a tool was called with specific arguments
- type: jmespath
  expression: "tool_calls[?name=='file_write'].arguments.path | [0]"
  operator: exists

# Check token usage
- type: jmespath
  expression: "metadata.total_tokens"
  operator: lt
  value: 5000

# Check the model's final response
- type: jmespath
  expression: "response.content"
  operator: contains
  value: "successfully"
```

<details>
<summary><strong>Available operators</strong></summary>

| Operator | Description |
|----------|-------------|
| `eq` | Equal |
| `ne` | Not equal |
| `gt` | Greater than |
| `gte` | Greater than or equal |
| `lt` | Less than |
| `lte` | Less than or equal |
| `contains` | String/list contains value |
| `regex` | Matches regular expression |
| `exists` | Value is not null/missing |

</details>

<details>
<summary><strong>Queryable trace structure</strong></summary>

```json
{
  "response": {
    "content": "final assistant message",
    "finish_reason": "stop"
  },
  "turns": [
    { "role": "assistant", "content": "...", "tool_calls": [...] },
    { "role": "tool_result", "content": "...", "tool_name": "file_read" }
  ],
  "tool_calls": [
    { "name": "file_read", "arguments": { "path": "test.py" } },
    { "name": "file_write", "arguments": { "path": "src.py", "content": "..." } }
  ],
  "metadata": {
    "model": "gpt-4o",
    "provider": "openai",
    "cost_usd": 0.012,
    "latency_seconds": 2.3,
    "input_tokens": 1500,
    "output_tokens": 500,
    "total_tokens": 2000,
    "turn_count": 3,
    "finish_reason": "stop"
  }
}
```

</details>

### Cost & Latency Limits

Hard caps on spend and time:

```yaml
- type: cost_limit
  max_usd: 0.50

- type: latency_limit
  max_seconds: 30.0
```

### LLM Judge

When assertions can't be expressed as rules, use an LLM judge with k-vote consensus:

```yaml
- type: judge
  criteria:
    - name: correctness
      description: "Did the agent fix the actual bug?"
      weight: 2.0
    - name: methodology
      description: "Did the agent read before writing?"
      weight: 1.0
  judge_model: gpt-4o-mini   # Cheap model for judging
  k: 3                        # 3 votes, majority wins
  threshold: 0.7
```

---

## Commands

| Command | What it does |
|---------|-------------|
| `salvo init` | Create a starter project with example scenario |
| `salvo validate <path>` | Validate scenario files (catches typos, bad schemas) |
| `salvo run <path> [-n N]` | Run scenarios N times, show pass rates and scores |
| `salvo report <run-id>` | Show detailed breakdown of a completed run |
| `salvo replay [trace-id]` | Replay a recorded trace without API calls |
| `salvo reeval [trace-id]` | Re-evaluate a trace with updated assertions |

### Key Flags

```bash
# Run 20 trials with trace recording
salvo run scenarios/ -n 20 --record

# Run with a specific model
salvo run scenarios/ --model gpt-4o-mini

# Validate before running
salvo validate scenarios/

# Replay the latest recorded trace
salvo replay

# Re-evaluate with a modified scenario
salvo reeval --scenario scenarios/updated.yaml
```

---

## Adapters

Salvo supports OpenAI and Anthropic out of the box, with a plugin system for custom adapters.

| Adapter | Models | Install |
|---------|--------|---------|
| `openai` | gpt-4o, gpt-4o-mini, o1, o3, etc. | `pip install salvo-ai[openai]` |
| `anthropic` | claude-4, claude-sonnet, etc. | `pip install salvo-ai[anthropic]` |
| Custom | Any model | Subclass `BaseAdapter` |

### Custom Adapters

```yaml
# In your scenario
adapter: my_package.adapters.LlamaAdapter
model: llama-3.1-70b
```

```python
# my_package/adapters.py
from salvo.adapters.base import BaseAdapter

class LlamaAdapter(BaseAdapter):
    async def run(self, scenario, resolved_extras):
        # Your implementation here
        ...
```

---

## Configuration

### `salvo.yaml`

Project-level defaults that scenarios can override:

```yaml
# Default model settings
default_adapter: openai
default_model: gpt-4o

# Where to find scenarios
scenarios_dir: scenarios

# Where to store run data
storage_dir: .salvo

# Judge defaults
judge:
  adapter: openai
  model: gpt-4o-mini
  k: 3
  temperature: 0.0
  default_threshold: 0.8
```

### Reusable Tools

Extract tool definitions into YAML files and include them across scenarios:

```yaml
# tools/file_tools.yaml
name: file_read
description: "Read file contents"
parameters:
  type: object
  properties:
    path: { type: string }
  required: [path]
mock_response: "file contents here"
```

```yaml
# In your scenario
tools:
  - !include tools/file_tools.yaml
  - name: inline_tool
    description: "Defined right here"
    mock_response: "ok"
```

---

## Trace Recording & Replay

Record complete traces during runs, then replay and re-evaluate without making API calls.

```bash
# Record traces
salvo run scenarios/ --record

# Replay the last recorded trace (no API calls)
salvo replay

# Replay a specific trace
salvo replay abc123

# Re-evaluate with updated assertions (no API calls)
salvo reeval abc123 --scenario scenarios/stricter.yaml
```

This is the money feature for iteration. Change your assertions, re-evaluate the same trace, see if your new scoring logic works. No API costs. Instant feedback.

---

## Validation

Salvo catches problems before you spend money on API calls:

```bash
$ salvo validate scenarios/bad.yaml

  scenarios/bad.yaml
    [error] Line 1: Unknown field 'modle'. Did you mean 'model'?
    [error] Assertion 0: Unknown type 'tool_calld'. Did you mean 'tool_called'?

  0/1 scenarios valid
```

Validates schema, field names (with typo suggestions), assertion types, tool definitions, and threshold ranges.

---

## Architecture

```
src/salvo/
  adapters/          # OpenAI, Anthropic, custom adapter registry
  cli/               # Typer CLI: init, validate, run, report, replay, reeval
  evaluation/        # Assertion engine: normalizer, scorer, 5 evaluators
  execution/         # Multi-turn runner, N-trial runner, trace capture
  loader/            # YAML loading, !include resolution, validation
  models/            # Pydantic v2 models: Scenario, RunResult, RunTrace
  recording/         # Trace recorder, replayer, redaction
  scaffold/          # Project templates for salvo init
  storage/           # JSON store for runs, traces, manifests
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Your agent works once. Salvo tells you if it works every time.**

</div>
