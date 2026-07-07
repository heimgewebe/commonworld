# Mobile Atlas Shift Interaction Model

## Status

- Type: product and interaction doctrine
- Scope: commonworld public atlas surfaces
- Anchor proof: `proofs/mobile-atlas-shift/`
- Runtime boundary: static/read-only; no backend, no accounts, no public submissions, no weltgewebe write path

## Decision

commonworld is smartphone-first. The public atlas must use one primary mobile surface and switch between two projections of the same Commons world:

```text
Karte <-> Aether
```

`Horizont` is not a selectable mode. It is the transition behavior of hybrid commons while shifting between Karte and Aether.

## Rationale

Most users will reach commonworld on a smartphone. The interface must not depend on desktop-style sidebars, stacked panels or multiple overlapping layers.

The atlas should be understandable through a single surface:

- one current projection;
- one thumb-safe projection switch;
- one focused project state when a Commons is opened;
- no persistent filter wall;
- no administrative action surface.

## Projection model

A Commons is not only either local or digital. A Commons can have projections.

```text
CommonProject
├─ map projection
├─ aether projection
└─ profile focus
```

The projection decides how a project appears in a given atlas surface. It does not create a second project identity.

## Karte projection

Karte is the ground projection for location-safe Commons.

It may show:

- exact public places when exact location is explicitly allowed;
- approximate places with a visible privacy affordance;
- hybrid Commons with a local anchor and a rising code pillar.

It must not show hidden locations as exact points.

## Aether projection

Aether is the projection for digital, hidden-location and strongly networked Commons.

It should appear as thematic, swipeable streams rather than an unbounded graph.

It may show:

- digital Commons without fake coordinates;
- hidden-location Commons without revealing a place;
- hybrid Commons as digital cards with an Ortssignal;
- streams such as knowledge, infrastructure, education, culture and mutual aid.

It must not become a hairball network or a raw database list.

## Hybrid behavior

Hybrid Commons may appear in both projections:

| Projection | Hybrid appearance |
| --- | --- |
| Karte | local marker plus rising code pillar |
| Aether | thematic card plus Ortssignal |

The code pillar is not a separate mode. It signals that a local anchor has a digital extension.

The Ortssignal is not an exact location claim. It signals that a digital Commons has a local relation.

## Profile focus

Project profile is a focus state, not a top-level navigation mode.

A project can be opened from Karte, Aether, search or later recommendation flows. The focus state should preserve the user’s previous projection when closing.

Profile focus may show:

- title and summary;
- aspect profile;
- confidence;
- evidence;
- source provenance;
- curation state;
- location visibility mode;
- locked handoff status.

It must not offer join, manage, submit or decide actions until a weltgewebe project identity exists.

## Interaction constraints

The mobile atlas must keep these constraints:

- no Karte / Horizont / Aether three-way navigation;
- no Horizont button;
- no persistent multi-panel desktop shell on phones;
- no overlapping panel stack as the primary navigation;
- no forced map placement for digital Commons;
- no fake coordinates for digital or hidden Commons;
- no backend, accounts, public submissions or weltgewebe write path in static proofs.

## Acceptance markers

A compliant mobile Atlas Shift surface has:

- visible Karte and Aether controls;
- no selectable Horizont control;
- a single atlas stage;
- hybrid map marker with code pillar;
- Aether streams with hybrid Ortssignal;
- profile as focus state;
- reduced-motion handling for animated projection changes;
- explicit static/read-only boundary.
