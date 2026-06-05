import pytest

from aienv.errors import AienvError
from aienv.validation import (
    parse_env_assignment,
    validate_env_name,
    validate_mount_alias,
)


@pytest.mark.parametrize("name", ["demo1", "demo-1", "demo_1", "demo.1"])
def test_validate_env_name_accepts_safe_names(name):
    assert validate_env_name(name) == name


@pytest.mark.parametrize("name", ["", ".", "..", "../demo", "demo/name", "demo name", "$demo"])
def test_validate_env_name_rejects_unsafe_names(name):
    with pytest.raises(AienvError):
        validate_env_name(name)


def test_parse_env_assignment():
    assert parse_env_assignment("TOKEN=abc=123") == ("TOKEN", "abc=123")


@pytest.mark.parametrize("assignment", ["TOKEN", "=value", "BAD-KEY=value", ""])
def test_parse_env_assignment_rejects_invalid_values(assignment):
    with pytest.raises(AienvError):
        parse_env_assignment(assignment)


@pytest.mark.parametrize("alias", ["src", "data_1", "repo-2", "repo.3"])
def test_validate_mount_alias_accepts_relative_name(alias):
    assert validate_mount_alias(alias) == alias


@pytest.mark.parametrize("alias", ["", "/src", "../src", "src/repo", "src..repo"])
def test_validate_mount_alias_rejects_path_like_values(alias):
    with pytest.raises(AienvError):
        validate_mount_alias(alias)
