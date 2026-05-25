# MIB Manager Guide

The current `2.0.1` release UI keeps `MIB Manager` as the main page for loading
and maintaining MIB files.

## What The Page Covers

`MIB Manager` is the place to:

- review loaded and failed MIB files
- validate a batch before upload
- upload and reload MIBs
- fetch missing dependencies from approved remote sources
- export the active catalog by scope and type
- inspect the current trap catalog exposed by loaded MIBs
- delete uploaded MIB files

## Upload Workflow

Use the upload modal for the normal flow:

1. choose one or more MIB files
2. let validation complete
3. review file status, imports, and missing dependencies
4. upload and reload

Validation is read-only. It does not change the live runtime until you upload.

## Dependency Fetch

If validation reports missing imports:

1. review the missing dependency list
2. use the dependency fetch action if approved sources are configured
3. if your deployment enables auto-fetch in `Settings`, upload or reload can try those sources automatically
4. re-run validation or reload after dependencies are available

If remote fetch is not configured for your deployment, upload the missing MIBs
manually first.

Validation stays read-only. Remote fetch happens only through the explicit fetch
action or during upload or reload when auto-fetch is enabled.

## Loaded And Failed MIB Lists

The status section shows:

- loaded MIB count
- failed MIB count
- trap count inferred from loaded modules
- per-file errors for failed MIBs

Use this section after every upload or reload so you do not assume a file was
accepted just because the HTTP request succeeded.

In `2.0.1`, the status model has two distinct views:

- `All modules` / active bundle stays deduplicated to the effective runtime set
- source-group views use per-source inventory and keep duplicate membership visible

Important rules:

- `shadowed` is informational, not a failed state
- failed views only include true failures such as `failed`, `missing_deps`, and `invalid`
- source-group exports follow the selected group membership even when a module is shadowed globally

## Aggregate Bundle Resolution

The live runtime uses one active aggregate bundle built from the managed upload
area plus the bundled starter MIBs.

Important rules:

- `common/` is a normal source group, not the aggregate bundle itself
- vendor groups such as `juniper/` or `ericsson/` stay separate on disk
- duplicate module names may exist in storage across source groups
- only one source copy is active in the aggregate bundle at a time

Current source precedence is:

1. files stored directly under the upload root if any exist
2. `common/`
3. other explicit source groups such as `juniper/` or `ericsson/`
4. `auto-fetched/`
5. bundled starter MIBs

That means:

- a manual copy in `common/` overrides the same module stored in a vendor group
- an explicit vendor upload overrides the same module if it only exists in `auto-fetched/`
- bundled MIBs are fallback sources, not the preferred active copy when a managed upload exists

If the same module exists in more than one managed source group, the non-active
copies are shown as `shadowed` in `MIB Manager`.

## Upload And Duplicate Behavior

Validation now reports when an uploaded file would be shadowed by an existing
higher-precedence source.

Typical examples:

- upload `JUNIPER-MAG-MIB` into `juniper/` while `common/JUNIPER-MAG-MIB.mib` already exists:
  the `common/` copy stays active and the new vendor copy is stored as shadowed
- upload a vendor MIB while only an `auto-fetched/` copy exists:
  the vendor copy becomes active after upload or reload

Source-group exports use the active aggregate result, not every stored duplicate
copy. If a module is currently active from `common/`, exporting `juniper` will
not include it until the active source changes.

## Trap Catalog

The lower section of `MIB Manager` exposes the trap catalog built from the
currently loaded MIBs.

Use it to:

- confirm a trap symbol exists
- inspect its numeric OID
- review associated objects
- jump directly into the `Traps` sender

The page also exposes scoped catalog export actions so you can export the active
catalog or notification-focused slices in JSON or CSV.

## Delete And Reload

Deleting a MIB file removes it from the managed upload area and then
reloads the remaining set.

Use delete when:

- one uploaded file is stale or incorrect
- a dependency chain changed
- you want to verify a smaller catalog set

If you delete the active copy of a module and another stored duplicate still
exists, reload promotes the next highest-precedence copy automatically. If the
rebuild fails, the deleted file is restored.

## Common Failure Patterns

Check these first if MIB workflows look wrong:

- unsupported file extension
- missing dependencies that were not uploaded or fetched
- a reload finished with partial failures
- the symbol you want is in a file that did not load successfully

## Related Docs

- [MIB Browser Guide](mib_browser_guide.md)
- [Traps Guide](trap_manager_guide.md)
- [Troubleshooting](troubleshooting.md)
