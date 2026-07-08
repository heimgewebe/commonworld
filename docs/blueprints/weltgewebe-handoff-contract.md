# weltgewebe Handoff Contract

## Status

- Task: COMMONWORLD-ATLAS-V1-T008
- Type: boundary contract doctrine
- Contract anchor: `contracts/commonworld/project.schema.json`
- Builds on: `docs/blueprints/source-curation-policy.md`
- Runtime boundary: static/read-only; no backend, no accounts, no public submissions, no implicit auth sharing, no weltgewebe write path

## Decision

commonworld may point a person from a public catalog entry toward the corresponding weltgewebe project, but it must not itself join, manage, administer, decide or submit anything.

The handoff is therefore a read-only continuation link, not an action authority.

```text
commonworld handoff = continue to known weltgewebe project
weltgewebe action  = join, coordinate, administer, decide
```

## Data shape

A handoff is disabled by default:

```json
{
  "enabled": false,
  "requirements": ["No join, manage or decide action until a weltgewebe project identity exists."]
}
```

An enabled handoff must be explicit:

```json
{
  "enabled": true,
  "system": "weltgewebe",
  "project_id": "known-weltgewebe-project-id",
  "action_label": "Open in weltgewebe",
  "url": "https://example.org/weltgewebe/projects/known-weltgewebe-project-id"
}
```

## Publication rules

- Disabled handoffs must not expose `project_id`, `url` or `action_label`.
- Enabled handoffs require `system: weltgewebe`.
- Enabled handoffs require a concrete `project_id`.
- Enabled handoffs require a concrete `url`.
- Enabled handoffs require `curation.state: curated`.
- Archived entries must not expose enabled handoffs.
- Fixture and candidate entries must not expose enabled handoffs.
- Handoff labels must stay neutral until authorization is modeled.
- Forbidden neutral-label breakouts include `join`, `coordinate`, `manage`, `decide`, `administer` and `submit`.

## Auth and responsibility boundary

commonworld must not share implicit authentication with weltgewebe.

A user who follows a handoff link enters weltgewebe as a separate authority surface. Any account state, role, permission, membership or management action belongs to weltgewebe, not commonworld.

## Non-goals

This contract does not create a login system, membership flow, public submission route, project claiming process, administration console or weltgewebe write path.
