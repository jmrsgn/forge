"""Command-line entry point for Forge."""

from importlib.metadata import version
from typing import Annotated

import typer

app = typer.Typer(
    help="Forge software engineering toolkit.", no_args_is_help=True, add_completion=False
)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"forge {version('forge')}")
        raise typer.Exit()


@app.callback()
def main(
    version_option: Annotated[
        bool,
        typer.Option(
            "--version", callback=_show_version, is_eager=True, help="Show Forge version."
        ),
    ] = False,
) -> None:
    """Forge software engineering toolkit."""
