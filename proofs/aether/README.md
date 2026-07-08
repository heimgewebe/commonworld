# Focused Aether proof

This is the T006 static proof for `COMMONWORLD-ATLAS-V1`.

The map proof deliberately skips hidden projects and must not invent false geographic points. This proof gives digital, hidden-location and hybrid Aether projections a focused surface instead of a tangled network graph.

## Boundary

- No backend.
- No public submissions.
- No map route or MapLibre dependency.
- No force-directed hairball network.
- No weltgewebe write path or handoff.
- One active Aether branch at a time.

## Run locally

From the repository root:

```bash
python3 -m http.server 4173
```

Then open:

```text
http://localhost:4173/proofs/aether/
```

## Acceptance coverage

- CommonProject entries with `projections.aether` render in the Aether branch rail.
- Hidden-location projects are not assigned coordinates.
- Place-based projects stay out of the Aether proof.
- The active branch shows summary, location privacy, aspects, evidence count, public sources and locked handoff state.
