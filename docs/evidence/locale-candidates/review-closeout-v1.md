# Wave-1 locale review closeout

This follow-up closes post-merge findings against Commonworld PR #175.

The implementation must prove:

- localized and directionless DMS coordinates are rejected in browser and offline proposal validation;
- ordinary English use of the verb “coordinates” remains allowed;
- the public issue body localizes the `Name` label and digital-only presence value;
- candidate notices occupy their own viewport row and cannot be covered by the application topbar;
- English catalog source labels and localized action labels retain explicit language and direction metadata in focus views;
- a future released region tag such as `pt-BR` matches `pt` and `pt-PT` preferences;
- the generated release remains deterministic and all canonical validation and browser smoke checks pass.

This document is evidence scope, not a locale promotion decision. Wave-1 locales remain candidate-only.
