"""salvo validate CLI command for scenario file validation.

Validates YAML scenario files against the Salvo schema, reporting
all errors at once with rich or CI-friendly formatting.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from salvo.loader.errors import ErrorFormatter
from salvo.loader.validator import validate_scenario_file


def validate(
    scenarios: Optional[list[str]] = typer.Argument(
        None, help="Scenario files to validate (default: all in scenarios/)"
    ),
    ci: bool = typer.Option(False, "--ci", help="CI-friendly concise output"),
) -> None:
    """Validate scenario YAML files against the Salvo schema.

    Checks YAML syntax and Pydantic model validation, reporting all
    errors at once. Exits with code 0 if all valid, 1 if any errors.
    """
    formatter = ErrorFormatter(ci_mode=ci)

    # Resolve file paths
    files: list[Path] = []
    if scenarios:
        for s in scenarios:
            p = Path(s)
            if not p.exists():
                typer.echo(f"Error: File not found: {s}", err=True)
                raise typer.Exit(code=1)
            files.append(p)
    else:
        # Scan scenarios/ directory
        scenarios_dir = Path.cwd() / "scenarios"
        if scenarios_dir.is_dir():
            files = sorted(
                list(scenarios_dir.glob("**/*.yaml"))
                + list(scenarios_dir.glob("**/*.yml"))
            )
        if not files:
            typer.echo("No scenario files found. Specify files or create a scenarios/ directory.")
            raise typer.Exit(code=1)

    total = len(files)
    valid_count = 0
    error_count = 0

    for filepath in files:
        source = filepath.read_text(encoding="utf-8")
        scenario, errors = validate_scenario_file(filepath)

        if errors:
            error_count += 1
            output = formatter.format_all(errors, source, str(filepath))
            typer.echo(output, err=not ci)
            if ci:
                # In CI mode, also print to stdout for parser consumption
                pass
        else:
            valid_count += 1
            formatter.print_success(str(filepath))

    # Print summary
    typer.echo(f"\n{valid_count}/{total} scenarios valid")

    if error_count > 0:
        raise typer.Exit(code=1)
