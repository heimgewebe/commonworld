# Static Catalog Export Contract

## Status

- Task: COMMONWORLD-ATLAS-V1-T010
- Type: read-only catalog export contract
- Builds on: `docs/blueprints/runtime-scale-boundary.md`
- Runtime boundary: static export first; no API server, no database, no ingestion worker, no public submissions, no write path
- Contract anchor: `contracts/commonworld/catalog-export.schema.json`

## Decision

The first Phase 7 data surface is a static catalog export contract, not a runtime API.

The export is a read-only projection over existing CommonProject entries. It may help a future static site, search prototype or read-only catalog API understand what is in the catalog, but it must not become a source of authority.

```text
CommonProject files = catalog claim source
catalog export      = deterministic read-only projection
runtime API         = later delivery surface, if still needed
```

## Data shape

A static catalog export has:

- `schema_version: 1`;
- `kind: commonworld.static_catalog_export`;
- `scope: proof` or `public`;
- `source_manifest_path` pointing at the manifest that enumerates entries;
- `entries` with project id, project path, curation state, location mode and profile handoff state;
- a `boundary` block declaring read-only access and no write side effects.

## Publication rules

- Proof exports may include fixture and candidate entries for static proof surfaces.
- Public exports must only include accepted catalog data.
- Public exports must not publish fixture entries.
- Public exports must not publish candidate entries as if they were curated.
- The export must not contain secrets, credentials, account state, role state or private review notes.
- The export must not create a public submission route.
- The export must not create a weltgewebe write path.

## Authority boundary

The export is derived. It does not decide whether a project is valid, curated, joinable or manageable.

Source curation remains with CommonProject files and their curation policy. Participation, administration and review write effects remain outside commonworld's static export surface.

## Next safe implementation

The next implementation slice may add a deterministic static export generator or a proof-only export file. It should still avoid API runtime, database selection, ingestion workers and public write paths.
