# Migration To Trishul SNMP Suite 2.0.x

This guide covers migration from the older `1.x` runtime line to the current
`2.0.2` platform.

This document intentionally references `1.x` and legacy runtime names because
it is the migration guide. Use the other operator docs for the normal `2.0.2`
steady-state view.

## What Changed

`2.0.2` keeps the backend platform introduced in `2.0.0`, but the shipped release UI
keeps the familiar page-based operator shell.

Main changes:

- new FastAPI runtime under `backend/app`
- single API surface under `/api/...` plus the live shell socket at `/api/ws`
- SQLite-backed product state with Alembic migrations
- in-process SNMP runtime — no subprocess simulator or trap-receiver workers
- compiled bundle pipeline via `trishul-smi`; active MIB bundle queried in memory

## What The Installer Still Does

The installer still helps with Docker-era migration by:

- stopping legacy containers if present
- creating the `trishul-snmp-suite-data` volume if needed
- copying the old Docker volume forward when the new volume is empty
- keeping the old volume intact for rollback

## What Carries Forward Best

The restored release shell is designed to stay close to the older operator
flow, so these areas usually carry forward most naturally:

- credentials bootstrapped from legacy files into SQLite
- uploaded MIB file paths copied with the data volume
- simulator custom data stored under the shared data root
- familiar page-level operator workflows

Even when files are preserved, validate them after upgrade rather than assuming
they are still correct for the new runtime.

## What Still Needs Manual Validation

Do not assume all old state is automatically correct after upgrade.

Manually verify:

- loaded MIB catalog contents
- simulator custom data behavior
- trap history expectations
- app settings
- any saved operator habits that depended on the old container layout

The new runtime stores durable state in SQLite and compiled bundle artifacts, so
the old file layout is no longer the whole source of truth.

## Recommended Upgrade Path

1. create a backup before changing the runtime
2. run `./install-trishul-snmp-suite.sh up` or `up-local`
3. log in to the new shell
4. rotate credentials in `Settings`
5. verify or reload MIBs in `MIB Manager`
6. validate simulator and walk flows
7. validate trap receive and send flows
8. review dashboard status and settings metadata

## Operational Differences To Expect

Compared with `1.x`:

- the backend is now FastAPI plus SQLite; no separate Nginx layer or subprocess workers
- the SNMP responder and trap receiver run in-process as async tasks
- live shell updates come from the FastAPI-served `/api/ws` socket directly, with no UDP loopback IPC
- active credentials and sessions are stored in SQLite, not only `secrets.json`
- MIB catalog is queried from the in-memory compiled bundle, not from a pysnmp mibBuilder
- durable notification history and bundle state live in SQLite

## Rollback Guidance

If you need to roll back during validation:

1. stop the merged `2.0.2` container
2. keep `trishul-snmp-suite-data` intact
3. use the preserved `trishul-snmp-data` volume as the source of truth for the old runtime
4. recreate the old containers only if you intentionally return to `1.x`

The installer does not delete the old volume automatically.
