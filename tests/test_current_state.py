import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_current_state import ROOT, validate_current_state


class CurrentStateTests(unittest.TestCase):
    def copy_current_state(self, directory: str) -> Path:
        target = Path(directory)
        paths = (
            "contracts/commonworld/current-state.contract.json",
            "contracts/commonworld/public-maplibre-vertical-slice.contract.json",
            "contracts/commonworld/digital-ring-taxonomy.contract.json",
            "contracts/commonworld/production-delivery-provider.contract.json",
            "contracts/commonworld/renderer-selection.contract.json",
            "contracts/commonworld/digital-sphere.contract.json",
            "catalog/catalog.json",
            "catalog/projects/cltb-le-nid.json",
            "docs/research/public-maplibre-vertical-slice-v1.result.json",
            "LICENSE",
            "LICENSE-DATA.md",
        )
        for relative in paths:
            source = ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return target

    def test_current_state_validates(self) -> None:
        self.assertEqual([], validate_current_state(ROOT))

    def test_rejects_regression_to_unapproved_production(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["production"]["architecture_authorized"] = False
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("production truth" in error for error in errors))

    def test_rejects_historical_contract_as_current_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["precedence"]["current_operational_truth"] = "renderer-selection.contract.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("precedence" in error for error in errors))

    def test_rejects_rewritten_historical_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "docs/research/public-maplibre-vertical-slice-v1.result.json"
            path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("historical evidence was rewritten" in error for error in errors))

    def test_rejects_missing_odbl_catalogue_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["licensing"]["catalogue_data_exceptions"] = []
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("licensing truth" in error for error in errors))

        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            path = root / "contracts/commonworld/current-state.contract.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["licensing"]["catalogue_data_exceptions"][0]["source_ids"] = [
                "osm-node-13966522352",
                "osm-way-260066697",
            ]
            path.write_text(json.dumps(value), encoding="utf-8")
            errors = validate_current_state(root)
        self.assertTrue(any("licensing truth" in error for error in errors))

    def test_rejects_missing_data_licence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_current_state(directory)
            (root / "LICENSE-DATA.md").unlink()
            errors = validate_current_state(root)
        self.assertTrue(any("licences must exist" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
