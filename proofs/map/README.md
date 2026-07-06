# Privacy-aware map proof

This is the T003 static map proof for `COMMONWORLD-ATLAS-V1`.

It remains a proof, not an application stack. It uses MapLibre GL JS from a CDN and a public CARTO raster basemap to validate one narrow question: can the CommonProject `location` contract decide what is allowed to appear on a public map?

## Boundary

- No backend.
- No public submissions.
- No weltgewebe write path or handoff.
- No SvelteKit commitment.
- CDN and tile requests are external proof dependencies, not production infrastructure decisions.

## Run locally

From the repository root:

```bash
python3 -m http.server 4173
```

Then open:

```text
http://localhost:4173/proofs/map/
```

## Privacy acceptance coverage

- `hidden` projects must not create map markers.
- `approximate` projects with coordinates render as mixed-node markers with a visible approximate-location halo.
- `exact` projects with coordinates would render as mixed-node markers without the halo.
- Projects without renderable coordinates are skipped.
- Hidden digital commons are deferred to a later digital proof instead of being forced onto the map.
