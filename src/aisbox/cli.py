from __future__ import annotations

from typing import Optional

import typer

from aisbox import __version__
from aisbox.commands import (
    add_mount,
    create_environment,
    delete_environment,
    doctor as run_doctor,
    inspect_environment,
    list_environments,
    rebuild_environment,
    remove_mount,
    resolve_environment_name,
    run_environment,
    set_default_environment as set_default_environment_command,
    set_env_vars,
    unset_env_vars,
)
from aisbox.errors import AisboxError
from aisbox.validation import parse_env_assignment


app = typer.Typer(no_args_is_help=True)
env_app = typer.Typer(no_args_is_help=True)
set_app = typer.Typer(no_args_is_help=True)
app.add_typer(env_app, name="env")
app.add_typer(set_app, name="set")


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aisbox {__version__}")
        raise typer.Exit()


def handle_error(exc: AisboxError) -> None:
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(code=1)


def effective_environment_name(name: str | None) -> str:
    try:
        return resolve_environment_name(name)
    except AisboxError as exc:
        handle_error(exc)
    raise typer.Exit(code=1)


def resolve_env_assignments(assignments: list[str]) -> list[str]:
    resolved = []
    for assignment in assignments:
        key, value = parse_env_assignment(assignment)
        if value == "":
            value = typer.prompt(
                f"Value for {key}",
                default="",
                hide_input=True,
                show_default=False,
            )
        resolved.append(f"{key}={value}")
    return resolved


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
    env: list[str] = typer.Option(
        [],
        "-e",
        "--env",
        help="Set KEY=VALUE; an empty value prompts without echo.",
    ),
    workspace: str | None = typer.Option(None, "--workspace"),
) -> None:
    try:
        assignments = resolve_env_assignments(env)
        created = create_environment(name, agent, assignments, workspace)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Created {created.name}")


@app.command("list")
def list_envs() -> None:
    try:
        envs = list_environments()
    except AisboxError as exc:
        handle_error(exc)
    if not envs:
        typer.echo("No environments found")
        return
    for env in envs:
        typer.echo(f"{env.name}\t{env.agent}\t{env.workspace}")


@app.command("inspect")
def inspect(name: str | None = typer.Option(None, "-n", "--name")) -> None:
    effective_name = effective_environment_name(name)
    try:
        env = inspect_environment(effective_name)
    except AisboxError as exc:
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
    name: str | None = typer.Option(None, "-n", "--name"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    effective_name = effective_environment_name(name)
    if not force and not typer.confirm(f"Delete environment {effective_name}"):
        raise typer.Exit(code=1)
    try:
        delete_environment(effective_name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Deleted {effective_name}")


@app.command("mount")
def mount(
    name: str | None = typer.Option(None, "-n", "--name"),
    source: str = typer.Argument(...),
    alias: str = typer.Argument(...),
) -> None:
    effective_name = effective_environment_name(name)
    try:
        created = add_mount(effective_name, source, alias)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Mounted {created.alias}")


@app.command("unmount")
def unmount(
    name: str | None = typer.Option(None, "-n", "--name"),
    alias: str = typer.Argument(...),
) -> None:
    effective_name = effective_environment_name(name)
    try:
        remove_mount(effective_name, alias)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Unmounted {alias}")


@env_app.command("set")
def env_set(
    env: list[str] = typer.Option(
        ...,
        "-e",
        "--env",
        help="Set KEY=VALUE; an empty value prompts without echo.",
    ),
    name: str | None = typer.Option(None, "-n", "--name"),
) -> None:
    effective_name = effective_environment_name(name)
    try:
        assignments = resolve_env_assignments(env)
        keys = set_env_vars(effective_name, assignments)
    except AisboxError as exc:
        handle_error(exc)
    for key in keys:
        typer.echo(f"Set {key}")


@env_app.command("unset")
def env_unset(
    env: list[str] = typer.Option(
        ...,
        "-e",
        "--env",
        help="Unset an environment variable key; repeat for multiple keys.",
    ),
    name: str | None = typer.Option(None, "-n", "--name"),
) -> None:
    effective_name = effective_environment_name(name)
    try:
        keys = unset_env_vars(effective_name, env)
    except AisboxError as exc:
        handle_error(exc)
    for key in keys:
        typer.echo(f"Unset {key}")


@app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "-n", "--name"),
) -> None:
    effective_name = effective_environment_name(name)
    prompt = " ".join(ctx.args) if ctx.args else None
    try:
        run_environment(effective_name, "run", prompt)
    except AisboxError as exc:
        handle_error(exc)


@app.command("attach")
def attach(name: str | None = typer.Option(None, "-n", "--name")) -> None:
    effective_name = effective_environment_name(name)
    try:
        run_environment(effective_name, "attach")
    except AisboxError as exc:
        handle_error(exc)


@app.command("shell")
def shell(name: str | None = typer.Option(None, "-n", "--name")) -> None:
    effective_name = effective_environment_name(name)
    try:
        run_environment(effective_name, "shell")
    except AisboxError as exc:
        handle_error(exc)


@app.command("rebuild")
def rebuild(name: str | None = typer.Option(None, "-n", "--name")) -> None:
    effective_name = effective_environment_name(name)
    try:
        rebuild_environment(effective_name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Rebuilt {effective_name}")


@set_app.command("default")
def set_default(name: str = typer.Option(..., "-n", "--name")) -> None:
    try:
        default_name = set_default_environment_command(name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Default environment set to {default_name}")


@app.command("doctor")
def doctor() -> None:
    result = run_doctor()
    for line in result.lines:
        typer.echo(line)
    if not result.ok:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
