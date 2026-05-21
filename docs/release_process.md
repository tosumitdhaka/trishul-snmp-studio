# Release Process

This checklist is the repo source of truth for cutting a release.

## 1. Lock Scope

Before bumping versions:

1. update [issue_tracker.md](issue_tracker.md) so included items are `Done`
2. confirm shipped scope still matches [roadmap.md](roadmap.md)
3. verify any deferred work is called out explicitly in docs and release notes

Do not cut a release while release-blocking issues remain open.

## 2. Bump Version Markers

Version markers that must stay aligned:

- `.env`
- `backend/app/core/config.py`
- `backend/app/__init__.py`
- `frontend/package.json`
- `docker-compose.yml`
- `install-trishul-snmp-suite.sh`
- `docs/changelog.md`

If the release changes packaging or startup behavior, also review:

- `Dockerfile`
- `docs/installation_guide.md`
- `docs/development_setup.md`
- `docs/migration_to_trishul_snmp_suite.md`

## 3. Update Release Notes

Add a new section to [changelog.md](changelog.md) with:

- release date
- major architecture or behavior changes
- new API or UI changes
- migration notes
- fixes

## 4. Verify The Tree

Run the full test suite from the repo root:

```bash
.venv/bin/python -m pytest backend/ -q
```

Expected result: the full backend suite passes. Do not pin release docs to a
fixed pass count because the suite grows over time.

Run the backend coverage gate:

```bash
.venv/bin/python scripts/check_backend_coverage.py
```

Build the frontend and verify it compiles cleanly:

```bash
npm --prefix frontend run build
```

For packaging or deployment changes, also build and verify the container:

```bash
docker build -t trishul-snmp-suite-local:rc .
```

## 5. Manual Smoke

Before publish, validate these flows in a local runtime built from the release
candidate:

1. login, logout, and credential rotation
2. `Dashboard` loads status and counters; live connection indicator stays online
3. `Simulator` starts, serves a local walk target, appends live activity updates
4. `Walk & Parse` returns expected data from the local responder
5. `Traps` starts a listener and records one received event live in the table
6. `MIB Manager` uploads a MIB file and reloads; status reflects the new module
7. `Settings` save and metadata panels load correctly
8. `/api/meta`, `/api/health`, and `/docs` respond correctly
9. `/api/ws` accepts an authenticated connection

## 6. Publish Images

Image publishing is automatic. After the release commit is pushed to `main`,
GitHub Actions runs `.github/workflows/ghcr-publish.yml` and publishes:

- `ghcr.io/<owner>/trishul-snmp-suite:latest`
- `ghcr.io/<owner>/trishul-snmp-suite:${APP_VERSION}`

Multi-architecture manifest for `linux/amd64` and `linux/arm64`.

Before calling the release complete, verify the workflow run succeeded and the
expected tags are available.

## 7. Migration Checks

Before shipping a public cut:

1. verify `install-trishul-snmp-suite.sh up` on a clean host
2. verify `up-local` from a local checkout
3. verify old Docker volumes are preserved during migration
4. verify the migration guide accurately documents what is and is not converted

## 8. Post-Release Checks

After the publish completes:

1. pull or build the final image
2. confirm `/api/meta` returns the release version
3. confirm the shell header and `Settings` metadata show the same version
4. confirm the changelog entry and compare links are correct
5. confirm the installer still starts the expected image tag
