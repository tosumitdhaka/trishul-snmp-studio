# Traps Guide

`Traps` is the current release page for trap listener and trap sender workflows.

It keeps the familiar operator model:

- listener control
- trap library from loaded MIBs
- varbind editing
- trap send
- received-event history

## Listener Control

Use the listener form to choose:

- port
- community
- whether to resolve MIBs in the UI

For container-based local validation, use the host-facing UDP port exposed by
your deployment. The default installer convention is `1162/udp`.

## Trap Library

The trap library is backed by the current loaded MIB set.

Use it to:

- search for a trap symbol
- inspect its numeric OID
- review associated objects
- load it directly into the sender

The current sender uses a searchable trap-library field, so you can type part
of a symbol and load the matching trap without leaving the page.

If the trap library is empty, confirm your MIBs were loaded successfully in
`MIB Manager`.

## Varbind Editing

The sender supports manual varbind rows and a picker driven by loaded MIB
objects.

Use the picker when:

- you want the correct symbolic object name quickly
- you want the UI to prefill a reasonable data type
- you are building a trap from a library entry

If the loaded MIB metadata defines enumerated integer values for an object, the
value editor can switch from a free-text field to a drop-down selector for that
varbind.

## Sending A Trap

The normal loopback test is:

1. start the listener on `1162`
2. set sender target to `127.0.0.1:1162`
3. keep community `public`
4. choose a trap or enter a numeric trap OID
5. send the trap

Confirm the received-events table updates.

## Received History

The page keeps a received-events table for recent trap activity.

Use it to:

- confirm loopback delivery
- inspect the source and time of an event
- review simplified varbind output
- clear the current received-event list when starting a fresh test cycle

When the live shell socket is connected, newly received traps appear on the
page without a manual refresh.

## Common Failure Patterns

Check these first when trap flows fail:

- listener and sender ports do not match
- community mismatch
- trap OID or varbind OID is unresolved
- trap library depends on MIBs that never loaded

## Related Docs

- [MIB Manager Guide](mib_manager_guide.md)
- [MIB Browser Guide](mib_browser_guide.md)
- [Troubleshooting](troubleshooting.md)
