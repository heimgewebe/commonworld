# CommonProject Projection Contract

## Status

- Type: data contract doctrine
- Builds on: `docs/blueprints/mobile-atlas-shift-interaction-model.md`
- Contract anchor: `contracts/commonworld/project.schema.json`
- Contract version: `schema_version: 2`

## Decision

`CommonProject` now carries an explicit `projections` object.

This is a v2 contract change: pre-projection v1 project entries are not valid against the v2 contract until they declare projections.

`sphere` describes the project type:

```text
place | digital | hybrid
```

`projections` describes where and how the project appears in commonworld:

```text
map | aether | profile
```

This keeps project identity separate from visual projection. A project is still one project when it appears in more than one surface.

## Required shape

Every project must have a `profile` projection. A project must also appear in at least one atlas projection: `map` or `aether`.

```text
CommonProject
├─ projections.map?
├─ projections.aether?
└─ projections.profile
```

## Projection meanings

### map

The `map` projection is only for location-safe projects.

It may use:

- `local-marker` for exact public places;
- `approximate-halo` for approximate public locations;
- `hybrid-code-pillar` for hybrid projects with a local anchor and digital extension.

Hidden locations must not expose a `map` projection.

### aether

The `aether` projection is for digital, hidden-location and hybrid digital extension views.

It may use:

- `digital-card`;
- `hidden-location-card`;
- `hybrid-card`.

Hybrid aether cards can set `ortssignal: true` to signal local relation without asserting an exact location.

### profile

The `profile` projection is a focus state. It is not a top-level navigation mode.

It must preserve the previous atlas projection where possible.

## Semantic rules

- `place` projects must include `map` and must not include `aether`.
- `digital` projects must include `aether` and must not include `map`.
- location-safe `hybrid` projects, using exact or approximate location, must include both `map` and `aether`.
- hidden `hybrid` projects must include `aether` and must not include `map`.
- hidden locations must not include `map`.
- all projects must include `profile`.
- map projection claims must not be more precise than the location mode permits.
- disabled handoffs must not advertise an available profile handoff state.
- projection metadata must not create a second project identity.

## Example mapping

| Project kind | Sphere | Location mode | Projections |
| --- | --- | --- | --- |
| Neighborhood repair fixture | `place` | `approximate` | `map`, `profile` |
| OpenStreetMap | `digital` | `hidden` | `aether`, `profile` |
| OSM Hamburg hybrid fixture | `hybrid` | `approximate` | `map`, `aether`, `profile` |

A hidden hybrid Commons would use `aether` and `profile` only, with an `ortssignal` where local relation should be signaled without publishing a map point.
