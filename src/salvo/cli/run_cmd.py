"""salvo run -- execute a scenario against an LLM and display results.

Loads a scenario YAML, resolves the adapter, validates extras, runs the
multi-turn execution loop, prints a structured summary, and persists
the run result and redacted trace to .salvo/.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid7

import typer
from rich.console import Console

from salvo import __version__
from salvo.adapters.registry import get_adapter
from salvo.evaluation.formatting import format_eval_results
from salvo.evaluation.scorer import compute_score, evaluate_trace
from salvo.execution.extras import validate_extras
from salvo.execution.redaction import apply_trace_limits
from salvo.execution.runner import ScenarioRunner, ToolMockNotFoundError
from salvo.loader.validator import validate_scenario_file
from salvo.models.result import RunMetadata, RunResult
from salvo.storage.json_store import RunStore

console = Console(stderr=True)


def run(
    scenario_path: str = typer.Argument(..., help="Path to scenario YAML file"),
) -> None:
    """Run a scenario against an LLM and display results."""
    asyncio.run(_run_async(scenario_path))


async def _run_async(scenario_path: str) -> None:
    """Async implementation of the run command."""
    from salvo.adapters.base import AdapterConfig

    filepath = Path(scenario_path)

    # 1. Load and validate scenario
    scenario, errors = validate_scenario_file(filepath)
    if errors:
        console.print("[bold red]Scenario validation errors:[/bold red]")
        for err in errors:
            loc = f" (line {err.line})" if err.line else ""
            console.print(f"  {err.field}: {err.message}{loc}")
        raise typer.Exit(code=1)

    assert scenario is not None

    # 2. Resolve adapter
    try:
        adapter = get_adapter(scenario.adapter)
    except ImportError as exc:
        console.print(f"[bold red]Adapter error:[/bold red] {exc}")
        console.print(
            f"[dim]Install the required SDK for the '{scenario.adapter}' adapter.[/dim]"
        )
        raise typer.Exit(code=1)

    # 3. Validate extras
    try:
        validate_extras(scenario.extras)
    except ValueError as exc:
        console.print(f"[bold red]Extras validation error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 4. Build AdapterConfig
    config = AdapterConfig(
        model=scenario.model,
        temperature=scenario.temperature,
        max_tokens=None,  # Let provider default
        seed=scenario.seed,
        extras=scenario.extras,
    )

    # 5. Execute scenario
    try:
        runner = ScenarioRunner(adapter)
        trace = await runner.run(scenario, config)
    except ToolMockNotFoundError as exc:
        console.print(f"[bold red]Tool mock error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print(f"[bold red]Execution error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    # 6. Apply trace limits (redaction + truncation)
    trace = apply_trace_limits(trace)

    # 7. Evaluate assertions
    assertion_dicts = [
        a.model_dump(exclude_none=True) for a in scenario.assertions
    ]
    eval_results, score, passed = evaluate_trace(
        trace, assertion_dicts, scenario.threshold
    )
    hard_fail = any(r.required and not r.passed for r in eval_results)

    # 8. Print structured summary
    desc = scenario.description or filepath.stem
    cost_str = f"${trace.cost_usd:.6f} (estimated)" if trace.cost_usd is not None else "unknown"
    turns_suffix = " (max turns hit)" if trace.max_turns_hit else ""

    output = Console()
    output.print()
    output.print(f"[bold]Scenario:[/bold] {desc}")
    output.print(f"[bold]Model:[/bold]    {trace.model} ({trace.provider})")
    output.print(f"[bold]Turns:[/bold]    {trace.turn_count}{turns_suffix}")
    output.print(f"[bold]Tools:[/bold]    {len(trace.tool_calls_made)} call(s)")
    output.print(
        f"[bold]Tokens:[/bold]   {trace.input_tokens} in / {trace.output_tokens} out"
    )
    output.print(f"[bold]Cost:[/bold]     {cost_str}")
    output.print(f"[bold]Latency:[/bold]  {trace.latency_seconds:.2f}s")
    output.print(f"[bold]Hash:[/bold]     {trace.scenario_hash[:12]}...")
    output.print()

    # 9. Print evaluation results
    eval_output = format_eval_results(
        eval_results, score, scenario.threshold, passed, hard_fail
    )
    output.print(eval_output)
    output.print()

    # 10. Print pass/fail status with Rich markup
    if hard_fail:
        output.print("[bold red]HARD FAIL[/bold red]")
    elif passed:
        output.print("[bold green]PASS[/bold green]")
    else:
        output.print("[bold red]FAILED[/bold red]")
    output.print()

    # 11. Build RunResult for persistence
    run_id = str(uuid7())
    metadata = RunMetadata(
        scenario_name=filepath.stem,
        scenario_file=str(filepath),
        scenario_hash=trace.scenario_hash,
        timestamp=datetime.now(timezone.utc),
        model=trace.model,
        adapter=scenario.adapter,
        salvo_version=__version__,
        passed=passed,
        score=score,
        cost_usd=trace.cost_usd,
        latency_seconds=trace.latency_seconds,
    )

    run_result = RunResult(
        run_id=run_id,
        metadata=metadata,
        eval_results=eval_results,
        score=score,
        passed=passed,
        trace_id=run_id,
    )

    # 12. Determine project root and store
    project_root = _find_project_root(filepath)
    store = RunStore(project_root)

    # 13. Save run result and trace
    store.save_run(run_result)
    store.save_trace(run_id, trace)

    output.print(f"[dim]Run saved: {run_id}[/dim]")

    # 14. Exit code 1 on failure (CI compatible)
    if not passed:
        raise typer.Exit(code=1)


def _find_project_root(scenario_path: Path) -> Path:
    """Find the project root by looking for .salvo/ directory or using cwd.

    Walks up from the scenario file directory looking for an existing
    .salvo/ directory. If not found, uses the current working directory.

    Args:
        scenario_path: Path to the scenario file.

    Returns:
        Path to the project root directory.
    """
    # Try walking up from scenario file
    current = scenario_path.resolve().parent
    while current != current.parent:
        if (current / ".salvo").exists():
            return current
        current = current.parent

    # Fall back to cwd
    return Path.cwd()
