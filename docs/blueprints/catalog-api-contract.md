# Read-only Catalog API Contract

## Status

- Task: COMMONWORLD-ATLAS-V1-T012
- Type: read-only API contract, no runtime implementation
- Builds on: `docs/blueprints/runtime-scale-boundary.md` and `docs/blueprints/catalog-export-contract.md`
- Contract anchor: `contracts/commonworld/catalog-api.contract.json`
- Boundary: no API server, no database, no ingestion worker, no public submissions, no write path

## Decision

commonworld may define a read-only catalog API contract before it builds any API runtime.

The contract describes what a future delivery surface may expose. It must not introduce a server, persistence layer, authentication system, submission flow, review workflow or weltgewebe write effect.

```text
static catalog export = current generated data source
catalog API contract  = allowed future read-only delivery shape
catalog API server    = not implemented by this contract
```

## Allowed read-only routes

The first allowed routes are:

- `GET /catalog/v1/catalog-export` for the static catalog export payload;
- `GET /catalog/v1/projects` for a read-only project list;
- `GET /catalog/v1/projects/{project_id}` for one read-only project detail.

All routes must derive from the generated static catalog export or accepted CommonProject data. None may mutate catalog state.

## Required response boundary

Every route in the contract must declare:

- `method: GET`;
- `access: public-read-only`;
- `source: generated static catalog export` or `source: accepted CommonProject data`;
- `writes: false`;
- `submissions: false`;
- `auth_required: false` for the public catalog surface.

## Prohibited shortcuts

T012 must not introduce:

- POST, PUT, PATCH or DELETE routes;
- public submission route;
- account or role system;
- review write path;
- import mutation path;
- database requirement;
- server implementation;
- weltgewebe write path.

## Next safe implementation

A later slice may add a static mock response or route fixture for these read-only routes. It should still avoid API runtime, database selection, ingestion workers and public write paths.
