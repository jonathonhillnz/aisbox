# aisbox

`aisbox` runs AI coding agents inside isolated Docker environments.

Each environment stores its own config and files under `~/.aisbox/<name>`.
Set `AISBOX_HOME` to use a different state directory.
Host `~/.claude` and `~/.codex` directories are not copied or mounted.
Docker must be usable by the current user. `aisbox` does not run Docker through `sudo`.

## Install From This Repository

```bash
pipx install .
```

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Commands

```bash
aisbox create -n demo1 -a claude -e ANTHROPIC_API_KEY=value
aisbox create -n demo1 -a codex --workspace /path/to/source
aisbox run -n demo1 -- "summarize this repository"
aisbox attach -n demo1
aisbox shell -n demo1
aisbox list
aisbox inspect -n demo1
aisbox rebuild -n demo1
aisbox mount -n demo1 /path/to/dir dir
aisbox unmount -n demo1 dir
aisbox env set -n demo1 KEY=VALUE
aisbox env unset -n demo1 KEY
aisbox doctor
aisbox delete -n demo1 --force
```

## Authentication

Authenticate interactively inside the container with `aisbox attach -n demo1`,
or provide explicit API tokens with `-e KEY=VALUE` during create and
`aisbox env set` after creation.
