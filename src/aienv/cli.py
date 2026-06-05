from __future__ import annotations

from typing import Optional

import typer

from aienv import __version__
from aienv.commands import (
    add_mount,
    create_environment,
    delete_environment,
    inspect_environment,
    list_environments,
    rebuild_environment,
    remove_mount,
    run_environment,
    set_env_var,
    unset_env_var,
)
from aienv.errors import AienvError


app = typer.Typer(no_args_is_help=True)
env_app = typer.Typer(no_args_is_help=True)
app.add_typer(env_app, name="env")


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
    try:
        envs = list_environments()
    except AienvError as exc:
        handle_error(exc)
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


@app.command("mount")
def mount(
    name: str = typer.Option(..., "-n", "--name"),
    source: str = typer.Argument(...),
    alias: str = typer.Argument(...),
) -> None:
    try:
        created = add_mount(name, source, alias)
    except AienvError as exc:
        handle_error(exc)
    typer.echo(f"Mounted {created.alias}")


@app.command("unmount")
def unmount(
    name: str = typer.Option(..., "-n", "--name"),
    alias: str = typer.Argument(...),
) -> None:
    try:
        remove_mount(name, alias)
    except AienvError as exc:
        handle_error(exc)
    typer.echo(f"Unmounted {alias}")


@env_app.command("set")
def env_set(
    assignment: str = typer.Argument(...),
    name: str = typer.Option(..., "-n", "--name"),
) -> None:
    try:
        key = set_env_var(name, assignment)
    except AienvError as exc:
        handle_error(exc)
    typer.echo(f"Set {key}")


@env_app.command("unset")
def env_unset(
    key: str = typer.Argument(...),
    name: str = typer.Option(..., "-n", "--name"),
) -> None:
    try:
        unset_env_var(name, key)
    except AienvError as exc:
        handle_error(exc)
    typer.echo(f"Unset {key}")


@app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    name: str = typer.Option(..., "-n", "--name"),
) -> None:
    prompt = " ".join(ctx.args) if ctx.args else None
    try:
        run_environment(name, "run", prompt)
    except AienvError as exc:
        handle_error(exc)


@app.command("attach")
def attach(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        run_environment(name, "attach")
    except AienvError as exc:
        handle_error(exc)


@app.command("shell")
def shell(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        run_environment(name, "shell")
    except AienvError as exc:
        handle_error(exc)


@app.command("rebuild")
def rebuild(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        rebuild_environment(name)
    except AienvError as exc:
        handle_error(exc)
    typer.echo(f"Rebuilt {name}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
