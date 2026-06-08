# Preview Limitations

`aisbox` is in public preview. The following limitations apply.

## Agent support

Only three agents are supported:

- Claude Code (`claude`)
- Codex CLI (`codex`)
- OpenCode (`opencode`)

No other agents or custom agent definitions are supported during the preview.

## Unpinned upstream CLI versions

Agent images are built locally and install the agent CLI via npm at build
time. Upstream CLI versions are not pinned. Re-running `aisbox rebuild` may
install a different version than the one previously built.

## Manual mount and environment configuration

Mounts and stored environment variables are configured manually through
`aisbox mount`, `aisbox env set`, and `-e` flags. There is no automatic
discovery of host paths, credentials, or configuration files.

## No Docker-backed integration tests in the normal suite

Docker-backed integration tests are not part of the normal test suite
(`pytest`) and must be run separately when needed.

## Best-effort compatibility and security timelines

Compatibility and security response timelines are best-effort during the
public preview. Interfaces and workflows may change, and there is no
commitment to backward compatibility between preview versions.

## Platform support

Only POSIX systems (Linux and macOS) are supported. Native Windows hosts are
not supported during the public preview.
