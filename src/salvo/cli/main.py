"""Salvo CLI entry point."""

import typer

from salvo import __version__
from salvo.cli.init_cmd import init
from salvo.cli.replay_cmd import replay
from salvo.cli.report_cmd import report as report_cmd
from salvo.cli.run_cmd import run
from salvo.cli.validate_cmd import validate

app = typer.Typer(
    name="salvo",
    help="Test framework for multi-step AI agents",
    no_args_is_help=True,
)

# Register subcommands
app.command()(init)
app.command(name="report")(report_cmd)
app.command()(replay)
app.command()(run)
app.command()(validate)


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
