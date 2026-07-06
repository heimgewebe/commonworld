import unittest

from scripts.validate_aether_proof import validate_aether_proof

class AetherProofTests(unittest.TestCase):
    def test_static_aether_proof_validates(self):
        self.assertEqual([], validate_aether_proof())

if __name__ == "__main__":
    pass
