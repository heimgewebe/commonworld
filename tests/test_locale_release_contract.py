import copy
import json
import unittest
from pathlib import Path

from scripts.locale_registry import match_registry_locale
from scripts.validate_locale_release import load_contract, validate_contract

ROOT = Path(__file__).resolve().parents[1]


class LocaleReleaseContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract(ROOT / "docs/architecture/locale-release.contract.json")

    def test_current_runtime_and_released_surfaces_match_contract(self) -> None:
        self.assertEqual(validate_contract(self.contract, ROOT), [])


    def test_independent_review_inputs_match_the_exact_wave1_pack(self) -> None:
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

    def test_independent_language_review_receipt_preserves_raw_evidence(self) -> None:
        import hashlib

        receipt = json.loads(
            (ROOT / "docs/evidence/locale-releases/receipts/shared/independent-language-review.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(receipt["status"], "passed")
        self.assertRegex(receipt["reviewed_source_pack_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(set(receipt["locale_verdicts"]), {"es", "fr", "pt-BR", "ar"})
        self.assertTrue(all(item["status"] == "passed" for item in receipt["locale_verdicts"].values()))
        for source in receipt["raw_sources"]:
            path = ROOT / source["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source["sha256"])
            self.assertRegex(source["label"], r"^(?:initial|final)-(?:es-fr|pt-ar)-(?:findings|pass)$")
        self.assertEqual(receipt["finding_history"]["final_findings"], [])
        self.assertFalse(receipt["review_class"]["claims_native_or_human_review"])

    def test_browser_registry_excludes_governance_evidence_pointers(self) -> None:
        from scripts.build_locale_runtime import runtime_locale_registry

        contract = copy.deepcopy(self.contract)
        contract["locale_registry"]["es"]["release_evidence"] = {
            "path": "docs/evidence/locale-releases/es.json",
            "sha256": "a" * 64,
        }
        projected = runtime_locale_registry(contract)
        self.assertEqual(projected["es"]["status"], "released")
        self.assertNotIn("candidate_evidence_path", projected["es"])
        self.assertNotIn("release_evidence", projected["es"])
        self.assertIn("surface_files", projected["es"])

    def test_candidate_locale_cannot_be_published_without_release_evidence(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["locale_registry"]["es"]["status"] = "candidate"
        contract["locale_registry"]["es"].pop("release_evidence")
        errors = validate_contract(contract, ROOT)
        self.assertTrue(
            any("candidate locale es must not be released" == error for error in errors)
        )
        # UI release of es must not require a Spanish catalogue-content policy copy.
        self.assertNotIn(
            "summary specificity policy missing for released locale es",
            errors,
        )
        self.assertNotIn(
            "summary specificity policy missing for published content language es",
            errors,
        )

    def test_release_gate_requires_locale_specific_summary_policy(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["release_gate"][
            "catalog_summary_specificity_policy_required"
        ] = False
        errors = validate_contract(contract, ROOT)
        self.assertIn(
            "release gate must require a locale-aware catalog summary specificity policy",
            errors,
        )

    def test_simplified_chinese_does_not_claim_traditional_script_or_regions(self) -> None:
        from scripts.locale_registry import match_registry_locale

        self.assertEqual(match_registry_locale(["zh-CN"], root=ROOT), "zh-Hans")
        self.assertEqual(match_registry_locale(["zh-SG"], root=ROOT), "zh-Hans")
        self.assertEqual(match_registry_locale(["zh-Hant", "fr-FR"], root=ROOT), "fr")
        self.assertEqual(match_registry_locale(["zh-TW", "fr-FR"], root=ROOT), "fr")
        self.assertEqual(match_registry_locale(["zh-HK", "fr-FR"], root=ROOT), "fr")

    def test_primary_subtag_matches_region_specific_released_locale(self) -> None:
        self.assertEqual(
            match_registry_locale(["pt-PT"], statuses=("released",), root=ROOT),
            "pt-BR",
        )
        self.assertEqual(
            match_registry_locale(["pt"], statuses=("released",), root=ROOT),
            "pt-BR",
        )

    def test_location_based_language_inference_is_rejected(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["decision"]["automatic_selection"]["geolocation_must_not_influence_locale"] = False
        self.assertTrue(any("geolocation" in error for error in validate_contract(contract, ROOT)))

    def test_partial_translation_cannot_pass_the_release_gate(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["release_gate"]["translation_coverage_ratio"] = 0.99
        contract["release_gate"]["untranslated_ui_markers_max"] = 1
        errors = validate_contract(contract, ROOT)
        self.assertTrue(any("100%" in error for error in errors))
        self.assertTrue(any("markers" in error for error in errors))

    def test_future_full_locales_are_demand_gated_but_browser_translation_is_only_an_assist(self) -> None:
        contract = copy.deepcopy(self.contract)
        for field in (
            "future_full_locale_activation_requires_observed_demand",
            "browser_translation_may_assist_long_tail_reading",
            "browser_translation_does_not_replace_owned_search_semantics",
        ):
            contract["rollout"][field] = False
            self.assertTrue(any(field in error for error in validate_contract(contract, ROOT)), field)
            contract["rollout"][field] = True

    def test_rollout_waves_are_disjoint_and_not_yet_selectable(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["rollout"]["wave_2"].append("es")
        self.assertTrue(any("duplicate" in error for error in validate_contract(contract, ROOT)))

    def test_arabic_keeps_rtl_as_an_early_architecture_gate(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["locale_registry"]["ar"]["direction"] = "ltr"
        self.assertTrue(any("Arabic" in error for error in validate_contract(contract, ROOT)))

    def test_content_languages_remain_independent_from_interface_languages(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["content_language_policy"]["independent_from_interface_locales"] = False
        self.assertTrue(any("independent_from_interface_locales" in error for error in validate_contract(contract, ROOT)))

    def test_malformed_locale_lists_fail_closed_without_exception(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["decision"]["released_locales"] = ["en", {}]
        contract["rollout"]["wave_1"] = ["es", {}]
        errors = validate_contract(contract, ROOT)
        self.assertTrue(any("released_locales" in error for error in errors))
        self.assertTrue(any("Wave 1" in error or "rollout waves" in error for error in errors))

    def test_registry_requires_stable_native_and_english_names(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["locale_registry"]["pt-BR"]["native_name"] = " "
        contract["locale_registry"]["ar"]["english_name"] = ""
        errors = validate_contract(contract, ROOT)
        self.assertTrue(any("pt-BR" in error and "native_name" in error for error in errors))
        self.assertTrue(any("ar" in error and "english_name" in error for error in errors))

    def test_default_and_fallback_locales_must_be_released(self) -> None:
        contract = copy.deepcopy(self.contract)
        contract["decision"]["default_locale"] = "hi"
        contract["decision"]["fallback_locale"] = "ja"
        errors = validate_contract(contract, ROOT)
        self.assertTrue(any("default_locale must be released" == error for error in errors))
        self.assertTrue(any("fallback_locale must be released" == error for error in errors))


    def test_release_evidence_scaffold_stays_pending_without_passed_receipts(self) -> None:
        from scripts.generate_locale_release_evidence import build_scaffold

        scaffold = build_scaffold("es")
        self.assertEqual(scaffold["schema_version"], 2)
        self.assertEqual(scaffold["status"], "pending")
        self.assertRegex(scaffold["catalog_overlay_sha256"], r"^[0-9a-f]{64}$")
        self.assertFalse(scaffold["gate_results"]["independent_language_review_passed"])
        self.assertNotEqual(scaffold["source_pack_sha256"], scaffold["reviewed_source_pack_sha256"])
        self.assertRegex(scaffold["reviewed_source_pack_sha256"], r"^[0-9a-f]{64}$")
        self.assertFalse(scaffold["review_class"]["claims_native_or_human_review"])
        self.assertTrue(scaffold["review_class"]["model_assisted_editorial_review"])
        self.assertTrue(scaffold["review_class"]["post_fix_review_required"])

    def test_release_evidence_requires_current_pack_and_honest_review_class(self) -> None:
        import hashlib
        import tempfile
        from scripts.validate_locale_release import _release_evidence_errors

        contract = copy.deepcopy(self.contract)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            surfaces = {"index": "es.html", "method": "method.es.html", "proposal": "propose.es.html"}
            for relative in surfaces.values():
                (root / relative).write_text('<html lang="es" dir="ltr"></html>\n', encoding="utf-8")
            evidence = {
                "schema_version": 2,
                "kind": "commonworld.ui_locale_release_evidence",
                "locale": "es",
                "status": "released",
                "source_revision": "a" * 40,
                "source_pack_sha256": "b" * 64,
                "reviewed_source_pack_sha256": "d" * 64,
                "catalog_overlay_sha256": "f" * 64,
                "surface_sha256": {name: hashlib.sha256((root / relative).read_bytes()).hexdigest() for name, relative in surfaces.items()},
                "gate_results": {
                    "required_surfaces_passed": sorted(contract["release_gate"]["required_surfaces"]),
                    "translation_coverage_ratio": 1.0,
                    "untranslated_ui_markers": 0,
                    "missing_runtime_keys": 0,
                    "machine_translation_only": False,
                    "independent_language_review_passed": True,
                    "keyboard_and_screen_reader_review_passed": True,
                    "browser_smoke_passed": True,
                    "state_preservation_smoke_passed": True,
                    "directional_layout_review": "not_required",
                    "mixed_script_review": "not_required",
                },
                "evidence_receipts": {},
                "review_class": {
                    "machine_translation_only": False,
                    "independent_of_writer": True,
                    "model_assisted_editorial_review": True,
                    "claims_native_or_human_review": True,
                    "digest_bound": True,
                    "findings_based": True,
                    "post_fix_review_required": True,
                },
            }
            evidence_path = root / "docs/evidence/locale-releases/es.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            entry = {
                "status": "released",
                "direction": "ltr",
                "surface_files": surfaces,
                "release_evidence": {
                    "path": "docs/evidence/locale-releases/es.json",
                    "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
                },
            }
            errors = _release_evidence_errors(
                "es", entry, contract, root,
                set(contract["release_gate"]["required_surfaces"]),
                "c" * 64,
                "e" * 64,
                "f" * 64,
            )
            self.assertIn("release evidence pack digest is stale for es", errors)
            self.assertIn("release evidence reviewed source pack digest is stale for es", errors)
            self.assertIn("release evidence must not overclaim native or human review for es", errors)


    def test_release_evidence_receipt_source_must_match_sha256(self) -> None:
        import hashlib
        import tempfile
        from scripts.validate_locale_release import _release_evidence_errors

        contract = copy.deepcopy(self.contract)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt_dir = root / "docs/evidence/locale-releases/receipts/es"
            receipt_dir.mkdir(parents=True)
            receipt_path = receipt_dir / "independent_language_review.json"
            receipt_path.write_text('{"status":"pending"}\n', encoding="utf-8")
            digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            surfaces = {
                "index": "es.html",
                "method": "method.es.html",
                "proposal": "propose.es.html",
            }
            for relative in surfaces.values():
                target = root / relative
                target.write_text(f"<html lang=\"es\" dir=\"ltr\"><body>{relative}</body></html>\n", encoding="utf-8")
            evidence = {
                "schema_version": 2,
                "kind": "commonworld.ui_locale_release_evidence",
                "locale": "es",
                "status": "released",
                "source_revision": "a" * 40,
                "source_pack_sha256": "c" * 64,
                "reviewed_source_pack_sha256": "d" * 64,
                "catalog_overlay_sha256": "e" * 64,
                "surface_sha256": {
                    name: hashlib.sha256((root / relative).read_bytes()).hexdigest()
                    for name, relative in surfaces.items()
                },
                "gate_results": {
                    "required_surfaces_passed": sorted(contract["release_gate"]["required_surfaces"]),
                    "translation_coverage_ratio": 1.0,
                    "untranslated_ui_markers": 0,
                    "missing_runtime_keys": 0,
                    "machine_translation_only": False,
                    "independent_language_review_passed": True,
                    "keyboard_and_screen_reader_review_passed": True,
                    "browser_smoke_passed": True,
                    "state_preservation_smoke_passed": True,
                    "directional_layout_review": "not_required",
                    "mixed_script_review": "not_required",
                },
                "review_class": {
                    "machine_translation_only": False,
                    "independent_of_writer": True,
                    "model_assisted_editorial_review": True,
                    "claims_native_or_human_review": False,
                    "digest_bound": True,
                    "findings_based": True,
                    "post_fix_review_required": True,
                },
                "evidence_receipts": {
                    name: {
                        "source": f"docs/evidence/locale-releases/receipts/es/{name}.json",
                        "sha256": digest if name == "independent_language_review" else ("b" * 64),
                    }
                    for name in contract["release_evidence"]["required_receipts"]
                },
            }
            evidence_path = root / "docs/evidence/locale-releases/es.json"
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            entry = {
                "status": "released",
                "direction": "ltr",
                "surface_files": surfaces,
                "release_evidence": {
                    "path": "docs/evidence/locale-releases/es.json",
                    "sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
                },
            }
            errors = _release_evidence_errors(
                "es",
                entry,
                contract,
                root,
                set(contract["release_gate"]["required_surfaces"]),
                "c" * 64,
                "d" * 64,
                "e" * 64,
            )
            self.assertTrue(any("receipt source is missing" in error or "stale" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
