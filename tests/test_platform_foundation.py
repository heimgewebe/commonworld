import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_platform_foundation import RobotsMetaParser, validate_platform_foundation

ROOT = Path(__file__).resolve().parents[1]


class PlatformFoundationTests(unittest.TestCase):
    def test_validator_passes_repository_state_without_freezing_improvements(self):
        errors, report = validate_platform_foundation(ROOT)
        self.assertEqual(errors, [])
        gate = json.loads((ROOT / "contracts/commonworld/platform-foundation-gate.contract.json").read_text())
        self.assertLessEqual(report["legacy_basis_debt"], gate["baseline"]["legacy_basis_debt_ceiling"])

        locale = json.loads((ROOT / gate["authoritative_inputs"]["locale_release"]).read_text())
        expected_candidates = sorted(
            tag for tag, data in locale["locale_registry"].items() if data["status"] == "candidate"
        )
        self.assertEqual(report["candidate_locales"], expected_candidates)

    def test_contract_contains_only_enforced_inputs_and_invariants(self):
        gate = json.loads((ROOT / "contracts/commonworld/platform-foundation-gate.contract.json").read_text())
        self.assertEqual(
            set(gate["authoritative_inputs"]),
            {"catalog", "commons_basis_index", "current_state", "locale_release", "project_schema"},
        )
        self.assertEqual(
            gate["invariants"],
            {
                "catalog_counts_are_derived_not_hardcoded": True,
                "basis_debt_must_not_grow": True,
                "candidate_locales_must_be_noindex": True,
                "candidate_locales_must_not_be_selectable": True,
                "public_activity_status_sets_must_match_project_schema": True,
            },
        )

    def test_current_state_matches_public_project_activity_schema(self):
        current = json.loads((ROOT / "contracts/commonworld/current-state.contract.json").read_text())
        schema = json.loads((ROOT / "contracts/commonworld/project.schema.json").read_text())
        self.assertEqual(
            set(current["activity_status_policy"]["public_states"]),
            set(schema["$defs"]["activity"]["properties"]["status"]["enum"]),
        )

    def test_robots_parser_requires_noindex_in_robots_content(self):
        parser = RobotsMetaParser()
        parser.feed('<meta name="robots" content="index"><footer class="noindex"></footer>')
        self.assertNotIn("noindex", parser.directives)

        parser = RobotsMetaParser()
        parser.feed('<meta content="nofollow, noindex" NAME="ROBOTS">')
        self.assertIn("noindex", parser.directives)

    def test_validator_collects_independent_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "contracts", root / "contracts")
            shutil.copytree(ROOT / "catalog", root / "catalog")
            shutil.copytree(ROOT / "docs/architecture", root / "docs/architecture")
            for surface in ("ar.html", "es.html", "fr.html", "pt-BR.html", "method.ar.html", "method.es.html", "method.fr.html", "method.pt-BR.html", "propose.ar.html", "propose.es.html", "propose.fr.html", "propose.pt-BR.html"):
                shutil.copy2(ROOT / surface, root / surface)

            gate_path = root / "contracts/commonworld/platform-foundation-gate.contract.json"
            gate = json.loads(gate_path.read_text())
            gate["decision"]["new_locale_indexing_allowed"] = True
            gate_path.write_text(json.dumps(gate))

            catalog_path = root / "catalog/catalog.json"
            catalog = json.loads(catalog_path.read_text())
            catalog["entry_count"] += 1
            catalog_path.write_text(json.dumps(catalog))

            errors, _ = validate_platform_foundation(root)
            self.assertIn("catalog entry_count drift", errors)
            self.assertIn("platform foundation decision differs from the enforced policy", errors)


if __name__ == "__main__":
    unittest.main()
