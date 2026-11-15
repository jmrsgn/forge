"""Command-line entry point for Forge."""

from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer

from forge.initialization import InitializationError, InitializationMode, initialize_project

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


@app.command()
def init(
    mode: Annotated[InitializationMode, typer.Option("--mode", help="Initialization mode.")],
    name: Annotated[str, typer.Option("--name", help="Project name.")],
    path: Annotated[Path, typer.Option("--path", help="Existing project directory.")] = Path("."),
) -> None:
    """Initialize Forge in an empty or existing project directory."""
    try:
        result = initialize_project(path, mode, name)
    except InitializationError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Initialized {result.mode.value} Forge workspace at {result.workspace_dir}")
