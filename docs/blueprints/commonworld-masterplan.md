# commonworld.net Product Plan v2

## Status

- Type: canonical product and delivery plan
- Decision: active
- Supersedes: the proof-first v1 masterplan
- Product boundary: public discovery in commonworld, participation and administration in weltgewebe
- Immediate priority: real catalog quality and a useful public website before further proof or runtime expansion

## Product promise

commonworld is the public showcase and discovery gateway for Commons.

A visitor should be able to find a Commons worth using, visiting, joining, supporting or learning from within two minutes, understand why it belongs in the catalog, and continue to the best available next place.

```text
commonworld = discover, explore, understand, trust, continue
weltgewebe   = propose, join, coordinate, administer, decide
```

commonworld must bring many good Commons under one coherent public roof without pretending that all Commons are the same, forcing digital projects onto a map, or creating a competing administration system beside weltgewebe.

## Product diagnosis

The v1 program established useful technical foundations:

- a versioned `CommonProject` contract;
- provenance and curation states;
- privacy-aware location modes;
- static map, search, profile and digital-projection proofs;
- a read-only boundary toward weltgewebe;
- deterministic generators, validators and browser checks.

But the product sequence became inverted.

The public site currently explains proofs, fixtures, contracts and boundaries while the catalog contains only four entries, three of them synthetic fixtures, one candidate and no curated public Commons. The implementation has more machinery for projecting and validating entries than real entries worth discovering.

The v2 plan corrects that imbalance:

```text
v1 emphasis: prove the system before filling the world
v2 emphasis: build a trustworthy world while keeping only the system needed to serve it
```

## Decisions retained from v1

These decisions remain correct:

1. **Separate public discovery from administration.** Commonworld stays read-oriented; weltgewebe owns participation and write authority.
2. **Keep provenance visible.** Public claims need sources, review state and freshness.
3. **Respect location privacy.** Exact, approximate and hidden locations remain explicit.
4. **Stay static-first.** A generated static site is sufficient until real catalog scale proves otherwise.
5. **Design mobile-first and accessibly.** The main experience must work without desktop sidebars or visual-only semantics.
6. **Use progressive enhancement.** Core catalog browsing must work before optional map or animation code loads.
7. **Keep automated validation.** Schemas, generated artifacts and browser interaction checks remain valuable safeguards.

## Decisions changed from v1

### The public website is not a proof hub

Proofs are development instruments, not the public product.

They may remain available under a clearly secondary `/lab/` or repository-only route, but the root website must present real Commons, useful discovery paths and human-readable project profiles. Task identifiers, fixture counts, implementation boundaries and test terminology must not dominate the public entry page.

### The map is a view, not the product spine

A map is useful for place-based Commons, but many Commons are digital, distributed, regional or intentionally location-hidden. The primary catalog must therefore be browseable as cards and lists. The map is an optional projection opened when geography is relevant.

On mobile, list and collection discovery should load first. MapLibre and tiles should load only after the user opens the map.

### Aether is not a primary public navigation concept

The v1 Aether proof correctly avoided fake coordinates for digital Commons, but the name and separate mode add conceptual overhead.

Digital, hidden-location and hybrid Commons should appear in the same catalog, search and collections as place-based Commons. A later visual treatment may remain as an experiment, but public navigation should use ordinary language such as:

- online;
- near me;
- places;
- networks;
- knowledge;
- tools;
- care;
- food;
- repair.

### Weighted aspect rings are optional, not foundational

The mixed-node ring is a useful visual experiment, but precise aspect weights and confidence values create editorial effort and apparent mathematical certainty that may not help visitors decide what to do next.

V2 treats the ring as an optional secondary visualization. The public catalog is based first on plain-language themes, shared resources, participation modes and verified evidence. Numeric weights must not be required merely to make a project publishable.

### Search follows real content

Search quality cannot be proven meaningfully against three fixtures and one candidate. Search contracts and fixtures may remain, but new search engineering stops until the catalog has enough real, diverse entries to expose actual discovery problems.

### Growth requires a candidate path

Permanent rejection of all public suggestions would prevent the catalog from growing beyond a small editorial list. Commonworld still must not publish unreviewed submissions directly, but it needs a low-risk suggestion path:

```text
visitor suggestion -> candidate inbox -> human review -> curated catalog -> public build
```

The candidate inbox and review effects should belong to weltgewebe or another explicitly owned curation surface. Commonworld only displays accepted public records.

## Primary audiences and jobs

### Curious newcomer

- Show me what Commons are through concrete examples.
- Help me see possibilities I did not know existed.
- Let me browse without understanding specialist vocabulary.

### Local seeker

- Show me Commons near a place.
- Tell me whether I can visit, use, borrow, repair, learn or meet there.
- Give me current access information and the official next link.

### Online participant

- Show me digital Commons I can use or contribute to from anywhere.
- Let me filter by language, skill level, contribution type and topic.

### Commons steward

- Represent my Commons accurately.
- Suggest corrections or updates.
- Understand how catalog inclusion and verification work.

### Curator

- Compare candidate evidence.
- Publish, refresh, downgrade or archive records through a traceable process.
- Detect stale and incomplete records.

## Public information architecture

The first coherent public product has six surfaces.

### 1. Home

The homepage is editorial discovery, not documentation.

It should contain:

- one clear promise;
- a small set of direct intents such as `near me`, `use online`, `learn`, `repair and share`, `contribute`;
- featured Commons selected by transparent editorial criteria;
- current collections or stories;
- a compact explanation of what qualifies as a Commons;
- a search or explore entry;
- no fixtures and no proof terminology.

### 2. Explore

Explore is the default catalog surface.

It combines place-based, digital and hybrid Commons in one result set and supports useful filters:

- what is shared;
- what a visitor can do;
- place or online availability;
- theme;
- audience;
- language;
- access conditions;
- current verification state.

Results must be readable without opening a map.

### 3. Map

Map is an optional geographic view over the same catalog.

It keeps the existing privacy contract:

- exact public places render exactly;
- approximate projects render with a visible approximation signal;
- hidden locations never become map points;
- digital projects remain discoverable outside the map.

### 4. Project profile

A project profile must answer, in this order:

1. What is this Commons?
2. What is shared or governed together?
3. What can I do here?
4. Who is it for?
5. Is it active and how recently was it verified?
6. Where or how is it available?
7. What conditions, costs, hours or prerequisites apply?
8. Who stewards it and under what governance or license?
9. Which sources support the description?
10. What is the safest useful next step?

Technical metadata belongs in a secondary trust section, not in the opening paragraph.

### 5. Collections and stories

Collections turn a database into an inviting world.

Examples:

- repair and share;
- open knowledge for everyone;
- Commons in Hamburg;
- food and care infrastructures;
- tools for collective work;
- contribute online today;
- places where neighbors make things together.

Collections may be editorial, thematic, geographic or seasonal. They should explain why the projects belong together and provide multiple entry points into the catalog.

### 6. About and method

A public method page explains:

- what commonworld means by Commons;
- inclusion and exclusion criteria;
- curation and verification;
- privacy and location handling;
- correction and suggestion paths;
- the boundary to weltgewebe;
- data and content licenses where applicable.

## CommonProject v3 direction

The existing schema is optimized for proofs and visual projections. V3 should be catalog-centered.

### Required public identity

- stable id;
- canonical name;
- short promise or one-line description;
- full summary;
- primary language and available languages;
- official links;
- representative image with source and rights information.

### Commons substance

- what resource, capability or space is held or produced in common;
- governance or stewardship form;
- access or contribution rights;
- relevant licenses;
- thematic tags;
- project form: place, digital service, network, collection, infrastructure or hybrid.

### Visitor usefulness

- supported actions such as visit, use, borrow, learn, contribute, volunteer, donate, contact or replicate;
- intended audiences;
- access conditions and costs;
- opening hours or availability where relevant;
- required skills, membership or equipment;
- contact and next-step links.

### Status and freshness

- operational status: active, seasonal, paused, unknown or ended;
- last verified date;
- verification method;
- next review date;
- known limitations or uncertainty.

### Place and reach

- exact, approximate or hidden location mode;
- public location label;
- service area or geographic reach;
- online availability;
- coordinates only when publication is appropriate.

### Trust

- provenance sources;
- curator and review date;
- catalog state;
- correction history or audit reference;
- explicit uncertainty notes.

### Relationships

- part of;
- operated by;
- local chapter of;
- depends on;
- related or similar Commons.

Relationships remain descriptive until a real need justifies a graph interface.

### Derived presentation, not source data

These fields should be derived by the presentation layer where possible rather than authored into every entry:

- map versus list projection;
- visual marker appearance;
- profile focus behavior;
- search document shape;
- optional mixed-node representation.

## Inclusion and quality model

Commonworld should maximize useful coverage without lowering trust. It therefore needs separate eligibility, verification and editorial prominence.

### Eligibility gate

A record is eligible when:

- a shared resource, infrastructure, knowledge base, space or capability genuinely exists;
- collective stewardship, open contribution, shared governance or public-use rights are materially present;
- the project is not merely a conventional vendor directory entry;
- at least one reliable public source supports identity and purpose;
- publication does not violate location or participant privacy.

### Catalog states

- `candidate`: plausible, not public in the main catalog;
- `listed`: public identity and basic usefulness verified from at least one strong source;
- `verified`: identity, activity, access and stewardship checked from multiple sources or directly confirmed;
- `featured`: verified and selected editorially for clarity, usefulness, diversity or exemplary practice;
- `stale`: public record needs refresh and is visibly marked or temporarily suppressed;
- `archived`: retained for continuity but no longer presented as active.

Synthetic fixtures remain test data outside the public catalog.

### No universal Commons score

Commonworld must not compress quality into one opaque number. Quality is shown through separate evidence:

- verification state;
- freshness;
- source quality;
- profile completeness;
- access clarity;
- editorial feature label.

Search relevance is not moral rank, and editorial featuring is not a claim that one Commons is universally better than another.

## Catalog growth strategy

### Golden set

The first product milestone is a deliberately balanced set of 30 to 50 real Commons, not another proof.

The set should cover:

- local and digital Commons;
- small and large projects;
- established and emerging forms;
- several countries and languages;
- knowledge, software, data, repair, food, land, culture, care and shared infrastructure;
- multiple participation modes.

Every golden-set entry must be human-reviewed and complete enough to make a useful decision.

### Source portfolio

Growth should combine:

1. official project websites;
2. public registries and movement directories;
3. partner-provided feeds with clear licensing and stewardship;
4. manual editorial discovery;
5. visitor suggestions routed into review, never directly published.

Imports create candidates, not catalog truth.

### Refresh cycle

Each public record receives a next-review date based on volatility:

- active local services: frequent review;
- stable digital infrastructure: slower review;
- event-based or seasonal Commons: date-aware review;
- unreachable or contradictory sources: immediate downgrade to stale.

## Technical delivery model

### Static-generated first

The next public product should still be generated from versioned accepted content. This keeps hosting simple, pages fast and catalog changes reviewable.

A real API, database or search service is justified only when static generation fails a measured need such as:

- build duration;
- catalog volume;
- freshness latency;
- editorial workflow;
- partner synchronization;
- search quality.

### Performance budget

- no map library or tile request on the initial homepage or list view;
- no per-frame JavaScript animation of catalog markers;
- images must be responsive, rights-documented and lazy-loaded below the fold;
- the main discovery path must remain usable with JavaScript disabled where practical;
- interaction checks cover mobile and desktop browsers;
- performance measurements use real catalog pages, not only fixtures.

### Language strategy

The interface starts bilingual in German and English, with a clear fallback strategy. Project records declare content language and available official languages. Machine translation must be marked and must not replace the original source text silently.

### Accessibility

- keyboard-complete navigation;
- visible focus;
- semantic headings and landmarks;
- text alternatives for images and non-text visualizations;
- no color-only meaning;
- reduced-motion support;
- readable plain language before specialist terms.

## Delivery phases

### Phase A: Product reset

Goal: stop presenting the workshop as the product.

Deliverables:

- adopt this v2 plan;
- define a short public Commons eligibility statement;
- move proof and fixture language out of the root experience;
- establish `/lab/` or repository-only ownership for existing proofs;
- define the golden-set editorial brief;
- freeze new API, search-ranking, projection and animation slices unless they directly unblock the public catalog.

Exit gate:

- root information architecture approved;
- fixtures cannot appear as public projects;
- next work queue is content- and product-led.

### Phase B: Golden catalog

Goal: produce enough real material to design against reality.

Deliverables:

- CommonProject v3 draft;
- 30 to 50 real reviewed entries;
- balanced category and geography coverage report;
- verified official links, participation modes and freshness dates;
- representative images with rights metadata;
- five editorial collections.

Exit gate:

- zero fixture entries in the public catalog;
- every public entry answers the ten profile questions;
- at least 80 percent of entries reach `verified` state;
- a visitor can find a relevant project in a moderated user test.

### Phase C: Showcase alpha

Goal: replace the proof hub with a coherent public website.

Deliverables:

- new homepage;
- Explore list and filters;
- real project profiles;
- collection pages;
- optional lazy-loaded map;
- German and English interface foundation;
- public method page;
- outbound continuation links.

Exit gate:

- homepage contains only real public content;
- core browsing works on mobile without loading MapLibre;
- project opening, filtering and continuation are browser-tested;
- five first-time visitors can explain what commonworld offers and find one useful Commons.

### Phase D: Public beta and growth

Goal: expand coverage without losing trust.

Deliverables:

- 150 to 300 real entries;
- suggestion-to-candidate path owned by a review surface;
- stale-record detection;
- correction path for stewards and visitors;
- improved search based on observed queries;
- related Commons and collection recommendations;
- public catalog health indicators.

Exit gate:

- no unreviewed suggestion reaches publication;
- freshness target is met;
- search no-result and abandonment rates are measured;
- catalog balance is reviewed rather than assumed.

### Phase E: Federated scale

Goal: reach broad coverage through trustworthy partners and reusable public data.

Deliverables:

- partner import adapters that create candidates;
- deduplication and identity matching;
- clear data and content licensing;
- read-only public export or API when consumers exist;
- thousands of entries only after review capacity and freshness controls scale with them.

Exit gate:

- ingestion volume cannot outrun human or accountable partner verification;
- failures degrade to stale or candidate states, never silent publication;
- commonworld remains a coherent product rather than a raw aggregator.

### Phase F: Weltgewebe continuation

Goal: connect discovery to collective action without merging authority boundaries.

Deliverables:

- explicit handoff for Commons represented in weltgewebe;
- suggestion, claiming and stewardship workflows owned by weltgewebe;
- preserved return path to the public profile;
- no implicit cross-system permissions.

Exit gate:

- every write action has one clear owner;
- commonworld remains safely browseable without an account;
- users understand when they leave discovery and enter participation.

## Immediate work queue

The next implementation sequence is:

1. Define the public Commons eligibility statement and catalog quality checklist.
2. Draft CommonProject v3 around usefulness, access, freshness and stewardship.
3. Select the 30 to 50-entry golden-set portfolio before collecting individual records.
4. Curate the first ten real entries end to end and identify schema gaps.
5. Design one real project profile using those entries, not fixtures.
6. Design the root homepage around visitor intents and editorial collections.
7. Build Explore as the shared list/search surface for local, digital and hybrid Commons.
8. Move current proof surfaces behind a development-lab boundary.
9. Add the lazy map view over the same Explore results.
10. Add bilingual interface structure and content-language metadata.
11. Test with first-time visitors and stewards.
12. Only then decide whether runtime search, imports or additional visualization are needed.

## Work explicitly paused

Until the Golden catalog and Showcase alpha exit gates are reached, do not prioritize:

- new Aether-specific interaction work;
- animated mixed-node ring reveals;
- new API route fixtures;
- new search scoring or vector search;
- spatial databases;
- separate commonworld accounts;
- automatic global crawling;
- public direct-to-catalog submissions;
- a second curation backend beside weltgewebe;
- visualization work that does not improve discovery or understanding of real entries.

## Success measures

### Catalog health

- count of real public entries;
- share verified and fresh;
- geographic, language and thematic balance;
- stale and archived rate;
- profile completeness;
- source and image-rights completeness.

### Visitor usefulness

- time to first relevant project;
- successful search or browse sessions;
- no-result rate;
- project-profile completion;
- continuation clicks to official resources or weltgewebe;
- return visits and collection exploration.

### Trust

- correction turnaround;
- visible freshness;
- source coverage;
- privacy incidents;
- unreviewed-publication incidents, target zero.

### Performance and access

- core mobile browsing without map load;
- browser interaction pass rate;
- keyboard and screen-reader task success;
- reduced-motion compliance;
- measured page and image budgets.

## North-star acceptance test

A person with no prior Commons vocabulary arrives on commonworld, recognizes several concrete possibilities, finds one project relevant to their place or interests, understands what is shared and what they can do, sees why the record is trustworthy, and reaches a useful next step without encountering proof terminology, synthetic fixtures or administrative complexity.
