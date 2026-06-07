import json
import multiprocessing
import os
import stat
import subprocess
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from aisbox import commands as commands_module
from aisbox.cli import app
from aisbox.commands import (
    attach_environment,
    delete_environment,
    kill_session,
    list_sessions,
    start_environment,
)
from aisbox.errors import AisboxError
from aisbox.models import DockerContainer, RetainedSession
from aisbox.store import EnvironmentStore
from aisbox.validation import validate_env_name


runner = CliRunner()


def hold_lifecycle_lock(aisbox_home, ready, release):
    os.environ["AISBOX_HOME"] = aisbox_home
    store = EnvironmentStore()
    with commands_module._lifecycle_lock("demo1", store):
        ready.set()
        if not release.wait(timeout=10):
            raise RuntimeError("timed out waiting to release lifecycle lock")


def setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    result = runner.invoke(app, ["create", "-n", "demo1", "-a", "claude", "-e", "TOKEN=abc"])
    assert result.exit_code == 0


def managed_container(
    *,
    environment: str = "demo1",
    agent: str = "claude",
    status: str = "running",
    name: str | None = None,
    container_id: str | None = None,
    labels: dict[str, str] | None = None,
) -> DockerContainer:
    return DockerContainer(
        container_id=container_id or f"sha256:{environment}",
        name=name or f"aisbox-{environment}",
        status=status,
        labels=labels
        or {
            "dev.aisbox.managed": "true",
            "dev.aisbox.environment": environment,
            "dev.aisbox.agent": agent,
        },
    )


def test_lifecycle_lock_creates_private_paths(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    store = EnvironmentStore()

    with commands_module._lifecycle_lock("demo1", store):
        lock_dir = store.root / commands_module._LIFECYCLE_LOCK_NAMESPACE
        lock_file = lock_dir / "demo1.lock"

        assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
        assert stat.S_IMODE(lock_dir.stat().st_mode) == 0o700
        assert stat.S_IMODE(lock_file.stat().st_mode) == 0o600


def test_lifecycle_lock_namespace_is_not_a_valid_environment_name():
    with pytest.raises(AisboxError):
        validate_env_name(commands_module._LIFECYCLE_LOCK_NAMESPACE)


def test_lifecycle_lock_releases_after_context_error(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    store = EnvironmentStore()

    with pytest.raises(RuntimeError, match="operation failed"):
        with commands_module._lifecycle_lock("demo1", store):
            raise RuntimeError("operation failed")

    with commands_module._lifecycle_lock("demo1", store):
        pass


@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="requires O_NOFOLLOW")
def test_lifecycle_lock_rejects_symlinked_lock_file(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    store = EnvironmentStore()
    lock_dir = store.root / commands_module._LIFECYCLE_LOCK_NAMESPACE
    lock_dir.mkdir(mode=0o700)
    external_file = tmp_path / "external.lock"
    external_file.write_text("unchanged", encoding="utf-8")
    (lock_dir / "demo1.lock").symlink_to(external_file)
    inspect_mock = Mock()
    monkeypatch.setattr("aisbox.commands.inspect_container", inspect_mock)

    with pytest.raises(
        AisboxError,
        match="Lifecycle lock could not be acquired for environment: demo1",
    ):
        attach_environment("demo1", store=store)

    inspect_mock.assert_not_called()
    assert external_file.read_text(encoding="utf-8") == "unchanged"


def test_deleting_dot_locks_environment_does_not_replace_active_lock(
    tmp_path, monkeypatch
):
    setup_env(tmp_path, monkeypatch)
    result = runner.invoke(app, ["create", "-n", ".locks", "-a", "claude"])
    assert result.exit_code == 0
    store = EnvironmentStore()
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    process = context.Process(
        target=hold_lifecycle_lock,
        args=(str(store.root), ready, release),
    )
    process.start()

    try:
        assert ready.wait(timeout=10), "lock holder did not become ready"
        monkeypatch.setattr("aisbox.commands.inspect_container", lambda name: None)

        delete_environment(".locks", store=store)

        with pytest.raises(
            AisboxError,
            match="Another lifecycle operation is active for environment: demo1",
        ):
            with commands_module._lifecycle_lock("demo1", store):
                pass
    finally:
        release.set()
        process.join(timeout=10)
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        if process.is_alive():
            process.kill()
            process.join(timeout=10)

    assert process.exitcode == 0
    with commands_module._lifecycle_lock("demo1", store):
        pass


@pytest.mark.parametrize(
    "operation",
    [
        lambda store: start_environment("demo1", keep=True, store=store),
        lambda store: attach_environment("demo1", store=store),
    ],
    ids=["start", "attach"],
)
def test_held_lifecycle_lock_blocks_retained_ensure_before_docker(
    tmp_path, monkeypatch, operation
):
    setup_env(tmp_path, monkeypatch)
    store = EnvironmentStore()
    load_mock = Mock(wraps=store.load)
    inspect_mock = Mock()
    run_mock = Mock()
    attach_mock = Mock()
    monkeypatch.setattr(store, "load", load_mock)
    monkeypatch.setattr("aisbox.commands.inspect_container", inspect_mock)
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)
    monkeypatch.setattr("aisbox.commands.attach_container", attach_mock)

    with commands_module._lifecycle_lock("demo1", store):
        with pytest.raises(
            AisboxError,
            match="Another lifecycle operation is active for environment: demo1",
        ):
            operation(store)

    load_mock.assert_not_called()
    inspect_mock.assert_not_called()
    run_mock.assert_not_called()
    attach_mock.assert_not_called()


def test_held_lifecycle_lock_blocks_delete_before_state_or_docker(
    tmp_path, monkeypatch
):
    setup_env(tmp_path, monkeypatch)
    store = EnvironmentStore()
    load_mock = Mock(wraps=store.load)
    delete_mock = Mock(wraps=store.delete)
    inspect_mock = Mock()
    monkeypatch.setattr(store, "load", load_mock)
    monkeypatch.setattr(store, "delete", delete_mock)
    monkeypatch.setattr("aisbox.commands.inspect_container", inspect_mock)

    with commands_module._lifecycle_lock("demo1", store):
        with pytest.raises(AisboxError) as exc_info:
            delete_environment("demo1", store=store)

    message = str(exc_info.value)
    assert "Another lifecycle operation is active for environment: demo1" in message
    assert "aisbox kill -n demo1" in message
    load_mock.assert_not_called()
    delete_mock.assert_not_called()
    inspect_mock.assert_not_called()


def test_kill_remains_callable_while_lifecycle_lock_is_held(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    store = EnvironmentStore()
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(),
    )
    remove_mock = Mock()
    monkeypatch.setattr("aisbox.commands.remove_container", remove_mock)

    with commands_module._lifecycle_lock("demo1", store):
        kill_session("demo1", store=store)

    remove_mock.assert_called_once_with("sha256:demo1")


def test_start_environment_without_keep_runs_disposable_start(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    run_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)

    start_environment("demo1", keep=False)

    assert run_mock.call_args.args[3] == "start"
    assert run_mock.call_args.kwargs == {}


def test_retained_start_creates_missing_session(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr("aisbox.commands.inspect_container", lambda name: None)
    run_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)

    start_environment("demo1", keep=True)

    assert run_mock.call_args.args[3] == "start"
    assert run_mock.call_args.kwargs == {"retained": True}


def test_attach_joins_running_retained_session(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(),
    )
    attach_mock = Mock()
    monkeypatch.setattr("aisbox.commands.attach_container", attach_mock)

    attach_environment("demo1")

    attach_mock.assert_called_once_with("sha256:demo1")


def test_attach_replaces_stopped_retained_session(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(status="exited"),
    )
    remove_mock = Mock()
    run_mock = Mock()
    monkeypatch.setattr("aisbox.commands.remove_container", remove_mock)
    monkeypatch.setattr("aisbox.commands.run_container", run_mock)

    attach_environment("demo1")

    remove_mock.assert_called_once_with("sha256:demo1")
    assert run_mock.call_args.args[3] == "start"
    assert run_mock.call_args.kwargs == {"retained": True}


@pytest.mark.parametrize(
    "container",
    [
        DockerContainer(
            container_id="sha256:unmanaged",
            name="aisbox-demo1",
            status="running",
            labels={},
        ),
        managed_container(name="not-aisbox-demo1"),
        managed_container(
            labels={
                "dev.aisbox.managed": "true",
                "dev.aisbox.environment": "other",
                "dev.aisbox.agent": "claude",
            }
        ),
        managed_container(
            labels={
                "dev.aisbox.managed": "true",
                "dev.aisbox.environment": "demo1",
                "dev.aisbox.agent": "codex",
            }
        ),
    ],
)
def test_attach_rejects_unowned_name_collision(
    tmp_path, monkeypatch, container
):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: container,
    )
    attach_mock = Mock()
    remove_mock = Mock()
    monkeypatch.setattr("aisbox.commands.attach_container", attach_mock)
    monkeypatch.setattr("aisbox.commands.remove_container", remove_mock)

    with pytest.raises(AisboxError, match="not managed by aisbox"):
        attach_environment("demo1")

    attach_mock.assert_not_called()
    remove_mock.assert_not_called()


def test_list_sessions_returns_only_valid_running_sessions(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    create = runner.invoke(app, ["create", "-n", "demo2", "-a", "codex"])
    assert create.exit_code == 0
    monkeypatch.setattr(
        "aisbox.commands.list_retained_containers",
        lambda: [
            managed_container(environment="demo2", agent="codex"),
            managed_container(),
            managed_container(environment="demo1", status="exited"),
            managed_container(environment="missing"),
            managed_container(environment="demo2", agent="claude"),
            managed_container(environment="demo2", agent="codex", name="other"),
            managed_container(labels={"dev.aisbox.managed": "true"}),
            managed_container(
                labels={
                    "dev.aisbox.managed": "false",
                    "dev.aisbox.environment": "demo1",
                    "dev.aisbox.agent": "claude",
                }
            ),
        ],
    )

    sessions = list_sessions()

    assert [
        (item.environment, item.agent, item.container, item.status)
        for item in sessions
    ] == [
        ("demo1", "claude", "aisbox-demo1", "running"),
        ("demo2", "codex", "aisbox-demo2", "running"),
    ]


def test_list_sessions_does_not_translate_store_json_failure_as_docker_failure(
    tmp_path, monkeypatch
):
    setup_env(tmp_path, monkeypatch)
    store = EnvironmentStore()
    state_file = store.env_dir("demo1") / "environment.json"
    state_file.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(
        "aisbox.commands.list_retained_containers",
        lambda: [managed_container()],
    )

    with pytest.raises(json.JSONDecodeError) as exc_info:
        list_sessions(store=store)

    assert "Docker session listing failed" not in str(exc_info.value)


@pytest.mark.parametrize("status", ["running", "exited"])
def test_kill_removes_owned_running_or_stopped_container(
    tmp_path, monkeypatch, status
):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(status=status),
    )
    remove_mock = Mock()
    monkeypatch.setattr("aisbox.commands.remove_container", remove_mock)

    kill_session("demo1")

    remove_mock.assert_called_once_with("sha256:demo1")


def test_kill_errors_when_retained_container_is_missing(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr("aisbox.commands.inspect_container", lambda name: None)

    with pytest.raises(AisboxError, match="No retained session"):
        kill_session("demo1")


def test_attach_translates_docker_inspection_failure(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: (_ for _ in ()).throw(
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["docker", "container", "inspect", name],
            )
        ),
    )

    with pytest.raises(
        AisboxError,
        match="Docker retained session operation failed for environment: demo1",
    ):
        attach_environment("demo1")


@pytest.mark.parametrize("status", ["running", "exited"])
def test_delete_refuses_when_owned_retained_container_exists(
    tmp_path, monkeypatch, status
):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.commands.inspect_container",
        lambda name: managed_container(status=status),
    )

    with pytest.raises(AisboxError, match=r"aisbox kill -n demo1"):
        delete_environment("demo1")


def test_run_builds_non_interactive_docker_command(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo1", "--", "hello"])

    assert result.exit_code == 0
    env, agent, config_source, mode, prompt = runner_mock.call_args.args
    assert env.name == "demo1"
    assert agent.name == "claude"
    assert config_source.endswith("/config")
    assert mode == "run"
    assert prompt == "hello"


def test_run_without_prompt_passes_none(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo1"])

    assert result.exit_code == 0
    assert runner_mock.call_args.args[4] is None


def test_run_uses_default_environment_when_name_omitted(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner.invoke(app, ["set", "default", "-n", "demo1"])
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "--", "hello"])

    assert result.exit_code == 0
    env, agent, config_source, mode, prompt = runner_mock.call_args.args
    assert env.name == "demo1"
    assert agent.name == "claude"
    assert config_source.endswith("/config")
    assert mode == "run"
    assert prompt == "hello"


def test_run_explicit_name_overrides_default_environment(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    runner.invoke(app, ["create", "-n", "demo2", "-a", "claude"])
    runner.invoke(app, ["set", "default", "-n", "demo1"])
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    result = runner.invoke(app, ["run", "-n", "demo2", "--", "hello"])

    assert result.exit_code == 0
    env = runner_mock.call_args.args[0]
    assert env.name == "demo2"


def test_start_and_shell_use_disposable_interactive_modes(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    start_mock = Mock()
    runner_mock = Mock()
    monkeypatch.setattr("aisbox.cli.start_environment", start_mock)
    monkeypatch.setattr("aisbox.commands.run_container", runner_mock)

    started = runner.invoke(app, ["start", "-n", "demo1"])
    shell = runner.invoke(app, ["shell", "-n", "demo1"])

    assert started.exit_code == 0
    assert shell.exit_code == 0
    assert started.stdout == ""
    start_mock.assert_called_once_with("demo1", False)
    assert runner_mock.call_args.args[3] == "shell"


def test_retained_commands_print_guidance_and_invoke_lifecycle(
    tmp_path, monkeypatch
):
    setup_env(tmp_path, monkeypatch)
    start_mock = Mock()
    attach_mock = Mock()
    monkeypatch.setattr("aisbox.cli.start_environment", start_mock)
    monkeypatch.setattr("aisbox.cli.attach_environment", attach_mock)

    started = runner.invoke(app, ["start", "-n", "demo1", "--keep"])
    attached = runner.invoke(app, ["attach", "-n", "demo1"])

    guidance = (
        "Detach without stopping: Ctrl-p Ctrl-q. "
        "Ctrl-c may stop the agent and session."
    )
    assert started.exit_code == 0
    assert attached.exit_code == 0
    assert started.stdout.strip() == guidance
    assert attached.stdout.strip() == guidance
    start_mock.assert_called_once_with("demo1", True)
    attach_mock.assert_called_once_with("demo1")


def test_retained_command_help_describes_session_behavior():
    expectations = [
        (["start", "--help"], "Start an interactive agent."),
        (["start", "--help"], "retained session"),
        (["attach", "--help"], "retained agent session"),
        (["attach", "--help"], "starting one when needed"),
        (["sessions", "--help"], "running retained agent sessions"),
        (["kill", "--help"], "Stop and remove a retained agent session."),
    ]

    for args, expected in expectations:
        result = runner.invoke(app, args, terminal_width=120)
        normalized = " ".join(result.stdout.replace("│", " ").split())

        assert result.exit_code == 0
        assert expected in normalized


def test_sessions_lists_rows_and_handles_empty_results(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "aisbox.cli.list_sessions",
        lambda: [
            RetainedSession(
                environment="demo1",
                agent="claude",
                container="aisbox-demo1",
                status="running",
            )
        ],
    )

    listed = runner.invoke(app, ["sessions"])

    assert listed.exit_code == 0
    assert listed.stdout.strip() == "demo1\tclaude\taisbox-demo1\trunning"

    monkeypatch.setattr("aisbox.cli.list_sessions", lambda: [])
    empty = runner.invoke(app, ["sessions"])

    assert empty.exit_code == 0
    assert empty.stdout.strip() == "No retained sessions found"


def test_kill_uses_explicit_environment_and_reports_success(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    kill_mock = Mock()
    monkeypatch.setattr("aisbox.cli.kill_session", kill_mock)

    result = runner.invoke(app, ["kill", "-n", "demo1"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Killed retained session for demo1"
    kill_mock.assert_called_once_with("demo1")


def test_kill_uses_default_environment_when_name_is_omitted(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    runner.invoke(app, ["set", "default", "-n", "demo1"])
    kill_mock = Mock()
    monkeypatch.setattr("aisbox.cli.kill_session", kill_mock)

    result = runner.invoke(app, ["kill"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "Killed retained session for demo1"
    kill_mock.assert_called_once_with("demo1")


@pytest.mark.parametrize(
    ("args", "target"),
    [
        (["start", "-n", "demo1"], "start_environment"),
        (["attach", "-n", "demo1"], "attach_environment"),
        (["sessions"], "list_sessions"),
        (["kill", "-n", "demo1"], "kill_session"),
    ],
)
def test_retained_cli_errors_do_not_emit_tracebacks(
    tmp_path, monkeypatch, args, target
):
    setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(
        f"aisbox.cli.{target}",
        lambda *arguments: (_ for _ in ()).throw(AisboxError("retained failure")),
    )

    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "Error: retained failure" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("command", ["start", "attach", "kill"])
def test_retained_environment_commands_without_name_or_default_error_cleanly(
    tmp_path, monkeypatch, command
):
    monkeypatch.setenv("AISBOX_HOME", str(tmp_path / "aisbox-home"))

    result = runner.invoke(app, [command])

    assert result.exit_code == 1
    assert "No environment specified and no default environment is set" in result.stderr
    assert "Traceback" not in result.stderr


def test_rebuild_invokes_image_build_for_stored_agent(tmp_path, monkeypatch):
    setup_env(tmp_path, monkeypatch)
    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    result = runner.invoke(app, ["rebuild", "-n", "demo1"])

    assert result.exit_code == 0
    assert "Rebuilt demo1" in result.stdout
    assert build_mock.call_args.args[0].name == "claude"
