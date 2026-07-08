# Runtime and Scale Boundary

## Status

- Task: COMMONWORLD-ATLAS-V1-T009
- Type: runtime boundary doctrine
- Builds on: `docs/blueprints/commonworld-masterplan.md`
- Runtime boundary: plan-before-build; no backend service, no database, no ingestion worker, no public submissions, no write path

## Decision

Phase 7 must start with a boundary, not with an API server.

commonworld may later add read-only runtime surfaces for catalog delivery, search and scale. Those surfaces must preserve the atlas role:

```text
commonworld runtime = read, search, project public catalog claims
weltgewebe runtime   = join, coordinate, administer, decide, review write effects
```

## Allowed future runtime surfaces

The first allowed runtime surfaces are:

- read-only catalog API;
- search index derived from accepted catalog data;
- spatial index only when static proof data no longer answers the product question;
- import candidate preview, not automatic publication;
- review console only if ownership remains explicit, likely in weltgewebe.

## Gates before implementation

Before adding a real runtime service, commonworld must define:

- source of truth for catalog entries;
- read-only API contract;
- search index input and rebuild policy;
- spatial indexing need and privacy impact;
- import candidate acceptance path;
- review authority owner;
- failure mode and cache behavior;
- deployment and observability boundary.

## Prohibited shortcuts

Phase 7 must not introduce:

- own administration backend;
- public submission writes;
- account or role system;
- Supabase core;
- PostGIS core;
- Rust API;
- automatic global imports;
- exact location defaults;
- weltgewebe write path.

## Sequencing rule

The next implementation slice after this doctrine should be a read-only catalog API contract or static catalog export contract. It should not start by choosing a database, framework or hosting stack.
