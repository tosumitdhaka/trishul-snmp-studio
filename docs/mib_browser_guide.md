# MIB Browser Guide

`MIB Browser` is the inspection page for the current release UI.

Use it after loading MIB files in `MIB Manager` when you need to browse a tree,
search symbols, inspect details, or jump into `Walk & Parse` or `Traps`.

## Before You Start

For the best experience:

1. load the MIB files you need in `MIB Manager`
2. confirm the loaded count is non-zero
3. open `MIB Browser`

If no MIBs are loaded, the browser can still show numeric root nodes, but
symbolic detail and search coverage will be limited.

## Main Views

The page supports two main browsing modes:

- module view
- numeric OID hierarchy view

Module view is the fastest way to inspect one module at a time. OID view is
better when you already know the numeric subtree you want.

## Search And Filters

Use the search box for:

- object names
- notification names
- module names
- numeric OIDs

Combine search with:

- module filter
- type filter

to narrow the result set quickly.

## Node Detail

Selecting a node shows:

- full symbolic name
- numeric OID
- module
- type
- syntax
- access and status when available
- description
- index members for table objects
- trap object members for notifications

## Jump Actions

The browser can hand a selected symbol to other pages:

- `Use in Walker`
- `Use in Traps`

Use this flow when you want to avoid retyping long symbolic names or numeric
targets.

## Common Failure Patterns

Check these first if browse or search looks incomplete:

- the required MIB file never loaded
- filters are still active from a previous session
- the symbol exists only in a dependency that is still missing
- the current node was removed after a reload

## Related Docs

- [MIB Manager Guide](mib_manager_guide.md)
- [Walk & Parse Guide](walker_guide.md)
- [Traps Guide](trap_manager_guide.md)
