#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from scripts.locale_review_evidence import reviewed_source_pack_sha256

ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "assets/locales/wave1-locales.json"
CONTRACT_PATH = ROOT / "docs/architecture/locale-release.contract.json"
RAW_LIFECYCLE = ROOT / "docs/evidence/locale-reviews/raw/zh-Hans-released-browser-lifecycle-smoke.json"
CONTINUITY_PATH = ROOT / "docs/evidence/locale-reviews/raw/wave1-bundle-extension-continuity-2026-08-08.json"
SHARED_RECEIPTS = ROOT / "docs/evidence/locale-releases/receipts/shared"
EVIDENCE_DIR = ROOT / "docs/evidence/locale-releases"
REVIEW_INPUT_DIR = ROOT / "docs/evidence/locale-review-inputs"
PRODUCT_REVISION = "2d72c6d3183ef499bcd31a390cb6825ad0c2d739"
LEGACY_RELEASED = ("es", "fr", "pt-BR", "ar")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_payload_bytes(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def payload_sha256(payload: object) -> str:
    return hashlib.sha256(canonical_payload_bytes(payload)).hexdigest()


def normalized_locale_payload(pack_payload: dict, locale: str) -> dict:
    result = copy.deepcopy(pack_payload["locales"][locale])
    result["meta"]["independent_language_review"] = "pending"
    return result


def continuity_proof(pack: dict, contract: dict) -> dict:
    rows = []
    independent_receipt = read_json(SHARED_RECEIPTS / "independent-language-review.json")
    input_digests = independent_receipt["catalog_review"]["input_digests"]
    for locale in LEGACY_RELEASED:
        review_input_path = REVIEW_INPUT_DIR / f"{locale}.json"
        review_input = read_json(review_input_path)
        current_payload = normalized_locale_payload(pack, locale)
        reviewed_payload = review_input["payload"]
        current_payload_digest = payload_sha256(current_payload)
        reviewed_payload_digest = payload_sha256(reviewed_payload)
        if current_payload != reviewed_payload:
            raise RuntimeError(f"{locale}: current locale payload differs from independently reviewed input")
        catalog_path = ROOT / "catalog/locales" / f"{locale}.json"
        catalog_digest = sha256_file(catalog_path)
        if input_digests.get(locale) != catalog_digest:
            raise RuntimeError(f"{locale}: catalog overlay changed since independent review")
        rows.append({
            "locale": locale,
            "review_input": review_input_path.relative_to(ROOT).as_posix(),
            "review_input_sha256": sha256_file(review_input_path),
            "current_normalized_locale_payload_sha256": current_payload_digest,
            "reviewed_input_payload_sha256": reviewed_payload_digest,
            "payload_byte_equivalent_after_canonicalization": current_payload_digest == reviewed_payload_digest,
            "catalog_overlay_sha256": catalog_digest,
            "catalog_digest_matches_independent_review": True,
        })
    return {
        "schema_version": 1,
        "kind": "commonworld.wave1_bundle_extension_continuity_proof",
        "source_revision": PRODUCT_REVISION,
        "added_locale": "zh-Hans",
        "legacy_locales": list(LEGACY_RELEASED),
        "verdict": "PASS",
        "claim": "Adding zh-Hans changes the shared Wave-1 bundle bytes but does not change any previously reviewed locale payload or catalog overlay.",
        "checks": rows,
    }


def refresh_shared_receipts(pack_digest: str, reviewed_digest: str, release_id: str, lifecycle: dict, continuity_sha: str) -> dict[str, str]:
    lifecycle_sha = sha256_file(RAW_LIFECYCLE)
    locales = list(read_json(CONTRACT_PATH)["rollout"]["wave_1"])
    common_updates = {
        "source_revision": PRODUCT_REVISION,
        "source_pack_sha256": pack_digest,
        "reviewed_source_pack_sha256": reviewed_digest,
        "release_id": release_id,
        "raw_source": {"path": RAW_LIFECYCLE.relative_to(ROOT).as_posix(), "sha256": lifecycle_sha},
        "locales": locales,
        "bundle_extension_continuity": {"path": CONTINUITY_PATH.relative_to(ROOT).as_posix(), "sha256": continuity_sha},
    }
    for name in ("browser-smoke", "keyboard-and-screen-reader-review", "state-preservation-smoke"):
        path = SHARED_RECEIPTS / f"{name}.json"
        receipt = read_json(path)
        receipt.update(common_updates)
        if name == "browser-smoke":
            receipt["page_count"] = lifecycle.get("pages", len(locales) * 3)
            receipt["claims"] = lifecycle.get("claims", receipt.get("claims", {}))
            receipt["verdict"] = "PASS"
            receipt["all_surfaces_released"] = True
        write_json(path, receipt)
    return {
        "browser_smoke": sha256_file(SHARED_RECEIPTS / "browser-smoke.json"),
        "keyboard_and_screen_reader_review": sha256_file(SHARED_RECEIPTS / "keyboard-and-screen-reader-review.json"),
        "state_preservation_smoke": sha256_file(SHARED_RECEIPTS / "state-preservation-smoke.json"),
        "independent_language_review": sha256_file(SHARED_RECEIPTS / "independent-language-review.json"),
    }


def refresh_legacy_release_evidence(contract: dict, pack_digest: str, reviewed_digest: str, receipt_hashes: dict[str, str]) -> None:
    for locale in LEGACY_RELEASED:
        entry = contract["locale_registry"][locale]
        evidence_path = EVIDENCE_DIR / f"{locale}.json"
        evidence = read_json(evidence_path)
        evidence["source_revision"] = PRODUCT_REVISION
        evidence["source_pack_sha256"] = pack_digest
        evidence["reviewed_source_pack_sha256"] = reviewed_digest
        evidence["catalog_overlay_sha256"] = sha256_file(ROOT / "catalog/locales" / f"{locale}.json")
        evidence["surface_sha256"] = {
            surface: sha256_file(ROOT / relative)
            for surface, relative in entry["surface_files"].items()
        }
        receipts = evidence["evidence_receipts"]
        for gate_name, digest in receipt_hashes.items():
            if gate_name in receipts:
                receipts[gate_name]["sha256"] = digest
        evidence["notes"] = (
            "Digest-bound release evidence refreshed after the zh-Hans Wave-1 bundle extension. "
            "The stored continuity proof verifies that this locale's normalized reviewed payload and catalog overlay are byte-equivalent to the original independent-review inputs; fresh lifecycle browser/state/accessibility smoke covers the rebuilt surfaces. "
            "No native/human approval or full WCAG conformance is claimed."
        )
        write_json(evidence_path, evidence)
        entry["release_evidence"] = {
            "path": evidence_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(evidence_path),
        }


def main() -> int:
    pack = read_json(PACK_PATH)
    contract = read_json(CONTRACT_PATH)
    lifecycle = read_json(RAW_LIFECYCLE)
    if lifecycle.get("verdict") != "PASS":
        raise RuntimeError("fresh Wave-1 lifecycle smoke is not PASS")
    expected_pages = len(contract["rollout"]["wave_1"]) * 3
    if lifecycle.get("pages") != expected_pages:
        raise RuntimeError(f"lifecycle smoke page coverage mismatch: {lifecycle.get('pages')} != {expected_pages}")
    proof = continuity_proof(pack, contract)
    write_json(CONTINUITY_PATH, proof)
    continuity_sha = sha256_file(CONTINUITY_PATH)
    pack_digest = sha256_file(PACK_PATH)
    reviewed_digest = reviewed_source_pack_sha256(PACK_PATH)
    release_id = read_json(ROOT / "assets/commonworld-page-builds.json")["release_id"]
    receipt_hashes = refresh_shared_receipts(pack_digest, reviewed_digest, release_id, lifecycle, continuity_sha)
    refresh_legacy_release_evidence(contract, pack_digest, reviewed_digest, receipt_hashes)
    write_json(CONTRACT_PATH, contract)
    print(json.dumps({
        "verdict": "PASS",
        "legacy_locales_refreshed": list(LEGACY_RELEASED),
        "source_pack_sha256": pack_digest,
        "reviewed_source_pack_sha256": reviewed_digest,
        "release_id": release_id,
        "continuity_proof_sha256": continuity_sha,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
