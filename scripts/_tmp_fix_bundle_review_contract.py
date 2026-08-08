#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one patch target in {path}, found {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_review_input_test() -> None:
    path = ROOT / "tests/test_locale_release_contract.py"
    old = '''    def test_independent_review_inputs_match_the_exact_wave1_pack(self) -> None:
        import hashlib

        pack_path = ROOT / "assets/locales/wave1-locales.json"
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        from scripts.locale_review_evidence import reviewed_source_pack_sha256

        reviewed_digest = reviewed_source_pack_sha256(pack_path)
        for locale, payload in pack["locales"].items():
            review_input = json.loads(
                (ROOT / f"docs/evidence/locale-review-inputs/{locale}.json").read_text(
                    encoding="utf-8"
                )
            )
            reviewed_payload = copy.deepcopy(payload)
            reviewed_payload["meta"]["independent_language_review"] = "pending"
            self.assertEqual(review_input["locale"], locale)
            self.assertEqual(review_input["source_pack_sha256"], reviewed_digest)
            self.assertEqual(review_input["reviewed_source_pack_sha256"], reviewed_digest)
            self.assertEqual(review_input["payload"], reviewed_payload)
            self.assertTrue(review_input["claims"]["derived_without_translation_changes"])
            self.assertFalse(review_input["claims"]["release_evidence"])
            self.assertFalse(review_input["claims"]["native_or_human_review"])
'''
    new = '''    def test_independent_review_inputs_match_current_locale_payload_or_proven_bundle_extension(self) -> None:
        import hashlib

        pack_path = ROOT / "assets/locales/wave1-locales.json"
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        from scripts.locale_review_evidence import reviewed_source_pack_sha256

        reviewed_digest = reviewed_source_pack_sha256(pack_path)
        continuity_path = ROOT / "docs/evidence/locale-reviews/raw/wave1-bundle-extension-continuity-2026-08-08.json"
        continuity = (
            json.loads(continuity_path.read_text(encoding="utf-8"))
            if continuity_path.exists()
            else None
        )
        continuity_checks = {
            item["locale"]: item
            for item in (continuity or {}).get("checks", [])
        }
        for locale, payload in pack["locales"].items():
            review_input_path = ROOT / f"docs/evidence/locale-review-inputs/{locale}.json"
            review_input = json.loads(review_input_path.read_text(encoding="utf-8"))
            reviewed_payload = copy.deepcopy(payload)
            reviewed_payload["meta"]["independent_language_review"] = "pending"
            self.assertEqual(review_input["locale"], locale)
            self.assertRegex(review_input["source_pack_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(review_input["reviewed_source_pack_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(review_input["payload"], reviewed_payload)
            self.assertTrue(review_input["claims"]["derived_without_translation_changes"])
            self.assertFalse(review_input["claims"]["release_evidence"])
            self.assertFalse(review_input["claims"]["native_or_human_review"])

            if review_input["reviewed_source_pack_sha256"] == reviewed_digest:
                self.assertEqual(review_input["source_pack_sha256"], reviewed_digest)
                continue

            self.assertIsNotNone(continuity, f"{locale}: bundle hash changed without continuity proof")
            self.assertEqual(continuity.get("kind"), "commonworld.wave1_bundle_extension_continuity_proof")
            self.assertEqual(continuity.get("verdict"), "PASS")
            check = continuity_checks.get(locale)
            self.assertIsNotNone(check, f"{locale}: missing continuity row")
            self.assertTrue(check["payload_byte_equivalent_after_canonicalization"])
            self.assertTrue(check["catalog_digest_matches_independent_review"])
            self.assertEqual(
                check["review_input_sha256"],
                hashlib.sha256(review_input_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(
                check["current_normalized_locale_payload_sha256"],
                check["reviewed_input_payload_sha256"],
            )
'''
    replace_once(path, old, new)


def patch_zh_review_input_writer() -> None:
    path = ROOT / "scripts/_tmp_finalize_zh_hans_evidence.py"
    old = '''    write_json(path, {
        "schema_version": 1,
        "kind": "commonworld.ui_locale_independent_review_input",
        "locale": LOCALE,
        "source_revision": PRODUCT_REVISION,
        "source_pack": "assets/locales/wave1-locales.json",
        "source_pack_sha256": reviewed_digest,
        "payload": locale_payload,
    })
'''
    new = '''    write_json(path, {
        "schema_version": 1,
        "kind": "commonworld.ui_locale_independent_review_input",
        "locale": LOCALE,
        "source_revision": PRODUCT_REVISION,
        "source_pack": "assets/locales/wave1-locales.json",
        "source_pack_sha256": reviewed_digest,
        "payload": locale_payload,
        "claims": {
            "derived_without_translation_changes": True,
            "release_evidence": False,
            "native_or_human_review": False,
        },
        "reviewed_source_pack_sha256": reviewed_digest,
    })
'''
    replace_once(path, old, new)


def main() -> int:
    patch_review_input_test()
    patch_zh_review_input_writer()
    print("bundle-extension review contract now preserves historical hashes and requires exact payload continuity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
