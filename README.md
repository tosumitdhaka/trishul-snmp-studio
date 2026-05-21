# 🔱 Trishul SNMP Suite

[![GitHub Stars](https://img.shields.io/github/stars/tosumitdhaka/trishul-snmp-suite?style=for-the-badge)](https://github.com/tosumitdhaka/trishul-snmp-suite/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/tosumitdhaka/trishul-snmp-suite?style=for-the-badge)](https://github.com/tosumitdhaka/trishul-snmp-suite/network)
[![GitHub Issues](https://img.shields.io/github/issues/tosumitdhaka/trishul-snmp-suite?style=for-the-badge)](https://github.com/tosumitdhaka/trishul-snmp-suite/issues)
[![License](https://img.shields.io/github/license/tosumitdhaka/trishul-snmp-suite?style=for-the-badge)](LICENSE)
[![GHCR](https://img.shields.io/badge/GHCR-Packages-blue?style=for-the-badge&logo=github)](https://github.com/tosumitdhaka?tab=packages&repo_name=trishul-snmp-suite)

Trishul SNMP Suite is a bundle-first SNMP lab and operations shell. The current
`2.0.0` line moves the runtime to the new FastAPI plus SQLite platform while
keeping the familiar page-based operator shell as the release UI.

![Trishul SNMP Suite Demo](./assets/trishul_snmp_demo.gif)

## 2.0.0 Highlights

- one FastAPI application in `backend/app`
- restored release UI in `frontend/` with `Dashboard`, `Simulator`, `Walk & Parse`, `Traps`, `MIB Browser`, `MIB Manager`, and `Settings`
- current `/api/...` operator-shell routes backed by the new `2.0.0` services and SQLite state
- SQLite-backed state for settings, sessions, bundles, and notification history
- bundle, catalog, and runtime services powered by `trishul-smi` and `trishul-snmp`
- one current installer for the suite image plus one pinned legacy installer for `1.4.1`

## Quick Start

From a local checkout, start the published image with:

```bash
./install-trishul-snmp-suite.sh up
```

Build and run the current checkout with:

```bash
./install-trishul-snmp-suite.sh up-local
```

Default access:

- app UI: `http://localhost:8080`
- API docs: `http://localhost:8080/docs`
- default login: `admin` / `admin123`

Change the default credentials immediately in `Settings`.

### Image And Platform Overrides

The current installer accepts:

- `--platform linux/amd64|linux/arm64`
- `--image <ref>`
- `TRISHUL_IMAGE`
- `DOCKER_PLATFORM`
- `TRISHUL_DOCKER_PLATFORM`

Examples:

```bash
./install-trishul-snmp-suite.sh up --platform linux/arm64
./install-trishul-snmp-suite.sh up --image ghcr.io/tosumitdhaka/trishul-snmp-suite:latest
./install-trishul-snmp-suite.sh up-local --image trishul-snmp-suite-local:test --platform linux/amd64
```

### Legacy 1.4.1 Runtime

If you need the pinned merged runtime from the old line:

This section is intentional compatibility guidance for coexistence or rollback,
not the normal `2.0.0` runtime path.

```bash
./install-trishul-snmp-suite-v1.4.1.sh up
```

That path keeps:

- container name `trishul-snmp`
- volume name `trishul-snmp-data`
- parallel-safe defaults `8081`, `2161/udp`, and `2162/udp`

It also accepts the same `--platform` and `--image` overrides.

## UI Map

- `Dashboard`: runtime status, counters, and shortcuts
- `Simulator`: responder lifecycle, custom OID data, and activity log
- `Walk & Parse`: SNMP walk execution, parsing, filtering, and export
- `Traps`: listener control, trap send, varbind editing, and received-event history
- `MIB Browser`: module or OID tree, search, resolve, and detail inspection
- `MIB Manager`: loaded MIB status, upload, reload, dependency fetch, and trap catalog
- `Settings`: auth rotation, app settings, stats reset or export, and product metadata

## Runtime Model

The current `2.0.0` path is built around:

- `backend/app` as the live FastAPI runtime
- `frontend/` as the authored release shell copied into `frontend/dist`
- `backend/data/trishul_v2.sqlite3` as the main durable data store
- `backend/data/bundles/sets/` and `backend/data/bundles/cache/tsmi/` for bundle artifacts
- `backend/data/mibs/` and `backend/data/configs/custom_data.json` for operator-shell runtime state
- `/api/ws` for live shell events such as status, stats, traps, and simulator log updates

There is no Nginx layer in the current release path. Real-time updates come
directly from FastAPI over `/api/ws`; the old split-runtime WebSocket bridge is
gone.

## Documentation

Start with:

- [Docs Home](docs/index.md)
- [Installation Guide](docs/installation_guide.md)
- [First Steps](docs/first_steps.md)
- [Workspaces](docs/workspaces.md)
- [Architecture Overview](docs/architecture_overview.md)
- [API Reference](docs/api_reference.md)

Operator guides:

- [MIB Manager Guide](docs/mib_manager_guide.md)
- [MIB Browser Guide](docs/mib_browser_guide.md)
- [Simulator Guide](docs/snmp_simulator_guide.md)
- [Walk & Parse Guide](docs/walker_guide.md)
- [Traps Guide](docs/trap_manager_guide.md)

Development and release:

- [Development Setup](docs/development_setup.md)
- [Release Process](docs/release_process.md)
- [Roadmap](docs/roadmap.md)
- [Issue Tracker](docs/issue_tracker.md)
- [GitHub Workflow](docs/github_workflow.md)

## Development

Typical verification commands from the repo root:

```bash
npm --prefix frontend run build
.venv/bin/pytest backend/tests/test_v2_schema.py backend/tests/test_v2_bootstrap.py backend/tests/test_operator_ui_routes.py backend/tests/test_v2_bundles.py backend/tests/test_v2_runtime.py backend/tests/test_v2_persistence.py backend/tests/test_v2_session.py backend/tests/test_v2_system.py -q
.venv/bin/python scripts/run_release_gate.py
```

For Docker-backed local validation:

```bash
./install-trishul-snmp-suite.sh up-local
./install-trishul-snmp-suite.sh logs
./install-trishul-snmp-suite.sh status
```

## Roadmap

The current `2.0.0` line delivers the rewritten backend platform, SQLite
persistence, the compatibility bridge for the current shell, and the shipped operator UI.

The first planned `2.1.0` follow-up keeps the current operator shell and
surfaces backend-delivered features that are not yet exposed in the UI, such as
bundle lifecycle controls, saved profiles, notification replay, direct manager
operations, and system diagnostics. See
[docs/plan_v2.1/backend_frontend_gaps.md](docs/plan_v2.1/backend_frontend_gaps.md).

Deferred beyond `2.0.0`:

- SNMPv3 runtime and UI parity
- writable `SET` responder behavior
- bundle import and export workflows
- one-click ecosystem demo flows
- distributed polling or orchestration features

See [docs/roadmap.md](docs/roadmap.md) and
[docs/plan_v2.0/](docs/plan_v2.0/index.md) for the current planning state.

## Contributing

Contributions are welcome.

Useful starting points:

- [docs/development_setup.md](docs/development_setup.md)
- [docs/github_workflow.md](docs/github_workflow.md)
- [docs/issue_tracker.md](docs/issue_tracker.md)
- [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md)

## License

MIT. See [LICENSE](LICENSE).
