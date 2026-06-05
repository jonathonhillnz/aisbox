# aienv

`aienv` runs AI coding agents inside isolated Docker environments.

Each environment stores its own config and files under `~/.aienv/<name>`.
Host `~/.claude` and `~/.codex` directories are not copied or mounted.
Docker must be usable by the current user. `aienv` does not run Docker through `sudo`.

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
aienv create -n demo1 -a claude -e ANTHROPIC_API_KEY=value
aienv create -n demo1 -a codex --workspace /path/to/source
aienv run -n demo1 -- "summarize this repository"
aienv attach -n demo1
aienv shell -n demo1
aienv list
aienv inspect -n demo1
aienv rebuild -n demo1
aienv mount -n demo1 /path/to/dir dir
aienv unmount -n demo1 dir
aienv env set -n demo1 KEY=VALUE
aienv env unset -n demo1 KEY
aienv doctor
aienv delete -n demo1 --force
```

## Authentication

Authenticate interactively inside the container with `aienv attach -n demo1`,
or provide explicit API tokens with `-e KEY=VALUE` during create and
`aienv env set` after creation.
