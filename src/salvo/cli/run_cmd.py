"""salvo run -- execute a scenario N times and display verdict.

Loads a scenario YAML, resolves the adapter, runs N trials via
TrialRunner, renders Rich verdict output, persists the suite result
with latest symlink, and exits with appropriate code.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from salvo.adapters.registry import get_adapter
from salvo.cli.output import (
    create_trial_progress,
    output_json,
    render_details,
    render_headline,
)
from salvo.execution.extras import validate_extras
from salvo.execution.trial_runner import TrialRunner
from salvo.loader.validator import validate_scenario_file
from salvo.models.trial import Verdict
from salvo.storage.json_store import RunStore

console = Console(stderr=True)

# Exit code mapping: verdict -> exit code
EXIT_CODES: dict[str, int] = {
    "PASS": 0,
    "FAIL": 1,
    "HARD FAIL": 2,
    "PARTIAL": 1,
    "INFRA_ERROR": 3,
}


def run(
    scenario_path: str = typer.Argument(..., help="Path to scenario YAML file"),
    n_trials: int = typer.Option(3, "-n", "--trials", help="Number of trials to run"),
    parallel: int = typer.Option(1, "--parallel", help="Max concurrent trials"),
    format_json: bool = typer.Option(False, "--json", "--format-json", help="Output pure JSON to stdout"),
    verbose: bool = typer.Option(False, "-V", "--verbose", help="Show detail sections even on pass"),
    report: bool = typer.Option(False, "--report", help="Show detail sections (CI alias)"),
    diagnose: bool = typer.Option(False, "--diagnose", help="Show detail sections (debug alias)"),
    early_stop: bool = typer.Option(False, "--early-stop", help="Stop when threshold unreachable or hard fail"),
    allow_infra: bool = typer.Option(False, "--allow-infra", help="Exit 0/1/2 instead of 3 on infra errors"),
    threshold: Optional[float] = typer.Option(None, "--threshold", help="Override scenario threshold"),
    record: bool = typer.Option(False, "--record", help="Record trace for replay"),
) -> None:
    """Run a scenario against an LLM and display results."""
    asyncio.run(
        _run_async(
            scenario_path,
            n_trials=n_trials,
            parallel=parallel,
            format_json=format_json,
            verbose=verbose,
            report=report,
            diagnose=diagnose,
            early_stop=early_stop,
            allow_infra=allow_infra,
            threshold_override=threshold,
            record=record,
        )
    )


async def _run_async(
    scenario_path: str,
    *,
    n_trials: int,
    parallel: int,
    format_json: bool,
    verbose: bool,
    report: bool,
    diagnose: bool,
    early_stop: bool,
    allow_infra: bool,
    threshold_override: float | None,
    record: bool = False,
) -> None:
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

    # 2. Resolve adapter (validate it exists)
    try:
        _test_adapter = get_adapter(scenario.adapter)
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
        max_tokens=None,
        seed=scenario.seed,
        extras=scenario.extras,
    )

    # 5. Create adapter_factory for fresh adapter per trial
    def adapter_factory():
        return get_adapter(scenario.adapter)

    # 6. Determine threshold
    effective_threshold = threshold_override if threshold_override is not None else scenario.threshold

    # 6b. Create store early so it can be passed to TrialRunner for immediate trace persistence
    project_root = _find_project_root(filepath)
    store = RunStore(project_root)

    # 7. Create TrialRunner
    runner = TrialRunner(
        adapter_factory=adapter_factory,
        scenario=scenario,
        config=config,
        n_trials=n_trials,
        max_parallel=parallel,
        max_retries=3,
        early_stop=early_stop,
        threshold=effective_threshold,
        store=store,
    )

    # 8. Output console (stdout for results, stderr for progress)
    output_console = Console()

    # 9. Execute trials with optional progress bar
    if not format_json and console.is_terminal:
        progress = create_trial_progress(console)
        if progress is not None:
            with progress:
                task = progress.add_task("Running trials", total=n_trials)

                def on_progress(trial_num: int, total: int) -> None:
                    progress.update(task, advance=1)

                suite = await runner.run_all(progress_callback=on_progress)
        else:
            suite = await runner.run_all()
    else:
        suite = await runner.run_all()

    # 10. Set scenario_file on the result
    suite = suite.model_copy(update={"scenario_file": str(filepath)})

    # 11. Persist suite result and update latest symlink
    store.save_suite_result(suite)
    store.update_latest_symlink(suite.run_id)

    # 12. Record traces if --record flag set
    if record:
        from salvo.recording.recorder import TraceRecorder, load_project_config

        proj_config = load_project_config(project_root)
        recorder = TraceRecorder(
            store=store,
            project_root=project_root,
            recording_mode=proj_config.recording.mode,
            custom_patterns=proj_config.recording.custom_redaction_patterns or None,
        )
        recorder.record_suite(suite, scenario, str(filepath))
        store.mark_run_recorded(suite.run_id)

    # 13. Output results
    if format_json:
        output_json(suite)
    else:
        render_headline(suite, output_console)

        # Show details if not PASS or any detail flag set
        show_details = verbose or report or diagnose
        verdict_value = suite.verdict.value if hasattr(suite.verdict, "value") else str(suite.verdict)
        if verdict_value != "PASS" or show_details:
            render_details(suite, output_console)

        output_console.print(f"[dim]Run saved: {suite.run_id}[/dim]")
        if record:
            output_console.print(f"[dim]Trace recorded: {suite.run_id}[/dim]")
            for trial in suite.trials:
                output_console.print(
                    f"[dim]  Trial {trial.trial_number}: trace_id={trial.trace_id}[/dim]"
                )

    # 14. Determine exit code
    if allow_infra and verdict_value == "INFRA_ERROR":
        # Use scored-trials-based verdict instead
        from salvo.evaluation.aggregation import determine_verdict as _det_verdict
        from salvo.models.trial import TrialStatus

        scored_trials = [t for t in suite.trials if t.status != TrialStatus.infra_error]
        if scored_trials:
            from salvo.evaluation.aggregation import compute_aggregate_metrics
            metrics = compute_aggregate_metrics(scored_trials, effective_threshold)
            alt_verdict = _det_verdict(
                scored_trials, metrics["score_avg"], effective_threshold, allow_infra=True,
            )
            alt_code = EXIT_CODES.get(alt_verdict.value, 1)
            if not format_json:
                output_console.print(
                    f"[dim yellow]Warning: {suite.trials_infra_error} infra error(s) "
                    f"ignored due to --allow-infra[/dim yellow]"
                )
            raise typer.Exit(code=alt_code)
        else:
            # All trials were infra errors, still exit 3
            raise typer.Exit(code=3)

    exit_code = EXIT_CODES.get(verdict_value, 1)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


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
