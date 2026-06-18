# Installation

## Requirements

- **POSIX system** (Linux or macOS). Native Windows hosts are not supported
  during the public preview.
- **Python 3.11** or newer.
- **Docker CLI access** to a reachable Docker daemon or compatible context.
  Rootless Docker is recommended on Linux. `aisbox` does not run Docker
  through `sudo`.
- **`pipx`** for the recommended CLI installation.
- **Network access** for Docker image builds, which install Ubuntu packages
  and npm agent CLIs.

## Check Docker access

Verify that Docker is installed and that your user can connect to the daemon or
configured context:

```bash
docker version
```

If this command fails, check that Docker is installed and that your Docker
context is reachable. On Linux, prefer rootless Docker. If you use the
standard rootful daemon through the `docker` group, treat that access as
root-equivalent on the host.

## Install from a checkout

Clone the repository and install `aisbox` globally with `pipx`:

```bash
git clone https://github.com/jonathonhillnz/aisbox.git
cd aisbox
pipx install .
```

After installation the `aisbox` CLI is available on your `PATH`:

```bash
aisbox --version
```

## Verify the installation

Run the built-in health check:

```bash
aisbox doctor
```

`aisbox doctor` checks that Docker is reachable, reports whether Docker is
rootless, checks that the state directory is writable, and lists the supported
agents. If a required check fails, `aisbox doctor` exits with a non-zero
status. A rootful Docker daemon is reported as a warning, not a failure.
