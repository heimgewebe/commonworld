# commonworld.net Masterplan

## Decision

commonworld is a separate repository and product surface for `commonworld.net`.

It is the public Commons atlas: a visual, curated discovery layer for physical, digital and hybrid commons projects.

weltgewebe remains the later action, administration and participation layer.

## Core boundary

```text
commonworld = discover, understand, trust, continue
weltgewebe   = join, coordinate, administer, decide
```

commonworld may build its own interface and public catalog. It must not silently create a competing administration truth beside weltgewebe.

## System axis

The important first axis is not only physical versus digital. The first axis is visibility versus responsibility.

A public atlas makes claims. Therefore every shown project needs provenance, curation state, confidence, and a location visibility mode.

## Product layers

1. Contract Layer: define `CommonProject` and aspect semantics.
2. Catalog Layer: curated public seed data.
3. Visual Layer: map, mixed nodes, detail panels and focused digital commons view.
4. Handoff Layer: explicit bridge to weltgewebe.

## CommonProject sketch

A project has:

- stable id
- title and summary
- sphere: `place`, `digital` or `hybrid`
- weighted aspects with label, color token, icon token, confidence and evidence
- optional public location with `exact`, `approximate` or `hidden` mode
- source provenance
- curation state
- optional weltgewebe handoff

Color is never the only semantic carrier. Every color segment also needs label, icon, text and source evidence.

## Visual model

The core visual object is the mixed node.

A mixed node has a dark center and a segmented ring. The ring compresses the project's aspect profile. Tapping the marker opens a bottom sheet on mobile or a side panel on desktop. The detail cards use the same aspect colors as borders, in the same order as the ring.

The ring indicates profile, not value. A 40 percent repair aspect is not morally better than a 20 percent education aspect; it is more prominent in the project profile.

## Map model

The map is a calm stage, not a data storm. It should render projects, clusters and approximate positions. Exact locations are opt-in. Approximate is the default for new entries. Hidden locations are never rendered as exact points.

## Digital commons model

The digital / Aether view is a focused lens, not an unbounded graph.

Only one branch is active at a time, for example:

```text
Code / Rust / Commons tools
Knowledge / Climate / Open data
Education / School / OER
Culture / Music / Free archives
```

Circle packing is allowed only when the data is actually hierarchical. Network relations need a later model.

## Build phases

### Phase 0: Repository and boundary

- private GitHub repo
- README
- AGENTS
- masterplan
- ADR for separate repository

### Phase 1: Contract

- `contracts/commonworld/project.schema.json`
- `contracts/commonworld/aspect.schema.json`
- seed examples
- validation tests

### Phase 2: Static visual proof

- isolated static proof before app-stack commitment
- mixed node marker
- aspect cards
- mobile bottom sheet
- desktop side panel
- fixture data loaded from the CommonProject examples
- no MapLibre route, backend, submissions or weltgewebe write path

### Phase 3: Map proof

Map source strategy: `docs/blueprints/map-source-strategy.md` defines proof, staging and production map-source boundaries before commonworld adopts shared basemap infrastructure.

- privacy-aware static map proof
- hidden digital projects skipped from map rendering
- approximate locations shown with visible privacy halo

- MapLibre route
- seed markers
- clusters
- public location modes

### Phase 4: Digital commons proof

- focused Aether view
- one active branch
- breadcrumb navigation
- no hairball network

### Phase 5: Governance

- source policy
- curation policy
- privacy policy
- taxonomy policy

### Phase 6: weltgewebe handoff

- handoff schema
- disabled-by-default CTA
- no implicit auth sharing
- no join/manage action without weltgewebe project identity

### Phase 7: Runtime and scale

- read-only catalog API
- search
- spatial indexing if proven necessary
- import candidates
- review console, likely in weltgewebe

## Non-goals at start

- no own administration backend
- no public submissions
- no Supabase core
- no PostGIS core
- no Rust API
- no automatic global imports
- no exact location defaults

## First good issue sequence

1. Define `CommonProject` JSON Schema.
2. Add two valid seed examples.
3. Add a schema validation test.
4. Build isolated `MixedNodeMarker`.
5. Build `CommonProjectSheet`.
6. Add MapLibre proof route.
7. Add Aether proof route.
8. Define weltgewebe handoff contract.

## Success criterion

A person taps a mixed node and understands within ten seconds what the commons project is, which aspects it contains, where the claims come from, and what the next safe action is.
