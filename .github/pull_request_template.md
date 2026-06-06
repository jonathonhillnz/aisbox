## Summary

Describe the change and its user-visible effect.

## Linked Issue

Link the issue discussed before this pull request for substantial changes.
Small documentation corrections do not require a linked issue.

## Tests

List the exact commands run and their results.

## Documentation

Describe documentation changes, or explain why none are needed.

## Safety Checklist

- [ ] This change does not copy or mount host agent configuration unexpectedly.
- [ ] This change does not broaden host directory mounts unexpectedly.
- [ ] This change does not print or commit secrets.
- [ ] This change does not add automatic `sudo` behavior for Docker.
- [ ] Expected user-facing failures remain concise and do not emit tracebacks.
