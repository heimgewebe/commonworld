import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from scripts.smoke_pages_live import LiveFetch
from scripts.verify_pages_deployment import (
    DEFAULT_ENVIRONMENT,
    ExactPublicFileReceipt,
    ExactPublicFilesResult,
    run_live_smoke_with_retry,
    run_production_readback,
    select_exact_deployment,
    verify_exact_public_files,
    wait_for_exact_deployment,
    write_receipt,
)

SHA = "a" * 40
OTHER_SHA = "b" * 40


@dataclass(frozen=True)
class FakeLiveReceipt:
    smoke_id: str = "fake-live-receipt"
    status: int = 200
    final_url: str = "https://commonworld.net/"


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds

    def now(self) -> str:
        return f"T+{int(self.value)}"


def exact_file_receipt(relative_url: str = "index.html") -> ExactPublicFileReceipt:
    return ExactPublicFileReceipt(
        relative_url=relative_url,
        requested_url=f"https://commonworld.net/{relative_url}",
        final_url=f"https://commonworld.net/{relative_url}",
        status=200,
        content_type="text/plain",
        body_bytes=4,
        sha256="a" * 64,
        expected_sha256="a" * 64,
        matched=True,
    )


def exact_pass(base_url: str, timeout_seconds: int) -> ExactPublicFilesResult:
    return ExactPublicFilesResult(
        verdict="pass",
        receipts=tuple(exact_file_receipt(name) for name in ("index.html", "propose.html", "catalog/catalog.json")),
        errors=(),
    )


def deployment(identifier: int, sha: str = SHA, environment: str = DEFAULT_ENVIRONMENT, created_at: str = "2026-07-18T00:00:00Z") -> dict:
    return {
        "id": identifier,
        "sha": sha,
        "environment": environment,
        "created_at": created_at,
        "ref": "main",
    }


class PagesDeploymentReadbackTests(unittest.TestCase):
    def test_select_exact_deployment_ignores_stale_sha_and_uses_newest_exact_match(self) -> None:
        selected = select_exact_deployment(
            [
                deployment(8, OTHER_SHA, created_at="2026-07-18T03:00:00Z"),
                deployment(9, SHA, created_at="2026-07-18T02:00:00Z"),
                deployment(7, SHA, created_at="2026-07-18T01:00:00Z"),
                deployment(10, SHA, environment="preview", created_at="2026-07-18T04:00:00Z"),
            ],
            SHA,
        )
        self.assertIsNotNone(selected)
        self.assertEqual(9, selected["id"])
        self.assertEqual(
            {"id", "sha", "environment", "ref", "created_at", "updated_at"},
            set(selected),
        )

    def test_select_exact_deployment_rejects_only_stale_deployments(self) -> None:
        self.assertIsNone(select_exact_deployment([deployment(1, OTHER_SHA)], SHA))

    def test_latest_deployment_state_is_selected_by_timestamp_not_response_order(self) -> None:
        from scripts.verify_pages_deployment import latest_deployment_state

        self.assertEqual(
            "success",
            latest_deployment_state(
                [
                    {"id": 1, "state": "in_progress", "created_at": "2026-07-18T00:00:00Z"},
                    {"id": 2, "state": "success", "created_at": "2026-07-18T00:00:01Z"},
                ]
            ),
        )

    def test_terminal_deployment_failure_stops_without_retry(self) -> None:
        calls: list[str] = []

        def api_get(endpoint: str):
            calls.append(endpoint)
            if endpoint.startswith("deployments?"):
                return [deployment(12)]
            return [{"state": "failure"}]

        result = wait_for_exact_deployment(
            expected_sha=SHA,
            environment=DEFAULT_ENVIRONMENT,
            timeout_seconds=600,
            poll_seconds=10,
            api_get=api_get,
        )
        self.assertEqual("fail", result.verdict)
        self.assertEqual("failure", result.state)
        self.assertEqual(1, result.attempts)
        self.assertEqual(2, len(calls))
        self.assertIn("terminal state failure", result.error)

    def test_missing_exact_deployment_times_out_with_bounded_attempts(self) -> None:
        clock = FakeClock()
        result = wait_for_exact_deployment(
            expected_sha=SHA,
            environment=DEFAULT_ENVIRONMENT,
            timeout_seconds=20,
            poll_seconds=10,
            api_get=lambda endpoint: [deployment(4, OTHER_SHA)],
            sleeper=clock.sleep,
            monotonic=clock.monotonic,
            now=clock.now,
        )
        self.assertEqual("fail", result.verdict)
        self.assertEqual(3, result.attempts)
        self.assertEqual([10.0, 10.0], clock.sleeps)
        self.assertTrue(all(item.state == "deployment_missing" for item in result.observations))
        self.assertIn("within 20 seconds", result.error)

    def test_pending_deployment_reaches_success(self) -> None:
        clock = FakeClock()
        status_calls = 0

        def api_get(endpoint: str):
            nonlocal status_calls
            if endpoint.startswith("deployments?"):
                return [deployment(15)]
            status_calls += 1
            return [{"state": "in_progress" if status_calls == 1 else "success"}]

        result = wait_for_exact_deployment(
            expected_sha=SHA,
            environment=DEFAULT_ENVIRONMENT,
            timeout_seconds=30,
            poll_seconds=10,
            api_get=api_get,
            sleeper=clock.sleep,
            monotonic=clock.monotonic,
            now=clock.now,
        )
        self.assertEqual("pass", result.verdict)
        self.assertEqual(2, result.attempts)
        self.assertEqual([10.0], clock.sleeps)
        self.assertEqual("success", result.state)

    def test_exact_public_files_match_checked_out_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "index.html": "shell",
                "propose.html": "proposal",
                "catalog/catalog.json": "catalog",
            }
            for relative, body in files.items():
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body, encoding="utf-8")

            def fetcher(url: str, **kwargs):
                relative = url.removeprefix("https://commonworld.net/") or "index.html"
                body = files[relative]
                return LiveFetch(url, url, 200, "text/plain", body)

            result = verify_exact_public_files(
                "https://commonworld.net/",
                5,
                fetcher=fetcher,
                root=root,
            )

        self.assertEqual("pass", result.verdict)
        self.assertEqual(3, len(result.receipts))
        self.assertTrue(all(receipt.matched for receipt in result.receipts))

    def test_exact_public_file_hash_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("index.html", "propose.html", "catalog/catalog.json"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("expected", encoding="utf-8")

            def fetcher(url: str, **kwargs):
                body = "changed" if url.endswith("propose.html") else "expected"
                return LiveFetch(url, url, 200, "text/plain", body)

            result = verify_exact_public_files(
                "https://commonworld.net/",
                5,
                fetcher=fetcher,
                root=root,
            )

        self.assertEqual("fail", result.verdict)
        self.assertIn("exact public file hash mismatch: propose.html", result.errors)

    def test_live_smoke_retries_only_on_declared_schedule(self) -> None:
        clock = FakeClock()
        attempts = 0

        def live_smoke(url: str, *, timeout_seconds: int, insecure: bool):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError(f"propagation-{attempts}")
            return FakeLiveReceipt()

        result = run_live_smoke_with_retry(
            url="https://commonworld.net/",
            timeout_seconds=5,
            retry_delays_seconds=(0, 30, 90),
            live_smoke=live_smoke,
            exact_file_check=exact_pass,
            sleeper=clock.sleep,
        )
        self.assertEqual("pass", result.verdict)
        self.assertEqual(3, result.attempts)
        self.assertEqual(("cycle 1: propagation-1", "cycle 2: propagation-2"), result.errors)
        self.assertEqual([30.0, 90.0], clock.sleeps)

    def test_failed_exact_identity_preserves_last_smoke_and_file_receipts(self) -> None:
        mismatch = ExactPublicFilesResult(
            verdict="fail",
            receipts=(
                ExactPublicFileReceipt(
                    relative_url="index.html",
                    requested_url="https://commonworld.net/",
                    final_url="https://commonworld.net/",
                    status=200,
                    content_type="text/html",
                    body_bytes=7,
                    sha256="b" * 64,
                    expected_sha256="a" * 64,
                    matched=False,
                ),
            ),
            errors=("exact public file hash mismatch: index.html",),
        )
        result = run_live_smoke_with_retry(
            url="https://commonworld.net/",
            timeout_seconds=5,
            retry_delays_seconds=(0,),
            live_smoke=lambda url, **kwargs: FakeLiveReceipt(),
            exact_file_check=lambda base_url, timeout_seconds: mismatch,
            sleeper=lambda seconds: None,
        )
        self.assertEqual("fail", result.verdict)
        self.assertEqual("fake-live-receipt", result.receipt.smoke_id)
        self.assertEqual(1, len(result.exact_public_files))
        self.assertFalse(result.exact_public_files[0].matched)
        self.assertEqual(("cycle 1: exact public file hash mismatch: index.html",), result.errors)

    def test_success_receipt_binds_exact_deployment_and_live_result(self) -> None:
        def api_get(endpoint: str):
            if endpoint.startswith("deployments?"):
                return [deployment(23), deployment(99, OTHER_SHA)]
            return [{"state": "success", "environment_url": "https://commonworld.net/"}]

        receipt = run_production_readback(
            repository="heimgewebe/commonworld",
            expected_sha=SHA,
            token="test-token",
            url="https://commonworld.net/",
            api_get=api_get,
            live_smoke=lambda url, **kwargs: FakeLiveReceipt(),
            exact_file_check=exact_pass,
            head_sha=lambda: SHA,
            sleeper=lambda seconds: None,
            now=lambda: "2026-07-18T00:00:00Z",
        )
        self.assertEqual("pass", receipt.verdict)
        self.assertEqual(SHA, receipt.deployment["sha"])
        self.assertEqual(23, receipt.deployment["id"])
        self.assertEqual(1, receipt.deployment_attempts)
        self.assertEqual(1, receipt.live_attempts)
        self.assertEqual("fake-live-receipt", receipt.live_receipt.smoke_id)
        self.assertEqual(3, len(receipt.exact_public_files))
        self.assertTrue(all(item.matched for item in receipt.exact_public_files))
        self.assertIn("automatic rollback authorization", receipt.does_not_establish)

    def test_superseded_before_deployment_is_not_a_false_failure(self) -> None:
        receipt = run_production_readback(
            repository="heimgewebe/commonworld",
            expected_sha=SHA,
            token="test-token",
            url="https://commonworld.net/",
            api_get=lambda endpoint: self.fail(f"unexpected API call: {endpoint}"),
            head_sha=lambda: OTHER_SHA,
            now=lambda: "2026-07-18T00:00:00Z",
        )
        self.assertEqual("superseded", receipt.verdict)
        self.assertEqual("before_deployment", receipt.superseded_at)
        self.assertEqual(OTHER_SHA, receipt.repository_head_sha)
        self.assertEqual(0, receipt.deployment_attempts)
        self.assertEqual(0, receipt.live_attempts)
        self.assertEqual((), receipt.errors)

    def test_superseded_after_deployment_skips_live_claim(self) -> None:
        heads = iter((SHA, OTHER_SHA))

        def api_get(endpoint: str):
            if endpoint.startswith("deployments?"):
                return [deployment(31)]
            return [{"state": "success", "created_at": "2026-07-18T00:00:01Z"}]

        receipt = run_production_readback(
            repository="heimgewebe/commonworld",
            expected_sha=SHA,
            token="test-token",
            url="https://commonworld.net/",
            api_get=api_get,
            head_sha=lambda: next(heads),
            live_smoke=lambda url, **kwargs: self.fail("live smoke must be skipped"),
            now=lambda: "2026-07-18T00:00:00Z",
        )
        self.assertEqual("superseded", receipt.verdict)
        self.assertEqual("after_deployment", receipt.superseded_at)
        self.assertEqual(OTHER_SHA, receipt.repository_head_sha)
        self.assertEqual(1, receipt.deployment_attempts)
        self.assertEqual(0, receipt.live_attempts)

    def test_live_failure_becomes_superseded_when_main_advanced(self) -> None:
        heads = iter((SHA, SHA, OTHER_SHA))

        def api_get(endpoint: str):
            if endpoint.startswith("deployments?"):
                return [deployment(32)]
            return [{"state": "success", "created_at": "2026-07-18T00:00:01Z"}]

        receipt = run_production_readback(
            repository="heimgewebe/commonworld",
            expected_sha=SHA,
            token="test-token",
            url="https://commonworld.net/",
            api_get=api_get,
            head_sha=lambda: next(heads),
            live_smoke=lambda url, **kwargs: (_ for _ in ()).throw(RuntimeError("stale content")),
            live_retry_delays_seconds=(0,),
            sleeper=lambda seconds: None,
            now=lambda: "2026-07-18T00:00:00Z",
        )
        self.assertEqual("superseded", receipt.verdict)
        self.assertEqual("during_live_verification", receipt.superseded_at)
        self.assertEqual(OTHER_SHA, receipt.repository_head_sha)
        self.assertEqual(("cycle 1: stale content",), receipt.live_errors)
        self.assertEqual((), receipt.errors)

    def test_failure_receipt_is_written_for_invalid_configuration(self) -> None:
        receipt = run_production_readback(
            repository="",
            expected_sha="bad",
            token="",
            url="https://commonworld.net/",
            now=lambda: "2026-07-18T00:00:00Z",
        )
        self.assertEqual("fail", receipt.verdict)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "receipt.json"
            write_receipt(target, receipt)
            stored = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual("fail", stored["verdict"])
        self.assertEqual("commonworld.pages-production-readback.v1", stored["receipt_id"])
        self.assertGreaterEqual(len(stored["errors"]), 3)
        self.assertEqual([], stored["exact_public_files"])

    def test_direct_workflow_invocation_writes_failure_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "receipt.json"
            environment = dict(os.environ)
            environment.pop("GITHUB_TOKEN", None)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/verify_pages_deployment.py",
                    "--repository",
                    "invalid",
                    "--sha",
                    "bad",
                    "--receipt",
                    str(target),
                    "--deployment-timeout-seconds",
                    "0",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            stored = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(1, result.returncode)
        self.assertEqual("fail", stored["verdict"])
        self.assertIn("repository must be in owner/name form", stored["errors"])

    def test_workflow_uses_minimal_read_permissions_and_always_uploads_receipt(self) -> None:
        workflow = Path(".github/workflows/production-readback.yml").read_text(encoding="utf-8")
        self.assertIn("push:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("deployments: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("ref: ${{ github.sha }}", workflow)
        self.assertIn("--sha \"${{ github.sha }}\"", workflow)
        self.assertIn("--source-ref main", workflow)
        self.assertIn("--live-timeout-seconds 5", workflow)
        self.assertIn("--live-retry-delays-seconds 0,30,90", workflow)
        self.assertIn("timeout-minutes: 20", workflow)
        self.assertIn("continue-on-error: true", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("actions/upload-artifact@v4", workflow)
        self.assertIn("scripts/verify_pages_deployment.py", workflow)


if __name__ == "__main__":
    unittest.main()
