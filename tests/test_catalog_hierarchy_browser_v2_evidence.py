import copy,json,unittest
from pathlib import Path
from scripts.validate_catalog_hierarchy_browser_v2 import validate_browser_evidence
ROOT=Path(__file__).resolve().parents[1];EVIDENCE=ROOT/'docs/evidence/catalog-hierarchy-browser-v2.json'
class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.evidence=json.loads(EVIDENCE.read_text())
 def test_valid(self):validate_browser_evidence(self.evidence)
 def test_digest_drift(self):
  x=copy.deepcopy(self.evidence);x['scenarios']['candidate_root']['requests'][0]['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'SHA-256 mismatch'):validate_browser_evidence(x)
 def test_cutover_claim(self):
  x=copy.deepcopy(self.evidence);x['candidate_runtime']['cutover_authorized']=True
  with self.assertRaisesRegex(ValueError,'candidate runtime mismatch'):validate_browser_evidence(x)
 def test_corrupt_acceptance(self):
  x=copy.deepcopy(self.evidence);x['scenarios']['corrupt_segment']['verdict']='accepted'
  with self.assertRaisesRegex(ValueError,'not rejected'):validate_browser_evidence(x)
 def test_timing_forbidden(self):
  x=copy.deepcopy(self.evidence);x['scenarios']['candidate_root']['duration_ms']=1
  with self.assertRaisesRegex(ValueError,'timing field'):validate_browser_evidence(x)
if __name__=='__main__':unittest.main()
