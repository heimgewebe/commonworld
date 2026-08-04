from pathlib import Path

root = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = root / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one replacement target, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "assets/commonworld-locale.mjs",
    """export const UI_LOCALE_STORAGE_KEY = 'commonworld.ui-locale';
export const UI_LOCALE_QUERY_PARAMETER = 'ui_lang';
export const UI_LOCALE_CHOICES = Object.freeze(['auto', ...RELEASED_LOCALES]);
""",
    """export const UI_LOCALE_STORAGE_KEY = 'commonworld.ui-locale';
export const UI_LOCALE_QUERY_PARAMETER = 'ui_lang';
export const SELECTABLE_UI_LOCALES = Object.freeze([
  ...RELEASED_LOCALES,
  ...CANDIDATE_LOCALES,
]);
export const UI_LOCALE_CHOICES = Object.freeze(['auto', ...SELECTABLE_UI_LOCALES]);
""",
)

replace_once(
    "assets/commonworld-locale.mjs",
    """export function normalizeLocalePreference(value) {
  const raw = String(value ?? '').trim();
  if (raw.toLowerCase() === 'auto') return 'auto';
  const canonical = canonicalLocaleTag(raw);
  return canonical && RELEASED_LOCALES.includes(canonical) ? canonical : null;
}
""",
    """export function normalizeLocalePreference(value) {
  const raw = String(value ?? '').trim();
  if (raw.toLowerCase() === 'auto') return 'auto';
  return matchSupportedLocaleTag(raw, SELECTABLE_UI_LOCALES);
}
""",
)

replace_once(
    "assets/commonworld-locale.mjs",
    """export function supportedLocale(value) {
  return matchSupportedLocaleTag(value);
}
""",
    """export function supportedLocale(value) {
  return matchSupportedLocaleTag(value);
}

export function selectableLocale(value) {
  return matchSupportedLocaleTag(value, SELECTABLE_UI_LOCALES);
}
""",
)

replace_once(
    "assets/commonworld-locale.mjs",
    """    choice = RELEASED_LOCALES.includes(current) ? current : null;
""",
    """    choice = SELECTABLE_UI_LOCALES.includes(current) ? current : null;
""",
)

replace_once(
    "assets/commonworld-locale.mjs",
    """  const normalizedTarget = supportedLocale(targetLocale) ?? DEFAULT_LOCALE;
""",
    """  const normalizedTarget = selectableLocale(targetLocale) ?? DEFAULT_LOCALE;
""",
)

replace_once(
    "scripts/commonworld_i18n.py",
    """SUPPORTED_LOCALES = locales_with_status("released")
CANDIDATE_LOCALES = locales_with_status("candidate")
KNOWN_UI_LOCALES = locales_with_status("released", "candidate", "planned")
DEFAULT_LOCALE = "en"
FALLBACK_LOCALE = "de"
CANDIDATE_PACK_PATH = ROOT / "assets/locales/wave1-candidates.json"
""",
    """SUPPORTED_LOCALES = locales_with_status("released")
CANDIDATE_LOCALES = locales_with_status("candidate")
SELECTABLE_UI_LOCALES = (*SUPPORTED_LOCALES, *CANDIDATE_LOCALES)
KNOWN_UI_LOCALES = locales_with_status("released", "candidate", "planned")
DEFAULT_LOCALE = "en"
FALLBACK_LOCALE = "de"
CANDIDATE_PACK_PATH = ROOT / "assets/locales/wave1-candidates.json"

PREVIEW_LABELS = {
    "en": "Preview",
    "de": "Vorschau",
    "es": "Vista previa",
    "fr": "Aperçu",
    "pt-BR": "Prévia",
    "ar": "معاينة",
}
""",
)

i18n_path = root / "scripts/commonworld_i18n.py"
i18n = i18n_path.read_text(encoding="utf-8")
start = i18n.index("def inject_locale_navigation(")
end = i18n.index("\n\ndef german_surface_links", start)
new_navigation = r'''def _locale_preview_label(locale: str) -> str:
    normalized = normalize_locale(locale)
    return PREVIEW_LABELS.get(normalized, PREVIEW_LABELS[DEFAULT_LOCALE])


def _locale_choice_link(surface: str, tag: str, current_locale: str) -> str:
    entry = locale_entry(tag)
    current = ' aria-current="page"' if current_locale == tag else ""
    status = "candidate" if tag in CANDIDATE_LOCALES else "released"
    status_markup = ""
    if status == "candidate":
        status_markup = (
            f'<span class="language-choice-status">{escape(_locale_preview_label(current_locale))}</span>'
        )
    return (
        f'<a class="language-choice" href="{_locale_choice_href(surface, tag)}" '
        f'lang="{tag}" dir="{entry.get("direction", "ltr")}" '
        f'data-locale-choice="{tag}" data-locale-surface="{surface}" '
        f'data-locale-status="{status}"{current}>'
        f'<span class="language-choice-name">{escape(entry["native_name"])}</span>'
        f'{status_markup}</a>'
    )


def inject_locale_navigation(markup: str, locale: str, surface: str = "index") -> str:
    normalized = normalize_locale(locale)
    copy = _locale_navigation_copy(normalized)
    automatic = (
        f'<a class="language-choice language-choice--auto" '
        f'href="{_locale_choice_href(surface, "auto")}" data-locale-choice="auto" '
        f'data-locale-surface="{surface}">'
        f'<span class="language-choice-name">{escape(copy["automatic"])}</span></a>'
    )
    links = "".join(
        _locale_choice_link(surface, tag, normalized)
        for tag in SELECTABLE_UI_LOCALES
    )
    if surface == "index":
        control = (
            f'<nav class="language-switch language-switch--settings" '
            f'aria-label="{escape(copy["label"])}" data-locale-surface="{surface}">'
            f'{automatic}<div class="language-choice-grid">{links}</div></nav>'
            f'<p class="language-effective visually-hidden" data-locale-effective '
            f'aria-live="polite">{escape(copy["effective"])}</p>'
        )
        section = (
            '<section class="settings-section language-settings"><h3>'
            + escape(copy["heading"])
            + '</h3>' + control + '</section>\n        '
        )
        interaction = "Interaction" if normalized == "en" else "Bedienung"
        if normalized in CANDIDATE_LOCALES:
            interaction = candidate_pack(normalized).get("static", {}).get("interaction", interaction)
        marker = '<section class="settings-section">\n          <h3>' + interaction + '</h3>'
        if marker not in markup:
            raise ValueError(f"locale navigation insertion marker missing for {normalized}/{surface}")
        return markup.replace(marker, section + marker, 1)

    control = (
        f'<div class="language-switch language-switch--compact" role="group" '
        f'aria-label="{escape(copy["label"])}" data-locale-surface="{surface}">'
        f'{automatic}{links}</div>'
        f'<p class="language-effective" data-locale-effective '
        f'aria-live="polite">{escape(copy["effective"])}</p>'
    )
    marker = '<p><a class="secondary-back-link"'
    position = markup.find(marker)
    if position < 0:
        raise ValueError(f"locale navigation insertion marker missing for {normalized}/{surface}")
    end = markup.find('</p>', position)
    if end < 0:
        raise ValueError(f"locale navigation paragraph is malformed for {normalized}/{surface}")
    end += 4
    return markup[:end] + '\n      ' + control + markup[end:]
'''
i18n_path.write_text(i18n[:start] + new_navigation + i18n[end:], encoding="utf-8")

replace_once(
    "scripts/render_proposal_page.py",
    "from scripts.commonworld_i18n import FALLBACK_LOCALE, german_surface_links, inject_locale_navigation, normalize_locale\n",
    "from scripts.commonworld_i18n import FALLBACK_LOCALE, german_surface_links, normalize_locale\n",
)
replace_once(
    "scripts/render_proposal_page.py",
    "    markup = inject_locale_navigation(markup, locale, 'propose')\n",
    "",
)

css_path = root / "index.css"
css = css_path.read_text(encoding="utf-8")
css_start = css.index(".language-switch {\n")
css_end = css.index("\n\n.method-page code {", css_start)
new_css = r'''.language-switch {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.7rem;
}

.language-switch a {
  justify-content: center;
  min-inline-size: var(--minimum-touch-target);
  padding: 0.45rem 0.72rem;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: rgba(7, 22, 18, 0.72);
  color: #c2ecd4;
  line-height: 1.2;
  text-align: center;
  text-decoration: none;
}

.language-switch a:hover {
  border-color: var(--green);
  background: #102c25;
  color: #edf4ef;
}

.language-switch a[aria-current="page"] {
  border-color: var(--green);
  background: rgba(79, 255, 178, 0.14);
  color: #edf4ef;
}

.language-switch--settings {
  display: grid;
  gap: 0.55rem;
}

.language-switch--settings .language-choice--auto {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: flex-start;
  border-radius: 0.72rem;
}

.language-choice-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
}

.language-switch--settings .language-choice {
  display: flex;
  min-width: 0;
  min-height: 3.2rem;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 0.22rem;
  border-radius: 0.72rem;
  text-align: start;
}

.language-choice-name {
  min-width: 0;
  overflow-wrap: anywhere;
}

.language-choice-status {
  display: inline-flex;
  min-height: 1.35rem;
  align-items: center;
  padding: 0.1rem 0.38rem;
  border: 1px solid rgba(255, 225, 168, 0.38);
  border-radius: 999px;
  color: #ffe1a8;
  font-size: 0.67rem;
  font-weight: 720;
  letter-spacing: 0.02em;
  line-height: 1;
}

.language-choice[data-locale-status="candidate"] {
  border-style: dashed;
}

.language-choice[data-locale-status="candidate"][aria-current="page"] {
  border-style: solid;
}

.language-switch--compact .language-choice-status {
  margin-inline-start: 0.2rem;
}

.language-effective {
  margin: 0.55rem 0 0;
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.45;
}

@media (max-width: 32rem) {
  .language-choice-grid {
    grid-template-columns: 1fr;
  }
}
'''
css_path.write_text(css[:css_start] + new_css + css[css_end:], encoding="utf-8")

test_path = root / "tests/js/commonworld-locale-selection.test.mjs"
if test_path.exists():
    raise RuntimeError(f"refusing to overwrite existing test: {test_path}")
test_path.write_text(
    """import test from 'node:test';
import assert from 'node:assert/strict';

import {
  SELECTABLE_UI_LOCALES,
  UI_LOCALE_CHOICES,
  matchSupportedLocale,
  normalizeLocalePreference,
  resolveLocalePreference,
} from '../../assets/commonworld-locale.mjs';

test('manual language choices include reviewed and preview locales', () => {
  assert.deepEqual(
    [...SELECTABLE_UI_LOCALES],
    ['en', 'de', 'es', 'fr', 'pt-BR', 'ar'],
  );
  assert.deepEqual(
    [...UI_LOCALE_CHOICES],
    ['auto', 'en', 'de', 'es', 'fr', 'pt-BR', 'ar'],
  );
  assert.equal(normalizeLocalePreference('fr-FR'), 'fr');
  assert.equal(normalizeLocalePreference('pt-br'), 'pt-BR');
  assert.equal(normalizeLocalePreference('zh-Hans'), null);
});

test('automatic language matching remains limited to released locales', () => {
  assert.equal(matchSupportedLocale(['fr-FR', 'de-DE']), 'de');
  assert.equal(matchSupportedLocale(['ar', 'en-GB']), 'en');
});

test('manual and direct preview locale navigation keeps the preview choice', () => {
  const manual = resolveLocalePreference({
    pathname: '/index.html',
    currentLocale: 'en',
    queryChoice: 'fr',
    languages: ['de-DE'],
  });
  assert.equal(manual.choice, 'fr');
  assert.equal(manual.locale, 'fr');
  assert.equal(manual.source, 'query');
  assert.equal(manual.shouldRedirect, true);

  const direct = resolveLocalePreference({
    pathname: '/fr.html',
    currentLocale: 'fr',
  });
  assert.equal(direct.choice, 'fr');
  assert.equal(direct.locale, 'fr');
  assert.equal(direct.source, 'explicit-surface');
  assert.equal(direct.shouldRedirect, false);
});
""",
    encoding="utf-8",
)
