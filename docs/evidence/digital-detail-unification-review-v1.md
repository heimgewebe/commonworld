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

- Earlier review threads were resolved; the current head then received one additional Codex P1 about cross-surface selection parity.
- Project and provenance links remain filtered through the existing HTTPS sanitizer before rendering.
- Integration with the current `main` was conflict-free, but review found four real stale contracts: generated public-shell asset hashes, the vertical-slice source token for `createRibbonSegment`, and revision-bound benchmark/browser-smoke evidence.
- The generated shell was rebuilt; the vertical-slice validator now checks the canonical project-routing path; static, throttled-browser and public-smoke evidence was regenerated and digest-bound.
- Codex P1 for 667×375 landscape was confirmed: the fixed four-column minimum grid could be clipped. The low-height layout now adapts to one or two columns, with a browser regression proving zero horizontal overflow and reachability of the final evidence section.
- Codex P1 for selection parity was confirmed: digital ribbon activation bypassed the shared `#project-focus` used by map, search and text views. Digital selection now opens and focuses that shared panel, suppresses a duplicate selected inline detail, and restores the inline preview only after the shared focus is closed. Browser coverage binds pointer, keyboard, filtering and Back/Forward behavior to this contract.

## Validation

- JavaScript unit tests: 106 passed, 0 failed.
- Python unit tests: 510 passed, 0 failed.
- Public browser smoke: 31 scenarios passed, including desktop, mobile, iPad, keyboard/history, empty digital paths and external-link safety.
- Proposal browser smoke: 24 scenarios passed.
- Focus-overlay browser smoke: PASS across phone-small, phone, tablet and desktop, including inline digital detail ownership and focus restoration.
- Accessibility browser smoke: 4 scenarios passed for forced colors and increased contrast.
- Catalogue delivery budget: 65 records, 20,132 catalogue/bootstrap gzip bytes and 0 startup project requests.
- Complete local validation receipt SHA-256: `8bdd2b755fa630e98279c6fe3dff71bd33c0236b889be35394ef62da90c70140`.
- Public browser-smoke lifecycle receipt SHA-256: `6af8d36870e9bfbdfb33b54fb6fe4f9164e83097e5f0a4f41eefdaabe67f3128`.
- Focus-overlay browser-smoke lifecycle receipt SHA-256: `ecfb23bf89a6ccc472eefffc71fdfbcbbf22a0501f548c1c20231e43ac6c092a`.
- Complete browser-smoke lifecycle receipt SHA-256: `3c076814d8d36d1225520e112f3956804c0a186f27f78050dcd965ef7540be27`.

## Merge gate

Merge only when GitHub CI is green on the exact final pull-request head and the merge operation is bound to that head SHA.
