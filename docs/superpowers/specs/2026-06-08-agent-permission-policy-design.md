# Agent Permission Policy Design

## Summary

`aisbox run` currently launches each supported agent with a fixed non-interactive
command:

```text
claude -p
codex exec
opencode run
```

That leaves the agent's own permission system in its default mode. In a
non-interactive Docker run this can block useful write tests and automation,
because the agent asks for an approval that the user cannot grant from the
outer `aisbox run` command.

This change adds an aisbox-level permission policy flag for `run`:

```text
aisbox run --permission-policy auto -- "create test.temp in this repo"
aisbox run --permission-policy bypass -- "create test.temp in this repo"
```

The flag is intentionally cross-agent. Users choose the behavior they want, and
aisbox maps that behavior to the selected agent's current CLI or configuration
mechanism.

## Goals

- Let non-interactive `aisbox run` perform ordinary in-workspace file writes
  without waiting for impossible approval prompts.
- Keep a stable aisbox interface across Claude Code, Codex CLI, and OpenCode.
- Update the local `aisbox-coagent` skill so delegated coagent runs ask for an
  explicit permission policy and recommend a policy from task intent.
- Preserve Docker isolation, bind mount boundaries, and the existing rule that
  host agent configuration and credential directories are not copied or
  mounted.
- Keep the feature temporary per invocation. It must not mutate saved
  environment JSON.

## Non-Goals

- Do not add automatic `sudo` behavior for Docker.
- Do not copy, mount, or inspect host `~/.claude`, `~/.codex`, or OpenCode user
  state.
- Do not make bypass mode the default.
- Do not add persisted permission policy to `aisbox create` in this change.
- Do not add raw arbitrary agent-argument passthrough in this change.
- Do not let the coagent skill silently choose elevated agent permissions.

## User Interface

`aisbox run` gains:

```text
--permission-policy [default|auto|bypass]
```

`default` is the implicit behavior and preserves the current command exactly.

`auto` means "run without routine approval prompts while preserving the most
useful available safety boundary for this agent." For the motivating case, it
should allow normal writes inside `/workspace`.

`bypass` means "disable the agent permission layer as much as the selected
agent supports." This is suitable only because the agent is already running
inside an aisbox Docker container with explicit bind mounts.

The flag is accepted only by `aisbox run` in this design. Interactive retained
sessions need separate semantics because their permission mode can often be
changed in-session and because retained containers may live past a single
command.

## Agent Mapping

The implementation will store per-agent mappings in code, near the existing
`AgentDefinition` data.

| Agent | `default` | `auto` | `bypass` |
| --- | --- | --- | --- |
| Claude Code | `claude -p` | `claude -p --permission-mode auto` | `claude -p --dangerously-skip-permissions` |
| Codex CLI | `codex exec` | `codex exec --ask-for-approval never --sandbox workspace-write` | `codex exec --dangerously-bypass-approvals-and-sandbox` |
| OpenCode | `opencode run` | `opencode run --dangerously-skip-permissions` | `opencode run --dangerously-skip-permissions` |

OpenCode currently has one documented CLI flag for non-interactive approval
skipping. Its richer permission model is configuration based. For this feature,
`auto` and `bypass` intentionally map to the same OpenCode command because
aisbox cannot express a stronger distinction without generating temporary
OpenCode config.

## Upstream Compatibility Notes

Claude Code's older `--enable-auto-mode` flag is no longer the right target.
Current Claude Code documentation says it was removed in v2.1.111 and that
startup auto mode should use `--permission-mode auto`.

Codex exposes approval and sandbox controls as command-line flags. The
workable auto policy for aisbox is `--ask-for-approval never` with
`--sandbox workspace-write`, because the Docker container already exposes only
the selected workspace and explicit mounts. The full bypass policy uses
Codex's documented dangerous bypass flag.

OpenCode exposes `opencode run --dangerously-skip-permissions` for
non-interactive auto-approval and also supports permission configuration via
JSON or environment variables. Temporary config generation is out of scope for
this first pass.

## Architecture

Add a small value object or enum-like type for permission policies:

```python
PermissionPolicy = Literal["default", "auto", "bypass"]
```

Thread the policy through:

```text
cli.run -> commands.run_environment -> docker.run_container -> docker.container_command
```

`container_command` will continue to build Docker arguments first, append the
image, then append the agent command. For `mode == "run"`, it will ask the
agent definition for the command matching the selected policy and then append
the prompt string when one is present.

The stored `Environment` model remains unchanged. The policy is an invocation
option, not environment state.

## Coagent Skill Behavior

The local skill at `skills/aisbox-coagent/SKILL.md` will be updated because it
constructs `aisbox run` commands for delegated one-shot work.

The skill already requires the operator to choose workspace exposure before a
coagent run. It will add permission policy as another operator-owned decision.
The agent using the skill should infer the likely policy from the delegated
task, explain the recommendation briefly, and ask before running.

Recommended heuristic:

- Use `default` for clearly read-only work: explain code, inspect repository
  structure, summarize files, review architecture, or answer questions.
- Use `auto` for work likely to need normal in-workspace writes or write-like
  commands: create files, edit code, add tests, generate docs, run formatters
  that update files, or validate write permissions.
- Mention `bypass` when the operator explicitly asks for maximum autonomy or
  when the task needs broad command execution. Do not recommend it by default.

The prompt should be concise and explicit, for example:

```text
This looks write-capable, so I recommend --permission-policy auto. Use that,
choose bypass, or keep the agent default?
```

The skill's quick reference will include:

```text
aisbox run --permission-policy auto -- "<prompt>"
```

The workflow and flowchart will add permission policy selection after workspace
selection and before sandbox resolution. Common mistakes and red flags will add:

- using `default` for a write task and causing an approval deadlock
- using `auto` or `bypass` without operator approval

## Validation And Errors

Typer should reject invalid `--permission-policy` values before command
execution.

If a future agent has no mapping for a requested policy, aisbox should raise
`AisboxError` with a concise message:

```text
Permission policy 'auto' is not supported for agent: <agent>
```

For the current three agents, all three policy values are supported.

Expected user-facing errors must remain traceback-free.

## Safety

This feature changes the agent's internal approval behavior, not the Docker
container shape. Docker still:

- runs as the current user
- mounts only the environment workspace and explicit extra mounts
- mounts aisbox-managed agent config from the environment's private state root
- avoids host agent configuration and credential directories
- removes disposable runtime containers by default

`bypass` is still dangerous inside the mounted workspace. Documentation must
state that it lets the agent write and run commands without agent-level
approval prompts, and that users should use it only for trusted repositories
and scoped prompts.

## Testing

Unit and CLI tests will cover:

- `aisbox run --permission-policy default` preserves current run commands.
- `aisbox run` without the flag preserves current run commands.
- Claude `auto` appends `--permission-mode auto` before the prompt.
- Claude `bypass` appends `--dangerously-skip-permissions` before the prompt.
- Codex `auto` appends `--ask-for-approval never --sandbox workspace-write`
  before the prompt.
- Codex `bypass` appends `--dangerously-bypass-approvals-and-sandbox` before
  the prompt.
- OpenCode `auto` and `bypass` append `--dangerously-skip-permissions` before
  the prompt.
- The policy is passed through `cli.run` to `commands.run_environment` and then
  to `run_container`.
- The policy is not saved to environment JSON.
- Invalid policy values fail through Typer without a traceback.
- README documents the flag, the per-agent mapping, and the safety tradeoff.
- The `aisbox-coagent` skill documents permission policy selection, includes
  the read-only/write-capable heuristic, and warns against silent escalation.

## Documentation

`README.md` will add a section under run usage or supported agents:

```text
aisbox run --permission-policy auto -- "update the tests"
aisbox run --permission-policy bypass -- "prototype the change"
```

The docs will explain:

- `default` keeps the agent's default approval behavior.
- `auto` is the recommended mode for non-interactive write-capable runs.
- `bypass` is more permissive and should be used only inside trusted aisbox
  containers with explicit workspace and mount choices.
- Claude, Codex, and OpenCode do not use identical upstream terminology, so
  aisbox maps the policy to each agent's closest supported behavior.

`skills/aisbox-coagent/SKILL.md` will document how local AI agents should ask
for a coagent permission policy before launching `aisbox run`, including the
recommended heuristic for read-only versus write-capable delegated work.
