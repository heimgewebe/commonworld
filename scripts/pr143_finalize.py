#!/usr/bin/env python3
"""Temporary, idempotent PR #143 finalizer. Removed by the final commit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch() -> None:
    css_path = ROOT / "index.css"
    css = css_path.read_text(encoding="utf-8")
    adaptive = "grid-template-columns: repeat(auto-fit, minmax(min(14rem, 100%), 1fr));"
    if adaptive not in css:
        pattern = re.compile(
            r"(@media \(orientation: landscape\) and \(max-height: 30rem\) \{"
            r".*?\.project-detail-grid\s*\{\s*)"
            r"grid-template-columns:\s*repeat\(4,\s*minmax\(11rem,\s*1fr\)\);",
            re.DOTALL,
        )
        css, count = pattern.subn(r"\1" + adaptive, css, count=1)
        if count != 1:
            raise SystemExit(f"expected one low-height fixed detail grid, replaced {count}")
    css_path.write_text(css, encoding="utf-8")

    smoke_path = ROOT / "scripts/smoke_public_browser.mjs"
    smoke = smoke_path.read_text(encoding="utf-8")
    insertion_marker = (
        "const landscapeDetail = await newPage({ mobile: true, "
        "viewportOverride: { width: 667, height: 375 }"
    )
    if insertion_marker not in smoke:
        anchor = """  await landscapeOverview.context.close();

  const run = await newPage({ viewportOverride: { width: 844, height: 390 }, touch: true, reducedMotion: 'reduce' });"""
        replacement = """  await landscapeOverview.context.close();

  const landscapeDetail = await newPage({ mobile: true, viewportOverride: { width: 667, height: 375 }, touch: true, reducedMotion: 'reduce' });
  await landscapeDetail.page.goto(`${baseUrl}/?view=layers`, { waitUntil: 'domcontentloaded' });
  await landscapeDetail.page.waitForSelector('html.runtime-ready');
  await landscapeDetail.page.waitForSelector('.globe-stage[data-view-phase="layers"]');
  const detailTrigger = landscapeDetail.page.locator('.digital-ribbon-item').first();
  assert((await detailTrigger.count()) === 1, 'live UI 667x375 detail: no digital Commons trigger is available');
  await detailTrigger.click();
  await landscapeDetail.page.waitForSelector('#layer-projects:not([hidden]) .project-detail-grid');
  const detailGeometry = await landscapeDetail.page.evaluate(() => {
    const rect = (node) => {
      const box = node.getBoundingClientRect();
      return { left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height };
    };
    const panel = document.querySelector('#layer-projects');
    const grid = panel.querySelector('.project-detail-grid');
    const sections = [...grid.querySelectorAll('.project-detail-section')];
    const gridColumns = getComputedStyle(grid).gridTemplateColumns.split(/\s+/).filter(Boolean);
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      panel: rect(panel),
      panelClientWidth: panel.clientWidth,
      panelScrollWidth: panel.scrollWidth,
      gridClientWidth: grid.clientWidth,
      gridScrollWidth: grid.scrollWidth,
      gridColumnCount: gridColumns.length,
      sections: sections.map(rect),
    };
  });
  assert(detailGeometry.sections.length === 4, `live UI 667x375 detail: expected four detail sections (${JSON.stringify(detailGeometry)})`);
  assert(detailGeometry.gridColumnCount <= 2, `live UI 667x375 detail: low-height layout forced too many columns (${JSON.stringify(detailGeometry)})`);
  assert(detailGeometry.panelScrollWidth <= detailGeometry.panelClientWidth + 1, `live UI 667x375 detail: clipped horizontal panel overflow (${JSON.stringify(detailGeometry)})`);
  assert(detailGeometry.gridScrollWidth <= detailGeometry.gridClientWidth + 1, `live UI 667x375 detail: detail grid overflows horizontally (${JSON.stringify(detailGeometry)})`);
  assert(detailGeometry.sections.every(({ left, right }) => left >= detailGeometry.panel.left - 0.5 && right <= detailGeometry.panel.right + 0.5), `live UI 667x375 detail: section lies outside the clipped panel (${JSON.stringify(detailGeometry)})`);
  const lastDetailSection = landscapeDetail.page.locator('.project-detail-section').last();
  await lastDetailSection.scrollIntoViewIfNeeded();
  const lastSectionVisibility = await lastDetailSection.evaluate((node) => {
    const section = node.getBoundingClientRect();
    const panel = node.closest('#layer-projects').getBoundingClientRect();
    return {
      horizontallyReachable: section.left >= panel.left - 0.5 && section.right <= panel.right + 0.5,
      verticallyReachable: section.bottom > panel.top + 0.5 && section.top < panel.bottom - 0.5,
    };
  });
  assert(lastSectionVisibility.horizontallyReachable && lastSectionVisibility.verticallyReachable, `live UI 667x375 detail: final section is unreachable (${JSON.stringify(lastSectionVisibility)})`);
  assert(landscapeDetail.consoleErrors.length === 0, `live UI 667x375 detail: console errors: ${landscapeDetail.consoleErrors.join(' | ')}`);
  assert(landscapeDetail.pageErrors.length === 0, `live UI 667x375 detail: page errors: ${landscapeDetail.pageErrors.join(' | ')}`);
  await landscapeDetail.context.close();

  const run = await newPage({ viewportOverride: { width: 844, height: 390 }, touch: true, reducedMotion: 'reduce' });"""
        if smoke.count(anchor) != 1:
            raise SystemExit(f"expected one live UI insertion anchor, found {smoke.count(anchor)}")
        smoke = smoke.replace(anchor, replacement, 1)

    result_marker = "landscapeDetail: {"
    if result_marker not in smoke:
        result_anchor = """      minimumCatalogSelectHeight,
    },
  });"""
        result_replacement = """      minimumCatalogSelectHeight,
    },
    landscapeDetail: {
      viewport: detailGeometry.viewport,
      gridColumnCount: detailGeometry.gridColumnCount,
      panelHorizontalOverflow: Math.max(0, detailGeometry.panelScrollWidth - detailGeometry.panelClientWidth),
      gridHorizontalOverflow: Math.max(0, detailGeometry.gridScrollWidth - detailGeometry.gridClientWidth),
      finalSectionReachable: lastSectionVisibility.horizontallyReachable && lastSectionVisibility.verticallyReachable,
    },
  });"""
        if smoke.count(result_anchor) != 1:
            raise SystemExit(f"expected one live UI result anchor, found {smoke.count(result_anchor)}")
        smoke = smoke.replace(result_anchor, result_replacement, 1)
    smoke_path.write_text(smoke, encoding="utf-8")


def bind(static_path: Path, browser_path: Path, smoke_path: Path) -> None:
    benchmark_path = ROOT / "docs/evidence/catalog-delivery-benchmark-v1.json"
    smoke_evidence_path = ROOT / "docs/evidence/catalog-delivery-public-browser-smoke-v1.json"
    receipt_path = ROOT / "docs/evidence/pr143-finalization-receipt-v1.json"
    review_path = ROOT / "docs/evidence/digital-detail-unification-review-v1.md"

    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    smoke_evidence = json.loads(smoke_evidence_path.read_text(encoding="utf-8"))
    static = json.loads(static_path.read_text(encoding="utf-8"))
    browser = json.loads(browser_path.read_text(encoding="utf-8"))
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    contract = json.loads(
        (ROOT / "contracts/commonworld/catalog-delivery-budget.contract.json").read_text(encoding="utf-8")
    )
    budgets = contract["budgets"]

    scenarios = smoke.get("scenarios", [])
    if smoke.get("verdict") != "PASS" or len(scenarios) != 31:
        raise SystemExit("fresh public smoke is not PASS with exactly 31 scenarios")
    if any(item.get("verdict") != "PASS" for item in scenarios):
        raise SystemExit("fresh public smoke contains a failing scenario")
    live_ui = next(item for item in scenarios if item.get("id") == "live-ui-hardening")
    detail = live_ui.get("landscapeDetail", {})
    if (
        detail.get("gridColumnCount", 99) > 2
        or detail.get("panelHorizontalOverflow") != 0
        or detail.get("gridHorizontalOverflow") != 0
        or detail.get("finalSectionReachable") is not True
    ):
        raise SystemExit(f"low-height detail evidence is unhealthy: {detail!r}")

    profiles = browser.get("profiles", [])
    if browser.get("cpu_throttle_rate") != 4:
        raise SystemExit("fresh browser measurement lacks fourfold CPU throttling")
    if {item.get("profile") for item in profiles} != {"mobile-low-power", "desktop-low-power"}:
        raise SystemExit("fresh browser profiles are incomplete")

    result_hashes = {
        "static": sha256(static_path),
        "browser": sha256(browser_path),
        "smoke": sha256(smoke_path),
    }
    receipt = {
        "schema_version": 1,
        "kind": "commonworld_pr143_finalization_receipt",
        "source_commit": os.environ["GITHUB_SHA"],
        "github_run_id": os.environ["GITHUB_RUN_ID"],
        "github_run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "branch": "feat/digital-detail-unification-v1",
        "base_commit": "47b6e82c6e359dda1b03737ab45de0dbbca8f794",
        "result_sha256": result_hashes,
        "validation": {
            "public_browser_scenarios": len(scenarios),
            "low_height_detail": detail,
            "browser_profiles": [item["profile"] for item in profiles],
            "cpu_throttle_rate": browser["cpu_throttle_rate"],
        },
        "does_not_establish": ["final_commit_sha", "post_merge_pages_readback"],
    }
    write_json(receipt_path, receipt)
    receipt_sha = sha256(receipt_path)
    job_id = f"github-actions-{os.environ['GITHUB_RUN_ID']}-attempt-{os.environ['GITHUB_RUN_ATTEMPT']}"

    baseline_static = benchmark["baseline"]["static"]
    baseline_profiles = {
        item["profile"]: item for item in benchmark["baseline"]["browser"]["profiles"]
    }
    fresh_profiles = {item["profile"]: item for item in profiles}
    benchmark["optimized"]["static"] = static
    benchmark["optimized"]["browser"] = browser
    benchmark["budget_binding"] = {
        "bootstrap_gzip_bytes": static["bootstrap"]["gzip_bytes"],
        "warn_bootstrap_gzip_bytes": budgets["warn_bootstrap_gzip_bytes"],
        "max_bootstrap_gzip_bytes": budgets["max_bootstrap_gzip_bytes"],
    }
    base_delivery = baseline_static["catalog_initial_delivery"]
    fresh_delivery = static["catalog_initial_delivery"]
    raw_delta = fresh_delivery["raw_bytes"] - base_delivery["raw_bytes"]
    gzip_delta = fresh_delivery["gzip_bytes"] - base_delivery["gzip_bytes"]
    benchmark["delta"] = {
        "startup_project_json_requests": static["runtime_verification_fetch"]["project_request_count"]
        - baseline_static["runtime_verification_fetch"]["project_request_count"],
        "duplicate_identity_payload_count": static["runtime_verification_fetch"]["duplicate_identity_payload_count"]
        - baseline_static["runtime_verification_fetch"]["duplicate_identity_payload_count"],
        "catalog_initial_raw_bytes": raw_delta,
        "catalog_initial_gzip_bytes": gzip_delta,
        "catalog_initial_raw_reduction_percent": round((-raw_delta / base_delivery["raw_bytes"]) * 100, 1),
        "catalog_initial_gzip_reduction_percent": round((-gzip_delta / base_delivery["gzip_bytes"]) * 100, 1),
        "first_party_request_count_by_profile": {
            name: fresh_profiles[name]["first_party_request_count"] - base["first_party_request_count"]
            for name, base in baseline_profiles.items()
        },
        "browser_dom_nodes_by_profile": {
            name: fresh_profiles[name]["dom_node_count"] - base["dom_node_count"]
            for name, base in baseline_profiles.items()
        },
    }
    scenario_ids = [item["id"] for item in scenarios]
    blocked = next(item for item in scenarios if item["id"] == "catalogue-network-blocked")
    benchmark["validation"]["public_browser_smoke"] = {
        "verdict": "PASS",
        "scenario_count": len(scenario_ids),
        "scenario_ids": scenario_ids,
        "catalogue_network_blocked_requests": blocked["blockedCatalogRequests"],
        "job_id": job_id,
        "finalization_receipt_sha256": receipt_sha,
        "result_sha256": result_hashes["smoke"],
    }
    benchmark["validation"]["catalog_delivery_browser_measurement"] = {
        "verdict": "PASS",
        "profiles": [item["profile"] for item in profiles],
        "cpu_throttle_rate": browser["cpu_throttle_rate"],
        "result_sha256": result_hashes["browser"],
        "job_id": job_id,
        "finalization_receipt_sha256": receipt_sha,
    }

    surface_hashes = {item["first_party_surface_sha256"] for item in profiles}
    if len(surface_hashes) != 1:
        raise SystemExit("browser profiles disagree on first-party surface")
    smoke_evidence["execution"] = {
        "job_id": job_id,
        "finalization_receipt_sha256": receipt_sha,
        "result_sha256": result_hashes["smoke"],
    }
    smoke_evidence["binding"]["smoke_script_sha256"] = sha256(ROOT / "scripts/smoke_public_browser.mjs")
    smoke_evidence["binding"]["smoke_runner_sha256"] = sha256(ROOT / "scripts/run_browser_smoke.py")
    smoke_evidence["binding"]["smoke_plan_sha256"] = sha256(ROOT / "scripts/browser_smoke_plan.py")
    smoke_evidence["binding"]["first_party_surface_sha256"] = next(iter(surface_hashes))
    smoke_evidence["binding"]["scenario_ids"] = scenario_ids
    smoke_evidence["verdict"] = "PASS"
    smoke_evidence["scenarios"] = scenarios

    write_json(benchmark_path, benchmark)
    write_json(smoke_evidence_path, smoke_evidence)

    review = review_path.read_text(encoding="utf-8")
    review = review.replace(
        "- Integration with the current `main` was conflict-free, but review found three real stale contracts:",
        "- Integration with the current `main` was conflict-free, but review found four real stale contracts:",
    )
    marker = (
        "- The generated shell was rebuilt; the vertical-slice validator now checks the canonical "
        "project-routing path; static, throttled-browser and public-smoke evidence was regenerated "
        "and digest-bound.\n"
    )
    addition = marker + (
        "- Codex P1 for 667×375 landscape was confirmed: the fixed four-column minimum grid could "
        "be clipped. The low-height layout now adapts to one or two columns, with a browser regression "
        "proving zero horizontal overflow and reachability of the final evidence section.\n"
    )
    if "Codex P1 for 667×375 landscape was confirmed" not in review:
        if marker not in review:
            raise SystemExit("review evidence insertion marker missing")
        review = review.replace(marker, addition, 1)
    review_path.write_text(review, encoding="utf-8")

    print(json.dumps({"receipt_sha256": receipt_sha, "low_height_detail": detail}, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("patch")
    bind_parser = subparsers.add_parser("bind")
    bind_parser.add_argument("--static", type=Path, required=True)
    bind_parser.add_argument("--browser", type=Path, required=True)
    bind_parser.add_argument("--smoke", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "patch":
        patch()
    else:
        bind(args.static, args.browser, args.smoke)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
