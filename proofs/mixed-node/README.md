# Mixed-node visual proof

This is the T002 static proof for `COMMONWORLD-ATLAS-V1`.

It deliberately does not introduce a SvelteKit app, MapLibre route, backend, submission flow or weltgewebe write integration. The proof answers one narrower question: can a `CommonProject` aspect profile be compressed into one mixed node without hiding the meaning, confidence or evidence behind color?

## Run locally

From the repository root:

```bash
python3 -m http.server 4173
```

Then open:

```text
http://localhost:4173/proofs/mixed-node/
```

The proof loads the existing seed examples from `examples/commonworld/projects/*.json`.

## Acceptance coverage

- Weighted aspect segments are derived from the contract seed weights.
- Segment order is deterministic: weight descending, label ascending, id ascending.
- Selecting a node opens one detail surface: bottom sheet on narrow screens, side panel on desktop.
- The detail surface opens and closes with transform/opacity motion instead of a hard visibility jump.
- Touch users can swipe the mobile sheet down from the grip/top edge to close it.
- Aspect cards repeat the ring order and show label, icon token, weight, confidence and evidence.
- CSS includes a `prefers-reduced-motion` rule and the JS closes immediately for reduced-motion users.
