# Authentication

Agents need API credentials to call their respective LLM providers.
`aisbox` provides several ways to supply credentials, with different
trade-offs between convenience and exposure.

!!! warning
    All values provided through `-e` or `aisbox env set` are stored unencrypted
    in `<state-root>/<name>/environment.json`. Managed state directories use
    mode `0700` and state files use mode `0600`, but credentials remain stored
    as plain text on disk. Protect `AISBOX_HOME` and do not share tokens in
    logs or reports.

## Interactive authentication via `start`

The safest path: launch an interactive session and authenticate inside the
container.

```bash
aisbox start -n <name>
```

Once inside, follow the agent's normal authentication flow.

## Hidden-prompt environment variables

Use an empty assignment with `-e` to enter a value at a hidden prompt. The
value is never displayed and stays out of shell history:

```bash
aisbox create -n <name> -a claude -e ANTHROPIC_API_KEY=
aisbox env set -n <name> -e OPENAI_API_KEY=
```

An assignment ending in `=` (such as `OPENAI_API_KEY=`) opens one hidden
prompt. Press Enter at that prompt to store an empty value. Prompted values
stay out of shell history and normal command-line process inspection.

## Explicit environment variables

Explicit values are also supported and options can be repeated:

```bash
aisbox create -n <name> -a claude -e LOG_LEVEL=debug
aisbox env set -n <name> -e LOG_LEVEL=debug -e FEATURE_FLAG=enabled
```

!!! warning
    Explicit non-empty values on the command line may remain in shell history
    and, depending on the host, may be observable to local processes or users.
    Prefer interactive authentication or the hidden-prompt flow for secrets.

## Managing environment variables after creation

Set additional variables:

```bash
aisbox env set -n <name> -e OPENAI_API_KEY=
```

Remove variables:

```bash
aisbox env unset -n <name> -e LOG_LEVEL -e FEATURE_FLAG
```

## OpenCode authentication

OpenCode has its own provider configuration system. Start the TUI and run
`/connect`:

```bash
aisbox start -n <name>
```

Use `/connect` to configure OpenCode Zen or another supported provider.

OpenCode also recognizes provider credentials supplied through the
environment:

```bash
aisbox create -n <name> -a opencode -e ANTHROPIC_API_KEY=
aisbox env set -n <name> -e OPENAI_API_KEY=
```

OpenCode supports many providers. Its `opencode.json` configuration can
reference any environment variable supplied to the container using
`{env:NAME}`. Consult the OpenCode provider documentation for
provider-specific requirements.

## Inspect masks values

`aisbox inspect` shows which keys are set but masks their values:

```
ANTHROPIC_API_KEY=<set>
OPENAI_API_KEY=<set>
```

Values are never printed in plain text by `aisbox inspect`.
