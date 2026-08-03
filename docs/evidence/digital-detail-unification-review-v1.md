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

- Three Codex P1 findings existed on the reviewed pull request. Generated public-shell hashes and the vertical-slice routing contract were stale; both were corrected.
- The remaining Codex P1 was confirmed at 667×375 landscape: the fixed four-column detail grid and the two-column header could clip the right-side controls and evidence content.
- Low-height detail cards now use an adaptive one- or two-column grid. The header also collapses when the back action and direct actions do not fit side by side.
- Project and provenance links remain filtered through the existing HTTPS sanitizer before rendering.
- Static, fourfold CPU-throttled browser and public-smoke evidence was regenerated and digest-bound.

## Validation

- Public browser smoke: 31 scenarios passed.
- 667×375 detail: 2 grid columns, 0 px panel overflow, 0 px grid overflow, final evidence section reachable.
- Catalogue delivery: 65 records, 20,132 catalogue/bootstrap gzip bytes and 0 startup project requests.
- Fourfold CPU-throttled browser profiles: mobile and desktop share the same first-party surface hash.
- Composite evidence receipt SHA-256: `f5b7b1bc2802ed9ddec6781cf649f059bcab17d2784f9d066908b0c9d9d6d26c`.
- The composite receipt intentionally does not establish the final commit SHA, GitHub CI on that final head, merge completion or post-merge deployment readback.

## Merge gate

Merge only when GitHub CI is green on the exact final pull-request head, all Codex threads are resolved and the merge operation is bound to that head SHA.
