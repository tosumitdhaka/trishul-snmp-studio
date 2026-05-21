# Installation Guide

This guide covers the supported `2.0.0` installation paths for Trishul SNMP
Suite.

## What Gets Installed

The runtime is one container that serves:

- the shell UI
- the unified API under `/api/...`
- the live shell socket at `/api/ws`
- metadata and health under `/api/meta` and `/api/health`
- OpenAPI docs under `/docs`

Persistent state is stored in the Docker volume `trishul-snmp-suite-data`.

## Prerequisites

- Docker
- Docker Compose v2 if you want to use `docker compose`
- free ports for:
  - `8080/tcp` app access by default
  - `1061/udp` local responder testing by convention
  - `1162/udp` local notification-listener testing by convention

## Recommended: One-Shot Installer

From a local checkout:

```bash
./install-trishul-snmp-suite.sh up
```

What it does:

- pulls the published image
- uses the image produced automatically by GitHub Actions on each push to `main`
- creates the data volume if needed
- preserves legacy data volumes for rollback
- starts the merged application container

After startup:

- app UI: `http://localhost:8080`
- API docs: `http://localhost:8080/docs`
- default login: `admin` / `admin123`

The current installer also accepts explicit platform and image overrides:

```bash
./install-trishul-snmp-suite.sh up --platform linux/arm64
./install-trishul-snmp-suite.sh up --image ghcr.io/tosumitdhaka/trishul-snmp-suite:latest
./install-trishul-snmp-suite.sh up-local --platform linux/amd64 --image trishul-snmp-suite-local:test
```

Notes:

- `--platform` tells Docker which manifest to pull, build, or run for the selected image
- `--image` overrides the published image reference or the local build tag

Environment variable equivalents are also supported:

- `TRISHUL_IMAGE`
- `DOCKER_PLATFORM`
- `TRISHUL_DOCKER_PLATFORM`

## Build And Run From This Checkout

Use this when you want the image built from local source:

```bash
./install-trishul-snmp-suite.sh up-local
```

Useful companion commands:

```bash
./install-trishul-snmp-suite.sh build-local
./install-trishul-snmp-suite.sh restart-local
./install-trishul-snmp-suite.sh logs
./install-trishul-snmp-suite.sh status
./install-trishul-snmp-suite.sh down
```

## Docker Compose Path

The repo still ships a Compose file for convenience:

```bash
docker compose up -d
docker compose logs -f app
docker compose down
```

For `2.0.0` release validation, prefer the installer over Compose.

## Custom Ports

Primary app port:

```bash
APP_PORT=8980 ./install-trishul-snmp-suite.sh up
```

Custom SNMP test ports:

```bash
APP_PORT=8980 SNMP_PORT=2161 TRAP_PORT=2162 ./install-trishul-snmp-suite.sh up
```

Compatibility access:

```bash
FRONTEND_PORT=8980 BACKEND_PORT=8900 ./install-trishul-snmp-suite.sh up-local
```

In that mode:

- `FRONTEND_PORT` acts as the main app URL
- `BACKEND_PORT` exposes the same merged app on a second host port

## Legacy `1.4.1` Runtime

If you need the pinned merged runtime from the `1.4.1` line, use the legacy
installer:

This section is intentional compatibility guidance. It is not the recommended
`2.0.0` runtime path.

```bash
./install-trishul-snmp-suite-v1.4.1.sh up
```

That installer intentionally keeps the old runtime names:

- container: `trishul-snmp`
- volume: `trishul-snmp-data`

Its default ports are shifted so it can run alongside the `2.0.0` installer on
the same host:

- app UI: `http://localhost:8081`
- SNMP: `2161/udp`
- traps: `2162/udp`

Useful legacy examples:

```bash
./install-trishul-snmp-suite-v1.4.1.sh up-cached
./install-trishul-snmp-suite-v1.4.1.sh up --platform linux/arm64
./install-trishul-snmp-suite-v1.4.1.sh up-cached --image ghcr.io/tosumitdhaka/trishul-snmp-suite:1.4.1
APP_PORT=8980 ./install-trishul-snmp-suite-v1.4.1.sh up-cached
```

Notes:

- `up-cached` uses an already-pulled local image instead of pulling again
- `--platform` tells Docker which manifest to pull or run for the pinned `1.4.1` image
- the same `TRISHUL_IMAGE`, `DOCKER_PLATFORM`, and `TRISHUL_DOCKER_PLATFORM` environment variables work here as well

## First Login

After installation:

1. open the app
2. log in as `admin` / `admin123`
3. go to `Settings`
4. rotate the operator credentials
5. go to `Dashboard`, `Simulator`, or `MIB Manager` to begin validation

## Data Layout

The runtime stores state under `/app/backend/data/`.

Important paths include:

- `trishul_v2.sqlite3`
- `bundles/sets/`
- `bundles/cache/tsmi/`
- `mibs/`
- `configs/custom_data.json`
- `logs/`

## Backup And Restore

Create a backup:

```bash
./install-trishul-snmp-suite.sh backup
```

Restore a backup:

```bash
./install-trishul-snmp-suite.sh restore trishul-snmp-suite-backup-YYYYMMDD-HHMMSS.tar.gz
```

Restore stops the running container first.

## Upgrade From 1.x

If you are coming from the old split or early merged runtime, read
[Migration To Trishul SNMP Suite 2.0.0](migration_to_trishul_snmp_suite.md)
before relying on old state.

The installer can preserve or copy old Docker volumes forward, but the `2.0.0`
runtime uses a new SQLite-plus-bundles model and does not automatically convert
every old file-based workflow into current SQLite state and compiled bundle
artifacts.
