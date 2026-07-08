# Search Index Input Contract

## Status

- Task: COMMONWORLD-ATLAS-V1-T014
- Type: search index input contract and rebuild policy, no runtime implementation
- Builds on: `docs/blueprints/runtime-scale-boundary.md`, `docs/blueprints/catalog-export-contract.md` and `docs/blueprints/source-curation-policy.md`
- Contract anchor: `contracts/commonworld/search-index-input.contract.json`
- Boundary: no search service, no vector database, no crawler, no ingestion worker, no public submissions, no write path

## Decision

commonworld may define a search index input contract before it builds search.

The contract describes which read-only catalog fields a future search index may consume and when such an index may be rebuilt. It must not introduce a search endpoint, search server, vector store, database, crawler, live ingestion process, ranking model, account system, submission flow, review workflow or weltgewebe write effect.

```text
CommonProject files        = catalog claim source
static catalog export      = deterministic read-only projection
search index input contract = allowed future search input shape and rebuild policy
search runtime             = not implemented by this contract
```

## Allowed search input fields

The first allowed index input fields are:

- `id`;
- `title`;
- `summary`;
- `aspects`;
- `curation_state`;
- `location_label`;
- `location_mode`;
- `project_path`;
- `profile_handoff_state`.

These fields must derive from accepted CommonProject files or from the generated static catalog export. They are enough for a later search prototype to find a project by name, summary, aspect, curation state or deliberately safe location label.

## Required boundary

Every search input field in the contract must declare:

- `source: CommonProject` or `source: generated static catalog export`;
- `indexable: true` only for the allowed public-read fields;
- `writes: false`;
- `submissions: false`;
- `private_review_data: false`.

The contract must also declare:

- `access: derived-read-only`;
- `authority: derived search input only; CommonProject files remain authoritative`;
- `rebuild_mode: deterministic batch rebuild`;
- `rebuild_trigger: committed CommonProject, seed manifest, catalog export or search input contract changes`;
- `runtime_dependency: none`.

## Prohibited shortcuts

T014 must not introduce:

- search endpoint or API route;
- search server;
- vector database;
- database requirement;
- crawler;
- live ingestion worker;
- ranking model authority;
- account or role system;
- public submission route;
- review write path;
- import mutation path;
- private review notes;
- hidden or exact private location data beyond the public CommonProject location label and mode;
- weltgewebe write path.

## Rebuild policy

A future generated search input artifact may be rebuilt deterministically from committed repository data. Rebuilds must be local or CI batch jobs, not a long-running ingestion worker.

A stale generated search input artifact must fail validation until regenerated. Staleness must not trigger automatic publication, mutation or review decisions.

## Next safe implementation

A later slice may add a deterministic generated search input sample. It should still avoid a search endpoint, database choice, vector store, crawler, ingestion worker and public write path.


## Implemented proof search input generator

COMMONWORLD-ATLAS-V1-T015 is implemented by `scripts/generate_search_index_input.py` and `examples/commonworld/search-index-input.sample.json`.

The generator deterministically derives the proof search input from the static catalog export and referenced CommonProject files. `make generate-search-index-input` rewrites the sample, while `make validate` checks that the committed sample is up to date. It exposes only the T014 allowed fields and does not introduce a search endpoint, database, vector store, crawler, ingestion worker or public write path.
