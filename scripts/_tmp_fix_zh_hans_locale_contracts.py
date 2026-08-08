#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected fragment missing in {path}: {old[:160]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_runtime_matcher() -> None:
    path = ROOT / "scripts/build_locale_runtime.py"
    old = '''    const parts = canonical.split('-');
    if (parts.length >= 2 && parts[1].length === 4) {{
      const languageScript = parts.slice(0, 2).join('-').toLowerCase();
      const scriptMatch = allowed.find((tag) => tag.toLowerCase() === languageScript);
      if (scriptMatch) return scriptMatch;
    }}
    const primary = parts[0].toLowerCase();
    const primaryMatch = allowed.find((tag) => tag.split('-')[0].toLowerCase() === primary);
    if (primaryMatch) return primaryMatch;
'''
    new = '''    const parts = canonical.split('-');
    const primary = parts[0].toLowerCase();
    const explicitScript = parts.length >= 2 && parts[1].length === 4 ? parts[1] : null;
    const region = parts.find((part, index) => index > 0 && (part.length === 2 || /^\\d{{3}}$/.test(part))) ?? null;
    const inferredChineseScript = primary === 'zh' && region
      ? (['TW', 'HK', 'MO'].includes(region.toUpperCase()) ? 'Hant' : ['CN', 'SG'].includes(region.toUpperCase()) ? 'Hans' : null)
      : null;
    const requestedScript = explicitScript ?? inferredChineseScript;
    if (requestedScript) {{
      const languageScript = `${{primary}}-${{requestedScript}}`.toLowerCase();
      const scriptMatch = allowed.find((tag) => tag.toLowerCase() === languageScript);
      if (scriptMatch) return scriptMatch;
      const scriptlessPrimary = allowed.find((tag) => {{
        const candidateParts = tag.split('-');
        return candidateParts[0].toLowerCase() === primary
          && !(candidateParts.length >= 2 && candidateParts[1].length === 4);
      }});
      if (scriptlessPrimary) return scriptlessPrimary;
      continue;
    }}
    const primaryMatch = allowed.find((tag) => tag.split('-')[0].toLowerCase() === primary);
    if (primaryMatch) return primaryMatch;
'''
    replace_once(path, old, new)

    path = ROOT / "scripts/locale_registry.py"
    insert_after = 'TAG_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|[0-9]{3}))?$")\n'
    helper = insert_after + '''ZH_REGION_SCRIPT = {\n    "CN": "Hans",\n    "SG": "Hans",\n    "TW": "Hant",\n    "HK": "Hant",\n    "MO": "Hant",\n}\n\n\ndef requested_script(tag: str) -> str | None:\n    parts = tag.split("-")\n    if len(parts) >= 2 and len(parts[1]) == 4 and parts[1].isalpha():\n        return parts[1].title()\n    primary = parts[0].lower()\n    region = next((part for part in parts[1:] if (len(part) == 2 and part.isalpha()) or (len(part) == 3 and part.isdigit())), None)\n    if primary == "zh" and region:\n        return ZH_REGION_SCRIPT.get(region.upper())\n    return None\n'''
    replace_once(path, insert_after, helper)
    old = '''        parts = canonical.split("-")
        if len(parts) >= 2 and len(parts[1]) == 4:
            language_script = "-".join(parts[:2])
            matched = next((tag for tag in candidates if tag.casefold() == language_script.casefold()), None)
            if matched:
                return matched
        primary = parts[0]
        matched = next((tag for tag in candidates if tag.split("-", 1)[0].casefold() == primary.casefold()), None)
        if matched:
            return matched
'''
    new = '''        parts = canonical.split("-")
        primary = parts[0]
        script = requested_script(canonical)
        if script:
            language_script = f"{primary}-{script}"
            matched = next((tag for tag in candidates if tag.casefold() == language_script.casefold()), None)
            if matched:
                return matched
            scriptless = next(
                (
                    tag
                    for tag in candidates
                    if tag.split("-", 1)[0].casefold() == primary.casefold()
                    and not (len(tag.split("-")) >= 2 and len(tag.split("-")[1]) == 4)
                ),
                None,
            )
            if scriptless:
                return scriptless
            continue
        matched = next((tag for tag in candidates if tag.split("-", 1)[0].casefold() == primary.casefold()), None)
        if matched:
            return matched
'''
    replace_once(path, old, new)


def patch_js_tests() -> None:
    path = ROOT / "tests/js/i18n.test.mjs"
    old = '''  actionLabel,
  catalogContentLocale,
  hasThemeLabel,
'''
    new = '''  actionLabel,
  catalogContentLocale,
  RELEASED_LOCALES,
  WAVE1_LOCALES,
  hasThemeLabel,
'''
    replace_once(path, old, new)

    path = ROOT / "tests/js/commonworld-locale-selection.test.mjs"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "} from '../../assets/commonworld-locale.mjs';\n",
        "} from '../../assets/commonworld-locale.mjs';\nimport { RELEASED_LOCALES } from '../../assets/commonworld-locale-registry.mjs';\n",
        1,
    )
    text = text.replace("    ['en', 'de', 'es', 'fr', 'pt-BR', 'ar'],", "    [...RELEASED_LOCALES],", 1)
    text = text.replace("    ['auto', 'en', 'de', 'es', 'fr', 'pt-BR', 'ar'],", "    ['auto', ...RELEASED_LOCALES],", 1)
    text = text.replace("  assert.equal(normalizeLocalePreference('zh-Hans'), null);", "  assert.equal(normalizeLocalePreference('zh-Hans'), 'zh-Hans');\n  assert.equal(normalizeLocalePreference('zh-Hant'), null);")
    text = text.replace(
        "  assert.equal(matchSupportedLocale(['ar', 'en-GB']), 'ar');",
        "  assert.equal(matchSupportedLocale(['ar', 'en-GB']), 'ar');\n  assert.equal(matchSupportedLocale(['zh-CN', 'fr-FR']), 'zh-Hans');\n  assert.equal(matchSupportedLocale(['zh-Hant', 'fr-FR']), 'fr');\n  assert.equal(matchSupportedLocale(['zh-TW', 'fr-FR']), 'fr');",
    )
    text = text.replace(
        "  assert.equal(writeStoredLocalePreference('zh-Hans', storage), false);\n  assert.equal(readStoredLocalePreference(storage), 'fr');",
        "  assert.equal(writeStoredLocalePreference('zh-Hans', storage), true);\n  assert.equal(readStoredLocalePreference(storage), 'zh-Hans');",
    )
    path.write_text(text, encoding="utf-8")

    path = ROOT / "tests/js/locale-preference.test.mjs"
    text = path.read_text(encoding="utf-8")
    text = text.replace("  assert.equal(supportedLocale('zh-Hant'), null);", "  assert.equal(supportedLocale('zh-Hant'), null);\n  assert.equal(supportedLocale('zh-CN'), 'zh-Hans');\n  assert.equal(supportedLocale('zh-TW'), null);")
    text = text.replace("  assert.equal(normalizeLocalePreference('zh-Hans'), null);", "  assert.equal(normalizeLocalePreference('zh-Hans'), 'zh-Hans');\n  assert.equal(normalizeLocalePreference('zh-Hant'), null);\n  assert.equal(normalizeLocalePreference('zh-TW'), null);")
    path.write_text(text, encoding="utf-8")

    path = ROOT / "tests/js/locale-registry.test.mjs"
    text = path.read_text(encoding="utf-8")
    text = text.replace("  assert.deepEqual(RELEASED_LOCALES, ['en', 'de', 'es', 'fr', 'pt-BR', 'ar']);", "  assert.deepEqual(RELEASED_LOCALES, ['en', 'de', 'es', 'fr', 'pt-BR', 'ar', 'zh-Hans']);")
    text = text.replace("  assert.deepEqual(WAVE1_LOCALES, ['es', 'fr', 'pt-BR', 'ar']);", "  assert.deepEqual(WAVE1_LOCALES, ['es', 'fr', 'pt-BR', 'ar', 'zh-Hans']);")
    text = text.replace("  assert.deepEqual(KNOWN_UI_LOCALES.slice(0, 6), ['en', 'de', 'es', 'fr', 'pt-BR', 'ar']);", "  assert.deepEqual(KNOWN_UI_LOCALES.slice(0, 7), ['en', 'de', 'es', 'fr', 'pt-BR', 'ar', 'zh-Hans']);")
    text = text.replace("  assert.equal(canonicalLocaleTag('AR-arab-eg'), 'ar-Arab-EG');", "  assert.equal(canonicalLocaleTag('AR-arab-eg'), 'ar-Arab-EG');\n  assert.equal(canonicalLocaleTag('zh-hans'), 'zh-Hans');")
    text = text.replace("  assert.equal(matchRegistryLocale(['fr-CA'], { statuses: ['released'] }), 'fr');", "  assert.equal(matchRegistryLocale(['fr-CA'], { statuses: ['released'] }), 'fr');\n  assert.equal(matchRegistryLocale(['zh-CN'], { statuses: ['released'] }), 'zh-Hans');\n  assert.equal(matchRegistryLocale(['zh-Hant', 'fr-CA'], { statuses: ['released'] }), 'fr');\n  assert.equal(matchRegistryLocale(['zh-TW', 'fr-CA'], { statuses: ['released'] }), 'fr');")
    text = text.replace("  assert.equal(documentDirection('fr'), 'ltr');", "  assert.equal(text('zh-Hans', 'type_energy', ''), '能源');\n  assert.equal(documentDirection('fr'), 'ltr');\n  assert.equal(documentDirection('zh-Hans'), 'ltr');")
    path.write_text(text, encoding="utf-8")


def patch_python_tests() -> None:
    path = ROOT / "tests/test_locale_release_contract.py"
    marker = '    def test_runtime_registry_tracks_contract_lifecycle(self) -> None:\n'
    test = '''    def test_simplified_chinese_does_not_claim_traditional_script_or_regions(self) -> None:\n        from scripts.locale_registry import match_registry_locale\n\n        self.assertEqual(match_registry_locale(["zh-CN"], root=ROOT), "zh-Hans")\n        self.assertEqual(match_registry_locale(["zh-SG"], root=ROOT), "zh-Hans")\n        self.assertEqual(match_registry_locale(["zh-Hant", "fr-FR"], root=ROOT), "fr")\n        self.assertEqual(match_registry_locale(["zh-TW", "fr-FR"], root=ROOT), "fr")\n        self.assertEqual(match_registry_locale(["zh-HK", "fr-FR"], root=ROOT), "fr")\n\n'''
    replace_once(path, marker, test + marker)


def main() -> int:
    patch_runtime_matcher()
    patch_js_tests()
    patch_python_tests()
    print("zh-Hans script-aware locale matching and stale test contracts fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
