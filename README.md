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
4. Add a MapLibre map proof.
5. Add the focused digital Commons / Aether view.
6. Define the safe handoff to weltgewebe.

See `docs/blueprints/commonworld-masterplan.md` for the masterplan.

## Mixed-node proof

T002 is implemented as an isolated static proof under `proofs/mixed-node/`.
It uses the existing `examples/commonworld/projects/*.json` seeds and does not require a Node stack, MapLibre, a backend, public submissions or a weltgewebe write path.

Run it from the repository root with:

```bash
python3 -m http.server 4173
```

Then open `http://localhost:4173/proofs/mixed-node/`.
