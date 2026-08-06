# Commonworld locale strategy v1

## Decision

Commonworld exposes only interface languages whose complete public surface is translated, reviewed and tested. English and German remain the released interface languages. Spanish, French, Brazilian Portuguese and Arabic form the first expansion wave; Simplified Chinese, Hindi, Indonesian and Japanese form the second.

This is deliberately different from publishing a long language menu immediately. A selectable but incomplete language creates false inclusion: navigation may be translated while filters, runtime messages, project details, method text or proposal safeguards silently fall back to another language.

The machine-readable authority is `docs/architecture/locale-release.contract.json`. `scripts/validate_locale_release.py` binds that policy to the generated runtime registry, released surfaces, hidden candidate surfaces and digest-bound evidence. The test suite fails when runtime and contract drift apart, when a candidate becomes selectable, or when a non-baseline language is promoted without complete independent evidence.

## For non-specialists

There are two separate questions:

1. **Which language does the website use for buttons and explanations?** This is the interface language.
2. **In which language is a Commons described or searched?** This is the content language.

The two must not be confused. A Spanish project may remain discoverable while the interface is English. Conversely, a Spanish interface does not justify rewriting or guessing the language of catalog content.

## Selection order

The interface language is chosen in this order:

1. an explicit language in the URL;
2. the preference previously chosen by the visitor;
3. the ordered browser or operating-system language list;
4. English as the neutral default.

Physical location and IP-derived country must not influence the decision. Location is a weak proxy for language, creates surprising changes while travelling and introduces unnecessary privacy coupling. An explicit language page also remains explicit; a stored preference must not silently replace it.

## Tag and fallback model

Interface and content languages use BCP 47 tags. The architecture must preserve meaningful script and region subtags, for example:

- `pt-BR` rather than collapsing everything to `pt`;
- `zh-Hans` and later `zh-Hant` as distinct script choices;
- `sr-Latn` and `sr-Cyrl` if Serbian is introduced;
- `ar` with right-to-left direction.

Matching proceeds from the most specific usable tag to broader fallbacks: exact tag, language plus script, primary language, then the default language. Input matching is case-insensitive, but stored and emitted tags are canonical.

The runtime now derives known, released and candidate interface locales, canonical matching, page paths and document direction from one registry. Only `en` and `de` are released and selectable. Candidate pages are generated for technical review, carry `noindex,nofollow`, identify themselves as previews and cannot be selected by the public locale control.

## Release waves

### Released

- `en` — English, neutral default
- `de` — German, maintained fallback for canonical German source material

### Wave 1 — hidden candidates

- `es` — Spanish
- `fr` — French
- `pt-BR` — Brazilian Portuguese
- `ar` — Arabic

All three public surfaces and the runtime vocabulary are generated for these locales as technical candidates. They are not released, are not selectable and still require independent language, accessibility and browser review. Candidate evidence records technical results and blockers but is deliberately not release evidence.

Arabic is intentionally early. It forces the system to prove bidirectional layout, focus order, icon direction, punctuation and mixed-script behavior before the localization architecture becomes entrenched around left-to-right assumptions.

### Wave 2

- `zh-Hans` — Simplified Chinese
- `hi` — Hindi
- `id` — Indonesian
- `ja` — Japanese

The order inside a wave may change when real visitor, search and contribution-language data provide stronger evidence. The quality gate does not change.

## Promotion gate

A candidate locale becomes released and selectable only when all of the following are true:

- the globe, text view, method page and proposal page are complete;
- all runtime labels and error states are translated;
- catalog-localization and cross-language search behavior are defined;
- metadata, navigation and language links are correct;
- translation coverage is 100 percent, with no known fallback leakage or missing runtime keys;
- a language review independent of the implementation has passed;
- keyboard and screen-reader paths have been checked;
- browser smoke tests prove language choice, persistence and query/fragment preservation;
- right-to-left locales additionally pass directional layout and mixed-script review;
- machine-only raw translation remains forbidden;
- independent language review has passed; this review may be model-assisted only when it is labeled as such, kept independent of the writer, digest-bound, findings-based and followed by a fail-closed post-fix review;
- native or human polish may remain an explicit follow-up and must not be claimed by model-assisted review alone.

A language is therefore either released, a hidden technical candidate, or planned. There is no publicly selectable “mostly translated” state. Promotion of every non-baseline locale requires a revision- and SHA-256-bound release-evidence artifact with independent receipts; candidate evidence alone can never satisfy that gate.

## Alternative path

A growth-first strategy would expose machine-translated languages quickly and correct them later. That may increase nominal reach, but it shifts errors into safety-relevant proposal guidance, accessibility labels and Commons descriptions. Commonworld instead optimizes for trustworthy inclusion: fewer released languages initially, an open BCP 47 content model, and evidence-bound promotion.

## Catalogue content languages

Catalogue summaries keep their own content language. Interface locales do not invent parallel summary-specificity policies. Today published catalogue content languages are predominantly German and English. Wave-1 UI surfaces therefore present English catalogue content with explicit `lang` boundaries rather than rewritten local catalogue prose.

## Review classes

- Machine-generated raw translation is never a release gate pass.
- Independent model-assisted editorial review is allowed only when explicitly labeled, separated from the writer, bound to the pack digest, findings-based, and closed by a post-fix review that can still fail.
- This process never claims native or human approval by itself.

## Consequences

### Benefits

- language choice is predictable and privacy-preserving;
- script, region and right-to-left requirements are considered before expansion;
- incomplete translations cannot be activated accidentally;
- content languages remain globally open even while the interface rollout is staged;
- the contract gives CI a stable boundary between planned, hidden candidate and released locales;
- generated candidate previews make technical integration testable without implying public language support.

### Costs and risks

- visible language growth is slower;
- each language needs review and browser evidence, not only translated strings;
- English/German source asymmetry remains: Wave 1 currently presents canonical English catalog content with an explicit `lang="en"` boundary;
- candidate previews add generated files and release-snapshot weight before they create public reach;
- independent language, keyboard, screen-reader and browser reviews remain real activation work.

## Next implementation boundary

Wave 1 is technically integrated but intentionally inactive. The next boundary is independent review of the exact candidate-pack digest and generated surfaces, followed by accessibility and browser receipts. Only then may a locale registry entry move from `candidate` to `released` and appear in automatic or manual selection. Wave 2 remains planned and should reuse this same evidence path rather than introduce another localization mechanism.
