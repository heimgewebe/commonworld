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
