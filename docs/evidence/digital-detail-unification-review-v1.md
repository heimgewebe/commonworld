# Digital detail unification review v1

Pull request: #143

Integrated base: `47b6e82c6e359dda1b03737ab45de0dbbca8f794`

## Review scope

- selection routing from every digital lane to the canonical project path
- inline detail ownership versus the detached global focus
- keyboard, history, back-navigation and focus restoration
- responsive four-section information architecture
- external-link sanitization and horizontal-overflow policy

## Findings

- Earlier review threads were resolved; later heads received two additional Codex P1 findings about cross-surface selection parity and residual inline-detail ownership.
- Project and provenance links remain filtered through the existing HTTPS sanitizer before rendering.
- Integration with the current `main` was conflict-free, but review found four real stale contracts: generated public-shell asset hashes, the vertical-slice source token for `createRibbonSegment`, and revision-bound benchmark/browser-smoke evidence.
- The generated shell was rebuilt; the vertical-slice validator now checks the canonical project-routing path; static, throttled-browser and public-smoke evidence was regenerated and digest-bound.
- Codex P1 for 667×375 landscape was confirmed: the fixed four-column minimum grid could be clipped. The low-height layout now adapts to one or two columns, with a browser regression proving zero horizontal overflow and reachability of the final evidence section.
- Codex P1 for selection parity was confirmed: digital ribbon activation bypassed the shared `#project-focus` used by map, search and text views. Digital selection now opens and focuses that shared panel. A follow-up P1 correctly identified that restoring a complete inline preview after close still retained a competing architecture; the lane-local detail container now remains empty and hidden before, during and after selection. Browser coverage binds pointer, keyboard, filtering, close and Back/Forward behavior to this exclusive shared-focus contract.

## Validation

- JavaScript unit tests: 106 passed, 0 failed.
- Python unit tests: 510 passed, 0 failed.
- Public browser smoke: 31 scenarios passed, including desktop, mobile, iPad, keyboard/history, empty digital paths and external-link safety.
- Proposal browser smoke: 24 scenarios passed.
- Focus-overlay browser smoke: PASS across phone-small, phone, tablet and desktop, including exclusive shared-focus ownership and sphere-focus restoration.
- Accessibility browser smoke: 4 scenarios passed for forced colors and increased contrast.
- Catalogue delivery budget: 65 records, 20,132 catalogue/bootstrap gzip bytes and 0 startup project requests.
- Complete local validation receipt SHA-256: `4f107d718cb776dc8f1d898f06dd65e032ab877c73b397269ddfd545d453b7c0`.
- Public browser-smoke lifecycle receipt SHA-256: `dafed7214ecfda8e072add4aae62f9b11448d3b320f267dc552bb1e193d18d7a`.
- Complete browser-smoke lifecycle receipt SHA-256: `3f31f86141c49b6ffb335b5a0eed5da38842aa8bc77e1bf8ff16a3e1b6bd8a91`.

## Merge gate

Merge only when GitHub CI is green on the exact final pull-request head and the merge operation is bound to that head SHA.
