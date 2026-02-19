"""salvo reeval -- re-evaluate a recorded trace with updated assertions.

Loads a RecordedTrace from the store, runs the evaluation pipeline
with original or updated assertions, and saves a new RevalResult
linked to the original trace.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid7

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from salvo.evaluation.normalizer import normalize_assertions
from salvo.recording.models import RevalResult
from salvo.storage.json_store import RunStore

# Assertion types that require message content to evaluate
_CONTENT_DEPENDENT_TYPES = {"jmespath", "judge", "custom"}


def _find_project_root() -> Path:
    """Find project root by walking up from cwd looking for .salvo/.

    Returns:
        Path to directory containing .salvo/, or cwd if not found.
    """
    current = Path.cwd().resolve()
    while current != current.parent:
        if (current / ".salvo").exists():
            return current
        current = current.parent
    return Path.cwd()


def reeval(
    run_id: str = typer.Argument(
        ..., help="Run ID of the recorded trace to re-evaluate"
    ),
    scenario_path: Optional[str] = typer.Option(
        None,
        "--scenario",
        "-s",
        help="Path to updated scenario YAML (default: use original snapshot)",
    ),
    allow_partial_reeval: bool = typer.Option(
        False,
        "--allow-partial-reeval",
        help="Skip incompatible assertions on metadata_only traces instead of failing",
    ),
    strict_scenario: bool = typer.Option(
        False,
        "--strict-scenario",
        help="Fail if scenario has changed since trace was recorded",
    ),
) -> None:
    """Re-evaluate a recorded trace with original or updated assertions."""
    asyncio.run(
        _reeval_async(
            run_id,
            scenario_path,
            allow_partial_reeval=allow_partial_reeval,
            strict_scenario=strict_scenario,
        )
    )


async def _reeval_async(
    run_id: str,
    scenario_path: str | None,
    *,
    allow_partial_reeval: bool = False,
    strict_scenario: bool = False,
) -> None:
    """Async implementation of the reeval command."""
    import hashlib

    from salvo.evaluation.scorer import evaluate_trace_async
    from salvo.loader.validator import validate_scenario_file
    from salvo.models.scenario import Scenario

    console = Console()

    # Find project root and create store
    project_root = _find_project_root()
    store = RunStore(project_root)

    # Load recorded trace
    recorded = store.load_recorded_trace(run_id)
    if recorded is None:
        console.print(f"[bold red]Error:[/bold red] No recorded trace found for '{run_id}'")
        raise typer.Exit(code=1)

    # Banner
    console.print("\n[bold cyan]══════════ [RE-EVAL] ══════════[/bold cyan]\n")
    console.print(f"Re-evaluating trace: {run_id}")
    console.print(f"Original run: {recorded.metadata.source_run_id}")

    # Load scenario
    if scenario_path is not None:
        scenario_obj, errors = validate_scenario_file(Path(scenario_path))
        if errors:
            console.print("[bold red]Scenario validation errors:[/bold red]")
            for err in errors:
                loc = f" (line {err.line})" if err.line else ""
                console.print(f"  {err.field}: {err.message}{loc}")
            raise typer.Exit(code=1)
        assert scenario_obj is not None
        scenario = scenario_obj
    else:
        scenario = Scenario.model_validate(recorded.scenario_snapshot)
        console.print("[dim]Using original scenario snapshot[/dim]")

    # Scenario drift detection
    if scenario_path is not None:
        current_hash = hashlib.sha256(scenario.model_dump_json().encode()).hexdigest()
        recorded_hash = recorded.metadata.scenario_hash

        if current_hash != recorded_hash:
            if strict_scenario:
                console.print(
                    "[bold red]Error:[/bold red] Scenario hash mismatch. "
                    "The scenario has changed since the trace was recorded.\n"
                    f"  Recorded: {recorded_hash[:12]}...\n"
                    f"  Current:  {current_hash[:12]}...\n"
                    "Remove --strict-scenario to proceed with warnings."
                )
                raise typer.Exit(code=1)
            else:
                console.print(
                    f"[yellow]Warning: Scenario has changed since trace was recorded "
                    f"(recorded={recorded_hash[:12]}..., current={current_hash[:12]}...)[/yellow]"
                )

    # Check metadata_only mode
    metadata_only = recorded.metadata.recording_mode == "metadata_only"
    all_raw_assertions = [a.model_dump(exclude_none=True) for a in scenario.assertions]
    normalized_assertions = normalize_assertions(all_raw_assertions)

    # Inject scenario reference for judge assertions (matching trial_runner.py pattern)
    for a in normalized_assertions:
        if a.get("type") == "judge":
            a["_scenario"] = scenario

    assertions_skipped = 0
    if metadata_only:
        # Count content-dependent assertions
        content_dependent = [
            a for a in normalized_assertions if a.get("type") in _CONTENT_DEPENDENT_TYPES
        ]
        non_content = [
            a for a in normalized_assertions if a.get("type") not in _CONTENT_DEPENDENT_TYPES
        ]

        if len(content_dependent) == len(normalized_assertions):
            console.print(
                "[bold red]Error:[/bold red] All assertions require message content, "
                "which is unavailable in metadata_only mode. Re-evaluation not possible."
            )
            raise typer.Exit(code=1)

        if content_dependent:
            if not allow_partial_reeval:
                console.print(
                    f"[bold red]Error:[/bold red] {len(content_dependent)} assertion(s) "
                    "require message content unavailable in metadata_only mode. "
                    "Use --allow-partial-reeval to skip them."
                )
                raise typer.Exit(code=1)

            assertions_skipped = len(content_dependent)
            console.print(
                f"[yellow]Warning: {assertions_skipped} assertion(s) skipped "
                f"(require message content unavailable in metadata_only mode)[/yellow]"
            )
            normalized_assertions = non_content

    # Run evaluation
    eval_results, score, passed = await evaluate_trace_async(
        recorded.trace, normalized_assertions, scenario.threshold
    )

    # Build RevalResult
    reeval_result = RevalResult(
        reeval_id=str(uuid7()),
        original_trace_id=run_id,
        scenario_name=scenario.description or recorded.metadata.scenario_name,
        scenario_file=scenario_path,
        eval_results=eval_results,
        score=score,
        passed=passed,
        threshold=scenario.threshold,
        evaluated_at=datetime.now(timezone.utc),
        assertions_used=len(normalized_assertions),
        assertions_skipped=assertions_skipped,
    )

    # Display results table
    console.print()
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    result_style = "bold green" if passed else "bold red"
    result_text = "PASS" if passed else "FAIL"
    table.add_row("Result", f"[{result_style}]{result_text}[/{result_style}]")
    table.add_row("Score", f"{score:.2f} (threshold={scenario.threshold:.2f})")
    table.add_row(
        "Assertions",
        f"{reeval_result.assertions_used} evaluated, {assertions_skipped} skipped",
    )
    table.add_row("Original trace", run_id)
    table.add_row("Re-eval ID", reeval_result.reeval_id)

    console.print(table)

    # Display per-assertion results
    if eval_results:
        console.print("[bold]Per-Assertion Results[/bold]")

        # Sort: hard failures first, then soft failures, then passes
        def _sort_key(er):
            if er.required and not er.passed:
                return 0  # hard failure
            if not er.passed:
                return 1  # soft failure
            return 2  # pass

        sorted_results = sorted(eval_results, key=_sort_key)

        for er in sorted_results:
            if er.passed:
                indicator = "[green]PASS[/green]"
            elif er.required:
                indicator = "[bold red]HARD FAIL[/bold red]"
            else:
                indicator = "[red]FAIL[/red]"

            expr = er.details[:200] if len(er.details) > 200 else er.details
            console.print(
                f"  {indicator} {er.assertion_type}: score={er.score:.2f} -- {expr}"
            )
        console.print()

    # Save result
    store.save_reeval_result(reeval_result)
    console.print(f"[dim]Re-evaluation saved: {reeval_result.reeval_id}[/dim]")

    # Exit code
    if not passed:
        raise typer.Exit(code=1)
