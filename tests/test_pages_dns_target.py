import unittest

from scripts.check_pages_dns_target import (
    AUTHORITATIVE_NAMESERVERS,
    EXPECTED_APEX_A,
    EXPECTED_APEX_AAAA,
    EXPECTED_WWW_CNAME,
    FORBIDDEN_PARKING_A,
    ObservedDns,
    authoritative_values,
    dig_authoritative_answer,
    validate_observed,
)
from unittest import mock


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
        self.assertTrue(any(error.startswith("www must not have direct authoritative A records") for error in errors))
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

    def test_authoritative_parser_keeps_cname_separate_from_followed_a_records(self) -> None:
        with mock.patch("scripts.check_pages_dns_target.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stderr = ""
            run.return_value.stdout = "www.commonworld.net. 3600 IN CNAME heimgewebe.github.io.\n"
            self.assertEqual((("CNAME", "heimgewebe.github.io."),), dig_authoritative_answer("www.commonworld.net", "A", "ns.inwx.de"))

    def test_authoritative_values_accepts_cname_only_for_a_query(self) -> None:
        answers = tuple((("CNAME", "heimgewebe.github.io."),) for _ in AUTHORITATIVE_NAMESERVERS)
        with mock.patch("scripts.check_pages_dns_target.dig_authoritative_answer", side_effect=answers):
            self.assertEqual((), authoritative_values("www.commonworld.net", "A"))

    def test_authoritative_nameserver_disagreement_fails(self) -> None:
        answers = ((("CNAME", "heimgewebe.github.io."),), (("A", "185.199.108.153"),), (("CNAME", "heimgewebe.github.io."),))
        with mock.patch("scripts.check_pages_dns_target.dig_authoritative_answer", side_effect=answers):
            with self.assertRaisesRegex(RuntimeError, "authoritative nameserver disagreement"):
                authoritative_values("www.commonworld.net", "A")


if __name__ == "__main__":
    unittest.main()
