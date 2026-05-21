# Walk & Parse Guide

The current release page is `Walk & Parse`.

## What The Page Supports

Use `Walk & Parse` to:

- run an SNMP walk against a target
- switch between text and JSON-oriented output modes
- filter the current result set
- copy or export results
- jump into `MIB Browser` when you need more context

## Standard Inputs

The main fields are:

- target host
- port
- community
- root OID
- `JSON Output`
- `Resolve OIDs`
- `Grouped JSON`

Use numeric roots when you want the most robust path. Use symbolic roots when
the relevant MIBs are loaded and you want readable output.

Current output controls:

- `JSON Output` returns structured JSON-oriented output instead of plain text
- `Resolve OIDs` keeps symbolic resolution enabled when the active MIB set can resolve the walked objects
- `Grouped JSON` returns the nested grouped JSON layout and keeps OID resolution enabled

## Local Loopback Example

If you started the local simulator on the default port, use:

- host: `127.0.0.1`
- port: `1061`
- community: `public`
- root: `1.3.6.1.2.1.1`

Run the walk and confirm:

- the request succeeds
- the item count matches the expected subtree
- resolved output reflects the values provided by the simulator

## Result Handling

After a successful walk, you can:

- search within the current results
- copy the current output
- export JSON or CSV when the data shape allows it
- jump into `MIB Browser` for related symbol inspection

## Common Failure Patterns

Check these first if a walk fails:

- wrong host or host-facing UDP port
- wrong community string
- unreachable target
- invalid root OID format
- symbolic root that is not resolvable in the current MIB set

## Related Docs

- [Simulator Guide](snmp_simulator_guide.md)
- [MIB Browser Guide](mib_browser_guide.md)
- [Troubleshooting](troubleshooting.md)
