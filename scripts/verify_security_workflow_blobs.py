#!/usr/bin/env python3
"""Verify reviewed security workflow blobs before repository-controlled commands run."""

from __future__ import annotations

import argparse
import hashlib
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_WORKFLOW_SHA256 = {
    Path(".github/workflows/validate.yml"): "5303fd29f96a8f3bf6cd1afa0c9e3c823da840d766b4490d564fed29de30172e",
    Path(".github/workflows/production-readback.yml"): "c7bccab63a77e812a9df3b48232a99cf8b6b972fa6c671d6aac77332fb343417",
    Path(".github/workflows/security-policy-expiry.yml"): "7ed4582754086d0ffb871ac9503e3b5ab8980ff8a6cd8d7b321260abe8a90a05",
}


def _run_git(root: Path, arguments: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def validate_security_workflow_blobs(root: Path = ROOT, revision: str = "HEAD") -> list[str]:
    errors: list[str] = []
    for relative, expected_sha256 in EXPECTED_WORKFLOW_SHA256.items():
        path = root / relative
        try:
            metadata = path.lstat()
        except OSError as error:
            errors.append(f"security workflow worktree path is unavailable: {relative}: {error}")
            continue
        if not stat.S_ISREG(metadata.st_mode):
            errors.append(f"security workflow worktree path must be a regular file: {relative}")
            continue

        listing = _run_git(root, ["ls-tree", "-z", revision, "--", relative.as_posix()])
        if listing.returncode != 0:
            errors.append(
                f"security workflow tree lookup failed for {relative}: "
                f"{listing.stderr.decode('utf-8', errors='replace').strip()}"
            )
            continue
        entries = [entry for entry in listing.stdout.split(b"\0") if entry]
        if len(entries) != 1 or b"	" not in entries[0]:
            errors.append(f"security workflow must resolve to exactly one committed tree entry: {relative}")
            continue
        header, committed_path = entries[0].split(b"	", 1)
        parts = header.split()
        if len(parts) != 3:
            errors.append(f"security workflow tree entry is malformed: {relative}")
            continue
        mode, object_type, object_id = (part.decode("ascii", errors="replace") for part in parts)
        if committed_path.decode("utf-8", errors="replace") != relative.as_posix():
            errors.append(f"security workflow committed path mismatch: {relative}")
        if mode != "100644" or object_type != "blob":
            errors.append(
                f"security workflow must be a regular 100644 blob: {relative}; got {mode} {object_type}"
            )
            continue

        blob = _run_git(root, ["cat-file", "blob", object_id])
        if blob.returncode != 0:
            errors.append(
                f"security workflow blob read failed for {relative}: "
                f"{blob.stderr.decode('utf-8', errors='replace').strip()}"
            )
            continue
        committed_sha256 = hashlib.sha256(blob.stdout).hexdigest()
        if committed_sha256 != expected_sha256:
            errors.append(
                f"security workflow committed blob digest mismatch: {relative}; "
                f"expected {expected_sha256}, got {committed_sha256}"
            )
        try:
            worktree_bytes = path.read_bytes()
        except OSError as error:
            errors.append(f"security workflow worktree read failed: {relative}: {error}")
            continue
        if worktree_bytes != blob.stdout:
            errors.append(f"security workflow worktree bytes differ from committed blob: {relative}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="HEAD")
    arguments = parser.parse_args(argv)
    errors = validate_security_workflow_blobs(ROOT, arguments.revision)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("commonworld committed security workflow blob validation ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
