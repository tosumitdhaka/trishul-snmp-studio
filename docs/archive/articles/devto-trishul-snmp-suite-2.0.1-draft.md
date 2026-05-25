---
title: Trishul SNMP Suite 2.0.1: Better MIBs, Traps, and SNMP Labs
published: false
cover_image: https://raw.githubusercontent.com/tosumitdhaka/trishul-snmp-suite/main/assets/cover.png
description: Trishul SNMP Suite 2.0.1 turns a useful SNMP UI into a cleaner bundle-first platform with in-house MIB and runtime libraries, better trap flows, smarter browsing, and simpler deployment.
tags: snmp, python, fastapi, opensource
---

Trishul SNMP Suite is an SNMP lab and operations shell for people who need to simulate devices, walk targets, send and receive traps, browse MIB trees, and manage real vendor MIB corpora from one place.

If you are new to the project, that is the short intro.

If you last saw it around `1.2.5`, `2.0.1` is the point where the project stops feeling like “a useful UI with a lot of features” and starts feeling like a cleaner platform with a much stronger core.

That is the real story of this release.

![Trishul SNMP Suite 2.0.1 demo](../../../assets/trishul_snmp_demo.gif)

## What you get today

Compared with the `1.2.x` era, Trishul SNMP Suite now gives you:

- one FastAPI application serving the UI, API, and WebSocket layer
- one in-process SNMP runtime powered by the in-house `trishul-snmp` library
- one bundle-first MIB compilation pipeline powered by the in-house `trishul-smi` library
- SQLite-backed durable state for sessions, settings, bundles, and notification history
- one unified `/api/...` surface instead of split route families
- a cleaner single-container deployment path
- better MIB inventory handling, smarter exports, richer trap workflows, and a more intuitive browser experience

The pages are still familiar:

- `Dashboard`
- `Simulator`
- `Walk & Parse`
- `Traps`
- `MIB Browser`
- `MIB Manager`
- `Settings`

But the system underneath those pages is much more coherent now.

## From 1.2.x to 2.0.1, in one view

I do not want to turn this into a changelog dump, so here is the short version of the journey:

- `1.2.x` established the operator experience: MIB Browser, realtime dashboard behavior, simulator improvements, trap workflows, drag-and-drop MIB upload, auto-validation, and a more usable UI
- later `1.x` releases hardened the product with better security, better tests, better docs, better deployment, and a single-suite packaging path
- `2.0.0` rebuilt the core runtime and MIB pipeline around a much cleaner architecture
- `2.0.1` is the release where that architecture starts paying off in the workflows users touch every day

So the headline is not just “more features since `1.2.5`.”

The headline is that the same kind of workflows now run on a much better foundation.

## Why I built `trishul-smi` and `trishul-snmp`

This is the part I most wanted to share.

As the project grew, two kinds of friction kept showing up:

1. MIB compilation and compiled-data usage were too important to remain a loosely connected side concern.
2. SNMP runtime behavior was too central to keep treating it like a set of worker-style runtime pieces that had to be coordinated from the outside.

I wanted the product to have:

- a first-class compiled MIB artifact
- a shared in-memory representation that browser, catalog, trap enrichment, and runtime features could all rely on
- runtime control that lived inside the application instead of being orchestrated through extra process boundaries
- cleaner APIs for the exact behavior the product needed
- simpler debugging and testing

That is why I moved core responsibilities into two in-house libraries.

### `trishul-smi`

`trishul-smi` is the MIB compilation side of the platform.

Instead of compiling MIBs and then treating the output as a loose set of files, the app now works with a bundle-first model:

- versioned bundle storage
- compile metadata
- activation state
- compile history
- one active compiled bundle loaded for queries

That gives Trishul a more reliable answer to questions like:

- which modules are active right now?
- which modules belong to which source group?
- which module is shadowed and why?
- what should the browser, trap catalog, and runtime resolve against?

### `trishul-snmp`

`trishul-snmp` is the runtime side of the platform.

It lets the suite run the responder, manager-side operations, notification listener, trap and inform sending, and bundle-backed symbolic behavior inside the app itself.

That means:

- no subprocess choreography as the main runtime model
- no shell-outs as the normal SNMP execution path
- no extra worker coordination just to keep trap, stats, and simulator state aligned
- fewer layers between the UI, state, and runtime behavior

This was not “let’s build in-house libraries for the sake of it.”

It was a practical decision: the product had reached a point where better internal control over the MIB pipeline and SNMP runtime would improve both developer velocity and operator experience.

## What the architecture looks like now

A comparison table explains the shift better than a diagram:

| Area | Earlier line | 2.0.1 |
| --- | --- | --- |
| MIB compilation | pysmi-style compilation and looser generated artifacts around the app. | trishul-smi drives a bundle-first pipeline with versioned bundles, activation, source attribution, and export-friendly metadata. |
| Catalog query source | Browser and catalog views leaned on generated artifacts and pysnmp mibBuilder-style runtime views. | The active in-memory bundle is the source of truth for browser, catalog, exports, and resolution. |
| SNMP runtime | Subprocess-based pysnmp workers, with separate simulator and trap receiver processes and UDP loopback coordination. | trishul-snmp runs responder, manager operations, trap send and receive, and symbolic behavior in-process. |
| App topology | More glue between runtime pieces, route families, and cross-process status updates. | One FastAPI application serves the UI, API, and WebSocket layer. |
| State and stats | More file-backed and process-coordination-heavy runtime state, including file-based stats flow. | SQLite-backed state now covers settings, sessions, bundles, notification history, and persisted counters. |
| Deployment | More moving pieces to explain and reason about. | One suite, one app surface, one cleaner container path. |

That simplicity matters.

It reduces the amount of glue code needed to keep everything coherent, and it makes features easier to add without creating a larger mess around them.

## What users will notice first

All of that architecture work would not matter much if the workflows still felt awkward.

In `2.0.1`, they do not.

### More trustworthy compiled MIB data

This is one of the biggest practical improvements in the product.

Trishul now handles compiled MIB data with much clearer source attribution and bundle semantics. It distinguishes the deduplicated active runtime view from the per-source-group inventory view. That becomes very important once you load overlapping vendor corpora or want bundle-specific exports instead of a blurred “everything together” view.

The result is a more trustworthy MIB model:

- better duplicate and shadowed-module handling
- clearer active-versus-source inventory behavior
- better failed-module reporting
- more reliable compiled data for exports and downstream workflows

This is the kind of improvement that makes operators trust what the app is showing them.

### Better trap workflows

Trap handling is also much better in day-to-day use.

The trap flow now supports richer varbind editing, including enum-aware varbind dropdown behavior that makes common notification work more natural. Trap history is also more coherent because stored events preserve the event-time view of resolution data instead of drifting with whatever the current toggle state happens to be.

That means:

- better trap varbind authoring
- clearer trap history behavior
- stronger confidence in what a stored trap event actually represents
- better live operator experience around traps

For SNMP tooling, this matters a lot. Trap workflows become frustrating fast when the tool is “almost right.”

### A smarter MIB Browser

The MIB Browser was already one of the most visible features in the older line. In `2.0.1`, it feels much more intentional.

Search and type filtering work together more naturally. Filtered trees can auto-expand so users can actually see the result immediately. Interaction is also less fussy: larger click targets and smaller browser UX refinements make the tree feel more responsive and less fragile.

That turns into better everyday behavior:

- faster drill-down
- less hunting through collapsed branches
- more intuitive expand and collapse interaction
- fewer dead-click moments in the tree

This is exactly the kind of improvement users notice even if they do not name it explicitly.

### Better exports and catalog behavior

Exports are now much more aligned with what the user actually selected.

Source-group-scoped exports respect source-group membership instead of collapsing everything into the currently active deduplicated view. Export filenames are more useful. Stats export is also cleaner and does not drag the full runtime OID catalog into every export by default.

That makes exported data feel like a real operational artifact rather than a generic dump.

### More stable page-to-page behavior

One quiet but important improvement in the `2.0.x` line is that the app relies less on expensive reprocessing when users switch pages.

Because the platform now has clearer persisted state and runtime ownership, dashboard counters, MIB views, and related status panels behave more predictably when moving between screens.

That translates into:

- less waiting
- fewer stuck loading states
- less repeated inventory work
- better confidence that the UI reflects the current runtime state

## Many smaller UI and UX refinements matter too

Not everything valuable belongs in a release headline.

Some of the improvements in `2.0.1` are small on paper but meaningful in daily use:

- broader click targets in browser trees
- more intuitive expand and collapse behavior
- better filtered auto-expansion
- cleaner loading and status feedback
- less friction in modal-driven flows
- more consistent page-to-page behavior

These are the kinds of changes that make the product feel sharper even when users cannot point to a single “killer feature.”

## Why this helps developers too

One of the easiest ways to slow down a tooling project is to keep layering features on top of an architecture that is getting harder and harder to reason about.

Eventually you pay for that in:

- state bugs
- UI inconsistencies
- release risk
- painful debugging
- slower feature delivery

Moving the platform toward `trishul-smi` and `trishul-snmp` changed that for Trishul SNMP Suite.

For developers, the benefits are direct:

- fewer layers to mentally unpack
- flatter service architecture
- clearer boundaries between compile, runtime, and UI concerns
- stronger testability
- better release validation and observability

For users, the same architecture work shows up as:

- better reliability
- more predictable workflows
- cleaner logs
- easier deployment
- more trustworthy data in the UI

That is the kind of internal rewrite I like: one that results in visible product quality, not just prettier internal diagrams.

## A few snips

### One-shot install

If you just want to try the released suite on a Docker host, this is the quickest path:

```bash
curl -LfsS -o install-trishul-snmp-suite.sh \
  https://raw.githubusercontent.com/tosumitdhaka/trishul-snmp-suite/v2.0.1/install-trishul-snmp-suite.sh \
  && bash install-trishul-snmp-suite.sh up
```

Default access after startup:

- UI: `http://localhost:8980`
- API docs: `http://localhost:8980/docs`
- default login: `admin / admin123`

### Unified API shape

One part I like in the current release is that the API shape is much easier to explain:

```text
/api/meta
/api/health
/api/ws
/api/settings/*
/api/stats/*
/api/simulator/*
/api/walk/*
/api/traps/*
/api/mibs/*
```

It is a small thing, but it makes the product easier to understand for both developers and operators.

### Trap send example

The current trap flow is also easier to demonstrate with one clean request:

```json
{
  "target": "127.0.0.1",
  "port": 1162,
  "community": "public",
  "oid": "IF-MIB::linkDown",
  "varbinds": [
    { "oid": "1.3.6.1.2.1.2.2.1.1.1", "type": "Integer", "value": 1 }
  ]
}
```

That kind of simple, direct workflow is exactly what I wanted the platform to support better.

## Why `2.0.1` matters

I do not think `2.0.1` should be read as “just the next point release.”

`2.0.0` did the heavy architectural lift. `2.0.1` is where the system starts feeling polished enough that the benefits are obvious:

- more reliable compiled data
- better source-aware inventory and exports
- richer trap authoring
- smarter browsing
- quieter and more useful logs
- cleaner install and runtime defaults

That combination is what makes the release interesting.

## Closing

If you are new to Trishul SNMP Suite, `2.0.1` is a good point to try it because the platform is now much easier to understand:

- one app
- one runtime
- one MIB pipeline
- one installer path
- familiar operator pages

If you knew the older `1.2.x` line, `2.0.1` is where the project starts paying off the deeper work behind the scenes.

The UI is better. The MIB data is more trustworthy. Trap workflows are better. The browser is more intuitive. The deployment story is simpler. And the in-house `trishul-smi` and `trishul-snmp` foundation gives the project a much stronger path forward.

That is the release I wanted to ship.

If you work with SNMP labs, MIB-heavy device testing, or trap-driven workflows, I would love to know what you would want to see next: deeper bundle controls, richer browser/catalog features, stronger simulator behavior, or more advanced trap tooling.

<!-- Suggested assets for the published version:
- Hero GIF: product walkthrough across Dashboard, MIB Browser, MIB Manager, and Traps
- Inline diagram: old worker-style flow vs current bundle-first in-process flow
-->
