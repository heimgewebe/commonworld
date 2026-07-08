import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_contracts import ROOT
from scripts.validate_weltgewebe_handoff_contract import validate_weltgewebe_handoff_contract


class WeltgewebeHandoffContractTests(unittest.TestCase):
    def test_weltgewebe_handoff_contract_validates(self) -> None:
        self.assertEqual([], validate_weltgewebe_handoff_contract(ROOT))

    def copy_contract_surface(self, tmp_dir: str) -> Path:
        tmp_root = Path(tmp_dir)
        shutil.copytree(ROOT / "docs", tmp_root / "docs")
        shutil.copytree(ROOT / "contracts", tmp_root / "contracts")
        return tmp_root

    def test_doc_must_declare_no_implicit_auth_sharing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            doc_path = tmp_root / "docs" / "blueprints" / "weltgewebe-handoff-contract.md"
            text = doc_path.read_text(encoding="utf-8").replace("no implicit auth sharing", "auth may pass through")
            doc_path.write_text(text, encoding="utf-8")

            errors = validate_weltgewebe_handoff_contract(tmp_root)

        self.assertIn(
            "weltgewebe handoff contract missing doctrine token: no implicit auth sharing",
            errors,
        )

    def test_schema_must_require_url_for_enabled_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = self.copy_contract_surface(tmp_dir)
            schema_path = tmp_root / "contracts" / "commonworld" / "project.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            handoff = schema["$defs"]["handoff"]
            for branch in handoff["allOf"]:
                if branch.get("if", {}).get("properties", {}).get("enabled", {}).get("const") is True:
                    branch["then"]["required"].remove("url")
            schema_path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")

            errors = validate_weltgewebe_handoff_contract(tmp_root)

        self.assertIn("enabled handoff schema must require url", errors)


if __name__ == "__main__":
    unittest.main()
