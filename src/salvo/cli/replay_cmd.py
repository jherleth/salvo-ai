"""salvo replay -- display a recorded trace without making API calls.

Loads a RecordedTrace from the store and renders it in a format
matching the live `salvo run` output, with a [REPLAY] banner and
(recorded) suffixes on timing values.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError
from rich import box
from rich.console import Console
from rich.table import Table

from salvo.models.config import find_project_root, load_project_config
from salvo.recording.replayer import TraceReplayer
from salvo.storage.json_store import RunStore


def replay(
    run_id: Optional[str] = typer.Argument(
        None, help="Run ID to replay (default: latest recorded)"
    ),
    allow_partial: bool = typer.Option(
        False,
        "--allow-partial",
        help="Replay available traces even when some are missing",
    ),
) -> None:
    """Replay a recorded trace without making API calls."""
    console = Console()

    # Banner
    console.print("\n[bold cyan]══════════ [REPLAY] ══════════[/bold cyan]\n")

    # Find project root and create store
    project_root = find_project_root()
    project_config = load_project_config(project_root)
    store = RunStore(project_root, storage_dir=project_config.storage_dir)
    replayer = TraceReplayer(store)

    # Load trace with error handling for corrupt files
    try:
        recorded = replayer.load(run_id)
    except (json.JSONDecodeError, ValidationError) as exc:
        if allow_partial:
            console.print(
                f"[yellow]Warning: Trace file for '{run_id}' is corrupt. "
                f"Skipping.[/yellow]"
            )
            raise typer.Exit(code=0)
        else:
            console.print(
                f"[bold red]Error:[/bold red] Corrupt trace file for '{run_id}'. "
                "Use --allow-partial to skip corrupt traces."
            )
            raise typer.Exit(code=1)

    if recorded is None:
        if run_id is not None:
            if allow_partial:
                console.print(
                    f"[yellow]Warning: No recorded trace found for '{run_id}'. "
                    f"Skipping.[/yellow]"
                )
                raise typer.Exit(code=0)
            else:
                console.print(
                    f"[bold red]Error:[/bold red] No recorded trace found for '{run_id}'. "
                    "Run 'salvo run --record' first."
                )
                raise typer.Exit(code=1)
        else:
            console.print(
                "[dim]No recorded traces found. Run 'salvo run --record' first.[/dim]"
            )
            raise typer.Exit(code=0)

    # Check metadata_only
    metadata_only = replayer.is_metadata_only(recorded)
    if metadata_only:
        console.print(
            "[yellow]Note: Content excluded (metadata_only recording mode). "
            "Message content is not available.[/yellow]"
        )
        console.print()

    # Render trace info table
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value")

    table.add_row("Scenario", recorded.metadata.scenario_name)
    table.add_row(
        "Model",
        f"{recorded.trace.model} via {recorded.trace.provider}",
    )
    table.add_row(
        "Recorded",
        recorded.metadata.recorded_at.isoformat(),
    )
    table.add_row("Run ID", recorded.metadata.source_run_id)
    table.add_row("Turns", str(recorded.trace.turn_count))
    table.add_row(
        "Tokens",
        f"{recorded.trace.total_tokens} "
        f"(in={recorded.trace.input_tokens}, out={recorded.trace.output_tokens})",
    )
    table.add_row(
        "Latency",
        f"{recorded.trace.latency_seconds:.2f}s (recorded)",
    )
    cost_str = (
        f"${recorded.trace.cost_usd:.4f} (recorded)"
        if recorded.trace.cost_usd is not None
        else "-"
    )
    table.add_row("Cost", cost_str)
    table.add_row("Finish", recorded.trace.finish_reason)

    console.print(table)

    # Final output
    console.print()
    if metadata_only:
        console.print("[bold]Final Output:[/bold] [dim][CONTENT_EXCLUDED][/dim]")
    else:
        final = recorded.trace.final_content or ""
        if len(final) > 500:
            final = final[:500] + "..."
        console.print(f"[bold]Final Output:[/bold] {final}")

    # Message summary by role
    role_counts: Counter[str] = Counter()
    for msg in recorded.trace.messages:
        role_counts[msg.role] += 1

    if role_counts:
        parts = [f"{count} {role}" for role, count in role_counts.items()]
        console.print(f"\n[bold]Messages:[/bold] {', '.join(parts)}")

    # Schema version
    console.print(
        f"\n[dim]Schema version: {recorded.metadata.schema_version}[/dim]"
    )
