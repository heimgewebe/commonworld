# Commonworld Immersive Experience Doctrine

## Status

- Type: canonical interaction and visual-experience doctrine
- Decision: active
- Builds on: `docs/blueprints/commonworld-masterplan.md`
- Supersedes as public navigation doctrine: `docs/blueprints/mobile-atlas-shift-interaction-model.md`
- Product boundary: discovery in commonworld; participation and administration in weltgewebe

## Decision

Commonworld must feel like entering and exploring a living world of Commons, not like reading a directory and not like operating an administration dashboard.

The target is **game feel without gamification**:

```text
simple controls
+ immediate feedback
+ spatial continuity
+ atmospheric visual identity
+ meaningful discovery
- points, streaks, loot, artificial scarcity or manipulation
```

A first-time visitor must understand the interface without instruction. The world feeling comes from continuity, responsiveness, depth and discovery—not from adding more controls or game mechanics.

## Desired feeling

The experience should feel:

- inviting rather than institutional;
- alive rather than animated for its own sake;
- spatial rather than page-fragmented;
- clear rather than minimal to the point of emptiness;
- surprising without becoming unpredictable;
- rich without becoming dense;
- playful without trivializing the Commons;
- fast enough that the interface feels directly attached to the visitor's hand.

The visitor should feel that many different Commons belong to one world while each keeps its own identity, place, people and conditions.

## Core interaction loop

The primary loop is:

```text
orient -> notice -> approach -> open -> understand -> continue -> return
```

### Orient

The visitor sees one coherent world stage, a few recognizable landmarks and one obvious next action. No filter wall, modal tutorial or technical explanation blocks entry.

### Notice

Motion, scale, contrast and grouping gently reveal nearby or relevant Commons. Nothing flashes for attention. Important items are legible through shape, text and position, not color alone.

### Approach

A tap, click, drag or scroll produces immediate visual feedback. A selected Commons comes forward while the surrounding world remains recognizable.

### Open

The project focus grows from the selected object or position instead of appearing as an unrelated new page. Deep links remain possible, but exploration preserves spatial context.

### Understand

The first profile layer answers what the Commons is, what can be done there and why it may matter. Trust, evidence and detailed conditions unfold progressively rather than appearing as a metadata wall.

### Continue

The visitor can follow one clear next step: visit, use, learn, contribute, contact, open the official site or continue into weltgewebe when available.

### Return

Closing a profile returns to the same camera position, collection, filters and scroll state. The visitor never loses the world they were exploring.

## One world shell

Commonworld should not feel like six unrelated sections. Home, Explore, collections, search and the map are coordinated views within one persistent shell.

The shell contains:

- a world stage;
- a compact top or bottom navigation suited to the device;
- one search entry;
- one current lens indicator;
- one focus layer for an opened Commons;
- a preserved exploration state;
- URL and browser-history state sufficient for deep links, Back and Forward.

The public mental model is:

```text
World
├─ discover paths and landmarks
├─ search or filter the same world
├─ switch to a geographic lens when useful
└─ focus one Commons without leaving the world
```

Desktop and mobile may arrange controls differently, but they must share this mental model.

The conceptual lens names `World`, `Near` and `Find` must be localized in the interface, for example `Welt`, `Nähe` and `Finden` in German. They are product concepts, not mandatory English labels.

## Control model

The interface borrows responsiveness from games, not specialized game controls.

Primary controls are familiar web and touch actions:

- scroll or swipe to move through guided world space;
- tap or click a Commons to focus it;
- drag only where the surface clearly signals direct movement;
- pinch and standard map gestures only inside Near;
- Back or Escape to leave focus or an overlay;
- keyboard focus and ordinary links for the equivalent linear route.

The public entry must not require WASD, a virtual joystick, free-camera mastery, precision dragging, a tutorial level or 3D navigation. A free camera may be explored later only if usability evidence proves it simpler than guided movement.

Every spatial presentation must have a semantically ordered linear equivalent using the same Commons objects and actions. Spatial location may aid orientation but must never be the only way to discover or understand content.

## Primary lenses

### World

`World` is the default, non-geographic discovery lens.

It may combine:

- curated paths;
- thematic neighborhoods;
- featured landmarks;
- nearby opportunities when location is allowed;
- online Commons;
- calm movement between clusters of meaning.

Thematic placement is editorial and navigational. It must not pretend to be an objective scientific coordinate system.

### Near

`Near` is the geographic lens. It uses the existing exact, approximate and hidden location contract.

MapLibre and tiles load only when this lens is opened. Hidden and digital Commons remain reachable through World and search.

### Find

`Find` is a lightweight overlay or command surface, not a separate technical search application.

It supports plain-language queries and a small number of useful filters. Results retain the same project cards and focus behavior used elsewhere.

A visitor must always be able to leave Find and return to the previous world position.

## Curated paths instead of static collection pages

Collections should feel like routes through the world rather than isolated article indexes.

A path has:

- a clear human question or invitation;
- a short editorial introduction;
- a sequence or constellation of real Commons;
- optional branches;
- visible progress through the path without scores or completion pressure;
- an exit back into free exploration at any point.

Examples:

- Repair something together
- Learn from open knowledge
- Find Commons around Hamburg
- Contribute online today
- Discover shared food and care infrastructures

Paths create narrative and momentum while keeping every Commons independently discoverable.

## Project focus

Opening a Commons must feel like approaching an object in the same world.

The focus layer should:

- originate visually from the selected card, marker or landmark where feasible;
- keep part of the world visible;
- expose one clear close/back action;
- preserve focus and navigation accessibility;
- show the useful summary before trust metadata;
- allow a stable shareable URL;
- restore the exact previous exploration state when closed.

On mobile this may be a full-height sheet. On desktop it may be a centered or side focus layer. It must not become a stack of overlapping panels.

## Visual language

### World atmosphere

The base visual identity may use:

- a dark, calm world field;
- luminous but restrained Commons objects;
- depth through scale, blur, parallax and layering;
- environmental gradients and subtle texture;
- distinct thematic regions;
- optional sound only after explicit user activation and off by default;
- generous negative space;
- typography strong enough to carry meaning without effects.

Atmosphere must never lower text contrast or obscure controls.

### Commons objects

Each Commons needs a recognizable visual presence built from:

- title or short label;
- project image or meaningful symbol when rights permit;
- a small set of themes or actions;
- location or online signal;
- verification and freshness signal;
- optional mixed-node signature.

The mixed-node ring may remain as a brand motif or compact theme signature. It must not require false precision, dominate the object or animate continuously.

### Landmarks

Featured Commons and curated paths may become landmarks through scale, composition or illustration. Landmark status is editorial, visibly explained and never presented as a universal quality score.

## Motion doctrine

Motion communicates continuity, cause and depth. It is not decoration.

Allowed purposes:

- show where an object came from or moved to;
- preserve orientation during lens changes;
- reveal hierarchy;
- acknowledge input;
- distinguish entering focus from leaving it;
- make direct manipulation feel physical.

Disallowed patterns:

- perpetual pulsing of many objects;
- per-frame JavaScript rewriting of gradients or catalog markers;
- motion that delays access to information;
- unrelated entrance animation for every card;
- scroll hijacking;
- forced cinematic sequences;
- motion used to disguise loading or uncertainty;
- animation that competes with reading;
- pointer-bound parallax or camera updates on every raw movement event;
- large continuously animated blur or backdrop-filter surfaces;
- autoplay audio or sound required for orientation.

Default transitions should normally complete in roughly 160–320 ms. Longer camera moves are acceptable only when distance and orientation genuinely require them and must remain interruptible.

Input acknowledgement should begin in the next rendered frame. The interface must never wait for animation completion before accepting the next safe input.

## Rendering strategy

The experience goal does not prescribe a game engine. Use the simplest rendering technology that can satisfy clarity, direct manipulation and fluidity.

The preferred order is:

1. semantic HTML and CSS;
2. lightweight DOM-based spatial enhancement;
3. Canvas or WebGL only after profiling proves that the simpler approach cannot sustain the required world density or motion.

No phase may introduce a 3D engine, WebGL dependency or canvas-only interface merely to signal ambition. Search indexing, deep links, browser history, keyboard navigation and the linear equivalent must remain intact regardless of rendering technology.

## Fluidity and performance budgets

The experience is only immersive when it is responsive.

Required budgets:

- immediate pressed, hover or focus response;
- no long task above 50 ms during ordinary exploration on the reference mobile device;
- motion designed for a 60 Hz frame budget and tested for dropped frames;
- no continuous animation when the scene is idle;
- homepage and World lens load without MapLibre or tile traffic;
- images decode without blocking first interaction;
- project focus opens from already available summary data;
- expensive detail, evidence and map data may load progressively after focus begins;
- browser tests cover rapid open, close, reopen, lens change and interrupted motion;
- reduced-motion mode removes spatial travel while preserving state changes and clarity.

Performance must be measured against real project images and real catalog density, not only fixtures and DOM stubs.

## Simplicity rules

### One obvious primary action

Every state has one obvious primary action and no more than a few secondary actions. Important actions use ordinary language.

### Progressive disclosure

The visitor sees only what is needed for the current decision:

1. recognize;
2. inspect;
3. trust;
4. continue.

### No specialist vocabulary at entry

Terms such as projection, curation state, Aether, handoff contract and confidence weight do not belong in first-layer public navigation.

### No mode maze

The interface should expose at most the three public lenses `World`, `Near` and `Find`. Profile focus is a state, not another mode.

### Same objects everywhere

A Commons keeps the same title, image, theme signature and interaction behavior in World, Near, Find and curated paths. The visitor should not need to relearn the object.

## Game feel without game mechanics

Commonworld may borrow these qualities from games:

- direct manipulation;
- responsive camera and focus transitions;
- environmental storytelling;
- landmarks and paths;
- curiosity-driven exploration;
- persistent position and context;
- small moments of visual delight;
- mastery through familiarity rather than instruction.

Commonworld must not use:

- points or experience levels;
- streaks;
- badges for ordinary browsing;
- leaderboards;
- loot-box or variable-reward patterns;
- artificial scarcity;
- countdown pressure;
- manipulative notifications;
- compulsory accounts to preserve basic navigation state;
- moral ranking of projects or people.

The reward is discovering a real possibility and reaching it.

## Data and editorial implications

The experience must be generated from truthful catalog fields, not from invented game metadata.

CommonProject v3 and collection records should support:

- strong short descriptions;
- visitor actions;
- images and rights metadata;
- themes and intended audiences;
- location and online reach;
- status and freshness;
- clear next steps;
- editorial path membership;
- optional visual motif tokens derived from real themes.

The system may derive layout, emphasis and transitions. It must not invent participation, activity, popularity or geographic claims.

## Vertical-slice rule

The immersive experience must be tested before the full golden catalog is complete. `Playable` means that the complete discovery loop works through direct interaction; it does not mean that Commonworld becomes a game with scores or objectives.

The first playable vertical slice uses 8–12 real Commons selected to cover:

- local, digital and hybrid forms;
- at least four themes;
- different actions such as visit, use, learn and contribute;
- exact, approximate and hidden locations;
- different image and text conditions;
- German and English content.

The slice must include:

- World entry;
- one curated path;
- Find;
- Near as a lazy-loaded lens;
- project focus;
- return to preserved position;
- real continuation links;
- reduced-motion behavior;
- mobile and desktop browser tests.

Only after this slice feels clear and fluid should the catalog expand to 30–50 entries and the interaction pattern be generalized.

## Acceptance tests

### Five-second orientation

A first-time visitor can state what the site offers and identify one thing to do within five seconds.

### No-instruction navigation

A first-time visitor can open a Commons, close it and return to the same place without explanation.

### Discovery loop

A visitor can follow one curated path, leave it for free exploration and still understand where they are.

### Fluid focus

Rapid open, close and reopen actions remain correct. No panel is invisible, stranded, duplicated or delayed behind an animation.

### Lens continuity

Switching World -> Near -> World preserves the selected project or prior exploration context where meaningful.

### Reduced motion

Reduced-motion users receive immediate state changes, not a degraded or incomplete interface.

### Useful outcome

A visitor reaches at least one real next step—official site, visit information, contribution guide, contact or weltgewebe continuation—without encountering proof or fixture language.

## Relationship to existing proofs

The existing mixed-node, map, Aether, search and mobile-atlas-shift proofs remain evidence and a component laboratory.

They are not the public navigation architecture.

Useful parts may be reused only after they fit this doctrine. In particular:

- map privacy rules remain;
- mixed-node identity may remain;
- Aether's refusal of fake coordinates remains;
- the fixed `Karte <-> Aether` switch does not remain as public doctrine;
- proof-specific terminology and surfaces move behind a lab boundary.
