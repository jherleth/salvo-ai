"""salvo init CLI command for project scaffolding.

Creates a complete Salvo project with config, example scenario,
shared tool definitions, and .gitignore. Non-interactive.
"""

from __future__ import annotations

from pathlib import Path

import typer

from salvo.scaffold.init import ProjectExistsError, scaffold_project


def init(
    directory: str = typer.Argument(".", help="Directory to initialize"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing files"
    ),
) -> None:
    """Initialize a new Salvo project.

    Creates salvo.yaml, an example scenario, shared tool definitions,
    and a .gitignore. All files are generated with sensible defaults
    -- no prompts, no interaction.
    """
    target = Path(directory).resolve()

    try:
        scaffold_project(target, force=force)
    except ProjectExistsError as e:
        typer.echo(f"Error: Files already exist: {', '.join(e.conflicting_files)}", err=True)
        typer.echo("Use --force to overwrite existing files.", err=True)
        raise typer.Exit(code=1)
