#!/usr/bin/env python3
"""Verify committed trust-bound repository blobs before controlled commands run."""

from __future__ import annotations

import argparse
import hashlib
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUSTED_BLOBS: dict[Path, tuple[str, str | None]] = {
    Path(".github/workflows/validate.yml"): ("100644", None),
    Path(".github/workflows/production-readback.yml"): ("100644", None),
    Path(".github/workflows/security-policy-expiry.yml"): ("100644", None),
    Path("scripts/validate_security_policy.py"): ("100755", "6979fe3a29e44af0b43df9144bb7c40879f8b25db92d35adbed6fc27dd25fc7d"),
    Path("scripts/verify_pages_deployment.py"): ("100755", "199c5152bc7c6efe49a0d248ed256458757997d77b56f55d74e1a25ae99b560c"),
    Path("scripts/smoke_pages_live.py"): ("100755", "bf898c91f48a3165d1eeb1265d05ac9aad4e8eccbd51abd5f6618529ba2cc675"),
    Path("requirements-dev.txt"): ("100644", "2825f02444581d78ec8fae62d6c0e1ac52a01c49ba92873fe00aa3f3800dc74e"),
    Path("package.json"): ("100644", "ab1ad07609bab8a68df56f256219c0d1422a40c1e01ef1c3164f55ba7ff2d7cb"),
    Path("package-lock.json"): ("100644", "2477b7328337e250d3cbb490b4f86fc4a23a66e4455c66f668deffe31d52261b"),
}


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def validate_trusted_blobs(root: Path = ROOT, revision: str = "HEAD", expected_sha: str = "") -> list[str]:
    errors: list[str] = []
    head = _git(root, "rev-parse", revision)
    if head.returncode != 0:
        return [f"trusted-blob revision lookup failed: {head.stderr.decode('utf-8', errors='replace').strip()}"]
    resolved_sha = head.stdout.decode("ascii", errors="replace").strip().lower()
    if expected_sha and resolved_sha != expected_sha.lower():
        errors.append(f"trusted-blob revision mismatch: expected {expected_sha.lower()}, got {resolved_sha}")

    for relative, (expected_mode, expected_digest) in TRUSTED_BLOBS.items():
        path = root / relative
        try:
            metadata = path.lstat()
        except OSError as error:
            errors.append(f"trusted worktree path is unavailable: {relative}: {error}")
            continue
        if not stat.S_ISREG(metadata.st_mode):
            errors.append(f"trusted worktree path must be a regular file: {relative}")
            continue

        listing = _git(root, "ls-tree", "-z", revision, "--", relative.as_posix())
        if listing.returncode != 0:
            errors.append(f"trusted tree lookup failed for {relative}: {listing.stderr.decode('utf-8', errors='replace').strip()}")
            continue
        entries = [entry for entry in listing.stdout.split(b"\0") if entry]
        if len(entries) != 1 or b"\t" not in entries[0]:
            errors.append(f"trusted path must resolve to exactly one committed tree entry: {relative}")
            continue
        header, committed_path = entries[0].split(b"\t", 1)
        parts = header.split()
        if len(parts) != 3:
            errors.append(f"trusted tree entry is malformed: {relative}")
            continue
        mode, object_type, object_id = (part.decode("ascii", errors="replace") for part in parts)
        if committed_path.decode("utf-8", errors="replace") != relative.as_posix():
            errors.append(f"trusted committed path mismatch: {relative}")
        if mode != expected_mode or object_type != "blob":
            errors.append(f"trusted path mode/type mismatch: {relative}; expected {expected_mode} blob, got {mode} {object_type}")
            continue

        blob = _git(root, "cat-file", "blob", object_id)
        if blob.returncode != 0:
            errors.append(f"trusted blob read failed for {relative}: {blob.stderr.decode('utf-8', errors='replace').strip()}")
            continue
        digest = hashlib.sha256(blob.stdout).hexdigest()
        if expected_digest is not None and digest != expected_digest:
            errors.append(f"trusted committed blob digest mismatch: {relative}; expected {expected_digest}, got {digest}")
        try:
            worktree = path.read_bytes()
        except OSError as error:
            errors.append(f"trusted worktree read failed: {relative}: {error}")
            continue
        if worktree != blob.stdout:
            errors.append(f"trusted worktree bytes differ from committed blob: {relative}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--expected-sha", default="")
    args = parser.parse_args(argv)
    errors = validate_trusted_blobs(ROOT, args.revision, args.expected_sha)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld trusted committed blob validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
