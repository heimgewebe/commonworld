#!/usr/bin/env python3
"""Publish a durable commit status for the Commonworld production readback."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

STATUS_CONTEXT = "commonworld/production-readback"
STATUS_API_VERSION = "2022-11-28"
MAX_DESCRIPTION_LENGTH = 140
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
RELEASE_ID_PATTERN = re.compile(r"^[0-9a-f]{20}$")
SUCCESS = "success"
FAILURE = "failure"
PENDING = "pending"


@dataclass(frozen=True)
class StatusDecision:
    state: str
    description: str
    context: str = STATUS_CONTEXT


@dataclass(frozen=True)
class PublishedStatus:
    state: str
    description: str
    context: str
    target_url: str
    api_status: int


def bounded_description(value: str) -> str:
    compact = " ".join(value.split())
    if len(compact) <= MAX_DESCRIPTION_LENGTH:
        return compact
    return compact[: MAX_DESCRIPTION_LENGTH - 1].rstrip() + "…"


def pending_decision() -> StatusDecision:
    return StatusDecision(
        state=PENDING,
        description="production readback in progress",
    )


def load_json_object(path: Path | None) -> dict[str, object] | None:
    if path is None or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _outcome(value: str | None) -> str:
    return (value or "").strip().casefold()


def _failure(description: str) -> StatusDecision:
    return StatusDecision(FAILURE, bounded_description(description))


def _success(description: str) -> StatusDecision:
    return StatusDecision(SUCCESS, bounded_description(description))


def _validate_snapshot_receipt(
    receipt: dict[str, object] | None,
    *,
    expected_sha: str,
) -> tuple[str, int] | None:
    if receipt is None:
        return None
    release_id = receipt.get("release_id")
    repository_sha = receipt.get("repository_sha")
    verdict = receipt.get("verdict")
    total_files = receipt.get("total_files")
    total_requests = receipt.get("total_requests")
    errors = receipt.get("errors")
    files = receipt.get("files")
    if (
        verdict != "pass"
        or repository_sha != expected_sha
        or not isinstance(release_id, str)
        or RELEASE_ID_PATTERN.fullmatch(release_id) is None
        or not isinstance(total_files, int)
        or isinstance(total_files, bool)
        or total_files <= 0
        or not isinstance(total_requests, int)
        or isinstance(total_requests, bool)
        or total_requests < total_files
        or errors != []
        or not isinstance(files, list)
        or len(files) != total_files
        or any(
            not isinstance(item, dict) or item.get("matched") is not True
            for item in files
        )
    ):
        return None
    return release_id, total_files


def final_decision(
    *,
    expected_sha: str,
    pages_outcome: str,
    pages_verdict: str,
    snapshot_outcome: str,
    snapshot_superseded: str,
    security_outcome: str,
    pages_artifact_outcome: str,
    snapshot_artifact_outcome: str,
    security_artifact_outcome: str,
    snapshot_receipt: dict[str, object] | None,
) -> StatusDecision:
    pages_outcome = _outcome(pages_outcome)
    pages_verdict = _outcome(pages_verdict)
    snapshot_outcome = _outcome(snapshot_outcome)
    snapshot_superseded = _outcome(snapshot_superseded)
    security_outcome = _outcome(security_outcome)
    pages_artifact_outcome = _outcome(pages_artifact_outcome)
    snapshot_artifact_outcome = _outcome(snapshot_artifact_outcome)
    security_artifact_outcome = _outcome(security_artifact_outcome)

    if pages_outcome != SUCCESS:
        return _failure("exact Pages production readback step failed")
    if security_outcome != SUCCESS:
        return _failure("private vulnerability reporting readback failed")
    if pages_artifact_outcome != SUCCESS:
        return _failure("Pages production receipt upload failed")
    if security_artifact_outcome != SUCCESS:
        return _failure("private reporting receipt upload failed")

    if pages_verdict == "superseded":
        if snapshot_outcome not in {"", "skipped"}:
            return _failure("superseded Pages verdict unexpectedly ran snapshot scan")
        return _success("superseded: newer main commit is the production target")

    if pages_verdict != "pass":
        return _failure(
            f"exact Pages production readback verdict: {pages_verdict or 'missing'}"
        )

    if snapshot_outcome == SUCCESS:
        if snapshot_artifact_outcome != SUCCESS:
            return _failure("complete release snapshot receipt upload failed")
        validated = _validate_snapshot_receipt(
            snapshot_receipt,
            expected_sha=expected_sha,
        )
        if validated is None:
            return _failure("complete release snapshot receipt is invalid")
        release_id, total_files = validated
        return _success(
            f"release {release_id}: {total_files}/{total_files} snapshot files verified"
        )

    if snapshot_superseded == "true":
        if snapshot_artifact_outcome != SUCCESS:
            return _failure("superseded snapshot receipt upload failed")
        return _success("superseded during snapshot scan: newer main is production target")

    return _failure("complete release snapshot production readback failed")


def validate_identity(repository: str, sha: str, run_url: str) -> None:
    if REPOSITORY_PATTERN.fullmatch(repository) is None:
        raise ValueError("repository must be in owner/name form")
    if SHA_PATTERN.fullmatch(sha) is None:
        raise ValueError("sha must be a lowercase 40-character hexadecimal commit id")
    expected_prefix = f"https://github.com/{repository}/actions/runs/"
    if not run_url.startswith(expected_prefix):
        raise ValueError("run URL must identify this repository's GitHub Actions run")


def publish_status(
    *,
    repository: str,
    sha: str,
    run_url: str,
    token: str,
    decision: StatusDecision,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> PublishedStatus:
    validate_identity(repository, sha, run_url)
    if not token:
        raise ValueError("GITHUB_TOKEN is required")
    if decision.state not in {PENDING, SUCCESS, FAILURE}:
        raise ValueError(f"unsupported commit status state: {decision.state}")

    description = bounded_description(decision.description)
    payload = json.dumps(
        {
            "context": decision.context,
            "description": description,
            "state": decision.state,
            "target_url": run_url,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/statuses/{sha}",
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "commonworld-production-readback-status/1.0",
            "X-GitHub-Api-Version": STATUS_API_VERSION,
        },
    )
    try:
        with opener(request, timeout=20) as response:
            api_status = int(response.status)
            response.read()
    except urllib.error.HTTPError as error:
        try:
            detail = error.read().decode("utf-8", errors="replace")
        finally:
            error.close()
        raise RuntimeError(
            f"GitHub commit status publication failed with HTTP {error.code}: {detail[:300]}"
        ) from error
    except (urllib.error.URLError, OSError) as error:
        raise RuntimeError(
            f"GitHub commit status publication failed: {type(error).__name__}: {error}"
        ) from error
    if api_status != 201:
        raise RuntimeError(
            f"GitHub commit status publication returned unexpected HTTP {api_status}"
        )
    return PublishedStatus(
        state=decision.state,
        description=description,
        context=decision.context,
        target_url=run_url,
        api_status=api_status,
    )


def run_self_test() -> None:
    sha = "a" * 40
    repository = "heimgewebe/commonworld"
    run_url = "https://github.com/heimgewebe/commonworld/actions/runs/123"
    receipt = {
        "errors": [],
        "files": [
            {"matched": True, "relative_path": "index.html"},
            {"matched": True, "relative_path": "assets/app.js"},
        ],
        "release_id": "b" * 20,
        "repository_sha": sha,
        "total_files": 2,
        "total_requests": 3,
        "verdict": "pass",
    }
    success = final_decision(
        expected_sha=sha,
        pages_outcome="success",
        pages_verdict="pass",
        snapshot_outcome="success",
        snapshot_superseded="",
        security_outcome="success",
        pages_artifact_outcome="success",
        snapshot_artifact_outcome="success",
        security_artifact_outcome="success",
        snapshot_receipt=receipt,
    )
    assert success.state == SUCCESS
    assert "2/2 snapshot files verified" in success.description

    drifted = dict(receipt, repository_sha="c" * 40)
    assert final_decision(
        expected_sha=sha,
        pages_outcome="success",
        pages_verdict="pass",
        snapshot_outcome="success",
        snapshot_superseded="",
        security_outcome="success",
        pages_artifact_outcome="success",
        snapshot_artifact_outcome="success",
        security_artifact_outcome="success",
        snapshot_receipt=drifted,
    ).state == FAILURE

    superseded = final_decision(
        expected_sha=sha,
        pages_outcome="success",
        pages_verdict="pass",
        snapshot_outcome="failure",
        snapshot_superseded="true",
        security_outcome="success",
        pages_artifact_outcome="success",
        snapshot_artifact_outcome="success",
        security_artifact_outcome="success",
        snapshot_receipt=None,
    )
    assert superseded.state == SUCCESS
    assert superseded.description.startswith("superseded during snapshot scan")

    assert final_decision(
        expected_sha=sha,
        pages_outcome="success",
        pages_verdict="pass",
        snapshot_outcome="success",
        snapshot_superseded="",
        security_outcome="failure",
        pages_artifact_outcome="success",
        snapshot_artifact_outcome="success",
        security_artifact_outcome="success",
        snapshot_receipt=receipt,
    ).state == FAILURE
    assert pending_decision().state == PENDING
    assert len(bounded_description("x" * 500)) == MAX_DESCRIPTION_LENGTH

    recorded: dict[str, object] = {}

    class FakeResponse:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self) -> bytes:
            return b"{}"

    def fake_opener(request, timeout: int):
        recorded["url"] = request.full_url
        recorded["headers"] = dict(request.header_items())
        recorded["payload"] = json.loads(request.data.decode("utf-8"))
        recorded["timeout"] = timeout
        return FakeResponse()

    published = publish_status(
        repository=repository,
        sha=sha,
        run_url=run_url,
        token="test-token",
        decision=success,
        opener=fake_opener,
    )
    assert published.api_status == 201
    assert recorded["url"] == (
        f"https://api.github.com/repos/{repository}/statuses/{sha}"
    )
    assert recorded["payload"] == {
        "context": STATUS_CONTEXT,
        "description": success.description,
        "state": SUCCESS,
        "target_url": run_url,
    }
    assert recorded["timeout"] == 20
    assert "test-token" not in json.dumps(asdict(published))

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "receipt.json"
        path.write_text(json.dumps(receipt), encoding="utf-8")
        assert load_json_object(path) == receipt

    print("commonworld production readback commit status self-test ok")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish a durable commit status for a Commonworld production readback run."
    )
    parser.add_argument("--mode", choices=("pending", "final"))
    parser.add_argument("--repository")
    parser.add_argument("--sha")
    parser.add_argument("--run-url")
    parser.add_argument("--snapshot-receipt", type=Path)
    parser.add_argument("--pages-outcome", default="")
    parser.add_argument("--pages-verdict", default="")
    parser.add_argument("--snapshot-outcome", default="")
    parser.add_argument("--snapshot-superseded", default="")
    parser.add_argument("--security-outcome", default="")
    parser.add_argument("--pages-artifact-outcome", default="")
    parser.add_argument("--snapshot-artifact-outcome", default="")
    parser.add_argument("--security-artifact-outcome", default="")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0
    if not args.mode or not args.repository or not args.sha or not args.run_url:
        parser.error("--mode, --repository, --sha, and --run-url are required")

    if args.mode == "pending":
        decision = pending_decision()
    else:
        decision = final_decision(
            expected_sha=args.sha,
            pages_outcome=args.pages_outcome,
            pages_verdict=args.pages_verdict,
            snapshot_outcome=args.snapshot_outcome,
            snapshot_superseded=args.snapshot_superseded,
            security_outcome=args.security_outcome,
            pages_artifact_outcome=args.pages_artifact_outcome,
            snapshot_artifact_outcome=args.snapshot_artifact_outcome,
            security_artifact_outcome=args.security_artifact_outcome,
            snapshot_receipt=load_json_object(args.snapshot_receipt),
        )

    published = publish_status(
        repository=args.repository,
        sha=args.sha,
        run_url=args.run_url,
        token=os.environ.get("GITHUB_TOKEN", ""),
        decision=decision,
    )
    print(json.dumps(asdict(published), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
