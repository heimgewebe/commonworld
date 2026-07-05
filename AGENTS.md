# Agent rules for commonworld

## Product boundary

commonworld is the public Commons atlas and discovery layer. It must not become a second administration backend beside weltgewebe.

## Build order

1. Contract before UI.
2. Curated seed data before imports.
3. Static visual proof before API.
4. Read-only API before write paths.
5. Handoff to weltgewebe only after an explicit contract.

## Safety rules

- Do not add public submissions before governance exists.
- Do not add exact public locations by default.
- Do not treat color as the only semantic carrier.
- Do not introduce Supabase, PostGIS or a Rust backend before a dedicated ADR.
- Preserve source provenance for all catalog entries.

## Preferred first slices

- `CommonProject` JSON Schema.
- Seed project examples.
- Mixed node marker component.
- Detail panel with aspect-colored cards.
- MapLibre proof route.
