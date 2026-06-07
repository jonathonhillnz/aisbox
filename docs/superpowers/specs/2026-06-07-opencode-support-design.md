# OpenCode Support Design

## Summary

`aisbox` will support OpenCode as a third agent with the same environment,
runtime, persistence, and lifecycle behavior as Claude Code and Codex CLI.
The integration will use the existing data-driven agent definition rather than
introducing OpenCode-specific orchestration.

The supported create value will be `opencode`.

## Goals

- Add full OpenCode parity across environment creation, non-interactive runs,
  disposable interactive sessions, retained sessions, shells, rebuilds,
  inspection, listing, session lifecycle commands, and doctor output.
- Build OpenCode into a local `aisbox/opencode:latest` image.
- Persist OpenCode configuration, credentials, and user state without exposing
  corresponding host directories.
- Document supported OpenCode authentication workflows accurately.
- Preserve all existing aisbox isolation and credential-handling guarantees.

## Non-Goals

- Exposing OpenCode `serve` or `web` ports.
- Supporting remote TUI attachment, ACP, desktop integration, or the OpenCode
  GitHub agent.
- Selecting a provider, model, authentication method, or default OpenCode
  configuration on the user's behalf.
- Adding OpenCode-specific CLI options to aisbox.
- Documenting every provider-specific or experimental OpenCode environment
  variable.
- Pinning the OpenCode package version.

## Agent Definition

Add an `opencode` entry to `src/aisbox/agents.py` with:

- agent name: `opencode`
- image: `aisbox/opencode:latest`
- config mount destination: `/home/aisbox`
- install command: `npm install -g opencode-ai@latest`
- non-interactive command: `opencode run`
- interactive command: `opencode`
- shell command: the existing `/bin/bash` default
- working directory: `/workspace`

The npm package will be installed as root before the Dockerfile switches to
the unprivileged `aisbox` user, matching the existing Claude and Codex image
pattern.

OpenCode's upstream auto-update behavior will remain unchanged. aisbox will not
inject `OPENCODE_DISABLE_AUTOUPDATE` or other OpenCode defaults.

## Persistence And Isolation

The environment-specific configuration directory will continue to be mounted
at `/home/aisbox`. This single home mount persists OpenCode's relevant XDG
locations, including:

- credentials at `~/.local/share/opencode/auth.json`
- global configuration under `~/.config/opencode/`
- other OpenCode user state and sessions stored under the container user's home

aisbox will not read, copy, or mount host OpenCode state. The documented safety
contract will explicitly cover host OpenCode configuration and credential
locations in addition to host `~/.claude` and `~/.codex`.

Project files remain available only through explicit workspace and additional
bind mounts. OpenCode's upstream Claude compatibility remains enabled, so
project `CLAUDE.md` and `.claude/skills` files may be consumed when they exist
inside the mounted workspace. This does not grant access to host
`~/.claude` state.

## Command And Runtime Behavior

OpenCode will use all existing generic command paths:

- `aisbox create -n demo1 -a opencode` creates state and builds the image.
- `aisbox run -n demo1 -- "prompt"` invokes
  `opencode run "prompt"` in a disposable container.
- `aisbox start -n demo1` launches the OpenCode TUI in a disposable interactive
  container.
- `aisbox start -n demo1 --keep` launches or joins a retained OpenCode TUI
  session.
- `aisbox attach`, `sessions`, and `kill` manage retained OpenCode sessions
  through the existing lifecycle implementation.
- `shell`, `rebuild`, `inspect`, `list`, and `doctor` work through existing
  agent-neutral behavior.

OpenCode receives the configured workspace, additional mounts, stored
environment variables, default Docker network access, current host UID/GID,
and existing disposable or retained container behavior.

No ports will be published. OpenCode server and web modes remain available only
if a user invokes them manually inside a shell and handles Docker networking
outside the supported aisbox workflow.

## Authentication And Environment Variables

The primary authentication path will be interactive:

1. Start OpenCode with `aisbox start -n demo1`.
2. Run `/connect` in the OpenCode TUI.
3. Select and authenticate the desired provider.

This persists credentials in the environment-specific home mount. OpenCode Zen
will be documented through this `/connect` workflow because that is the
officially documented setup path.

README examples will also show hidden aisbox environment prompts for:

- `ANTHROPIC_API_KEY=`
- `OPENAI_API_KEY=`

The documentation will state that OpenCode supports many providers and can
reference arbitrary supplied environment variables through `{env:NAME}` in
`opencode.json`. It will not imply that the two examples are exhaustive, and it
will not present `OPENCODE_API_KEY` as a universal OpenCode Zen shortcut.

Existing credential warnings continue to apply: environment values are stored
unencrypted in `environment.json`, masked by `aisbox inspect`, and passed to
Docker as environment settings.

## Documentation Changes

Update `README.md` to:

- name Claude Code, Codex CLI, and OpenCode in the overview
- add OpenCode to the supported-agent table
- add an OpenCode creation or authentication example
- describe OpenCode `/connect` and OpenCode Zen authentication
- include Anthropic and OpenAI hidden-prompt examples for OpenCode
- explain provider extensibility and `{env:NAME}` references without an
  exhaustive environment-variable catalog
- explain project Claude compatibility without weakening host isolation
- replace the two-agent preview limitation with a three-agent statement
- preserve the existing persistence, unencrypted-secret, network, and retained
  container warnings

Update `AGENTS.md` so the core safety contract explicitly prohibits copying or
mounting host OpenCode configuration and credential directories.

## Error Handling

No new error types or OpenCode-specific branches are required.

- Unknown names remain rejected by `get_agent()` with `AisboxError`.
- Image build failures use the existing agent-specific build error.
- Runtime and lifecycle failures continue through existing Docker error paths.
- Expected CLI failures must continue to avoid tracebacks.

## Testing

Tests will remain isolated from Docker, the network, credentials, and a real
OpenCode installation.

Agent-definition tests will verify:

- `supported_agents()` returns `claude`, `codex`, and `opencode`
- the OpenCode name, image, home mount, run command, and interactive command
- installation of `opencode-ai@latest`
- package installation occurs before `USER aisbox`

Docker and command tests will verify:

- one-shot runs end with `opencode run <prompt>`
- disposable and retained interactive starts end with `opencode`
- the existing home bind mount targets `/home/aisbox`
- generic create, rebuild, doctor, list, inspect, and lifecycle paths accept
  OpenCode without agent-specific orchestration

Repository documentation tests will verify:

- all three supported agents are named accurately
- host OpenCode state is covered by the safety contract
- authentication examples distinguish environment keys from `/connect`
- OpenCode Zen is documented through interactive authentication
- project Claude compatibility does not claim access to host Claude state

## Implementation Scope

The implementation should be limited primarily to:

- `src/aisbox/agents.py`
- agent, Docker, CLI, doctor, and documentation tests that encode the supported
  agent set or command behavior
- `README.md`
- `AGENTS.md`

The existing `AgentDefinition`, Docker command builder, environment store, and
CLI command structure require no redesign.

## Research Basis

The design uses OpenCode's current official behavior as of June 7, 2026:

- npm package: `opencode-ai@latest`
- interactive CLI: `opencode`
- non-interactive CLI: `opencode run [message..]`
- credentials: `~/.local/share/opencode/auth.json`
- global configuration: `~/.config/opencode/`
- provider setup: `/connect` or supported provider environment variables
- arbitrary configuration substitution: `{env:VARIABLE_NAME}`

Primary references:

- https://github.com/anomalyco/opencode
- https://opencode.ai/docs/cli/
- https://opencode.ai/docs/config/
- https://opencode.ai/docs/providers/
- https://opencode.ai/docs/network/
- https://opencode.ai/docs/server/
