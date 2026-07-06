import unittest

from scripts.validate_contracts import ROOT
from scripts.validate_proof_hub import PROOF_LINKS, validate_proof_hub


class ProofHubTests(unittest.TestCase):
    def test_static_proof_hub_validates(self) -> None:
        self.assertEqual([], validate_proof_hub(ROOT))

    def test_proof_hub_links_all_surfaces(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        for proof_id, href in PROOF_LINKS.items():
            with self.subTest(proof_id=proof_id):
                self.assertIn(f'data-proof-link="{proof_id}"', html)
                self.assertIn(f'href="{href}"', html)


if __name__ == "__main__":
    unittest.main()
