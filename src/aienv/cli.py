from __future__ import annotations

from typing import Optional

import typer

from aienv import __version__


app = typer.Typer(no_args_is_help=True)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aienv {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    return None


@app.command("list")
def list_envs() -> None:
    typer.echo("No environments found")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
