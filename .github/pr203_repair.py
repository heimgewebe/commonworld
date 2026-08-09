#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / ".tmp-pr203"
BRANCH = "fix/touch-ring-orbit-v1"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args), flush=True)
    return subprocess.run(args, cwd=ROOT, text=True, check=check)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_sources() -> None:
    run("git", "fetch", "origin", "main")
    run(
        "git", "checkout", "origin/main", "--",
        "assets/commonworld-app.js",
        "index.css",
        "scripts/smoke_public_browser.mjs",
        "scripts/validate_digital_sphere.py",
    )

    css = ROOT / "index.css"
    s = css.read_text(encoding="utf-8")
    old = '''@media (hover: none) and (pointer: coarse) {
  /* Touch-first Android/iPad viewports can exceed the compact-width breakpoint in
     landscape or on tablets. Keep the SVG textPath parent groups off the compositor
     there as well; mouse/hover desktop keeps the orbit animation. */
  .sphere-ring-plane,
  .sphere-ring-plane[data-emphasis] {
    animation: none;
    transform: none;
  }

  .sphere-ring-text {
    font-size: var(--sphere-ring-font-size, 22px);
    stroke-width: var(--sphere-ring-stroke-width, 2.4px);
    letter-spacing: 0.018em;
  }
}
'''
    new = '''@media (hover: none) and (pointer: coarse) {
  /* Touch-first Android/iPad viewports can exceed the compact-width breakpoint in
     landscape or on tablets. Keep the SVG textPath parent groups off the compositor
     there as well; mouse/hover desktop keeps the orbit animation. */
  .sphere-ring-plane,
  .sphere-ring-plane[data-emphasis] {
    animation: none;
    transform: none;
  }

  .sphere-ring-plane > use,
  .sphere-ring-plane > .sphere-ring-text {
    transform-box: view-box;
    transform-origin: 320px 320px;
    transform: rotate(var(--ring-orbit-start-angle, 0deg));
    animation: sphere-ring-orbit var(--ring-orbit-duration, 240s) linear infinite;
  }

  .globe-stage[data-map-moving="true"] .sphere-ring-plane > use,
  .globe-stage[data-map-moving="true"] .sphere-ring-plane > .sphere-ring-text,
  .digital-sphere:has(.sphere-edge-control:focus) .sphere-ring-plane > use,
  .digital-sphere:has(.sphere-edge-control:focus) .sphere-ring-plane > .sphere-ring-text,
  .digital-sphere:has(.sphere-edge-control:active) .sphere-ring-plane > use,
  .digital-sphere:has(.sphere-edge-control:active) .sphere-ring-plane > .sphere-ring-text {
    animation-play-state: paused;
  }

  .sphere-ring-text {
    font-size: var(--sphere-ring-font-size, 22px);
    stroke-width: var(--sphere-ring-stroke-width, 2.4px);
    letter-spacing: 0.018em;
  }
}

@media (hover: none) and (pointer: coarse) and (prefers-reduced-motion: reduce) {
  .sphere-ring-plane > use,
  .sphere-ring-plane > .sphere-ring-text {
    --ring-orbit-direction: 0;
  }
}
'''
    if old not in s:
        raise RuntimeError("coarse touch CSS source block not found")
    css.write_text(s.replace(old, new, 1), encoding="utf-8")

    smoke = ROOT / "scripts/smoke_public_browser.mjs"
    s = smoke.read_text(encoding="utf-8")
    start_marker = "  await run.page.setViewportSize({ width: 844, height: 390 });\n"
    end_marker = "  const compactDesktopRun = await newPage({\n"
    start = s.index(start_marker)
    end = s.index(end_marker, start)
    block = '''  await run.page.setViewportSize({ width: 844, height: 390 });
  await run.page.waitForTimeout(100);
  const touchRingState = () => run.page.evaluate(() => [...document.querySelectorAll('.sphere-ring-plane')].map((plane) => {
    const label = plane.querySelector('.sphere-ring-text');
    const ring = plane.querySelector('use');
    const labelStyle = label ? getComputedStyle(label) : null;
    const ringStyle = ring ? getComputedStyle(ring) : null;
    const labelTransform = labelStyle?.transform && labelStyle.transform !== 'none' ? new DOMMatrixReadOnly(labelStyle.transform) : null;
    const ringTransform = ringStyle?.transform && ringStyle.transform !== 'none' ? new DOMMatrixReadOnly(ringStyle.transform) : null;
    const labelRect = label?.getBoundingClientRect();
    const ringRect = ring?.getBoundingClientRect();
    return {
      labelAnimationName: labelStyle?.animationName ?? 'none',
      labelAnimationPlayState: labelStyle?.animationPlayState ?? 'running',
      labelOrbitDirection: labelStyle?.getPropertyValue('--ring-orbit-direction').trim() ?? '',
      ringAnimationName: ringStyle?.animationName ?? 'none',
      ringAnimationPlayState: ringStyle?.animationPlayState ?? 'running',
      ringOrbitDirection: ringStyle?.getPropertyValue('--ring-orbit-direction').trim() ?? '',
      labelMatrix: labelTransform ? [labelTransform.a, labelTransform.b, labelTransform.c, labelTransform.d, labelTransform.e, labelTransform.f] : null,
      ringMatrix: ringTransform ? [ringTransform.a, ringTransform.b, ringTransform.c, ringTransform.d, ringTransform.e, ringTransform.f] : null,
      labelBox: labelRect ? [labelRect.x, labelRect.y, labelRect.width, labelRect.height] : null,
      ringBox: ringRect ? [ringRect.x, ringRect.y, ringRect.width, ringRect.height] : null,
    };
  }));
  const wideTouchMotionBefore = await touchRingState();
  await run.page.waitForTimeout(350);
  const wideTouchGeometry = await run.page.evaluate(() => {
    const planes = [...document.querySelectorAll('.sphere-ring-plane')];
    const primaryPlanes = planes.filter((plane) => plane.dataset.emphasis === 'primary');
    const depthPlanes = planes.filter((plane) => plane.dataset.emphasis === 'depth');
    const groupsAreStatic = (items) => items.every((plane) => {
      const style = getComputedStyle(plane);
      return style.animationName === 'none' && style.transform === 'none';
    });
    return {
      viewportWidth: window.innerWidth,
      mediaCompact: window.matchMedia('(max-width: 48rem)').matches,
      mediaCoarseTouch: window.matchMedia('(hover: none) and (pointer: coarse)').matches,
      primaryRingsStatic: groupsAreStatic(primaryPlanes),
      depthRingsStatic: groupsAreStatic(depthPlanes),
      representativePrimaryLabels: primaryPlanes.map((plane) => {
        const label = plane.querySelector('.sphere-ring-text');
        const rect = label?.getBoundingClientRect();
        const style = label ? getComputedStyle(label) : null;
        return {
          text: label?.textContent?.trim() ?? '',
          width: rect?.width ?? 0,
          height: rect?.height ?? 0,
          fontSize: style ? Number.parseFloat(style.fontSize) : 0,
          visible: Boolean(label && style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && rect.width > 0 && rect.height > 0),
        };
      }),
    };
  });
  const wideTouchMotionAfter = await touchRingState();
  const movingTouchRings = wideTouchMotionAfter.filter((after, index) => {
    const before = wideTouchMotionBefore[index];
    if (after.ringAnimationName !== 'sphere-ring-orbit' || !after.ringMatrix || !before?.ringMatrix) return false;
    return after.ringMatrix.some((value, matrixIndex) => Math.abs(value - before.ringMatrix[matrixIndex]) > 1e-5);
  });
  const movingTouchLabels = wideTouchMotionAfter.filter((after, index) => {
    const before = wideTouchMotionBefore[index];
    if (after.labelAnimationName !== 'sphere-ring-orbit' || !after.labelBox || !before?.labelBox) return false;
    return after.labelBox.some((value, boxIndex) => Math.abs(value - before.labelBox[boxIndex]) > 1e-3);
  });
  assert(wideTouchGeometry.viewportWidth > 768 && !wideTouchGeometry.mediaCompact && wideTouchGeometry.mediaCoarseTouch, scenarioId + ': wide touch viewport did not exercise the non-compact coarse-pointer path ' + JSON.stringify(wideTouchGeometry));
  assert(wideTouchGeometry.primaryRingsStatic && wideTouchGeometry.depthRingsStatic, scenarioId + ': wide touch ring group regained compositor animation or transform ' + JSON.stringify(wideTouchGeometry));
  assert(movingTouchRings.length >= 2, scenarioId + ': wide touch visible ring strokes did not advance ' + JSON.stringify({ before: wideTouchMotionBefore, after: wideTouchMotionAfter }));
  assert(movingTouchLabels.length >= 2, scenarioId + ': wide touch visible ring labels did not move with their ring strokes ' + JSON.stringify({ before: wideTouchMotionBefore, after: wideTouchMotionAfter }));
  assert(wideTouchGeometry.representativePrimaryLabels.length >= 2 && wideTouchGeometry.representativePrimaryLabels.every(({ text, visible, width, height, fontSize }) => text.length > 0 && visible && width > 80 && height > 0 && fontSize >= 20), scenarioId + ': wide touch primary ring labels are absent or not visibly laid out ' + JSON.stringify(wideTouchGeometry));

  const movingLabelsBetween = (before, after, threshold = 1e-3) => after.filter((entry, index) => {
    const previous = before[index];
    if (!entry.labelBox || !previous?.labelBox) return false;
    return entry.labelBox.some((value, boxIndex) => Math.abs(value - previous.labelBox[boxIndex]) > threshold);
  });
  await run.page.evaluate(() => { document.querySelector('.globe-stage').dataset.mapMoving = 'true'; });
  await run.page.waitForTimeout(80);
  const mapPausedBefore = await touchRingState();
  await run.page.waitForTimeout(350);
  const mapPausedAfter = await touchRingState();
  assert(mapPausedAfter.filter(({ labelAnimationName, labelAnimationPlayState, ringAnimationName, ringAnimationPlayState }) => labelAnimationName === 'sphere-ring-orbit' && labelAnimationPlayState === 'paused' && ringAnimationName === 'sphere-ring-orbit' && ringAnimationPlayState === 'paused').length >= 2, scenarioId + ': wide touch ring children did not pause while map-moving state was active ' + JSON.stringify(mapPausedAfter));
  assert(movingLabelsBetween(mapPausedBefore, mapPausedAfter).length === 0, scenarioId + ': wide touch labels moved while map-moving state paused the orbit ' + JSON.stringify({ before: mapPausedBefore, after: mapPausedAfter }));
  await run.page.evaluate(() => { delete document.querySelector('.globe-stage').dataset.mapMoving; });

  await run.page.locator('#sphere-edge-control').focus();
  await run.page.waitForTimeout(80);
  const focusPausedBefore = await touchRingState();
  await run.page.waitForTimeout(350);
  const focusPausedAfter = await touchRingState();
  assert(focusPausedAfter.filter(({ labelAnimationName, labelAnimationPlayState, ringAnimationName, ringAnimationPlayState }) => labelAnimationName === 'sphere-ring-orbit' && labelAnimationPlayState === 'paused' && ringAnimationName === 'sphere-ring-orbit' && ringAnimationPlayState === 'paused').length >= 2, scenarioId + ': wide touch ring children did not pause while sphere edge control was focused ' + JSON.stringify(focusPausedAfter));
  assert(movingLabelsBetween(focusPausedBefore, focusPausedAfter).length === 0, scenarioId + ': wide touch labels moved while sphere edge focus paused the orbit ' + JSON.stringify({ before: focusPausedBefore, after: focusPausedAfter }));
  await run.page.evaluate(() => document.querySelector('#sphere-edge-control')?.blur());
  await run.page.waitForTimeout(80);
  const focusResumedBefore = await touchRingState();
  await run.page.waitForTimeout(350);
  const focusResumedAfter = await touchRingState();
  assert(movingLabelsBetween(focusResumedBefore, focusResumedAfter).length >= 2, scenarioId + ': wide touch labels did not resume after sphere edge focus ended ' + JSON.stringify({ before: focusResumedBefore, after: focusResumedAfter }));

  await run.page.emulateMedia({ reducedMotion: 'reduce' });
  await run.page.waitForTimeout(80);
  const reducedTouchBefore = await touchRingState();
  await run.page.waitForTimeout(350);
  const reducedTouchAfter = await touchRingState();
  assert(reducedTouchAfter.filter(({ labelAnimationName, labelOrbitDirection, ringAnimationName, ringOrbitDirection }) => labelAnimationName === 'sphere-ring-orbit' && labelOrbitDirection === '0' && ringAnimationName === 'sphere-ring-orbit' && ringOrbitDirection === '0').length >= 2, scenarioId + ': live reduced-motion change did not zero wide touch ring motion ' + JSON.stringify(reducedTouchAfter));
  assert(movingLabelsBetween(reducedTouchBefore, reducedTouchAfter).length === 0, scenarioId + ': wide touch labels moved after live reduced-motion activation ' + JSON.stringify({ before: reducedTouchBefore, after: reducedTouchAfter }));
  await run.page.emulateMedia({ reducedMotion: 'no-preference' });
  await run.page.waitForTimeout(80);
  const resumedTouchBefore = await touchRingState();
  await run.page.waitForTimeout(350);
  const resumedTouchAfter = await touchRingState();
  assert(movingLabelsBetween(resumedTouchBefore, resumedTouchAfter).length >= 2, scenarioId + ': wide touch labels did not resume after live reduced-motion deactivation ' + JSON.stringify({ before: resumedTouchBefore, after: resumedTouchAfter }));

'''
    smoke.write_text(s[:start] + block + s[end:], encoding="utf-8")

    validator = ROOT / "scripts/validate_digital_sphere.py"
    s = validator.read_text(encoding="utf-8")
    marker = '        errors.append("digital sphere motion boundary mismatch")\n\n    interaction = contract.get("interaction", {})\n'
    replacement = '''        errors.append("digital sphere motion boundary mismatch")
    app_source = (ROOT / "assets" / "commonworld-app.js").read_text(encoding="utf-8")
    css_source = (ROOT / "index.css").read_text(encoding="utf-8")
    if "animateTransform" in app_source or "<animateTransform" in app_source:
        errors.append("digital sphere orbit runtime must not use SVG SMIL animateTransform")
    if "@keyframes sphere-ring-orbit" not in css_source or "animation: sphere-ring-orbit" not in css_source:
        errors.append("digital sphere orbit runtime must use CSS transform keyframes")

    interaction = contract.get("interaction", {})
'''
    if marker not in s:
        raise RuntimeError("digital sphere validator insertion point not found")
    validator.write_text(s.replace(marker, replacement, 1), encoding="utf-8")


def remove_superseded_added_releases() -> None:
    release_id = load(ROOT / "assets/commonworld-page-builds.json")["release_id"]
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", "origin/main", "--", "releases/"],
        cwd=ROOT, text=True, check=True, capture_output=True,
    )
    old_ids = {line.split("/")[1] for line in result.stdout.splitlines() if line.startswith("releases/") and len(line.split("/")) > 1}
    for old in sorted(old_ids):
        if old != release_id:
            shutil.rmtree(ROOT / "releases" / old, ignore_errors=True)
    print(f"release={release_id}")


def refresh_evidence() -> None:
    TMP.mkdir(exist_ok=True)
    run("node", "scripts/smoke_public_browser.mjs", "--result", str(TMP / "public-smoke.json"))
    run("node", "scripts/measure_catalog_delivery_browser.mjs", "--output", str(TMP / "browser-attempt-1.json"))
    decision = subprocess.run(
        ["python3", "scripts/evaluate_catalog_browser_measurements.py", "--attempt", str(TMP / "browser-attempt-1.json"), "--output", str(TMP / "browser-decision.json")],
        cwd=ROOT, text=True,
    )
    if decision.returncode == 2:
        run("node", "scripts/measure_catalog_delivery_browser.mjs", "--output", str(TMP / "browser-attempt-2.json"))
        run(
            "python3", "scripts/evaluate_catalog_browser_measurements.py",
            "--attempt", str(TMP / "browser-attempt-1.json"),
            "--attempt", str(TMP / "browser-attempt-2.json"),
            "--output", str(TMP / "browser-decision.json"),
        )
    elif decision.returncode != 0:
        raise RuntimeError(f"browser measurement decision failed: {decision.returncode}")
    run("python3", "scripts/measure_catalog_delivery.py", "--output", str(TMP / "static.json"))

    static = load(TMP / "static.json")
    smoke = load(TMP / "public-smoke.json")
    browser = load(TMP / "browser-decision.json")
    if smoke.get("verdict") != "PASS" or browser.get("gate_verdict") != "pass":
        raise RuntimeError("browser evidence is not terminal PASS")

    smoke["binding"] = {
        "smoke_script_sha256": sha(ROOT / "scripts/smoke_public_browser.mjs"),
        "smoke_runner_sha256": sha(ROOT / "scripts/run_browser_smoke.py"),
        "smoke_plan_sha256": sha(ROOT / "scripts/browser_smoke_plan.py"),
        "scenario_ids": [item["id"] for item in smoke["scenarios"]],
        "first_party_surface_sha256": browser["first_party_surface_sha256"],
    }
    dump(ROOT / "docs/evidence/catalog-delivery-public-browser-smoke-v1.json", smoke)

    evidence_path = ROOT / "docs/evidence/catalog-delivery-benchmark-v1.json"
    evidence = load(evidence_path)
    evidence["optimized"]["static"] = static
    evidence["optimized"]["browser"] = browser
    budgets = load(ROOT / "contracts/commonworld/catalog-delivery-budget.contract.json")["budgets"]
    evidence["budget_binding"] = {
        "bootstrap_gzip_bytes": static["bootstrap"]["gzip_bytes"],
        "warn_bootstrap_gzip_bytes": budgets["warn_bootstrap_gzip_bytes"],
        "max_bootstrap_gzip_bytes": budgets["max_bootstrap_gzip_bytes"],
    }

    baseline_static = evidence["baseline"]["static"]
    baseline_runtime = baseline_static["runtime_verification_fetch"]
    baseline_initial = baseline_static["catalog_initial_delivery"]
    optimized_runtime = static["runtime_verification_fetch"]
    optimized_initial = static["catalog_initial_delivery"]
    delta = evidence["delta"]
    delta["startup_project_json_requests"] = optimized_runtime["project_request_count"] - baseline_runtime["project_request_count"]
    delta["duplicate_identity_payload_count"] = optimized_runtime["duplicate_identity_payload_count"] - baseline_runtime["duplicate_identity_payload_count"]
    delta["catalog_initial_raw_bytes"] = optimized_initial["raw_bytes"] - baseline_initial["raw_bytes"]
    delta["catalog_initial_gzip_bytes"] = optimized_initial["gzip_bytes"] - baseline_initial["gzip_bytes"]
    delta["catalog_initial_raw_reduction_percent"] = round((-delta["catalog_initial_raw_bytes"] / baseline_initial["raw_bytes"]) * 100, 1)
    delta["catalog_initial_gzip_reduction_percent"] = round((-delta["catalog_initial_gzip_bytes"] / baseline_initial["gzip_bytes"]) * 100, 1)

    baseline_profiles = {p["profile"]: p for p in evidence["baseline"]["browser"]["profiles"]}
    optimized_profiles = {p["profile"]: p for p in browser["profiles"]}
    delta["first_party_request_count_by_profile"] = {
        name: optimized_profiles[name].get("first_party_request_count", 0) - profile.get("first_party_request_count", 0)
        for name, profile in baseline_profiles.items() if name in optimized_profiles
    }
    delta["browser_dom_nodes_by_profile"] = {
        name: optimized_profiles[name].get("dom_node_count", 0) - profile.get("dom_node_count", 0)
        for name, profile in baseline_profiles.items() if name in optimized_profiles
    }

    grouped: dict[str, list[dict]] = {}
    for attempt in browser["attempts"]:
        for profile in attempt["measurement"]["profiles"]:
            grouped.setdefault(profile["profile"], []).append(profile)

    def stats(values: list[float]) -> dict:
        values = sorted(values)
        return {"min": min(values), "median": statistics.median(values), "max": max(values)}

    evidence["browser_repeatability"] = {
        "run_count": len(browser["attempts"]),
        "cpu_throttle_rate": 4,
        "profiles": {
            name: {
                "runtime_ready_ms": stats([p["runtime_ready_ms"] for p in profiles]),
                "script_duration_ms": stats([p["script_duration_ms"] for p in profiles]),
                "task_duration_ms": stats([p["task_duration_ms"] for p in profiles]),
            }
            for name, profiles in grouped.items()
        },
        "interpretation": "Fresh no-store measurements on the exact current first-party surface at fourfold CPU throttling passed the bound startup budgets.",
    }
    release = load(ROOT / "assets/commonworld-page-builds.json")["release_id"]
    evidence["current_surface_note"] = (
        f"Fresh exact-tree static, browser-performance and public-smoke evidence for immutable release {release}; "
        "coarse-pointer ring motion is restored with CSS keyframes on the visible ring stroke and text while textPath parent groups remain compositor-static."
    )
    dump(evidence_path, evidence)

    locale_contract_path = ROOT / "docs/architecture/locale-release.contract.json"
    locale_contract = load(locale_contract_path)
    for locale in ("es", "fr", "pt-BR", "ar"):
        entry = locale_contract["locale_registry"][locale]
        locale_evidence_path = ROOT / entry["release_evidence"]["path"]
        locale_evidence = load(locale_evidence_path)
        locale_evidence["surface_sha256"] = {
            surface: sha(ROOT / rel) for surface, rel in entry["surface_files"].items()
        }
        dump(locale_evidence_path, locale_evidence)
        entry["release_evidence"]["sha256"] = sha(locale_evidence_path)
    dump(locale_contract_path, locale_contract)

    run("python3", "scripts/validate_catalog_delivery_budget.py", "--smoke-result", str(TMP / "public-smoke.json"))
    run("python3", "scripts/validate_locale_release.py")
    run("python3", "scripts/measure_release_snapshot_lifecycle.py")
    run("python3", "scripts/validate_release_snapshot_lifecycle.py")


def main() -> None:
    patch_sources()
    run("node", "--check", "scripts/smoke_public_browser.mjs")
    run("python3", "-m", "py_compile", "scripts/validate_digital_sphere.py")
    run("git", "diff", "--check")
    run("npm", "run", "build")
    remove_superseded_added_releases()
    refresh_evidence()
    run("git", "diff", "--check")
    run("make", "validate")
    run("npm", "run", "smoke:browser")
    shutil.rmtree(TMP, ignore_errors=True)
    run("git", "config", "user.name", "Commonworld Repair Bot")
    run("git", "config", "user.email", "commonworld-repair@users.noreply.github.com")
    run("git", "add", "-A")
    run("git", "commit", "-m", "fix: restore coarse-touch ring motion safely")
    run("npm", "run", "build")
    run("git", "diff", "--exit-code")
    run("git", "push", "origin", f"HEAD:{BRANCH}")


if __name__ == "__main__":
    main()
