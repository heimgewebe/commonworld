import unittest

from scripts.check_pages_dns_target import (
    EXPECTED_APEX_A,
    EXPECTED_APEX_AAAA,
    EXPECTED_WWW_CNAME,
    FORBIDDEN_PARKING_A,
    ObservedDns,
    validate_observed,
)


class PagesDnsTargetTests(unittest.TestCase):
    def test_expected_target_records_pass(self) -> None:
        observed = ObservedDns(
            apex_a=tuple(sorted(EXPECTED_APEX_A)),
            apex_aaaa=tuple(sorted(EXPECTED_APEX_AAAA)),
            apex_cname=(),
            www_a=(),
            www_aaaa=(),
            www_cname=(EXPECTED_WWW_CNAME,),
        )
        self.assertEqual([], validate_observed(observed))

    def test_current_inwx_parking_records_fail(self) -> None:
        observed = ObservedDns(
            apex_a=(FORBIDDEN_PARKING_A,),
            apex_aaaa=(),
            apex_cname=(),
            www_a=(FORBIDDEN_PARKING_A,),
            www_aaaa=(),
            www_cname=(),
        )
        errors = validate_observed(observed)
        self.assertTrue(any(error.startswith("apex A mismatch") for error in errors))
        self.assertTrue(any(error.startswith("apex AAAA mismatch") for error in errors))
        self.assertTrue(any(error.startswith("www CNAME mismatch") for error in errors))
        self.assertTrue(any(error.startswith("www must not have A records") for error in errors))
        self.assertIn(f"INWX parking A record still present: {FORBIDDEN_PARKING_A}", errors)

    def test_apex_cname_is_rejected(self) -> None:
        observed = ObservedDns(
            apex_a=tuple(sorted(EXPECTED_APEX_A)),
            apex_aaaa=tuple(sorted(EXPECTED_APEX_AAAA)),
            apex_cname=("heimgewebe.github.io.",),
            www_a=(),
            www_aaaa=(),
            www_cname=(EXPECTED_WWW_CNAME,),
        )
        self.assertIn("apex must not have CNAME records: got ['heimgewebe.github.io.']", validate_observed(observed))


if __name__ == "__main__":
    unittest.main()
