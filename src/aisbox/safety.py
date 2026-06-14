from __future__ import annotations

from pathlib import Path


SENSITIVE_HOME_PATHS = (
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


def find_sensitive_path_matches(
    path: str | Path, *, home: Path | None = None
) -> tuple[Path, ...]:
    candidate = Path(path).expanduser().resolve()
    resolved_home = (home if home is not None else Path.home()).expanduser().resolve()
    matches: list[Path] = []
    seen: set[Path] = set()

    for relative_path in SENSITIVE_HOME_PATHS:
        sensitive_path = (resolved_home / relative_path).expanduser().resolve()
        overlaps = (
            candidate == sensitive_path
            or candidate.is_relative_to(sensitive_path)
            or sensitive_path.is_relative_to(candidate)
        )
        if overlaps and sensitive_path not in seen:
            matches.append(sensitive_path)
            seen.add(sensitive_path)

    return tuple(sorted(matches))
