import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.smoke_proof_hub_offline import (
    EXPECTED_BOUNDARY_NEGATIONS,
    EXPECTED_EVIDENCE_MODES,
    EXPECTED_SURFACE_TYPES,
    EXPECTED_TRUST_STATES,
    expected_hub_cards,
    smoke_report,
    validate_offline_hub_smoke,
)
from scripts.validate_contracts import ROOT


class ProofHubOfflineSmokeTests(unittest.TestCase):
    def copy_valid_root(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        for path in ("index.html", "index.css"):
            shutil.copy2(ROOT / path, tmp_root / path)
        shutil.copytree(ROOT / "proofs", tmp_root / "proofs")
        shutil.copytree(ROOT / "examples", tmp_root / "examples")
        return tmp_root

    def test_offline_hub_smoke_validates_current_hub(self) -> None:
        self.assertEqual([], validate_offline_hub_smoke(ROOT))

    def test_offline_hub_smoke_reports_all_surface_types(self) -> None:
        report = smoke_report(ROOT)
        cards = {card.proof_id: card for card in report.surfaces}
        self.assertEqual("offline-static", report.network_mode)
        self.assertEqual("not-started", report.browser_mode)
        self.assertEqual(tuple(EXPECTED_SURFACE_TYPES.values()), report.taxonomy_entries)
        self.assertEqual(EXPECTED_TRUST_STATES, report.trust_states)
        self.assertEqual(EXPECTED_BOUNDARY_NEGATIONS, report.boundary_negations)
        for proof_id, expected_type in EXPECTED_SURFACE_TYPES.items():
            with self.subTest(proof_id=proof_id):
                self.assertEqual(expected_type, cards[proof_id].surface_type)
                self.assertEqual(EXPECTED_EVIDENCE_MODES[proof_id], cards[proof_id].evidence_mode)

    def test_expected_hub_cards_are_registry_ordered(self) -> None:
        ids = [card.proof_id for card in expected_hub_cards(ROOT)]
        self.assertEqual(["project-profile", "map", "aether", "search"], ids)

    def test_missing_taxonomy_entry_fails_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_valid_root(tmp_dir)
            html_path = root / "index.html"
            html_path.write_text(html_path.read_text(encoding="utf-8").replace("<strong>Projection focus</strong>", "<strong>Projection branch</strong>", 1), encoding="utf-8")

            errors = validate_offline_hub_smoke(root)

        self.assertIn(
            "offline hub smoke taxonomy entries mismatch: expected ('Visual explanation', 'Location rendering', 'Projection focus', 'Static data-quality check'), got ('Visual explanation', 'Location rendering', 'Static data-quality check')",
            errors,
        )

    def test_surface_type_drift_fails_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_valid_root(tmp_dir)
            html_path = root / "index.html"
            html_path.write_text(html_path.read_text(encoding="utf-8").replace("<dd>Location rendering</dd>", "<dd>Map display</dd>", 1), encoding="utf-8")

            errors = validate_offline_hub_smoke(root)

        self.assertIn(
            "offline hub smoke surface type mismatch for map: expected Location rendering, got Map display",
            errors,
        )

    def test_runtime_script_fails_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_valid_root(tmp_dir)
            html_path = root / "index.html"
            html_path.write_text(html_path.read_text(encoding="utf-8") + '\n<script src="./runtime.js"></script>\n', encoding="utf-8")

            errors = validate_offline_hub_smoke(root)

        self.assertIn("offline hub smoke forbids runtime affordance: <script", errors)

    def test_missing_registered_card_returns_smoke_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_valid_root(tmp_dir)
            html_path = root / "index.html"
            html_path.write_text(html_path.read_text(encoding="utf-8").replace('data-proof-link="search"', 'data-proof-link="search-missing"', 1), encoding="utf-8")

            errors = validate_offline_hub_smoke(root)

        self.assertIn("offline hub smoke card extraction failed: missing proof card: search", errors)


if __name__ == "__main__":
    unittest.main()
