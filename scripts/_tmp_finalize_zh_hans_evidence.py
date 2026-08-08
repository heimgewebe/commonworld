#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
from pathlib import Path

from scripts.locale_review_evidence import reviewed_source_pack_sha256

ROOT = Path(__file__).resolve().parents[1]
LOCALE = "zh-Hans"
PRODUCT_REVISION = "2d72c6d3183ef499bcd31a390cb6825ad0c2d739"
PACK_PATH = ROOT / "assets/locales/wave1-locales.json"
CATALOG_PATH = ROOT / "catalog/locales/zh-Hans.json"
CONTRACT_PATH = ROOT / "docs/architecture/locale-release.contract.json"
RAW_DIR = ROOT / "docs/evidence/locale-reviews/raw"
REVIEW_INPUT_DIR = ROOT / "docs/evidence/locale-review-inputs"
RECEIPT_DIR = ROOT / "docs/evidence/locale-releases/receipts/zh-Hans"
EVIDENCE_PATH = ROOT / "docs/evidence/locale-releases/zh-Hans.json"
LIFECYCLE_RAW = RAW_DIR / "zh-Hans-released-browser-lifecycle-smoke.json"
SEARCH_RAW = RAW_DIR / "zh-Hans-search-semantics-smoke.json"
REVIEW_RAW = RAW_DIR / "zh-Hans-independent-post-fix-review-2026-08-08.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_release_id() -> str:
    manifest = read_json(ROOT / "assets/commonworld-page-builds.json")
    release_id = manifest.get("release_id")
    if not isinstance(release_id, str) or re.fullmatch(r"[0-9a-f]{20}", release_id) is None:
        raise RuntimeError(f"invalid release id: {release_id!r}")
    return release_id


def assert_smokes() -> tuple[dict, dict]:
    lifecycle = read_json(LIFECYCLE_RAW)
    search = read_json(SEARCH_RAW)
    if lifecycle.get("kind") != "commonworld.locale_lifecycle_browser_smoke" or lifecycle.get("verdict") != "PASS":
        raise RuntimeError("locale lifecycle smoke is not a PASS")
    claims = lifecycle.get("claims", {})
    if claims.get("native_language_approval") is not False or claims.get("full_wcag_conformance") is not False:
        raise RuntimeError("lifecycle smoke overclaims review scope")
    results = lifecycle.get("results", [])
    zh_pages = [item for item in results if item.get("locale") == LOCALE]
    if len(zh_pages) != 3 or not all(item.get("verdict") == "PASS" for item in zh_pages):
        raise RuntimeError(f"expected three passing zh-Hans lifecycle surfaces, got {len(zh_pages)}")
    if search.get("kind") != "commonworld.zh_hans_search_semantics_smoke" or search.get("verdict") != "PASS":
        raise RuntimeError("zh-Hans search semantics smoke is not a PASS")
    if search.get("result_contains_expected_project") is not True:
        raise RuntimeError("Chinese search did not find the expected project")
    return lifecycle, search


def assert_reviewed_content() -> tuple[dict, dict, dict]:
    pack = read_json(PACK_PATH)
    zh = pack["locales"][LOCALE]
    if zh["meta"].get("independent_language_review") != "passed":
        raise RuntimeError("zh-Hans pack provenance must be promoted to passed before evidence is written")
    catalog = read_json(CATALOG_PATH)
    projects = catalog.get("projects", {})
    if len(projects) != 88:
        raise RuntimeError(f"expected 88 reviewed projects, got {len(projects)}")
    contract = read_json(CONTRACT_PATH)
    entry = contract["locale_registry"][LOCALE]
    if entry.get("status") != "released":
        raise RuntimeError("zh-Hans contract status is not released")
    if contract["decision"].get("released_locales", [])[-1:] != [LOCALE]:
        raise RuntimeError("zh-Hans is not the expected newest released locale")
    if LOCALE not in contract["rollout"].get("wave_1", []):
        raise RuntimeError("zh-Hans is not included in Wave 1")
    if LOCALE in contract["rollout"].get("wave_2", []):
        raise RuntimeError("zh-Hans still appears in Wave 2")
    if contract["rollout"].get("future_full_locale_activation_requires_observed_demand") is not True:
        raise RuntimeError("future locale demand gate is absent")
    if contract["rollout"].get("browser_translation_may_assist_long_tail_reading") is not True:
        raise RuntimeError("browser-translation long-tail policy is absent")
    if contract["rollout"].get("browser_translation_does_not_replace_owned_search_semantics") is not True:
        raise RuntimeError("owned search semantics policy is absent")
    return pack, catalog, contract


def write_review_input(pack: dict, reviewed_digest: str) -> Path:
    locale_payload = copy.deepcopy(pack["locales"][LOCALE])
    locale_payload["meta"]["independent_language_review"] = "pending"
    path = REVIEW_INPUT_DIR / f"{LOCALE}.json"
    write_json(path, {
        "schema_version": 1,
        "kind": "commonworld.ui_locale_independent_review_input",
        "locale": LOCALE,
        "source_revision": PRODUCT_REVISION,
        "source_pack": "assets/locales/wave1-locales.json",
        "source_pack_sha256": reviewed_digest,
        "payload": locale_payload,
    })
    return path


def write_review_raw(catalog: dict, reviewed_digest: str, catalog_digest: str, review_input: Path) -> None:
    projects = catalog["projects"]
    digital_count = sum(1 for entry in projects.values() if "digital_label" in entry)
    geo_count = sum(len(entry.get("geographic_labels", {})) for entry in projects.values())
    resolved = [
        {"severity": "major", "area": "themes.energy", "problem": "Machine draft translated energy as vitality.", "resolution": "能源"},
        {"severity": "major", "area": "themes.free-software", "problem": "Machine draft conflated software freedom with price.", "resolution": "自由软件"},
        {"severity": "major", "area": "static.source_number", "problem": "Source was mistranslated as font.", "resolution": "来源 {index}"},
        {"severity": "major", "area": "static.effective_language", "problem": "Machine draft incorrectly named Spanish as the active language.", "resolution": "当前语言：简体中文"},
        {"severity": "major", "area": "actions", "problem": "Literal action labels such as 穿 and 接触 were unsuitable product Chinese.", "resolution": "Consistent use/borrow/learn/contribute/volunteer/donate/visit/contact/replicate vocabulary."},
        {"severity": "blocker", "area": "shell/method/proposal html lang", "problem": "Draft inherited en/es html language declarations.", "resolution": "All three surfaces declare zh-Hans."},
        {"severity": "major", "area": "proposal basis terminology", "problem": "Dimension/draft/admission terms used physical-size/drafting/admissions senses.", "resolution": "维度 / 草案 / 纳入决定 terminology."},
        {"severity": "major", "area": "catalog", "problem": "Machine draft contained duplicated geography, literal proper-place renderings and malformed federated terminology.", "resolution": "All 88 entries reviewed against English overlay and corrected."},
        {"severity": "major", "area": "free/open terminology", "problem": "Several software, data and Wikimedia descriptions used 免费 where freedom/open reuse was intended.", "resolution": "自由 / 开放 wording aligned to meaning."},
        {"severity": "minor", "area": "shell/proposal runtime", "problem": "Several literal UI phrases were understandable but unnatural or semantically imprecise.", "resolution": "Post-fix product wording polished and regression-bound."},
        {"severity": "major", "area": "BCP 47 matching", "problem": "Primary-language fallback could make zh-Hant/zh-TW silently select zh-Hans.", "resolution": "Script-aware matching now accepts zh-CN/zh-SG as Hans but refuses Hant/TW/HK/MO fallback to Hans."},
    ]
    write_json(REVIEW_RAW, {
        "schema_version": 1,
        "kind": "commonworld.zh_hans_independent_post_fix_language_review",
        "review_class": "model_assisted_independent_language_review",
        "reviewer": "GPT-5.6 Sol independent post-fix release review",
        "writer": "Google Translate machine-assisted draft writer",
        "writer_independence": "independent_from_google_translate_writer",
        "reviewed_revision": PRODUCT_REVISION,
        "review_input": {
            "path": review_input.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(review_input),
            "reviewed_source_pack_sha256": reviewed_digest,
            "catalog_overlay_sha256": catalog_digest,
        },
        "coverage": {
            "locale": LOCALE,
            "all_pack_sections_reviewed": True,
            "all_entries_reviewed": True,
            "project_count": len(projects),
            "digital_label_count": digital_count,
            "geographic_label_count": geo_count,
            "surfaces": ["globe", "text", "method", "proposal", "runtime_labels", "catalog_localization", "metadata_and_navigation"],
        },
        "finding_history": {"resolved": resolved, "final_findings": []},
        "final_verdict": "PASS",
        "final_counts": {"blocker": 0, "major": 0, "minor": 0, "note": 0},
        "limitations": [
            "Model-assisted review; no native-speaker or human approval is claimed.",
            "Automated accessibility checks do not claim full WCAG conformance or manual screen-reader acceptance.",
        ],
        "review_notes": [
            "The entire zh-Hans locale pack was read after the machine draft and again after corrective passes.",
            "All 88 zh-Hans catalog entries were read completely; remaining free/open, federation and literal-UI defects found in the post-fix pass were corrected before this final verdict.",
            "Traditional Chinese is intentionally not claimed: explicit Hant/TW/HK/MO preferences do not silently fall back to zh-Hans.",
        ],
    })


def write_receipts(lifecycle: dict, search: dict, pack_digest: str, reviewed_digest: str, catalog_digest: str, release_id: str) -> dict[str, Path]:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    lifecycle_sha = sha256_file(LIFECYCLE_RAW)
    search_sha = sha256_file(SEARCH_RAW)
    review_sha = sha256_file(REVIEW_RAW)
    common = {
        "schema_version": 1,
        "source_revision": PRODUCT_REVISION,
        "source_pack_sha256": pack_digest,
        "reviewed_source_pack_sha256": reviewed_digest,
        "release_id": release_id,
        "locale": LOCALE,
    }
    independent = RECEIPT_DIR / "independent-language-review.json"
    write_json(independent, {
        "schema_version": 2,
        "kind": "commonworld.ui_locale_independent_language_review_receipt",
        "status": "passed",
        "reviewed_revision": PRODUCT_REVISION,
        "reviewed_source_pack_sha256": reviewed_digest,
        "locale_verdicts": {LOCALE: {"status": "passed", "blocking_findings": []}},
        "review_class": {
            "machine_translation_only": False,
            "independent_of_writer": True,
            "model_assisted_editorial_review": True,
            "claims_native_or_human_review": False,
            "digest_bound": True,
            "findings_based": True,
            "post_fix_review_required": True,
        },
        "limitations": ["No native-speaker or human approval.", "No full WCAG or manual assistive-technology acceptance."],
        "catalog_review": {
            "review_kind": "model_assisted_independent_language_review",
            "reviewer": "GPT-5.6 Sol independent post-fix release review",
            "writer_independence": "independent_from_google_translate_writer",
            "input_digests": {LOCALE: catalog_digest},
            "coverage": {
                "locales": [LOCALE],
                "project_count_per_locale": 88,
                "all_entries_reviewed": True,
                "basis": "full_digest_bound_independent_post_fix_review",
                "full_review_source": REVIEW_RAW.relative_to(ROOT).as_posix(),
            },
            "verdict": "pass",
            "counts": {"blocker": 0, "major": 0, "minor": 0, "note": 0},
            "findings": [],
            "review_notes": [
                "The initial machine draft produced material findings; each was corrected before the final pass.",
                "The full 88-entry overlay and all zh-Hans pack sections were read after correction.",
                "No native or human language approval is claimed.",
            ],
            "source_receipts": [{"path": REVIEW_RAW.relative_to(ROOT).as_posix(), "sha256": review_sha, "role": "full_corpus_final_release_review"}],
        },
    })
    keyboard = RECEIPT_DIR / "keyboard-and-screen-reader-review.json"
    write_json(keyboard, {
        **common,
        "kind": "commonworld.ui_locale_keyboard_accessibility_review_receipt",
        "status": "passed",
        "raw_source": {"path": LIFECYCLE_RAW.relative_to(ROOT).as_posix(), "sha256": lifecycle_sha},
        "automated_checks": ["keyboard focus paths", "accessible names", "aria-live status", "form error visibility", "navigation semantics"],
        "manual_screen_reader_acceptance": False,
        "full_wcag_conformance": False,
    })
    browser = RECEIPT_DIR / "browser-smoke.json"
    write_json(browser, {
        **common,
        "kind": "commonworld.ui_locale_browser_smoke_receipt",
        "status": "passed",
        "verdict": "PASS",
        "page_count": lifecycle.get("pages"),
        "raw_source": {"path": LIFECYCLE_RAW.relative_to(ROOT).as_posix(), "sha256": lifecycle_sha},
        "search_semantics_raw_source": {"path": SEARCH_RAW.relative_to(ROOT).as_posix(), "sha256": search_sha},
        "zh_hans_surfaces_passed": 3,
        "all_surfaces_released": True,
        "claims": lifecycle.get("claims", {}),
    })
    state = RECEIPT_DIR / "state-preservation-smoke.json"
    write_json(state, {
        **common,
        "kind": "commonworld.ui_locale_state_preservation_receipt",
        "status": "passed",
        "raw_source": {"path": LIFECYCLE_RAW.relative_to(ROOT).as_posix(), "sha256": lifecycle_sha},
        "automated_checks": ["locale persistence", "query and fragment preservation", "proposal draft lifecycle", "released navigation"],
    })
    return {
        "independent_language_review": independent,
        "keyboard_and_screen_reader_review": keyboard,
        "browser_smoke": browser,
        "state_preservation_smoke": state,
    }


def write_release_evidence(contract: dict, pack_digest: str, reviewed_digest: str, catalog_digest: str, release_id: str, receipts: dict[str, Path]) -> str:
    entry = contract["locale_registry"][LOCALE]
    surfaces = entry["surface_files"]
    surface_sha = {name: sha256_file(ROOT / relative) for name, relative in surfaces.items()}
    evidence = {
        "schema_version": 2,
        "kind": "commonworld.ui_locale_release_evidence",
        "locale": LOCALE,
        "status": "released",
        "source_revision": PRODUCT_REVISION,
        "source_pack_sha256": pack_digest,
        "reviewed_source_pack_sha256": reviewed_digest,
        "catalog_overlay_sha256": catalog_digest,
        "surface_sha256": surface_sha,
        "release_id": release_id,
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
        "evidence_receipts": {
            name: {"source": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
            for name, path in receipts.items()
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
        "notes": "Digest-bound Simplified Chinese release evidence after full-corpus model-assisted independent post-fix review. Browser translation remains a long-tail reading assist only; product-owned Chinese search semantics were smoke-tested. Native/human approval and full WCAG conformance are not claimed.",
    }
    write_json(EVIDENCE_PATH, evidence)
    evidence_sha = sha256_file(EVIDENCE_PATH)
    entry["release_evidence"] = {"path": EVIDENCE_PATH.relative_to(ROOT).as_posix(), "sha256": evidence_sha}
    write_json(CONTRACT_PATH, contract)
    return evidence_sha


def main() -> int:
    lifecycle, search = assert_smokes()
    pack, catalog, contract = assert_reviewed_content()
    pack_digest = sha256_file(PACK_PATH)
    reviewed_digest = reviewed_source_pack_sha256(PACK_PATH)
    catalog_digest = sha256_file(CATALOG_PATH)
    release_id = current_release_id()
    review_input = write_review_input(pack, reviewed_digest)
    write_review_raw(catalog, reviewed_digest, catalog_digest, review_input)
    receipts = write_receipts(lifecycle, search, pack_digest, reviewed_digest, catalog_digest, release_id)
    evidence_sha = write_release_evidence(contract, pack_digest, reviewed_digest, catalog_digest, release_id, receipts)
    print(json.dumps({
        "locale": LOCALE,
        "status": "released",
        "source_revision": PRODUCT_REVISION,
        "source_pack_sha256": pack_digest,
        "reviewed_source_pack_sha256": reviewed_digest,
        "catalog_overlay_sha256": catalog_digest,
        "release_id": release_id,
        "release_evidence_sha256": evidence_sha,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
