from __future__ import annotations

from typing import Literal, Optional, cast

import typer

from aisbox import __version__
from aisbox.commands import (
    add_mount,
    attach_environment,
    create_environment,
    delete_environment,
    doctor as run_doctor,
    inspect_environment,
    kill_session,
    list_environments,
    list_sessions,
    rebuild_environment,
    remove_mount,
    resolve_environment_name,
    run_environment,
    set_default_environment as set_default_environment_command,
    set_env_vars,
    start_environment,
    unset_env_vars,
)
from aisbox.errors import AisboxError
from aisbox.validation import parse_env_assignment


app = typer.Typer(no_args_is_help=True)
env_app = typer.Typer(no_args_is_help=True)
set_app = typer.Typer(no_args_is_help=True)
app.add_typer(env_app, name="env")
app.add_typer(set_app, name="set")

RETAINED_DETACH_GUIDANCE = (
    "Detach without stopping: Ctrl-p Ctrl-q. "
    "Ctrl-c may stop the agent and session."
)


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


def resolve_temporary_mounts(values: list[str]) -> list[tuple[str, str]]:
    if len(values) % 2 != 0:
        raise AisboxError("--mount requires SOURCE ALIAS")
    return [
        (values[index], values[index + 1])
        for index in range(0, len(values), 2)
    ]


def consume_temporary_mount_args(
    sources: list[str],
    args: list[str],
) -> tuple[list[tuple[str, str]], Literal["default", "auto", "bypass"] | None, list[str]]:
    values: list[str] = []
    permission_policy: Literal["default", "auto", "bypass"] | None = None
    remaining = list(args)
    saw_mount_option = bool(sources)
    for source in sources:
        if not remaining:
            raise AisboxError("--mount requires SOURCE ALIAS")
        values.extend([source, remaining.pop(0)])
    while remaining:
        if remaining[0] == "--":
            return resolve_temporary_mounts(values), permission_policy, remaining[1:]
        if remaining[0] == "--permission-policy" and saw_mount_option:
            if len(remaining) < 2:
                raise AisboxError("--permission-policy requires VALUE")
            permission_policy = parse_permission_policy(remaining[1])
            remaining = remaining[2:]
            continue
        if remaining[0] != "--mount" or not saw_mount_option:
            break
        if len(remaining) < 3:
            raise AisboxError("--mount requires SOURCE ALIAS")
        values.extend([remaining[1], remaining[2]])
        remaining = remaining[3:]
    return resolve_temporary_mounts(values), permission_policy, remaining


def parse_permission_policy(
    value: str,
) -> Literal["default", "auto", "bypass"]:
    if value not in {"default", "auto", "bypass"}:
        typer.echo(
            f"Invalid value for '--permission-policy': {value!r} is not one of "
            "'default', 'auto', 'bypass'."
        )
        raise typer.Exit(code=2)
    return cast(Literal["default", "auto", "bypass"], value)


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


@app.command(
    "run",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "allow_interspersed_args": False,
    },
)
def run(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "-n", "--name"),
    workspace: str | None = typer.Option(None, "--workspace"),
    permission_policy: Literal["default", "auto", "bypass"] = typer.Option(
        "default",
        "--permission-policy",
        help="Agent permission policy for this run: default, auto, or bypass.",
        metavar="default|auto|bypass",
        parser=parse_permission_policy,
    ),
    mount_sources: list[str] = typer.Option(
        [],
        "--mount",
        help="Temporarily mount SOURCE at ALIAS; repeat for multiple mounts.",
    ),
) -> None:
    effective_name = effective_environment_name(name)
    try:
        mounts, parsed_permission_policy, prompt_args = consume_temporary_mount_args(
            mount_sources, ctx.args
        )
        effective_permission_policy = parsed_permission_policy or permission_policy
        prompt = " ".join(prompt_args) if prompt_args else None
        run_environment(
            effective_name,
            "run",
            prompt,
            workspace=workspace,
            mounts=mounts,
            permission_policy=effective_permission_policy,
        )
    except AisboxError as exc:
        handle_error(exc)


@app.command(
    "start",
    help="Start an interactive agent.",
    context_settings={"allow_extra_args": True},
)
def start(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "-n", "--name"),
    keep: bool = typer.Option(
        False,
        "--keep",
        help="Keep one retained session for later attachment.",
    ),
    workspace: str | None = typer.Option(None, "--workspace"),
    mount_sources: list[str] = typer.Option(
        [],
        "--mount",
        help="Temporarily mount SOURCE at ALIAS; repeat for multiple mounts.",
    ),
) -> None:
    effective_name = effective_environment_name(name)
    if keep:
        typer.echo(RETAINED_DETACH_GUIDANCE)
    try:
        mounts, parsed_permission_policy, remaining_args = consume_temporary_mount_args(
            mount_sources, ctx.args
        )
        if parsed_permission_policy is not None:
            raise AisboxError("Unexpected argument: --permission-policy")
        if remaining_args:
            raise AisboxError(f"Unexpected argument: {remaining_args[0]}")
        start_environment(
            effective_name,
            keep,
            workspace=workspace,
            mounts=mounts,
        )
    except AisboxError as exc:
        handle_error(exc)


@app.command(
    "attach",
    help="Attach to a retained agent session, starting one when needed.",
    context_settings={"allow_extra_args": True},
)
def attach(
    ctx: typer.Context,
    name: str | None = typer.Option(None, "-n", "--name"),
    workspace: str | None = typer.Option(None, "--workspace"),
    mount_sources: list[str] = typer.Option(
        [],
        "--mount",
        help="Temporarily mount SOURCE at ALIAS; repeat for multiple mounts.",
    ),
) -> None:
    effective_name = effective_environment_name(name)
    typer.echo(RETAINED_DETACH_GUIDANCE)
    try:
        mounts, parsed_permission_policy, remaining_args = consume_temporary_mount_args(
            mount_sources, ctx.args
        )
        if parsed_permission_policy is not None:
            raise AisboxError("Unexpected argument: --permission-policy")
        if remaining_args:
            raise AisboxError(f"Unexpected argument: {remaining_args[0]}")
        attach_environment(effective_name, workspace=workspace, mounts=mounts)
    except AisboxError as exc:
        handle_error(exc)


@app.command("sessions", help="List running retained agent sessions.")
def sessions() -> None:
    try:
        retained = list_sessions()
    except AisboxError as exc:
        handle_error(exc)
    if not retained:
        typer.echo("No retained sessions found")
        return
    for session in retained:
        typer.echo(
            f"{session.environment}\t{session.agent}\t"
            f"{session.container}\t{session.status}"
        )


@app.command("kill", help="Stop and remove a retained agent session.")
def kill(name: str | None = typer.Option(None, "-n", "--name")) -> None:
    effective_name = effective_environment_name(name)
    try:
        kill_session(effective_name)
    except AisboxError as exc:
        handle_error(exc)
    typer.echo(f"Killed retained session for {effective_name}")


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
