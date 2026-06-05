from __future__ import annotations

from typing import Optional

import typer

from aienv import __version__
from aienv.commands import (
    create_environment,
    delete_environment,
    inspect_environment,
    list_environments,
)
from aienv.errors import AienvError


app = typer.Typer(no_args_is_help=True)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aienv {__version__}")
        raise typer.Exit()


def handle_error(exc: AienvError) -> None:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=1)


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


@app.command("create")
def create(
    name: str = typer.Option(..., "-n", "--name"),
    agent: str = typer.Option(..., "-a", "--agent"),
    env: list[str] = typer.Option([], "-e", "--env"),
    workspace: str | None = typer.Option(None, "--workspace"),
) -> None:
    try:
        created = create_environment(name, agent, env, workspace)
    except AienvError as exc:
        handle_error(exc)
    typer.echo(f"Created {created.name}")


@app.command("list")
def list_envs() -> None:
    envs = list_environments()
    if not envs:
        typer.echo("No environments found")
        return
    for env in envs:
        typer.echo(f"{env.name}\t{env.agent}\t{env.workspace}")


@app.command("inspect")
def inspect(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        env = inspect_environment(name)
    except AienvError as exc:
        handle_error(exc)
    typer.echo(f"name: {env.name}")
    typer.echo(f"agent: {env.agent}")
    typer.echo(f"workspace: {env.workspace}")
    typer.echo(f"image: {env.image}")
    typer.echo("env:")
    for key in sorted(env.env):
        typer.echo(f"  {key}=<set>")
    typer.echo("mounts:")
    for mount in env.mounts:
        typer.echo(f"  {mount.alias}: {mount.source}")


@app.command("delete")
def delete(
    name: str = typer.Option(..., "-n", "--name"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    if not force and not typer.confirm(f"Delete environment {name}"):
        raise typer.Exit(code=1)
    try:
        delete_environment(name)
    except AienvError as exc:
        handle_error(exc)
    typer.echo(f"Deleted {name}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
