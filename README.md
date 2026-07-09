# commonworld

`commonworld.net` is the public Commons atlas and discovery layer for the heimgewebe ecosystem.

## Product boundary

- `commonworld` helps people discover, understand and trust Commons projects.
- `weltgewebe` remains the deeper action, administration and participation layer.
- The bridge between both systems is an explicit Commons catalog contract, not an implicit shared database.

## Initial build order

1. Define the `CommonProject` contract.
2. Add curated seed projects.
3. Prove the mixed-node marker and detail-panel interaction.
4. Add a privacy-aware MapLibre map proof.
5. Add the focused digital Commons view.
6. Define the safe handoff to weltgewebe.

See `docs/blueprints/commonworld-masterplan.md` for the masterplan.

## Proof hub

The root `index.html` is the static proof hub. Its proof cards consume `proofs/proof-surfaces.json`: `title`, `href` and the user-facing `role` metadata must stay paired with each card's `data-proof-link` and visible role text. `scripts/validate_proof_hub.py` enforces that the hub does not drift from the registry.

## Mixed-node proof

T002 is implemented as an isolated static proof under `proofs/mixed-node/`.
It uses the existing `examples/commonworld/projects/*.json` seeds and does not require a Node stack, MapLibre, a backend, public submissions or a weltgewebe write path.

Run it from the repository root with:

```bash
python3 -m http.server 4173
```

Then open `http://localhost:4173/proofs/mixed-node/`.

## Map proof

T003 is implemented as an isolated static proof under `proofs/map/`.
It uses MapLibre GL JS from a CDN and a public CARTO raster basemap to prove that the `CommonProject` location privacy contract controls what may appear on a map.

Run it from the repository root with:

```bash
python3 -m http.server 4173
```

Then open `http://localhost:4173/proofs/map/`.

## Map source strategy

T004 is documented in `docs/blueprints/map-source-strategy.md`.
T005 is implemented by `proofs/map/map-source.json`, which keeps proof-only MapLibre and CARTO details behind a single replaceable boundary.
commonworld does not operate a second tile infrastructure; it should consume a shared heimgewebe basemap when production map sourcing is ready.

## weltgewebe handoff contract

T008 is documented in `docs/blueprints/weltgewebe-handoff-contract.md`. The handoff is a read-only continuation link to an explicitly known weltgewebe project, not a join, manage, submit, decide or implicit-auth path.

## Runtime and scale boundary

T009 is documented in `docs/blueprints/runtime-scale-boundary.md`. Phase 7 stays plan-before-build: future API, search, spatial index, import candidate and review surfaces must remain read-only until their authority and privacy gates are explicit.

## Static catalog export contract

T010 is documented in `docs/blueprints/catalog-export-contract.md` and anchored by `contracts/commonworld/catalog-export.schema.json`. It defines a read-only static export before any API server, database, ingestion worker or write path is introduced.
T011 is implemented by `scripts/generate_catalog_export.py`, which deterministically regenerates `examples/commonworld/catalog-export.sample.json` from the seed manifest.

## Read-only catalog API contract

T012 is documented in `docs/blueprints/catalog-api-contract.md` and anchored by `contracts/commonworld/catalog-api.contract.json`. It defines future read-only GET delivery routes without introducing an API server, database, ingestion worker, submissions or write path.

## Static catalog API route fixtures

T013 is documented in `docs/blueprints/catalog-api-route-fixtures.md` and implemented by `scripts/generate_catalog_api_route_fixtures.py`. It generates `examples/commonworld/catalog-api-route-fixtures.sample.json`, a deterministic static fixture for the T012 read-only GET routes without introducing an API server, database, ingestion worker, submissions or write path.

## Search index input contract

T014 is documented in `docs/blueprints/search-index-input-contract.md` and anchored by `contracts/commonworld/search-index-input.contract.json`. It defines allowed future search input fields and deterministic rebuild policy without introducing a search service, vector database, crawler, ingestion worker, submissions or write path.

## Static search index input sample

T015 is implemented by `scripts/generate_search_index_input.py` and `examples/commonworld/search-index-input.sample.json`. It deterministically projects the T014 allowed fields from committed CommonProject data and the static catalog export without introducing a search endpoint, search service, vector database, crawler, ingestion worker, submissions or write path.

## Static search proof

T016 is implemented as an isolated static proof under `proofs/search/`. It loads `examples/commonworld/search-index-input.sample.json` and filters the T014 allowed fields in the browser without introducing a search endpoint, search service, vector database, crawler, ingestion worker, submissions or write path. T017 adds transparent local match reasons and a browser-only proof score so search results can be inspected without treating ranking as authority. T018 anchors representative search queries in `examples/commonworld/search-query-fixtures.sample.json` so search quality drift is testable without runtime.
