import ast
import json
import re
import unittest
import unicodedata
from pathlib import Path

from scripts.proposal_runtime_i18n import proposal_runtime_inventory

ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "assets/locales/wave1-locales.json"
WAVE1_LOCALES = ("es", "fr", "pt-BR", "ar")
BIDI_CONTROL_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069]")
PLACEHOLDER_RE = re.compile(r"\{[^{}]+\}")
TAG_SEGMENT_RE = re.compile(r"<[^>]*>")
TAG_NAME_RE = re.compile(r"<\s*(/?)\s*([A-Za-z][A-Za-z0-9-]*)\b")
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


def tag_tokens(markup: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    for segment in TAG_SEGMENT_RE.findall(markup):
        match = TAG_NAME_RE.match(segment)
        if match:
            tokens.append((match.group(1), match.group(2).lower()))
    return tokens


class LocaleWave1PackTests(unittest.TestCase):
    def test_js_property_parser_rejects_adversarial_backslash_input(self) -> None:
        self.assertIsNone(parse_js_string_property("0:" + r"\&" * 100_000))

    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        cls.packs = cls.payload["locales"]
        cls.source = source_inventory()

    def test_wave1_pack_is_lifecycle_independent_and_complete(self) -> None:
        self.assertEqual(self.payload["schema_version"], 2)
        self.assertEqual(self.payload["source_locale"], "en")
        self.assertEqual(self.payload["wave"], "wave_1")
        self.assertNotIn("candidate_only", self.payload)
        self.assertEqual(tuple(self.packs), WAVE1_LOCALES)
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
                        self.assertEqual(tag_tokens(target), tag_tokens(source))
                        for attribute in CRITICAL_ATTRIBUTES:
                            self.assertEqual(
                                attribute_values(target, attribute),
                                attribute_values(source, attribute),
                                f"translated contract attribute {attribute}",
                            )

    def test_rtl_natural_language_controls_are_not_forced_ltr(self) -> None:
        css = (ROOT / "index.css").read_text(encoding="utf-8")
        self.assertNotIn(
            'html[dir="rtl"] input,\nhtml[dir="rtl"] textarea,',
            css,
        )
        self.assertIn('html[dir="rtl"] input[type="url"]', css)
        self.assertIn('html[dir="rtl"] input[type="text"]', css)
        self.assertIn('html[dir="rtl"] input[type="search"]', css)
        self.assertIn('html[dir="rtl"] textarea', css)

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
        self.assertNotRegex(
            arabic_text,
            r"[\u0621-\u063A\u0641-\u064A][A-Za-z]|[A-Za-z][\u0621-\u063A\u0641-\u064A]",
            "Arabic candidate contains a glued Arabic/Latin machine-translation fragment",
        )
        self.assertNotRegex(arabic_text, r"\bCommons\b", "Arabic candidate contains raw English Commons terminology")
        for legacy_term in ("الكامونز", "الكومنز", "الكامنز", "القirculars"):
            self.assertNotIn(legacy_term, arabic_text)

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
        for locale in WAVE1_LOCALES:
            entry = contract["locale_registry"][locale]
            for surface, relative in entry["surface_files"].items():
                markup = (ROOT / relative).read_text(encoding="utf-8")
                with self.subTest(locale=locale, surface=surface):
                    self.assertRegex(markup, rf'<html\b[^>]*\blang="{re.escape(locale)}"')
                    self.assertRegex(markup, rf'<html\b[^>]*\bdir="{entry["direction"]}"')
                    self.assertIn('name="robots" content="noindex,nofollow"', markup)
                    self.assertIn('class="locale-candidate-banner"', markup)
                    self.assertNotIn("[missing:", markup)
                    if surface == "proposal":
                        self.assertNotIn("data-locale-choice=", markup)
                        self.assertNotIn('class="language-switch"', markup)
                    else:
                        for candidate in WAVE1_LOCALES:
                            self.assertIn(f'data-locale-choice="{candidate}"', markup)
                        self.assertEqual(markup.count('data-locale-status="candidate"'), len(WAVE1_LOCALES))
            index_markup = (ROOT / entry["surface_files"]["index"]).read_text(encoding="utf-8")
            self.assertRegex(index_markup, r'<h2 lang="en" dir="ltr">')

    def test_arabic_surface_keeps_mixed_script_fragments_explicit(self) -> None:
        markup = (ROOT / "ar.html").read_text(encoding="utf-8")
        self.assertIn('<html lang="ar" dir="rtl">', markup)
        self.assertIn('lang="en" dir="ltr"', markup)
        self.assertIn('dir="ltr"', (ROOT / "index.css").read_text(encoding="utf-8"))


    def test_reviewed_wave1_terms_and_whitespace_regressions(self):
        locales = json.loads(PACK_PATH.read_text(encoding="utf-8"))["locales"]
        expected = {
            ("fr", "energy-democracy"): "Démocratie de l'énergie",
            ("fr", "savings-groups"): "Groupes d'épargne",
            ("pt-BR", "fisheries"): "Pesca",
            ("pt-BR", "mangroves"): "Manguezais",
            ("pt-BR", "open-media"): "Mídia aberta",
            ("ar", "creative-commons"): "المشاع الإبداعي",
            ("ar", "rural-infrastructure"): "البنية التحتية الريفية",
            ("ar", "free-software"): "برمجيات حرة",
        }
        for (locale, key), value in expected.items():
            self.assertEqual(locales[locale]["themes"][key], value)
        self.assertEqual(
            locales["pt-BR"]["proposal_runtime"]["no private address or coordinates in public suggestions."],
            "nenhum endereço privado ou coordenadas em sugestões públicas.",
        )
        for locale in locales.values():
            for section_name in ("themes", "proposal_runtime"):
                for value in locale[section_name].values():
                    self.assertEqual(value, value.strip())

    def test_language_quality_regressions_and_action_parity(self) -> None:
        forbidden = {
            "es": (
                "Miembroía", "striados", "Descreba", "editoría", "legajales",
                "principales-proximas", "primaria-near", "primarias-near",
                "se retenen", "telemetría del primer partido", "una catálogo",
                "problema público en GitHub", "siguiente cargue",
            ),
            "fr": (
                "pinchez", "Replicationner", "prétendement", "Réseauée",
                ">Ponte<", "régionallement", "Machine-readable:", "Strips pays",
                "une catalogue", "problème GitHub public", "cette onglet",
                "ne la rend pas apparaître",
            ),
            "pt-BR": (
                "locações", "prévistos", "Sitio web", "Consiento",
                "Coordenação Reduzida", "Comunidades Digitais", "base-mapa",
            ),
            "ar": (
                ">تكرار</option>", "مسألة علنية على GitHub", "فهرس الكتالوج",
                "الكرة الرقمية لـ Commonworld",
            ),
        }
        shell_actions = {
            "use": "shell_035",
            "borrow": "shell_036",
            "learn": "shell_037",
            "contribute": "shell_038",
            "volunteer": "shell_039",
            "donate": "shell_040",
            "visit": "shell_041",
            "contact": "shell_042",
            "replicate": "shell_043",
        }
        proposal_actions = {
            "visit": "proposal_044",
            "borrow": "proposal_045",
            "contribute": "proposal_046",
            "volunteer": "proposal_047",
            "donate": "proposal_048",
            "contact": "proposal_049",
            "replicate": "proposal_050",
        }

        for locale, pack in self.packs.items():
            localized_text = "\n".join(
                value
                for section, values in pack.items()
                if section != "meta"
                for value in values.values()
            )
            for fragment in forbidden[locale]:
                with self.subTest(locale=locale, fragment=fragment):
                    self.assertNotIn(fragment, localized_text)

            actions = pack["actions"]
            for action, expected in actions.items():
                with self.subTest(locale=locale, surface="ui", action=action):
                    self.assertEqual(pack["ui"][f"action_{action}"], expected)
            for action, key in shell_actions.items():
                match = re.fullmatch(r'<option value="[^"]+">(.*)</option>', pack["shell"][key])
                self.assertIsNotNone(match)
                with self.subTest(locale=locale, surface="shell", action=action):
                    self.assertEqual(match.group(1), actions[action])
            for action, key in proposal_actions.items():
                match = re.fullmatch(r'<option value="[^"]+">(.*)</option>', pack["proposal"][key])
                self.assertIsNotNone(match)
                with self.subTest(locale=locale, surface="proposal", action=action):
                    self.assertEqual(match.group(1), actions[action])


if __name__ == "__main__":
    unittest.main()
