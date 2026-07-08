# commonworld map source strategy

Status: accepted
Task: COMMONWORLD-ATLAS-V1-T004
Implementation marker: COMMONWORLD-ATLAS-V1-T005 is implemented by `proofs/map/map-source.json` for static proofs.
Owner layer: commonworld atlas semantics, heimgewebe shared map infrastructure

## Decision

commonworld must not operate a second tile infrastructure. The public atlas should consume a shared heimgewebe basemap service when one is available, while commonworld owns only the Commons discovery layer above that basemap.

The production target is a shared heimgewebe basemap, not a hard-coded third-party tile provider and not a commonworld-specific tile factory.

## Boundary

commonworld owns:

- CommonProject markers and mixed-node rendering.
- Location privacy projection: hidden, approximate, exact.
- Atlas copy, discovery surfaces and evidence language.
- Map source selection at the client/config boundary.

commonworld does not own:

- Tile generation.
- PMTiles packaging.
- Tile cache operations.
- Basemap database imports.
- Long-running basemap jobs.
- A separate operational map service.

weltgewebe remains the action, participation and administration layer. A shared basemap may serve both weltgewebe and commonworld, but that shared service must not turn commonworld into a second governance or operations truth.

## Source modes

### proof

The proof mode may use external CDN and raster tile dependencies. It must say so in the proof README and UI copy. It may be brittle and has no availability promise. It exists to validate the atlas and privacy logic, not to define production infrastructure.

### staging

The staging mode should use a configurable style URL. It may point either to the shared heimgewebe basemap or to a temporary provider. The choice must remain replaceable without changing CommonProject privacy logic or marker rendering.

### production

The production mode should use the shared heimgewebe basemap style URL once that service is ready for commonworld consumption. A fallback provider is allowed only when it is explicit, documented and governed by the same attribution, cache policy and provider terms gates.

## Required map source contract

A future map source config should expose at least:

- mode: proof, staging or production.
- style URL or style object reference.
- attribution text and attribution URL.
- cache policy.
- provider terms reference.
- allowed fallback behavior.
- failure mode copy for users.
- privacy notes for location projection.

The client may read this contract. It must not derive tile provider policy from scattered literals in proof code.

## Operational gates

Before commonworld uses any production basemap source, the following must be known:

- Attribution is visible and correct.
- Provider terms allow the intended traffic.
- Cache policy is explicit.
- No bulk loading and no prefetch behavior are introduced by commonworld.
- Tile failures produce user-visible failure mode copy.
- Privacy projection remains independent from basemap choice.
- Provider switching does not change CommonProject semantics.

## Relationship to existing map infrastructure

The weltgewebe codebase already contains a local-sovereign and remote-style basemap pattern, including local basemap style references and basemap build/publish scripts in its repository snapshot. commonworld should treat that as an architectural precedent, not as proof that the current live service is ready.

The ideal shared shape is:

```text
heimgewebe shared basemap service
  -> consumed by weltgewebe for action and administration
  -> consumed by commonworld for public atlas discovery
```

## Implemented static proof config

T005 is implemented by `proofs/map/map-source.json` for static proofs. The config keeps the current proof working while moving provider details behind a single replaceable boundary.

The static proof config still avoids backend work, tile hosting, public write paths and weltgewebe handoff logic.
