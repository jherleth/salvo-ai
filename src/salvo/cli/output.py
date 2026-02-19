"""Rich terminal output layer for N-trial results.

Provides progress bar, headline verdict table, detail sections,
and JSON output for TrialSuiteResult display in terminal and CI.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

from rich import box
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

if TYPE_CHECKING:
    from salvo.models.trial import TrialSuiteResult


# Verdict styling map: verdict value -> (symbol, Rich markup style)
_VERDICT_STYLES: dict[str, tuple[str, str]] = {
    "PASS": ("\u2713 PASS", "bold green"),
    "FAIL": ("\u2717 FAIL", "bold red"),
    "HARD FAIL": ("! HARD FAIL", "bold bright_red"),
    "PARTIAL": ("~ PARTIAL", "bold yellow"),
    "INFRA_ERROR": ("! INFRA ERROR", "bold bright_red"),
}


def create_trial_progress(console: Console) -> Progress | None:
    """Create a Rich Progress bar for trial execution.

    Returns None if the console is not a terminal (CI/pipe mode),
    so the caller can skip progress display.

    Args:
        console: Rich Console instance to check terminal status.

    Returns:
        Progress instance configured for trial display, or None.
    """
    if not console.is_terminal:
        return None

    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


def render_headline(suite: TrialSuiteResult, console: Console) -> None:
    """Render a compact headline verdict table for the suite result.

    Displays verdict, trial counts, score stats, and optional
    failure/latency/cost/retry/infra rows in a key-value table.

    Args:
        suite: The TrialSuiteResult to display.
        console: Rich Console for output.
    """
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    # Verdict row
    verdict_value = suite.verdict.value if hasattr(suite.verdict, "value") else str(suite.verdict)
    symbol, style = _VERDICT_STYLES.get(verdict_value, ("\u2717 UNKNOWN", "bold red"))
    table.add_row("Verdict", f"[{style}]{symbol}[/{style}]")

    # Trials row
    table.add_row(
        "Trials",
        f"{suite.trials_passed}/{suite.trials_total} passed ({suite.pass_rate:.0%})",
    )

    # Score row
    table.add_row(
        "Score",
        f"avg={suite.score_avg:.2f} min={suite.score_min:.2f} "
        f"p50={suite.score_p50:.2f} p95={suite.score_p95:.2f} "
        f"(threshold={suite.threshold:.2f})",
    )

    # Judge row (if judge assertions detected)
    judge_info = None
    for trial in suite.trials:
        for er in trial.eval_results:
            if er.assertion_type == "judge" and er.metadata:
                judge_info = er.metadata
                break
        if judge_info:
            break

    if judge_info:
        jm = judge_info.get("judge_model", "unknown")
        jk = judge_info.get("judge_k", "?")
        table.add_row("Judge", f"model={jm} k={jk}")

    # Failures row (only if any)
    if suite.trials_hard_fail > 0 or suite.trials_failed > 0:
        table.add_row(
            "Failures",
            f"{suite.trials_hard_fail} hard fail, {suite.trials_failed} soft fail",
        )

    # Latency row (only if available)
    if suite.latency_p50 is not None and suite.latency_p95 is not None:
        table.add_row(
            "Latency",
            f"p50={suite.latency_p50:.2f}s p95={suite.latency_p95:.2f}s",
        )

    # Cost row (only if available)
    if suite.cost_total is not None and suite.cost_avg_per_trial is not None:
        agent_cost = suite.cost_total
        judge_cost = suite.judge_cost_total or 0.0
        combined = agent_cost + judge_cost
        if judge_cost > 0:
            cost_str = (
                f"total=${combined:.4f} "
                f"(agent=${agent_cost:.4f} + judge=${judge_cost:.4f}) "
                f"avg=${suite.cost_avg_per_trial:.4f}/trial"
            )
        else:
            cost_str = f"total=${agent_cost:.4f} avg=${suite.cost_avg_per_trial:.4f}/trial"
        table.add_row("Cost", cost_str)

    # Retries row (only if any)
    if suite.total_retries > 0:
        table.add_row(
            "Retries",
            f"{suite.total_retries} retries across {suite.trials_with_retries} trials",
        )

    # Infra errors row (only if any)
    if suite.trials_infra_error > 0:
        table.add_row(
            "Infra errors",
            f"{suite.trials_infra_error} trial(s) (excluded from score)",
        )

    # Early stop row
    if suite.early_stopped:
        table.add_row(
            "Status",
            f"FAIL (early stop after {suite.trials_total}/{suite.n_requested} trials)",
        )

    console.print()
    console.print(table)


def render_details(suite: TrialSuiteResult, console: Console) -> None:
    """Render detail sections for failure analysis.

    Shows top offenders, score breakdown, latency distribution,
    cost breakdown, and sample failures when available.

    Args:
        suite: The TrialSuiteResult to display.
        console: Rich Console for output.
    """
    console.print()

    # 1. Top offenders
    if suite.assertion_failures:
        console.print("[bold]Top Offenders[/bold]")
        for i, failure in enumerate(suite.assertion_failures[:5], 1):
            atype = failure.get("assertion_type", "unknown")
            expr = failure.get("expression", "")
            fail_count = failure.get("fail_count", 0)
            total = suite.trials_total
            fail_rate = failure.get("fail_rate", 0.0)
            total_weight_lost = failure.get("total_weight_lost", 0.0)
            avg_weight_lost = total_weight_lost / fail_count if fail_count > 0 else 0.0
            console.print(
                f"  {i}. {atype}: {expr} "
                f"-- failed {fail_count}/{total} ({fail_rate:.0%}), "
                f"weight impact: {avg_weight_lost:.2f}"
            )
        console.print()

    # 2. Score breakdown - per-trial scores
    scored_trials = [
        t for t in suite.trials if t.status.value != "infra_error"
    ]
    if scored_trials:
        scores_str = ", ".join(f"{t.score:.1f}" for t in scored_trials)
        console.print(f"[bold]Scores:[/bold] {scores_str}")
        console.print()

    # 3. Latency distribution
    latencies = [t.latency_seconds for t in suite.trials]
    if latencies:
        lat_min = min(latencies)
        lat_max = max(latencies)
        lat_p50 = suite.latency_p50 if suite.latency_p50 is not None else lat_min
        lat_p95 = suite.latency_p95 if suite.latency_p95 is not None else lat_max
        console.print(
            f"[bold]Latency:[/bold] min={lat_min:.2f}s p50={lat_p50:.2f}s "
            f"p95={lat_p95:.2f}s max={lat_max:.2f}s"
        )
        console.print()

    # 4. Cost breakdown
    if suite.cost_total is not None:
        costs = [t.cost_usd for t in suite.trials if t.cost_usd is not None]
        if costs:
            cost_str = (
                f"total=${suite.cost_total:.4f} "
                f"min=${min(costs):.4f} max=${max(costs):.4f} "
                f"avg=${suite.cost_avg_per_trial:.4f}/trial"
            )
            if suite.judge_cost_total is not None and suite.judge_cost_total > 0:
                agent_cost = suite.cost_total
                cost_str += (
                    f" (agent=${agent_cost:.4f}"
                    f" + judge=${suite.judge_cost_total:.4f})"
                )
            console.print(f"[bold]Cost:[/bold] {cost_str}")
            console.print()

    # 5. Judge criteria breakdown
    judge_criteria: list[dict] = []
    for trial in suite.trials:
        for er in trial.eval_results:
            if er.assertion_type == "judge" and er.metadata and "per_criterion" in er.metadata:
                judge_criteria = er.metadata["per_criterion"]
                break
        if judge_criteria:
            break

    if judge_criteria:
        console.print("[bold]Judge Criteria[/bold]")
        for pc in judge_criteria:
            name = pc.get("name", "unknown")
            median = pc.get("median_score", 0.0)
            weight = pc.get("weight", 1.0)
            all_scores = pc.get("all_scores", [])
            scores_str = ", ".join(f"{s:.2f}" for s in all_scores)
            # Color-code median: green >= 0.7, yellow >= 0.4, red < 0.4
            if median >= 0.7:
                color_style = "green"
            elif median >= 0.4:
                color_style = "yellow"
            else:
                color_style = "red"
            console.print(
                f"  [{color_style}]{name}[/{color_style}]: median={median:.2f} "
                f"scores=[{scores_str}] weight={weight:.1f}"
            )
        console.print()

    # 6. Sample failures
    if suite.assertion_failures:
        top_failure = suite.assertion_failures[0]
        samples = top_failure.get("sample_details", [])
        if samples:
            console.print("[bold]Sample Failures[/bold]")
            for j, detail in enumerate(samples[:3], 1):
                # Truncate to 200 chars
                truncated = detail[:200] + "..." if len(detail) > 200 else detail
                console.print(f"  {j}. {truncated}")
            console.print()


def output_json(suite: TrialSuiteResult) -> None:
    """Write suite result as pure JSON to stdout.

    No Rich markup, no color, no extra text. Suitable for
    CI pipeline consumption and machine parsing.

    Args:
        suite: The TrialSuiteResult to serialize.
    """
    sys.stdout.write(suite.model_dump_json(indent=2))
    sys.stdout.write("\n")
