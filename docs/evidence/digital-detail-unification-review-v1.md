# Digital detail unification review v1

Pull request: #143

Integrated base: `47b6e82c6e359dda1b03737ab45de0dbbca8f794`

## Review scope

- selection routing from every digital lane into the shared project focus
- preservation of the originating digital lane across open, close, Escape and history navigation
- exclusive detail ownership versus retired lane-local detail rendering
- keyboard, pointer, responsive, external-link and overflow behavior
- deterministic shell, browser and delivery-evidence bindings
- removal of temporary PR-only automation before merge

## Findings

- Codex P1 confirmed that project activation from a non-identity lane silently rewrote `digital_path` to a derived child bundle. Closing the shared focus therefore stranded the user in a lane that was never selected. Digital activation now changes only the project focus; the originating lane remains stable through pointer, keyboard, Escape and Back/Forward paths.
- Codex P1 confirmed that the removed lane-local renderer left an orphaned `.layer-project-detail` / `.project-detail-*` stylesheet and unused English labels behind. The dead selectors, responsive variants and translations were deleted rather than preserving a second detail architecture.
- Self-review found two browser contracts that still required obsolete lane-focus state: one demanded an automatic child-lane jump, another demanded a non-root `focusedPath` after opening a project from the root lane. Both now prove the canonical behavior instead: the originating root or parent lane remains unchanged while the shared `#project-focus` opens above it.
- Live-state review found temporary PR follow-up automation repeatedly committing its own failure diagnostics and retriggering itself. The workflow was disabled before reconciliation; its workflow, helper scripts and temporary error artifact are absent from the final product tree.
- Project and provenance links remain filtered through the existing HTTPS sanitizer before rendering. The canonical shared focus remains the sole complete project-detail surface.

## Validation evidence

- Public browser smoke: 31 scenarios passed on the final product surface, including root-lane and parent-lane preservation, pointer and keyboard activation, Escape, Back/Forward, mobile, iPad, recovery and external-link safety.
- Public smoke lifecycle receipt SHA-256: `6ad2f35969943e5c718aedf2125fa3d1914b1565ad14819ced7482116e4713bc`.
- Public smoke result SHA-256: `6ce88ba61fc142c70af27540c4e63f56ae13882bf17afe77ee6e6578fcab1e24`.
- Fourfold-CPU browser measurement: mobile runtime-ready 722 ms; desktop runtime-ready 698 ms; 1,578 DOM nodes; 1,828,166 first-party raw bytes; zero startup project JSON requests.
- Browser measurement result SHA-256: `50632c968980ed0e41588056f78f19f1b0ae73555f426d58e4c3e73c6ba0a431`.
- First-party surface SHA-256: `af9e9750f8f5915d9ffb6480ba43c04dc4b7dd35662667784ef1dbaa65059622`.
- Catalogue delivery budget: 65 records, 20,132 catalogue/bootstrap gzip bytes and zero startup project requests.
- Final complete-validation and complete-browser-smoke receipts are published in the exact-head pull-request review comment, avoiding a self-referential evidence file.

## Merge gate

Merge only when the complete local gates, GitHub CI and fresh Codex review are all bound to the exact final pull-request head. The complete UTF-8 pull-request diff must be available before merge.
