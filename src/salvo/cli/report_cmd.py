"""salvo report -- display stored run results and history trends.

Shows the latest run's detailed results by default, supports a
--history trend view across recent runs, and provides failure
filtering. Reads suite results from RunStore.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from salvo.models.config import find_project_root, load_project_config
from salvo.models.trial import TrialSuiteResult, Verdict
from salvo.storage.json_store import RunStore

# Verdict styling: verdict value -> (symbol, Rich style)
_VERDICT_STYLES: dict[str, tuple[str, str]] = {
    "PASS": ("\u2713 PASS", "bold green"),
    "FAIL": ("\u2717 FAIL", "bold red"),
    "HARD FAIL": ("! HARD FAIL", "bold bright_red"),
    "PARTIAL": ("~ PARTIAL", "bold yellow"),
    "INFRA_ERROR": ("! INFRA ERROR", "bold bright_red"),
}


def _verdict_display(verdict: Verdict) -> tuple[str, str]:
    """Return (symbol, style) for a verdict value."""
    value = verdict.value if hasattr(verdict, "value") else str(verdict)
    return _VERDICT_STYLES.get(value, ("\u2717 UNKNOWN", "bold red"))


def _render_run_detail(
    suite: TrialSuiteResult,
    console: Console,
    *,
    failures_only: bool = False,
) -> None:
    """Render detailed view of a single suite result.

    Args:
        suite: The TrialSuiteResult to display.
        console: Rich Console for output.
        failures_only: If True, only show failed assertions.
    """
    # Header
    console.print()
    symbol, style = _verdict_display(suite.verdict)
    console.print(f"[bold]Run:[/bold] {suite.run_id}")
    console.print(f"[bold]Scenario:[/bold] {suite.scenario_name}")
    console.print(f"[bold]Model:[/bold] {suite.model}  [bold]Adapter:[/bold] {suite.adapter}")
    console.print(f"[bold]Verdict:[/bold] [{style}]{symbol}[/{style}]")
    console.print()

    # Metrics summary
    metrics_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    metrics_table.add_column("Key", style="bold")
    metrics_table.add_column("Value")

    metrics_table.add_row(
        "Trials",
        f"{suite.trials_passed}/{suite.trials_total} passed ({suite.pass_rate:.0%})",
    )
    metrics_table.add_row(
        "Score",
        f"avg={suite.score_avg:.2f} min={suite.score_min:.2f} "
        f"p50={suite.score_p50:.2f} p95={suite.score_p95:.2f}",
    )
    if suite.cost_total is not None:
        metrics_table.add_row(
            "Cost",
            f"total=${suite.cost_total:.4f}"
            + (f" avg=${suite.cost_avg_per_trial:.4f}/trial" if suite.cost_avg_per_trial is not None else ""),
        )
    if suite.latency_p50 is not None and suite.latency_p95 is not None:
        metrics_table.add_row(
            "Latency",
            f"p50={suite.latency_p50:.2f}s p95={suite.latency_p95:.2f}s",
        )

    console.print(metrics_table)

    # Per-trial breakdown
    console.print("[bold]Per-Trial Breakdown[/bold]")
    trial_table = Table(box=box.ROUNDED)
    trial_table.add_column("Trial#", justify="right")
    trial_table.add_column("Status")
    trial_table.add_column("Score", justify="right")
    trial_table.add_column("Latency", justify="right")
    trial_table.add_column("Cost", justify="right")
    trial_table.add_column("Retries", justify="right")

    for trial in suite.trials:
        status_value = trial.status.value if hasattr(trial.status, "value") else str(trial.status)
        cost_str = f"${trial.cost_usd:.4f}" if trial.cost_usd is not None else "-"
        trial_table.add_row(
            str(trial.trial_number),
            status_value,
            f"{trial.score:.2f}",
            f"{trial.latency_seconds:.2f}s",
            cost_str,
            str(trial.retries_used),
        )

    console.print(trial_table)
    console.print()

    # Assertion failures
    if suite.assertion_failures:
        failures = suite.assertion_failures
        if failures_only:
            # Filter to only entries that have fail_count > 0
            failures = [f for f in failures if f.get("fail_count", 0) > 0]

        if failures:
            console.print("[bold]Assertion Failures[/bold]")
            for i, failure in enumerate(failures, 1):
                atype = failure.get("assertion_type", "unknown")
                expr = failure.get("expression", "")
                fail_count = failure.get("fail_count", 0)
                total_weight_lost = failure.get("total_weight_lost", 0.0)
                avg_weight = total_weight_lost / fail_count if fail_count > 0 else 0.0
                console.print(
                    f"  {i}. {atype}: {expr} "
                    f"-- failed {fail_count}x, weight impact: {avg_weight:.2f}"
                )
            console.print()
    elif not failures_only:
        console.print("[dim]No assertion failures.[/dim]")
        console.print()


def _render_history(
    suites: list[TrialSuiteResult],
    console: Console,
    *,
    failures_only: bool = False,
) -> None:
    """Render trend table of recent runs.

    Args:
        suites: List of suite results, ordered chronologically.
        console: Rich Console for output.
        failures_only: If True, only show runs with non-PASS verdict.
    """
    if failures_only:
        suites = [s for s in suites if s.verdict != Verdict.PASS]

    if not suites:
        console.print("[dim]No matching runs found.[/dim]")
        return

    console.print()
    table = Table(box=box.ROUNDED, title="Run History")
    table.add_column("Run ID")
    table.add_column("Scenario")
    table.add_column("Verdict")
    table.add_column("Score", justify="right")
    table.add_column("Trials", justify="right")
    table.add_column("Cost", justify="right")

    for suite in suites:
        symbol, style = _verdict_display(suite.verdict)
        cost_str = f"${suite.cost_total:.4f}" if suite.cost_total is not None else "-"
        trials_str = f"{suite.trials_passed}/{suite.trials_total}"
        table.add_row(
            suite.run_id[:8],
            suite.scenario_name,
            f"[{style}]{symbol}[/{style}]",
            f"{suite.score_avg:.2f}",
            trials_str,
            cost_str,
        )

    console.print(table)

    # Summary line with trend
    if len(suites) >= 2:
        first_rate = suites[0].pass_rate
        last_rate = suites[-1].pass_rate
        console.print(
            f"\n{len(suites)} runs shown. "
            f"Pass rate trend: {first_rate:.0%} -> {last_rate:.0%}"
        )
    else:
        console.print(f"\n{len(suites)} run(s) shown.")


def report(
    run_id: Optional[str] = typer.Argument(None, help="Run ID to display (default: latest)"),
    history: bool = typer.Option(False, "--history", help="Show trend view of recent runs"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of runs to show in history"),
    scenario: Optional[str] = typer.Option(None, "--scenario", "-s", help="Filter by scenario name"),
    failures_only: bool = typer.Option(False, "--failures", help="Show only failed assertions"),
) -> None:
    """Display stored run results and history trends."""
    console = Console()

    # Find project root and create store
    project_root = find_project_root()
    project_config = load_project_config(project_root)
    if not (project_root / project_config.storage_dir).exists():
        console.print("[dim]No .salvo/ directory found. Run 'salvo run' first.[/dim]")
        raise typer.Exit(code=0)

    store = RunStore(project_root, storage_dir=project_config.storage_dir)

    if history:
        # History mode: show trend table of recent runs
        run_ids = store.list_runs(scenario_name=scenario)
        if not run_ids:
            if scenario:
                console.print(f"[dim]No runs found for scenario '{scenario}'.[/dim]")
            else:
                console.print("[dim]No runs found. Run 'salvo run' first.[/dim]")
            raise typer.Exit(code=0)

        # Take last `limit` runs
        run_ids = run_ids[-limit:]

        # Load each suite result, skip failures
        suites: list[TrialSuiteResult] = []
        for rid in run_ids:
            try:
                suite = store.load_suite_result(rid)
                suites.append(suite)
            except (FileNotFoundError, Exception):
                # Skip corrupted or incompatible entries
                console.print(f"[dim]Warning: skipping run {rid} (could not load)[/dim]")

        _render_history(suites, console, failures_only=failures_only)
    else:
        # Detail mode: show single run
        if run_id is not None:
            # Load specific run
            try:
                suite = store.load_suite_result(run_id)
            except FileNotFoundError:
                console.print(f"Run '{run_id}' not found.")
                # List available run IDs
                available = store.list_runs()
                if available:
                    console.print(f"Available runs: {', '.join(available[:10])}")
                raise typer.Exit(code=1)
        else:
            # Load latest
            suite = store.load_latest_suite()
            if suite is None:
                console.print("[dim]No runs found. Run 'salvo run' first.[/dim]")
                raise typer.Exit(code=0)

        # Apply scenario filter in detail mode
        if scenario and suite.scenario_name != scenario:
            console.print(f"[dim]No runs found for scenario '{scenario}'.[/dim]")
            raise typer.Exit(code=0)

        _render_run_detail(suite, console, failures_only=failures_only)
