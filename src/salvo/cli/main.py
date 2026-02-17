"""Salvo CLI entry point."""

import typer

from salvo import __version__

app = typer.Typer(
    name="salvo",
    help="Test framework for multi-step AI agents",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"salvo {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Test framework for multi-step AI agents."""
