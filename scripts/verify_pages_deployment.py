#!/usr/bin/env python3
"""Bind one GitHub Pages deployment to its public Commonworld live receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.smoke_pages_live import PagesLiveSmokeReceipt, fetch_live_url, run_live_smoke

API_ROOT = "https://api.github.com"
DEFAULT_ENVIRONMENT = "github-pages"
DEFAULT_DEPLOYMENT_TIMEOUT_SECONDS = 600
DEFAULT_DEPLOYMENT_POLL_SECONDS = 10
DEFAULT_LIVE_TIMEOUT_SECONDS = 5
DEFAULT_LIVE_RETRY_DELAYS_SECONDS = (0, 30, 90)
EXACT_PUBLIC_FILES = (("", "index.html"), ("propose.html", "propose.html"), ("catalog/catalog.json", "catalog/catalog.json"))
PENDING_DEPLOYMENT_STATES = {"waiting", "queued", "pending", "in_progress"}
FAILED_DEPLOYMENT_STATES = {"error", "failure", "inactive"}


@dataclass(frozen=True)
class DeploymentObservation:
    attempt: int
    deployment_id: int | None
    deployment_sha: str | None
    state: str
    observed_at: str


@dataclass(frozen=True)
class DeploymentWaitResult:
    verdict: str
    deployment: dict[str, object] | None
    state: str | None
    attempts: int
    observations: tuple[DeploymentObservation, ...]
    error: str | None


@dataclass(frozen=True)
class ExactPublicFileReceipt:
    relative_url: str
    requested_url: str
    final_url: str
    status: int
    content_type: str
    body_bytes: int
    sha256: str
    expected_sha256: str
    matched: bool


@dataclass(frozen=True)
class ExactPublicFilesResult:
    verdict: str
    receipts: tuple[ExactPublicFileReceipt, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class LiveWaitResult:
    verdict: str
    attempts: int
    errors: tuple[str, ...]
    receipt: PagesLiveSmokeReceipt | None
    exact_public_files: tuple[ExactPublicFileReceipt, ...]


@dataclass(frozen=True)
class ProductionReadbackReceipt:
    schema_version: int
    kind: str
    receipt_id: str
    repository: str
    expected_sha: str
    source_ref: str
    repository_head_sha: str | None
    superseded_at: str | None
    environment: str
    requested_url: str
    started_at: str
    completed_at: str
    verdict: str
    deployment_timeout_seconds: int
    deployment_poll_seconds: int
    deployment_attempts: int
    deployment: dict[str, object] | None
    deployment_state: str | None
    deployment_observations: tuple[DeploymentObservation, ...]
    live_retry_delays_seconds: tuple[int, ...]
    live_attempts: int
    live_errors: tuple[str, ...]
    live_receipt: PagesLiveSmokeReceipt | None
    exact_public_files: tuple[ExactPublicFileReceipt, ...]
    errors: tuple[str, ...]
    does_not_establish: tuple[str, ...]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def github_api_get(repository: str, endpoint: str, token: str, timeout_seconds: int = 20) -> object:
    url = f"{API_ROOT}/repos/{repository}/{endpoint.lstrip('/')}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "commonworld-pages-production-readback/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"GitHub API request failed for {endpoint}: {error}") from error


def select_exact_deployment(
    deployments: object,
    expected_sha: str,
    environment: str = DEFAULT_ENVIRONMENT,
) -> dict[str, object] | None:
    if not isinstance(deployments, list):
        raise RuntimeError("GitHub deployments response must be a list")
    matches = [
        item
        for item in deployments
        if isinstance(item, dict)
        and item.get("sha") == expected_sha
        and item.get("environment") == environment
        and isinstance(item.get("id"), int)
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (str(item.get("created_at", "")), int(item["id"])), reverse=True)
    selected = matches[0]
    return {
        "id": int(selected["id"]),
        "sha": str(selected["sha"]),
        "environment": str(selected["environment"]),
        "ref": str(selected.get("ref", "")),
        "created_at": str(selected.get("created_at", "")),
        "updated_at": str(selected.get("updated_at", "")),
    }


def current_repository_head(api_get: Callable[[str], object], source_ref: str) -> str:
    response = api_get(f"commits/{urllib.parse.quote(source_ref, safe='')}")
    if not isinstance(response, dict) or not isinstance(response.get("sha"), str):
        raise RuntimeError("GitHub commit response must contain a SHA")
    sha = str(response["sha"]).lower()
    if len(sha) != 40 or any(character not in "0123456789abcdef" for character in sha):
        raise RuntimeError("GitHub commit response contains an invalid SHA")
    return sha


def latest_deployment_state(statuses: object) -> str:
    if not isinstance(statuses, list):
        raise RuntimeError("GitHub deployment statuses response must be a list")
    valid = [
        status
        for status in statuses
        if isinstance(status, dict) and isinstance(status.get("state"), str)
    ]
    if not valid:
        return "missing_status"
    valid.sort(
        key=lambda status: (
            str(status.get("created_at", "")),
            int(status.get("id", 0)) if isinstance(status.get("id", 0), int) else 0,
        ),
        reverse=True,
    )
    return str(valid[0]["state"])


def wait_for_exact_deployment(
    *,
    expected_sha: str,
    environment: str,
    timeout_seconds: int,
    poll_seconds: int,
    api_get: Callable[[str], object],
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], str] = utc_now,
) -> DeploymentWaitResult:
    if timeout_seconds < 0 or poll_seconds <= 0:
        raise ValueError("deployment timeout must be non-negative and poll interval must be positive")
    deadline = monotonic() + timeout_seconds
    attempts = 0
    observations: list[DeploymentObservation] = []
    last_deployment: dict[str, object] | None = None
    last_state: str | None = None

    while True:
        attempts += 1
        query = urllib.parse.urlencode(
            {"sha": expected_sha, "environment": environment, "per_page": 100}
        )
        deployments = api_get(f"deployments?{query}")
        deployment = select_exact_deployment(deployments, expected_sha, environment)
        if deployment is None:
            state = "deployment_missing"
            deployment_id = None
            deployment_sha = None
        else:
            last_deployment = deployment
            deployment_id = int(deployment["id"])
            deployment_sha = str(deployment.get("sha"))
            statuses = api_get(f"deployments/{deployment_id}/statuses?per_page=100")
            state = latest_deployment_state(statuses)
            last_state = state
        observations.append(
            DeploymentObservation(
                attempt=attempts,
                deployment_id=deployment_id,
                deployment_sha=deployment_sha,
                state=state,
                observed_at=now(),
            )
        )
        if state == "success":
            return DeploymentWaitResult(
                verdict="pass",
                deployment=last_deployment,
                state=state,
                attempts=attempts,
                observations=tuple(observations),
                error=None,
            )
        if state in FAILED_DEPLOYMENT_STATES:
            return DeploymentWaitResult(
                verdict="fail",
                deployment=last_deployment,
                state=state,
                attempts=attempts,
                observations=tuple(observations),
                error=f"exact Pages deployment entered terminal state {state}",
            )
        if state not in PENDING_DEPLOYMENT_STATES | {"deployment_missing", "missing_status"}:
            return DeploymentWaitResult(
                verdict="fail",
                deployment=last_deployment,
                state=state,
                attempts=attempts,
                observations=tuple(observations),
                error=f"exact Pages deployment returned unknown state {state}",
            )
        remaining = deadline - monotonic()
        if remaining <= 0:
            return DeploymentWaitResult(
                verdict="fail",
                deployment=last_deployment,
                state=last_state or state,
                attempts=attempts,
                observations=tuple(observations),
                error=f"exact Pages deployment did not succeed within {timeout_seconds} seconds",
            )
        sleeper(min(float(poll_seconds), remaining))


def verify_exact_public_files(
    base_url: str,
    timeout_seconds: int,
    fetcher: Callable[..., object] = fetch_live_url,
    root: Path = Path(__file__).resolve().parents[1],
) -> ExactPublicFilesResult:
    receipts: list[ExactPublicFileReceipt] = []
    errors: list[str] = []
    for relative_url, local_relative in EXACT_PUBLIC_FILES:
        requested_url = urllib.parse.urljoin(base_url, relative_url)
        try:
            fetch = fetcher(
                requested_url,
                timeout_seconds=timeout_seconds,
                insecure=False,
                accept="*/*",
            )
            remote_bytes = fetch.body.encode("utf-8")
            expected_bytes = (root / local_relative).read_bytes()
        except (OSError, RuntimeError) as error:
            errors.append(f"exact public file fetch failed for {relative_url or 'index.html'}: {error}")
            continue
        remote_sha256 = hashlib.sha256(remote_bytes).hexdigest()
        expected_sha256 = hashlib.sha256(expected_bytes).hexdigest()
        matched = fetch.status == 200 and remote_sha256 == expected_sha256
        receipts.append(
            ExactPublicFileReceipt(
                relative_url=relative_url or "index.html",
                requested_url=requested_url,
                final_url=fetch.final_url,
                status=fetch.status,
                content_type=fetch.content_type,
                body_bytes=len(remote_bytes),
                sha256=remote_sha256,
                expected_sha256=expected_sha256,
                matched=matched,
            )
        )
        if fetch.status != 200:
            errors.append(f"exact public file status must be 200 for {relative_url or 'index.html'}, got {fetch.status}")
        if remote_sha256 != expected_sha256:
            errors.append(f"exact public file hash mismatch: {relative_url or 'index.html'}")
    return ExactPublicFilesResult(
        verdict="pass" if not errors and len(receipts) == len(EXACT_PUBLIC_FILES) else "fail",
        receipts=tuple(receipts),
        errors=tuple(errors),
    )


def run_live_smoke_with_retry(
    *,
    url: str,
    timeout_seconds: int,
    retry_delays_seconds: Sequence[int],
    live_smoke: Callable[..., PagesLiveSmokeReceipt] = run_live_smoke,
    exact_file_check: Callable[[str, int], ExactPublicFilesResult] = verify_exact_public_files,
    sleeper: Callable[[float], None] = time.sleep,
) -> LiveWaitResult:
    delays = tuple(int(delay) for delay in retry_delays_seconds)
    if not delays or delays[0] != 0 or any(delay < 0 for delay in delays):
        raise ValueError("live retry delays must be non-negative and start with zero")
    errors: list[str] = []
    last_receipt: PagesLiveSmokeReceipt | None = None
    last_exact_public_files: tuple[ExactPublicFileReceipt, ...] = ()
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            sleeper(float(delay))
        try:
            receipt = live_smoke(url, timeout_seconds=timeout_seconds, insecure=False)
            last_receipt = receipt
            exact_result = exact_file_check(receipt.final_url, timeout_seconds)
            last_exact_public_files = exact_result.receipts
        except (OSError, RuntimeError) as error:
            errors.append(f"cycle {attempt}: {error}")
            continue
        if exact_result.verdict == "pass":
            return LiveWaitResult(
                verdict="pass",
                attempts=attempt,
                errors=tuple(errors),
                receipt=receipt,
                exact_public_files=exact_result.receipts,
            )
        errors.extend(f"cycle {attempt}: {error}" for error in exact_result.errors)
    return LiveWaitResult(
        verdict="fail",
        attempts=len(delays),
        errors=tuple(errors),
        receipt=last_receipt,
        exact_public_files=last_exact_public_files,
    )


def run_production_readback(
    *,
    repository: str,
    expected_sha: str,
    token: str,
    url: str,
    environment: str = DEFAULT_ENVIRONMENT,
    source_ref: str = "main",
    deployment_timeout_seconds: int = DEFAULT_DEPLOYMENT_TIMEOUT_SECONDS,
    deployment_poll_seconds: int = DEFAULT_DEPLOYMENT_POLL_SECONDS,
    live_timeout_seconds: int = DEFAULT_LIVE_TIMEOUT_SECONDS,
    live_retry_delays_seconds: Sequence[int] = DEFAULT_LIVE_RETRY_DELAYS_SECONDS,
    api_get: Callable[[str], object] | None = None,
    live_smoke: Callable[..., PagesLiveSmokeReceipt] = run_live_smoke,
    exact_file_check: Callable[[str, int], ExactPublicFilesResult] = verify_exact_public_files,
    head_sha: Callable[[], str] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], str] = utc_now,
) -> ProductionReadbackReceipt:
    started_at = now()
    errors: list[str] = []
    if not repository or "/" not in repository:
        errors.append("repository must be in owner/name form")
    if len(expected_sha) != 40 or any(character not in "0123456789abcdef" for character in expected_sha.lower()):
        errors.append("expected SHA must be a full 40-character hexadecimal commit id")
    if not token:
        errors.append("GitHub token is required")
    if not source_ref:
        errors.append("source ref is required")

    repository_head_sha: str | None = None
    superseded_at: str | None = None
    deployment_result = DeploymentWaitResult("fail", None, None, 0, (), None)
    live_result = LiveWaitResult("fail", 0, (), None, ())
    if not errors:
        request = api_get or (lambda endpoint: github_api_get(repository, endpoint, token))
        read_head = head_sha or (lambda: current_repository_head(request, source_ref))
        try:
            repository_head_sha = read_head()
        except RuntimeError as error:
            errors.append(str(error))
        if not errors and repository_head_sha != expected_sha:
            superseded_at = "before_deployment"
        if not errors and superseded_at is None:
            try:
                deployment_result = wait_for_exact_deployment(
                    expected_sha=expected_sha,
                    environment=environment,
                    timeout_seconds=deployment_timeout_seconds,
                    poll_seconds=deployment_poll_seconds,
                    api_get=request,
                    sleeper=sleeper,
                    monotonic=monotonic,
                    now=now,
                )
            except (RuntimeError, ValueError) as error:
                deployment_result = DeploymentWaitResult(
                    verdict="fail",
                    deployment=None,
                    state=None,
                    attempts=0,
                    observations=(),
                    error=str(error),
                )
            if deployment_result.error:
                try:
                    repository_head_sha = read_head()
                except RuntimeError as error:
                    errors.extend((deployment_result.error, str(error)))
                if not errors and repository_head_sha != expected_sha:
                    superseded_at = "during_deployment_wait"
                elif not errors:
                    errors.append(deployment_result.error)
        if not errors and deployment_result.verdict == "pass":
            try:
                repository_head_sha = read_head()
            except RuntimeError as error:
                errors.append(str(error))
            if not errors and repository_head_sha != expected_sha:
                superseded_at = "after_deployment"
        if not errors and deployment_result.verdict == "pass" and superseded_at is None:
            try:
                live_result = run_live_smoke_with_retry(
                    url=url,
                    timeout_seconds=live_timeout_seconds,
                    retry_delays_seconds=live_retry_delays_seconds,
                    live_smoke=live_smoke,
                    exact_file_check=exact_file_check,
                    sleeper=sleeper,
                )
            except ValueError as error:
                live_result = LiveWaitResult("fail", 0, (str(error),), None, ())
            if live_result.verdict != "pass":
                try:
                    repository_head_sha = read_head()
                except RuntimeError as error:
                    errors.append(str(error))
                if not errors and repository_head_sha != expected_sha:
                    superseded_at = "during_live_verification"
                else:
                    errors.append("public Pages content did not match the exact checked-out commit")

    verdict = "superseded" if superseded_at is not None else ("pass" if not errors else "fail")
    return ProductionReadbackReceipt(
        schema_version=1,
        kind="commonworld_pages_production_readback",
        receipt_id="commonworld.pages-production-readback.v1",
        repository=repository,
        expected_sha=expected_sha,
        source_ref=source_ref,
        repository_head_sha=repository_head_sha,
        superseded_at=superseded_at,
        environment=environment,
        requested_url=url,
        started_at=started_at,
        completed_at=now(),
        verdict=verdict,
        deployment_timeout_seconds=deployment_timeout_seconds,
        deployment_poll_seconds=deployment_poll_seconds,
        deployment_attempts=deployment_result.attempts,
        deployment=deployment_result.deployment,
        deployment_state=deployment_result.state,
        deployment_observations=deployment_result.observations,
        live_retry_delays_seconds=tuple(int(delay) for delay in live_retry_delays_seconds),
        live_attempts=live_result.attempts,
        live_errors=live_result.errors,
        live_receipt=live_result.receipt,
        exact_public_files=live_result.exact_public_files,
        errors=tuple(errors),
        does_not_establish=(
            "GitHub Pages SLA",
            "automatic rollback authorization",
            "DNS mutation authorization",
            "redundant delivery or automatic failover",
            "absence of all transient CDN or client-network failures",
        ),
    )


def unexpected_failure_receipt(
    *,
    repository: str,
    expected_sha: str,
    environment: str,
    source_ref: str,
    url: str,
    deployment_timeout_seconds: int,
    deployment_poll_seconds: int,
    live_retry_delays_seconds: Sequence[int],
    error: Exception,
    now: Callable[[], str] = utc_now,
) -> ProductionReadbackReceipt:
    timestamp = now()
    return ProductionReadbackReceipt(
        schema_version=1,
        kind="commonworld_pages_production_readback",
        receipt_id="commonworld.pages-production-readback.v1",
        repository=repository,
        expected_sha=expected_sha,
        source_ref=source_ref,
        repository_head_sha=None,
        superseded_at=None,
        environment=environment,
        requested_url=url,
        started_at=timestamp,
        completed_at=timestamp,
        verdict="fail",
        deployment_timeout_seconds=deployment_timeout_seconds,
        deployment_poll_seconds=deployment_poll_seconds,
        deployment_attempts=0,
        deployment=None,
        deployment_state=None,
        deployment_observations=(),
        live_retry_delays_seconds=tuple(int(delay) for delay in live_retry_delays_seconds),
        live_attempts=0,
        live_errors=(),
        live_receipt=None,
        exact_public_files=(),
        errors=(f"unexpected production readback failure: {type(error).__name__}: {error}",),
        does_not_establish=(
            "GitHub Pages SLA",
            "automatic rollback authorization",
            "DNS mutation authorization",
            "redundant delivery or automatic failover",
            "absence of all transient CDN or client-network failures",
        ),
    )


def parse_retry_delays(value: str) -> tuple[int, ...]:
    try:
        delays = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError("retry delays must be comma-separated integers") from error
    if not delays or delays[0] != 0 or any(delay < 0 for delay in delays):
        raise argparse.ArgumentTypeError("retry delays must be non-negative and start with zero")
    return delays


def write_receipt(path: Path, receipt: ProductionReadbackReceipt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove that one exact commit is deployed and live on Commonworld Pages.")
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--url", default=os.environ.get("COMMONWORLD_PAGES_URL", "https://commonworld.net/"))
    parser.add_argument("--environment", default=DEFAULT_ENVIRONMENT)
    parser.add_argument("--source-ref", default="main")
    parser.add_argument("--receipt", type=Path, default=Path("artifacts/commonworld-pages-production-readback.json"))
    parser.add_argument("--deployment-timeout-seconds", type=int, default=DEFAULT_DEPLOYMENT_TIMEOUT_SECONDS)
    parser.add_argument("--deployment-poll-seconds", type=int, default=DEFAULT_DEPLOYMENT_POLL_SECONDS)
    parser.add_argument("--live-timeout-seconds", type=int, default=DEFAULT_LIVE_TIMEOUT_SECONDS)
    parser.add_argument(
        "--live-retry-delays-seconds",
        type=parse_retry_delays,
        default=DEFAULT_LIVE_RETRY_DELAYS_SECONDS,
    )
    args = parser.parse_args()
    try:
        receipt = run_production_readback(
            repository=args.repository,
            expected_sha=args.sha.lower(),
            token=os.environ.get("GITHUB_TOKEN", ""),
            url=args.url,
            environment=args.environment,
            source_ref=args.source_ref,
            deployment_timeout_seconds=args.deployment_timeout_seconds,
            deployment_poll_seconds=args.deployment_poll_seconds,
            live_timeout_seconds=args.live_timeout_seconds,
            live_retry_delays_seconds=args.live_retry_delays_seconds,
        )
    except Exception as error:
        print(f"ERROR: unexpected production readback failure: {error}", file=sys.stderr)
        receipt = unexpected_failure_receipt(
            repository=args.repository,
            expected_sha=args.sha.lower(),
            environment=args.environment,
            source_ref=args.source_ref,
            url=args.url,
            deployment_timeout_seconds=args.deployment_timeout_seconds,
            deployment_poll_seconds=args.deployment_poll_seconds,
            live_retry_delays_seconds=args.live_retry_delays_seconds,
            error=error,
        )
    write_receipt(args.receipt, receipt)
    print(json.dumps(asdict(receipt), indent=2, sort_keys=True))
    return 0 if receipt.verdict in {"pass", "superseded"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
