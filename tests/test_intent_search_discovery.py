import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.validate_intent_search_discovery import ROOT, validate_intent_search_discovery


class IntentSearchDiscoveryTests(unittest.TestCase):
    def copy_slice(self, directory: str) -> Path:
        target = Path(directory)
        for name in ("assets", "catalog", "contracts", "docs", "scripts"):
            shutil.copytree(ROOT / name, target / name)
        for name in ("index.html", "index.css"):
            shutil.copy2(ROOT / name, target / name)
        return target

    def mutate_json(self, root: Path, relative: str, mutation) -> None:
        path = root / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        mutation(value)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_intent_search_discovery_validates(self) -> None:
        self.assertEqual([], validate_intent_search_discovery(ROOT))

    def test_missing_direct_action_link_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            self.mutate_json(
                root,
                "catalog/projects/debian.json",
                lambda record: record.update(
                    {"links": [link for link in record["links"] if link.get("type") != "donate"]}
                ),
            )
            errors = validate_intent_search_discovery(root)
        self.assertTrue(any("action donate must have exactly one" in error for error in errors))

    def test_hidden_location_search_leak_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)

            def expose(record: dict) -> None:
                location = next(
                    item
                    for item in record["presence"]["geographic"]
                    if item["id"] == "freifunk-hamburg-private-routers"
                )
                location["mode"] = "exact"
                location["geometry"] = {"type": "Point", "coordinates": [10.0, 53.5]}

            self.mutate_json(root, "catalog/projects/freifunk-hamburg.json", expose)
            errors = validate_intent_search_discovery(root)
        self.assertTrue(any("hidden geographic values leaked" in error for error in errors))

    def test_digital_coordinate_target_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)

            def add_target(record: dict) -> None:
                record["kind"] = "hybrid"
                record["presence"]["geographic"] = [
                    {
                        "id": "invented-debian-office",
                        "mode": "exact",
                        "label": "Invented Debian office",
                        "geometry": {"type": "Point", "coordinates": [10.0, 53.5]},
                        "source_ids": ["debian-about"],
                    }
                ]

            self.mutate_json(root, "catalog/projects/debian.json", add_target)
            errors = validate_intent_search_discovery(root)
        self.assertTrue(any("digital Commons acquired" in error for error in errors))

    def test_contract_cannot_drop_a_required_filter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            self.mutate_json(
                root,
                "contracts/commonworld/intent-search-discovery.contract.json",
                lambda value: value.update({"filters": value["filters"][:-1]}),
            )
            errors = validate_intent_search_discovery(root)
        self.assertTrue(any("filter contract mismatch" in error for error in errors))

    def test_million_scale_claim_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.copy_slice(directory)
            self.mutate_json(
                root,
                "contracts/commonworld/intent-search-discovery.contract.json",
                lambda value: value["scalability"].update({"million_scale_delivery_claimed": True}),
            )
            errors = validate_intent_search_discovery(root)
        self.assertTrue(any("must not claim million-scale" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
