# Source and Curation Policy

## Status

- Type: data trust doctrine
- Applies to: `contracts/commonworld/project.schema.json`
- Builds on: `docs/blueprints/commonproject-projection-contract.md`
- Runtime boundary: static/read-only; no backend, no public submissions, no accounts, no weltgewebe write path

## Decision

commonworld separates project identity, projection and trust state.

`provenance.sources` describes where a claim came from.

`curation.state` describes how far commonworld has reviewed that claim.

A project may be visible in static proofs without being a public catalog claim. Public-facing catalog claims require curated provenance, not fixture data.

## Source classes

| Source type | Meaning | Required evidence |
| --- | --- | --- |
| `fixture` | Synthetic test data | Must only be used with `curation.state: fixture` |
| `official-source` | Source controlled by the project or steward | Must include `url` and `retrieved_at` |
| `public-registry` | Public directory, open data catalog or official register | Must include `url` and `retrieved_at` |
| `manual-curation` | Human curation note | Must include `note` |
| `derived` | Derived from another available source or internal transform | Must include `note`; should not be the only source for curated entries |

## Curation states

### fixture

Fixture entries are synthetic. They are allowed for contract, proof and rendering validation.

They must not be shown as real public catalog entries.

### candidate

Candidate entries are plausible public seeds. They may appear in static proofs or preview surfaces when their candidate status is visible.

They must have at least one non-fixture source and an explicit review marker.

### curated

Curated entries are accepted public catalog candidates.

They must have at least two non-fixture sources, a reviewer, a review date and no fixture provenance.

### archived

Archived entries are retained for continuity and audit. They must not expose handoff actions.

## Publication rules

- fixture entries must use fixture provenance and must not use non-fixture provenance.
- candidate, curated and archived entries must not use fixture provenance.
- candidate, curated and archived entries must include `reviewed_by` and `reviewed_at`.
- official-source and public-registry sources must include `url` and `retrieved_at`.
- manual-curation and derived sources must include `note`.
- curated entries need at least two non-fixture sources.
- curated entries must not rely only on derived sources.
- handoff actions require `curation.state: curated`.
- archived entries must not expose handoff actions.

## Privacy and projection boundary

Curation does not override projection privacy.

A curated project with hidden location still must not expose a map projection. A candidate project with a local anchor still must obey the projection contract.

## Non-goals

This policy does not create public submissions, accounts, backend ingestion, automatic approvals, or a weltgewebe write path.
