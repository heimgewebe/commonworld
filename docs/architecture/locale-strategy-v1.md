# Commonworld locale strategy v1

## Decision

Commonworld exposes only interface languages whose complete public surface is translated, reviewed and tested. English and German remain the released interface languages. Spanish, French, Brazilian Portuguese and Arabic form the first expansion wave; Simplified Chinese, Hindi, Indonesian and Japanese form the second.

This is deliberately different from publishing a long language menu immediately. A selectable but incomplete language creates false inclusion: navigation may be translated while filters, runtime messages, project details, method text or proposal safeguards silently fall back to another language.

The machine-readable authority is `docs/architecture/locale-release.contract.json`. `scripts/validate_locale_release.py` binds that policy to the actual runtime declarations and released HTML surfaces. The test suite fails when runtime and contract drift apart or when a planned language is promoted without the required evidence.

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

The current runtime still supports only `en` and `de`. Generalizing runtime matching and surface generation is the next integration step after the active catalog-generation work has terminated, because both operations modify the same release-bound files.

## Release waves

### Released

- `en` — English, neutral default
- `de` — German, maintained fallback for canonical German source material

### Wave 1

- `es` — Spanish
- `fr` — French
- `pt-BR` — Brazilian Portuguese
- `ar` — Arabic

Arabic is intentionally early. It forces the system to prove bidirectional layout, focus order, icon direction, punctuation and mixed-script behavior before the localization architecture becomes entrenched around left-to-right assumptions.

### Wave 2

- `zh-Hans` — Simplified Chinese
- `hi` — Hindi
- `id` — Indonesian
- `ja` — Japanese

The order inside a wave may change when real visitor, search and contribution-language data provide stronger evidence. The quality gate does not change.

## Promotion gate

A planned locale becomes selectable only when all of the following are true:

- the globe, text view, method page and proposal page are complete;
- all runtime labels and error states are translated;
- catalog-localization and cross-language search behavior are defined;
- metadata, navigation and language links are correct;
- translation coverage is 100 percent, with no known fallback leakage or missing runtime keys;
- a language review independent of the implementation has passed;
- keyboard and screen-reader paths have been checked;
- browser smoke tests prove language choice, persistence and query/fragment preservation;
- right-to-left locales additionally pass directional layout and mixed-script review;
- machine translation, when used as a draft, has received human editorial review.

A language is therefore either released or planned. There is no publicly selectable “mostly translated” state.

## Alternative path

A growth-first strategy would expose machine-translated languages quickly and correct them later. That may increase nominal reach, but it shifts errors into safety-relevant proposal guidance, accessibility labels and Commons descriptions. Commonworld instead optimizes for trustworthy inclusion: fewer released languages initially, an open BCP 47 content model, and evidence-bound promotion.

## Consequences

### Benefits

- language choice is predictable and privacy-preserving;
- script, region and right-to-left requirements are considered before expansion;
- incomplete translations cannot be activated accidentally;
- content languages remain globally open even while the interface rollout is staged;
- the contract gives CI a stable boundary between “planned” and “released”.

### Costs and risks

- visible language growth is slower;
- each language needs review and browser evidence, not only translated strings;
- English/German source asymmetry remains until catalog localization is generalized;
- a runtime registry and generated surface convention still need implementation after the current catalog release operation.

## Next implementation boundary

After the active catalog-growth operation is terminal, the runtime should derive locale choices, canonical matching, page paths, display names and document direction from one registry rather than hard-coded English/German branches. That change must preserve the already merged precedence contract: explicit URL, stored preference, browser languages, English default.
