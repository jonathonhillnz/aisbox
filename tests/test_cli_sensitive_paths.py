from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from aisbox import cli
from aisbox.cli import app
from aisbox.store import EnvironmentStore


runner = CliRunner()


@pytest.fixture
def test_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    aisbox_home = tmp_path / "aisbox-home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AISBOX_HOME", str(aisbox_home))
    return home, aisbox_home


def test_supplied_host_paths_lists_workspace_before_mounts():
    assert cli.supplied_host_paths(
        "workspace",
        [("source-one", "src"), ("source-two", "cache")],
    ) == [
        ("workspace", "workspace"),
        ("mount src", "source-one"),
        ("mount cache", "source-two"),
    ]


def test_safe_create_workspace_does_not_warn_or_prompt_and_builds_once(
    tmp_path, monkeypatch, test_home
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    result = runner.invoke(
        app,
        [
            "create",
            "-n",
            "demo1",
            "-a",
            "claude",
            "--workspace",
            str(workspace),
        ],
    )

    assert result.exit_code == 0
    assert "Warning:" not in result.stderr
    assert "Continue?" not in result.stderr
    assert "Warning:" not in result.stdout
    assert "Continue?" not in result.stdout
    assert "Created demo1" in result.stdout
    build_mock.assert_called_once()
    assert EnvironmentStore().exists("demo1")


def test_sensitive_create_workspace_defaults_no_without_state_or_build(
    monkeypatch, test_home
):
    home, aisbox_home = test_home
    workspace = home / ".ssh"
    workspace.mkdir()
    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    result = runner.invoke(
        app,
        [
            "create",
            "-n",
            "demo1",
            "-a",
            "claude",
            "-e",
            "TOKEN=",
            "--workspace",
            str(workspace),
        ],
        input="\n",
    )

    assert result.exit_code == 1
    assert result.stderr.count("Warning:") == 1
    assert f"workspace: {workspace.resolve()}" in result.stderr
    assert f"matched sensitive path: {workspace.resolve()}" in result.stderr
    assert "read/write access" in result.stderr
    assert "credentials" in result.stderr
    assert "sensitive data" in result.stderr
    assert "Continue?" in result.stderr
    assert "Value for TOKEN" not in result.stderr
    assert "Warning:" not in result.stdout
    assert "Continue?" not in result.stdout
    assert "Value for TOKEN" not in result.stdout
    assert "Created demo1" not in result.stdout
    assert "Traceback" not in result.stderr
    assert not aisbox_home.exists()
    assert not EnvironmentStore().exists("demo1")
    build_mock.assert_not_called()


def test_sensitive_create_workspace_eof_exits_cleanly_without_state_or_build(
    monkeypatch, test_home
):
    home, aisbox_home = test_home
    workspace = home / ".ssh"
    workspace.mkdir()
    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    result = runner.invoke(
        app,
        [
            "create",
            "-n",
            "demo1",
            "-a",
            "claude",
            "--workspace",
            str(workspace),
        ],
        input="",
    )

    assert result.exit_code == 1
    assert result.stderr.count("Warning:") == 1
    assert "Continue?" in result.stderr
    assert "Warning:" not in result.stdout
    assert "Continue?" not in result.stdout
    assert "Created demo1" not in result.stdout
    assert "Traceback" not in result.stderr
    assert not aisbox_home.exists()
    assert not EnvironmentStore().exists("demo1")
    build_mock.assert_not_called()


def test_sensitive_create_workspace_explicit_yes_permits_creation(
    monkeypatch, test_home
):
    home, _ = test_home
    workspace = home / ".ssh"
    workspace.mkdir()
    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    result = runner.invoke(
        app,
        [
            "create",
            "-n",
            "demo1",
            "-a",
            "claude",
            "--workspace",
            str(workspace),
        ],
        input="y\n",
    )

    assert result.exit_code == 0
    assert result.stderr.count("Warning:") == 1
    assert "Continue?" in result.stderr
    assert "Warning:" not in result.stdout
    assert "Continue?" not in result.stdout
    assert "Created demo1" in result.stdout
    build_mock.assert_called_once()
    assert EnvironmentStore().exists("demo1")


def test_sensitive_create_workspace_yes_option_skips_prompt_but_warns(
    monkeypatch, test_home
):
    home, _ = test_home
    workspace = home / ".ssh"
    workspace.mkdir()
    build_mock = Mock()
    monkeypatch.setattr("aisbox.commands.build_image", build_mock)

    result = runner.invoke(
        app,
        [
            "create",
            "-n",
            "demo1",
            "-a",
            "claude",
            "--workspace",
            str(workspace),
            "--yes",
        ],
        input="",
    )

    assert result.exit_code == 0
    assert result.stderr.count("Warning:") == 1
    assert f"workspace: {workspace.resolve()}" in result.stderr
    assert f"matched sensitive path: {workspace.resolve()}" in result.stderr
    assert "read/write access" in result.stderr
    assert "credentials" in result.stderr
    assert "sensitive data" in result.stderr
    assert "Continue?" not in result.stderr
    assert "Warning:" not in result.stdout
    assert "Continue?" not in result.stdout
    assert "Created demo1" in result.stdout
    build_mock.assert_called_once()
    assert EnvironmentStore().exists("demo1")


def test_create_forwards_resolved_workspace_used_for_sensitive_assessment(
    monkeypatch, test_home
):
    home, _ = test_home
    target = home / ".ssh"
    target.mkdir()
    link = home / "workspace-link"
    link.symlink_to(target, target_is_directory=True)
    create_mock = Mock(return_value=Mock(name="demo1"))
    monkeypatch.setattr("aisbox.cli.create_environment", create_mock)

    result = runner.invoke(
        app,
        [
            "create",
            "-n",
            "demo1",
            "-a",
            "claude",
            "--workspace",
            str(link),
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert f"workspace: {target.resolve()}" in result.stderr
    create_mock.assert_called_once_with(
        "demo1",
        "claude",
        [],
        str(target.resolve()),
    )


def test_sensitive_persistent_mount_defaults_no_without_state_mutation(
    monkeypatch, test_home
):
    home, _ = test_home
    source = home / ".ssh"
    source.mkdir()
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    created = runner.invoke(
        app,
        ["create", "-n", "demo1", "-a", "claude"],
    )
    assert created.exit_code == 0
    add_mount_mock = Mock()
    monkeypatch.setattr("aisbox.cli.add_mount", add_mount_mock)

    result = runner.invoke(
        app,
        ["mount", "-n", "demo1", str(source), "credentials"],
        input="\n",
    )

    assert result.exit_code == 1
    assert result.stderr.count("Warning:") == 1
    assert f"mount credentials: {source.resolve()}" in result.stderr
    assert "Continue?" in result.stderr
    assert "Warning:" not in result.stdout
    assert "Continue?" not in result.stdout
    assert EnvironmentStore().load("demo1").mounts == []
    add_mount_mock.assert_not_called()


def test_sensitive_persistent_mount_yes_saves_resolved_mount_without_prompt(
    monkeypatch, test_home
):
    home, _ = test_home
    source = home / ".ssh"
    source.mkdir()
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    created = runner.invoke(
        app,
        ["create", "-n", "demo1", "-a", "claude"],
    )
    assert created.exit_code == 0

    result = runner.invoke(
        app,
        [
            "mount",
            "-n",
            "demo1",
            str(source),
            "credentials",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert result.stderr.count("Warning:") == 1
    assert f"mount credentials: {source.resolve()}" in result.stderr
    assert "Continue?" not in result.stderr
    stored_mount = EnvironmentStore().load("demo1").mounts[0]
    assert stored_mount.source == str(source.resolve())
    assert stored_mount.alias == "credentials"


def test_persistent_mount_forwards_resolved_source_used_for_assessment(
    monkeypatch, test_home
):
    home, _ = test_home
    target = home / ".ssh"
    target.mkdir()
    link = home / "mount-link"
    link.symlink_to(target, target_is_directory=True)
    create_test_environment(monkeypatch)
    add_mount_mock = Mock(return_value=Mock(alias="credentials"))
    monkeypatch.setattr("aisbox.cli.add_mount", add_mount_mock)

    result = runner.invoke(
        app,
        [
            "mount",
            "-n",
            "demo1",
            str(link),
            "credentials",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert f"mount credentials: {target.resolve()}" in result.stderr
    add_mount_mock.assert_called_once_with(
        "demo1",
        str(target.resolve()),
        "credentials",
    )


def create_test_environment(monkeypatch, *, workspace=None):
    monkeypatch.setattr("aisbox.commands.build_image", lambda agent: None)
    args = ["create", "-n", "demo1", "-a", "claude"]
    if workspace is not None:
        args.extend(["--workspace", str(workspace), "--yes"])
    result = runner.invoke(app, args)
    assert result.exit_code == 0


@pytest.mark.parametrize(
    ("command", "runtime_name"),
    [
        ("run", "run_environment"),
        ("start", "start_environment"),
        ("attach", "attach_environment"),
    ],
)
def test_runtime_commands_forward_resolved_overrides_used_for_assessment(
    monkeypatch, test_home, command, runtime_name
):
    home, _ = test_home
    workspace_target = home / ".ssh"
    mount_target = home / ".aws"
    workspace_target.mkdir()
    mount_target.mkdir()
    workspace_link = home / "workspace-link"
    mount_link = home / "mount-link"
    workspace_link.symlink_to(workspace_target, target_is_directory=True)
    mount_link.symlink_to(mount_target, target_is_directory=True)
    create_test_environment(monkeypatch)
    runtime_mock = Mock()
    monkeypatch.setattr(f"aisbox.cli.{runtime_name}", runtime_mock)
    args = [
        command,
        "-n",
        "demo1",
        "--workspace",
        str(workspace_link),
        "--mount",
        str(mount_link),
        "credentials",
        "--yes",
    ]
    if command == "run":
        args.extend(["--", "hello"])

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert f"workspace: {workspace_target.resolve()}" in result.stderr
    assert f"mount credentials: {mount_target.resolve()}" in result.stderr
    expected_kwargs = {
        "workspace": str(workspace_target.resolve()),
        "mounts": [(str(mount_target.resolve()), "credentials")],
    }
    if command == "run":
        runtime_mock.assert_called_once_with(
            "demo1",
            "run",
            "hello",
            permission_policy="default",
            **expected_kwargs,
        )
    elif command == "start":
        runtime_mock.assert_called_once_with(
            "demo1",
            False,
            **expected_kwargs,
        )
    else:
        runtime_mock.assert_called_once_with("demo1", **expected_kwargs)


@pytest.mark.parametrize(
    ("command", "runtime_name"),
    [
        ("run", "run_environment"),
        ("start", "start_environment"),
        ("attach", "attach_environment"),
    ],
)
def test_temporary_sensitive_workspace_decline_does_not_invoke_runtime(
    monkeypatch, test_home, command, runtime_name
):
    home, _ = test_home
    workspace = home / ".ssh"
    workspace.mkdir()
    create_test_environment(monkeypatch)
    runtime_mock = Mock()
    monkeypatch.setattr(f"aisbox.cli.{runtime_name}", runtime_mock)

    result = runner.invoke(
        app,
        [command, "-n", "demo1", "--workspace", str(workspace)],
        input="\n",
    )

    assert result.exit_code == 1
    assert result.stderr.count("Warning:") == 1
    assert f"workspace: {workspace.resolve()}" in result.stderr
    assert result.stderr.count("Continue?") == 1
    assert "Warning:" not in result.stdout
    assert "Continue?" not in result.stdout
    assert "Detach without stopping" not in result.stdout
    runtime_mock.assert_not_called()


@pytest.mark.parametrize(
    ("command", "runtime_name"),
    [
        ("run", "run_environment"),
        ("start", "start_environment"),
        ("attach", "attach_environment"),
    ],
)
def test_temporary_sensitive_mount_yes_invokes_runtime_without_prompt(
    monkeypatch, test_home, command, runtime_name
):
    home, _ = test_home
    source = home / ".ssh"
    source.mkdir()
    create_test_environment(monkeypatch)
    runtime_mock = Mock()
    monkeypatch.setattr(f"aisbox.cli.{runtime_name}", runtime_mock)
    args = [
        command,
        "-n",
        "demo1",
        "--mount",
        str(source),
        "credentials",
        "--yes",
    ]
    if command == "run":
        args.extend(["--", "hello"])

    result = runner.invoke(app, args)

    assert result.exit_code == 0
    assert result.stderr.count("Warning:") == 1
    assert f"mount credentials: {source.resolve()}" in result.stderr
    assert "Continue?" not in result.stderr
    assert "Warning:" not in result.stdout
    assert "Continue?" not in result.stdout
    runtime_mock.assert_called_once()


def test_run_multiple_sensitive_paths_warns_and_prompts_once(
    monkeypatch, test_home
):
    home, _ = test_home
    source = home / ".ssh"
    source.mkdir()
    create_test_environment(monkeypatch)
    runtime_mock = Mock()
    monkeypatch.setattr("aisbox.cli.run_environment", runtime_mock)

    result = runner.invoke(
        app,
        [
            "run",
            "-n",
            "demo1",
            "--workspace",
            str(home),
            "--mount",
            str(source),
            "credentials",
            "--",
            "hello",
        ],
        input="y\n",
    )

    assert result.exit_code == 0
    assert result.stderr.count("Warning:") == 1
    assert result.stderr.count("Continue?") == 1
    assert f"workspace: {home.resolve()}" in result.stderr
    assert f"mount credentials: {source.resolve()}" in result.stderr
    assert "Warning:" not in result.stdout
    assert "Continue?" not in result.stdout
    runtime_mock.assert_called_once()


def test_run_yes_after_temporary_mount_preserves_prompt_tokens(
    monkeypatch, test_home
):
    home, _ = test_home
    source = home / ".ssh"
    source.mkdir()
    create_test_environment(monkeypatch)
    runtime_mock = Mock()
    monkeypatch.setattr("aisbox.cli.run_environment", runtime_mock)

    result = runner.invoke(
        app,
        [
            "run",
            "-n",
            "demo1",
            "--mount",
            str(source),
            "credentials",
            "--yes",
            "--",
            "hello",
        ],
    )

    assert result.exit_code == 0
    assert "Continue?" not in result.stderr
    runtime_mock.assert_called_once_with(
        "demo1",
        "run",
        "hello",
        workspace=None,
        mounts=[(str(source), "credentials")],
        permission_policy="default",
    )


@pytest.mark.parametrize(
    ("command_args", "runtime_name"),
    [
        (["start", "--keep"], "start_environment"),
        (["attach"], "attach_environment"),
    ],
)
def test_declined_retained_command_does_not_print_detach_guidance(
    monkeypatch, test_home, command_args, runtime_name
):
    home, _ = test_home
    workspace = home / ".ssh"
    workspace.mkdir()
    create_test_environment(monkeypatch)
    runtime_mock = Mock()
    monkeypatch.setattr(f"aisbox.cli.{runtime_name}", runtime_mock)

    result = runner.invoke(
        app,
        [*command_args, "-n", "demo1", "--workspace", str(workspace)],
        input="\n",
    )

    assert result.exit_code == 1
    assert "Continue?" in result.stderr
    assert "Detach without stopping" not in result.stdout
    runtime_mock.assert_not_called()


@pytest.mark.parametrize(
    ("command", "runtime_name"),
    [
        ("start", "start_environment"),
        ("attach", "attach_environment"),
    ],
)
def test_interactive_unexpected_argument_is_rejected_before_sensitive_prompt(
    monkeypatch, test_home, command, runtime_name
):
    home, _ = test_home
    source = home / ".ssh"
    source.mkdir()
    create_test_environment(monkeypatch)
    runtime_mock = Mock()
    monkeypatch.setattr(f"aisbox.cli.{runtime_name}", runtime_mock)

    result = runner.invoke(
        app,
        [
            command,
            "-n",
            "demo1",
            "--mount",
            str(source),
            "credentials",
            "unexpected",
        ],
    )

    assert result.exit_code == 1
    assert "Unexpected argument: unexpected" in result.stderr
    assert "Warning:" not in result.stderr
    assert "Continue?" not in result.stderr
    assert "Detach without stopping" not in result.stdout
    runtime_mock.assert_not_called()


@pytest.mark.parametrize(
    ("command", "runtime_name"),
    [
        ("run", "run_environment"),
        ("start", "start_environment"),
        ("attach", "attach_environment"),
        ("shell", "run_environment"),
    ],
)
def test_stored_sensitive_workspace_does_not_reprompt(
    monkeypatch, test_home, command, runtime_name
):
    home, _ = test_home
    workspace = home / ".ssh"
    workspace.mkdir()
    create_test_environment(monkeypatch, workspace=workspace)
    runtime_mock = Mock()
    monkeypatch.setattr(f"aisbox.cli.{runtime_name}", runtime_mock)

    result = runner.invoke(app, [command, "-n", "demo1"])

    assert result.exit_code == 0
    assert "Warning:" not in result.stderr
    assert "Continue?" not in result.stderr
    runtime_mock.assert_called_once()
