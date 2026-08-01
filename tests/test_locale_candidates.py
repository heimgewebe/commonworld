import ast
import json
import re
import unittest
import unicodedata
from pathlib import Path

from scripts.proposal_runtime_i18n import proposal_runtime_inventory

ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "assets/locales/wave1-candidates.json"
CANDIDATES = ("es", "fr", "pt-BR", "ar")
BIDI_CONTROL_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069]")
PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9-]*)\b")
CRITICAL_ATTRIBUTES = (
    "href",
    "rel",
    "id",
    "name",
    "type",
    "value",
    "for",
    "data-locale-choice",
    "data-locale-surface",
)


def assignment(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"missing assignment {name} in {path}")


def parse_js_string_property(line: str) -> tuple[str, str] | None:
    candidate = line.strip()
    if not candidate or candidate.startswith("//"):
        return None
    if candidate.endswith(","):
        candidate = candidate[:-1].rstrip()

    quote: str | None = None
    escaped = False
    separator = -1
    for index, character in enumerate(candidate):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
            continue
        if character == ":":
            separator = index
            break
    if separator < 1:
        return None

    raw_key = candidate[:separator].strip()
    raw_value = candidate[separator + 1 :].strip()
    if len(raw_value) < 2 or raw_value[0] != "'" or raw_value[-1] != "'":
        return None

    if raw_key[0:1] in {"'", '"'}:
        key = ast.literal_eval(raw_key)
    elif re.fullmatch(r"[A-Za-z0-9_]+", raw_key):
        key = raw_key
    else:
        return None
    value = ast.literal_eval(raw_value)
    if not isinstance(key, str) or not isinstance(value, str):
        return None
    return key, value


def js_object(name: str) -> dict[str, str]:
    source = (ROOT / "assets/commonworld-i18n.mjs").read_text(encoding="utf-8")
    start = source.index(f"const {name} = Object.freeze({{")
    end = source.index("\n});", start)
    block = source[start:end]
    result: dict[str, str] = {}
    for line in block.splitlines()[1:]:
        parsed = parse_js_string_property(line)
        if parsed is not None:
            key, value = parsed
            result[key] = value
    return result


def source_inventory() -> dict[str, dict[str, str]]:
    shell = assignment(ROOT / "scripts/commonworld_i18n.py", "SHELL_REPLACEMENTS_EN")
    method = assignment(ROOT / "scripts/commonworld_i18n.py", "METHOD_REPLACEMENTS_EN")
    proposal = assignment(ROOT / "scripts/proposal_i18n.py", "PROPOSAL_REPLACEMENTS_EN")
    taxonomy = json.loads((ROOT / "catalog/locales/en.json").read_text(encoding="utf-8"))[
        "taxonomy_labels"
    ]
    actions = assignment(ROOT / "scripts/commonworld_i18n.py", "ACTION_LABELS_EN")
    static = {
        "digital_commons": "Digital Commons",
        "on_site": "On site",
        "digital": "Digital",
        "commons": "Commons",
        "location_independent_digital": "Location-independent digital presence",
        "public_location_one": "{count} public location",
        "public_location_many": "{count} public locations",
        "hidden_location_one": "{count} hidden location",
        "hidden_location_many": "{count} hidden locations",
        "no_public_geometry": "No public geometry",
        "activity_unknown": "Current operating status has not been verified recently. Sources reviewed on {observed_at}; priority re-review {next_review_at}.",
        "open": "Open",
        "official_website": "Official website",
        "source_number": "Source {index}",
    }
    def indexed(prefix: str, values) -> dict[str, str]:
        unique = list(dict.fromkeys(values))
        return {f"{prefix}_{index:03d}": value for index, value in enumerate(unique, 1)}

    return {
        "ui": js_object("UI_EN"),
        "themes": js_object("THEME_LABELS_EN"),
        "shell": indexed("shell", shell.values()),
        "method": indexed("method", method.values()),
        "proposal": indexed("proposal", proposal.values()),
        "proposal_runtime": {key: key for key in proposal_runtime_inventory()},
        "taxonomy": taxonomy,
        "actions": actions,
        "static": static,
    }


def attribute_values(markup: str, name: str) -> list[str]:
    return re.findall(rf'\b{re.escape(name)}="([^"]*)"', markup)


class LocaleCandidatePackTests(unittest.TestCase):
    def test_js_property_parser_rejects_adversarial_backslash_input(self) -> None:
        self.assertIsNone(parse_js_string_property("0:" + r"\&" * 100_000))

    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        cls.packs = cls.payload["locales"]
        cls.source = source_inventory()

    def test_pack_is_candidate_only_and_complete(self) -> None:
        self.assertEqual(self.payload["schema_version"], 1)
        self.assertEqual(self.payload["source_locale"], "en")
        self.assertIs(self.payload["candidate_only"], True)
        self.assertEqual(tuple(self.packs), CANDIDATES)
        required_sections = {
            "meta", "ui", "themes", "static", "shell", "method", "proposal", "proposal_runtime", "taxonomy", "actions"
        }
        for locale, pack in self.packs.items():
            with self.subTest(locale=locale):
                self.assertEqual(set(pack), required_sections)
                self.assertEqual(pack["meta"]["draft_origin"], "machine_translation_assisted")
                self.assertEqual(pack["meta"]["independent_language_review"], "pending")
                for section in ("ui", "themes", "shell", "method", "proposal", "proposal_runtime", "taxonomy", "actions"):
                    self.assertEqual(set(pack[section]), set(self.source[section]), f"{locale}/{section}")
                self.assertTrue(set(self.source["static"]).issubset(pack["static"]))

    def test_placeholders_html_and_contract_attributes_are_preserved(self) -> None:
        for locale, pack in self.packs.items():
            for section, source_values in self.source.items():
                for key, source in source_values.items():
                    target = pack[section][key]
                    with self.subTest(locale=locale, section=section, key=key):
                        self.assertEqual(PLACEHOLDER_RE.findall(target), PLACEHOLDER_RE.findall(source))
                        self.assertEqual(TAG_RE.findall(target), TAG_RE.findall(source))
                        for attribute in CRITICAL_ATTRIBUTES:
                            self.assertEqual(
                                attribute_values(target, attribute),
                                attribute_values(source, attribute),
                                f"translated contract attribute {attribute}",
                            )

    def test_candidates_have_no_directional_control_characters_or_empty_values(self) -> None:
        for locale, pack in self.packs.items():
            for section, values in pack.items():
                if section == "meta":
                    continue
                for key, value in values.items():
                    with self.subTest(locale=locale, section=section, key=key):
                        self.assertIsInstance(value, str)
                        self.assertTrue(value.strip())
                        self.assertIsNone(BIDI_CONTROL_RE.search(value))
        for locale in ("es", "fr", "pt-BR"):
            text = " ".join(
                value
                for section, values in self.packs[locale].items()
                if section != "meta"
                for value in values.values()
            )
            self.assertNotRegex(text, r"[\u0600-\u06ff]", f"{locale} contains Arabic-script contamination")
            self.assertNotRegex(PLACEHOLDER_RE.sub("", text), r"(?i)\bnext\b", f"{locale} contains raw English UI leakage")
        arabic_text = " ".join(
            value
            for section, values in self.packs["ar"].items()
            if section != "meta"
            for value in values.values()
        )
        self.assertRegex(arabic_text, r"[\u0600-\u06ff]")

    def test_candidate_packs_reject_unexpected_script_contamination(self) -> None:
        forbidden_for_latin = (
            "ARABIC",
            "THAI",
            "HANGUL",
            "HEBREW",
            "CJK UNIFIED",
            "CYRILLIC",
        )
        for locale, pack in self.packs.items():
            for section, values in pack.items():
                if section == "meta":
                    continue
                for key, value in values.items():
                    for character in value:
                        if not character.isalpha():
                            continue
                        unicode_name = unicodedata.name(character, "")
                        with self.subTest(
                            locale=locale, section=section, key=key, character=character
                        ):
                            if locale == "ar":
                                self.assertTrue(
                                    "ARABIC" in unicode_name or "LATIN" in unicode_name,
                                    f"unexpected script in Arabic candidate: {unicode_name}",
                                )
                            else:
                                self.assertFalse(
                                    any(script in unicode_name for script in forbidden_for_latin),
                                    f"unexpected script in {locale} candidate: {unicode_name}",
                                )

    def test_generated_candidate_surfaces_are_preview_only(self) -> None:
        contract = json.loads(
            (ROOT / "docs/architecture/locale-release.contract.json").read_text(encoding="utf-8")
        )
        for locale in CANDIDATES:
            entry = contract["locale_registry"][locale]
            for surface, relative in entry["surface_files"].items():
                markup = (ROOT / relative).read_text(encoding="utf-8")
                with self.subTest(locale=locale, surface=surface):
                    self.assertRegex(markup, rf'<html\b[^>]*\blang="{re.escape(locale)}"')
                    self.assertRegex(markup, rf'<html\b[^>]*\bdir="{entry["direction"]}"')
                    self.assertIn('name="robots" content="noindex,nofollow"', markup)
                    self.assertIn('class="locale-candidate-banner"', markup)
                    self.assertNotIn("[missing:", markup)
                    for candidate in CANDIDATES:
                        self.assertNotIn(f'data-locale-choice="{candidate}"', markup)
            index_markup = (ROOT / entry["surface_files"]["index"]).read_text(encoding="utf-8")
            self.assertRegex(index_markup, r'<h2 lang="en">')

    def test_arabic_surface_keeps_mixed_script_fragments_explicit(self) -> None:
        markup = (ROOT / "ar.html").read_text(encoding="utf-8")
        self.assertIn('<html lang="ar" dir="rtl">', markup)
        self.assertIn('lang="en"', markup)
        self.assertIn('dir="ltr"', (ROOT / "index.css").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
