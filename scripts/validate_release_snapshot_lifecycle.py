#!/usr/bin/env python3
"""Validate the conflict-resistant generated release lifecycle."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "docs/architecture/release-snapshot-lifecycle.contract.json"
EVIDENCE_PATH = ROOT / "docs/evidence/release-snapshot-lifecycle-v1.json"
CURRENT_MANIFEST_PATH = ROOT / "assets/commonworld-page-builds.json"
BUILD_SCRIPT_PATH = ROOT / "scripts/build_page_release_manifest.py"
CACHE_VALIDATOR_PATH = ROOT / "scripts/validate_cache_coherence.py"
DELIVERY_EVIDENCE = (
    "docs/evidence/catalog-delivery-benchmark-v1.json",
    "docs/evidence/catalog-delivery-public-browser-smoke-v1.json",
)
PROPOSED_HEAD_INPUTS = (
    "Makefile",
    "docs/architecture/release-snapshot-lifecycle.contract.json",
    "package.json",
    "assets/commonworld-release-check.js",
    "scripts/build_page_release_manifest.py",
    "scripts/measure_release_snapshot_lifecycle.py",
    "scripts/public_cache.py",
    "scripts/render_public_shell.py",
    "scripts/validate_cache_coherence.py",
    "scripts/validate_canonical_plan.py",
    "scripts/validate_catalog_delivery_budget.py",
    "scripts/validate_release_snapshot_lifecycle.py",
    "tests/test_release_snapshot_lifecycle.py",
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scope_sha256(input_hashes: dict[str, str]) -> str:
    payload = json.dumps(input_hashes, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def _seed_repo(root: Path) -> str:
    base_release = "1" * 20
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Commonworld fixture")
    _git(root, "config", "user.email", "fixture@commonworld.invalid")
    release_root = root / "releases" / base_release
    release_root.mkdir(parents=True)
    for index in range(12):
        (release_root / f"payload-{index:02d}.txt").write_text(
            f"shared immutable payload {index}\n", encoding="utf-8"
        )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base release")
    return base_release


def _unmerged_paths(root: Path) -> list[str]:
    result = _git(root, "diff", "--name-only", "--diff-filter=U", check=False)
    return [line for line in result.stdout.splitlines() if line]


def reproduce_legacy_conflict() -> tuple[bool, int]:
    """Reproduce the old delete-and-replace lifecycle as competing Git renames."""
    with tempfile.TemporaryDirectory(prefix="commonworld-release-legacy-") as directory:
        root = Path(directory)
        base_release = _seed_repo(root)
        feature_release = "2" * 20
        main_release = "3" * 20

        _git(root, "switch", "-c", "feature")
        (root / "releases" / base_release).rename(root / "releases" / feature_release)
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "feature replaces release")

        _git(root, "switch", "main")
        (root / "releases" / base_release).rename(root / "releases" / main_release)
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "main replaces release")

        merge = _git(root, "merge", "--no-edit", "feature", check=False)
        unmerged = _unmerged_paths(root)
        return merge.returncode != 0 and bool(unmerged), len(unmerged)


def reproduce_append_only_merge() -> tuple[bool, int]:
    """Prove that retaining the common ancestor turns releases into disjoint additions."""
    with tempfile.TemporaryDirectory(prefix="commonworld-release-append-") as directory:
        root = Path(directory)
        base_release = _seed_repo(root)
        feature_release = "2" * 20
        main_release = "3" * 20

        _git(root, "switch", "-c", "feature")
        shutil.copytree(root / "releases" / base_release, root / "releases" / feature_release)
        _git(root, "add", ".")
        _git(root, "commit", "-m", "feature appends release")

        _git(root, "switch", "main")
        shutil.copytree(root / "releases" / base_release, root / "releases" / main_release)
        _git(root, "add", ".")
        _git(root, "commit", "-m", "main appends release")

        merge = _git(root, "merge", "--no-edit", "feature", check=False)
        unmerged = _unmerged_paths(root)
        retained = all(
            (root / "releases" / release).is_dir()
            for release in (base_release, feature_release, main_release)
        )
        return merge.returncode == 0 and not unmerged and retained, len(unmerged)


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    contract_path = root / CONTRACT_PATH.relative_to(ROOT)
    evidence_path = root / EVIDENCE_PATH.relative_to(ROOT)
    manifest_path = root / CURRENT_MANIFEST_PATH.relative_to(ROOT)
    build_script_path = root / BUILD_SCRIPT_PATH.relative_to(ROOT)
    cache_validator_path = root / CACHE_VALIDATOR_PATH.relative_to(ROOT)
    required_paths = (
        contract_path,
        evidence_path,
        manifest_path,
        build_script_path,
        cache_validator_path,
        *(root / relative for relative in PROPOSED_HEAD_INPUTS),
        *(root / relative for relative in DELIVERY_EVIDENCE),
    )
    for path in required_paths:
        if not path.is_file():
            errors.append(f"missing release lifecycle artifact: {path.relative_to(root)}")
    if errors:
        return errors

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if contract.get("kind") != "commonworld.release_snapshot_lifecycle" or contract.get("schema_version") != 1:
        errors.append("release lifecycle contract identity mismatch")
    history = contract.get("history", {})
    if history.get("mode") != "append-only-content-addressed" or history.get("automatic_pruning") is not False:
        errors.append("release history must remain append-only without build-time pruning")
    if history.get("existing_release_policy") != "verify-byte-identical-or-fail":
        errors.append("existing content-addressed releases are not fail-closed")
    conflict_model = contract.get("conflict_model", {})
    if conflict_model.get("observed_pull_request") != 186:
        errors.append("release conflict model is not bound to the observed PR 186 incident")
    generated_paths = contract.get("generated_paths", {})
    if generated_paths.get("immutable_release_snapshots", {}).get("pattern") != "releases/<release_id>/**":
        errors.append("release lifecycle contract does not identify the immutable generated release tree")
    if generated_paths.get("current_release_selector", {}).get("path") != "assets/commonworld-page-builds.json":
        errors.append("release lifecycle contract does not identify the mutable current-release selector")
    semantic_conflicts = contract.get("semantic_source_conflicts", {})
    if semantic_conflicts.get("automatic_resolution") is not False:
        errors.append("semantic source conflicts must not be auto-resolved by the release lifecycle")

    if evidence.get("kind") != "commonworld.release_snapshot_lifecycle_evidence" or evidence.get("schema_version") != 1:
        errors.append("release lifecycle evidence identity mismatch")
    if evidence.get("status") != "fresh":
        errors.append("release lifecycle delivery evidence is explicitly invalidated")
    if evidence.get("freshness_model") != "digest-defined-proposed-head-scope":
        errors.append("release lifecycle evidence lacks the digest-defined proposed-head freshness model")
    current_release = manifest.get("release_id")
    if evidence.get("current_release_id") != current_release:
        errors.append("release lifecycle evidence is stale for the current public release")

    current_inputs = {
        relative: file_sha256(root / relative)
        for relative in PROPOSED_HEAD_INPUTS
    }
    bound_inputs = evidence.get("proposed_head_inputs", {})
    if bound_inputs != current_inputs:
        stale = sorted(
            relative
            for relative in set(current_inputs) | set(bound_inputs)
            if current_inputs.get(relative) != bound_inputs.get(relative)
        )
        errors.append(f"release lifecycle proposed-head input digests are stale: {stale[:5]}")
    current_scope = scope_sha256(current_inputs)
    if evidence.get("proposed_head_scope_sha256") != current_scope:
        errors.append("release lifecycle proposed-head scope digest is stale")

    bound_delivery = evidence.get("delivery_evidence", {})
    for relative in DELIVERY_EVIDENCE:
        target = root / relative
        if bound_delivery.get(relative) != file_sha256(target):
            errors.append(f"release lifecycle delivery evidence hash is stale: {relative}")

    build_source = build_script_path.read_text(encoding="utf-8")
    if "shutil.rmtree(releases_root)" in build_source:
        errors.append("release builder still deletes the common-ancestor release history")
    for token in (
        "assert_current_snapshot_immutable",
        "tempfile.mkdtemp",
        "staging_root.rename(target_root)",
        "releases_root.mkdir(parents=True, exist_ok=True)",
    ):
        if token not in build_source:
            errors.append(f"release builder lacks conflict-resistant lifecycle token: {token}")

    cache_source = cache_validator_path.read_text(encoding="utf-8")
    for token in (
        "historical release manifest identity mismatch",
        "public release history does not contain the current snapshot",
        "public release history contains invalid snapshot identities",
    ):
        if token not in cache_source:
            errors.append(f"cache validator lacks retained-release guard: {token}")

    try:
        legacy_conflicts, legacy_unmerged = reproduce_legacy_conflict()
        append_clean, append_unmerged = reproduce_append_only_merge()
    except RuntimeError as error:
        errors.append(f"release conflict fixture failed to execute: {error}")
    else:
        if not legacy_conflicts or legacy_unmerged == 0:
            errors.append("legacy two-branch fixture no longer reproduces generated release conflicts")
        if not append_clean or append_unmerged != 0:
            errors.append("append-only two-branch fixture does not merge cleanly")
        conflict_evidence = evidence.get("conflict_reproduction", {})
        if conflict_evidence.get("legacy") != {
            "conflict": legacy_conflicts,
            "unmerged_path_count": legacy_unmerged,
        }:
            errors.append("release lifecycle evidence is stale for the legacy conflict reproduction")
        if conflict_evidence.get("append_only") != {
            "clean_merge": append_clean,
            "unmerged_path_count": append_unmerged,
        }:
            errors.append("release lifecycle evidence is stale for the append-only merge reproduction")
    return errors


def main() -> int:
    errors = validate(ROOT)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    legacy_conflicts, legacy_unmerged = reproduce_legacy_conflict()
    append_clean, append_unmerged = reproduce_append_only_merge()
    print(
        "release snapshot lifecycle valid: "
        f"legacy_conflict={legacy_conflicts} ({legacy_unmerged} unmerged), "
        f"append_only_clean={append_clean} ({append_unmerged} unmerged)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
