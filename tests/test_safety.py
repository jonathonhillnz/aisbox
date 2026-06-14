from pathlib import Path

import pytest

from aisbox.safety import SENSITIVE_HOME_PATHS, find_sensitive_path_matches


EXPECTED_SENSITIVE_HOME_PATHS = (
    Path(".ssh"),
    Path(".gnupg"),
    Path(".aws"),
    Path(".azure"),
    Path(".config/gcloud"),
    Path(".kube"),
    Path(".docker"),
    Path(".claude"),
    Path(".codex"),
    Path(".config/opencode"),
    Path(".local/share/opencode"),
    Path(".local/state/opencode"),
)


def test_sensitive_home_paths_contains_exact_policy_paths():
    assert SENSITIVE_HOME_PATHS == EXPECTED_SENSITIVE_HOME_PATHS


@pytest.mark.parametrize("relative_path", EXPECTED_SENSITIVE_HOME_PATHS)
def test_matches_each_exact_sensitive_path(tmp_path, relative_path):
    home = tmp_path / "home"
    sensitive_path = home / relative_path

    assert find_sensitive_path_matches(sensitive_path, home=home) == (
        sensitive_path.resolve(),
    )


def test_matches_descendant_of_sensitive_path(tmp_path):
    home = tmp_path / "home"
    candidate = home / ".ssh" / "keys" / "id_ed25519"

    assert find_sensitive_path_matches(candidate, home=home) == (
        (home / ".ssh").resolve(),
    )


@pytest.mark.parametrize("ancestor", (Path("."), Path("/")))
def test_matches_sensitive_paths_below_ancestor(tmp_path, ancestor):
    home = tmp_path / "home"
    candidate = home if ancestor == Path(".") else ancestor
    expected = tuple(sorted((home / path).resolve() for path in SENSITIVE_HOME_PATHS))

    assert find_sensitive_path_matches(candidate, home=home) == expected


@pytest.mark.parametrize(
    "relative_path",
    (Path(".ssh-backup"), Path(".config/gcloud-backup"), Path(".config/example")),
)
def test_does_not_match_safe_sibling(tmp_path, relative_path):
    home = tmp_path / "home"

    assert find_sensitive_path_matches(home / relative_path, home=home) == ()


def test_expands_user_before_matching(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))

    assert find_sensitive_path_matches("~/.ssh", home=Path("~")) == (
        (home / ".ssh").resolve(),
    )


def test_resolves_home_symlink_before_matching_policy_paths(tmp_path):
    resolved_home = tmp_path / "resolved-home"
    resolved_home.mkdir()
    home = tmp_path / "home-link"
    home.symlink_to(resolved_home, target_is_directory=True)
    sensitive_path = resolved_home / ".ssh"

    assert find_sensitive_path_matches(sensitive_path, home=home) == (
        sensitive_path.resolve(),
    )


def test_resolves_candidate_symlink_to_exact_sensitive_path(tmp_path):
    home = tmp_path / "home"
    sensitive_path = home / ".ssh"
    sensitive_path.mkdir(parents=True)
    candidate = tmp_path / "exact-link"
    candidate.symlink_to(sensitive_path, target_is_directory=True)

    assert find_sensitive_path_matches(candidate, home=home) == (
        sensitive_path.resolve(),
    )


def test_resolves_candidate_symlink_to_sensitive_descendant(tmp_path):
    home = tmp_path / "home"
    sensitive_path = home / ".ssh"
    descendant = sensitive_path / "keys"
    descendant.mkdir(parents=True)
    candidate = tmp_path / "descendant-link"
    candidate.symlink_to(descendant, target_is_directory=True)

    assert find_sensitive_path_matches(candidate, home=home) == (
        sensitive_path.resolve(),
    )


def test_resolves_candidate_symlink_to_sensitive_ancestor(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    candidate = tmp_path / "ancestor-link"
    candidate.symlink_to(home, target_is_directory=True)
    expected = tuple(sorted((home / path).resolve() for path in SENSITIVE_HOME_PATHS))

    assert find_sensitive_path_matches(candidate, home=home) == expected


def test_matches_resolved_policy_symlink_target(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    target = tmp_path / "ssh-secrets"
    target.mkdir()
    (home / ".ssh").symlink_to(target, target_is_directory=True)

    assert find_sensitive_path_matches(target, home=home) == (target.resolve(),)


def test_deduplicates_policy_paths_resolving_to_same_target(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    target = tmp_path / "shared-secrets"
    target.mkdir()
    (home / ".ssh").symlink_to(target, target_is_directory=True)
    (home / ".gnupg").symlink_to(target, target_is_directory=True)

    assert find_sensitive_path_matches(target, home=home) == (target.resolve(),)
