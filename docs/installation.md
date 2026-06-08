# Installation

## Requirements

- **POSIX system** (Linux or macOS). Native Windows hosts are not supported
  during the public preview.
- **Python 3.11** or newer.
- **Docker** available to the current user without `sudo`. `aisbox` does not
  run Docker through `sudo`.
- **`pipx`** for the recommended CLI installation.
- **Network access** for Docker image builds, which install Ubuntu packages
  and npm agent CLIs.

## Check Docker access

Verify that Docker is installed and that your user can connect to the daemon:

```bash
docker version
```

If this command fails, check that Docker is installed and your user is a
member of the `docker` group (or an equivalent configuration on your system).

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

`aisbox doctor` checks that Docker is reachable and the state directory is
writable, and lists the supported agents. If any check fails, `aisbox doctor`
exits with a non-zero status.
