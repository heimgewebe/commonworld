#!/usr/bin/env python3
"""Refresh or check Commonworld catalogue evidence in one fail-closed order.

The refresh path only mutates machine-derived artefacts whose existing writers are
safe to replay. Browser measurements, timing-bearing composite evidence and locale
review evidence stay verification-only: this script never fabricates observations,
review receipts or editorial claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PYTHON = sys.executable


@dataclass(frozen=True)
class CommandStep:
    name: str
    argv: tuple[str, ...]
    evidence_class: str


SAFE_REFRESH_STEPS = (
    CommandStep("public-build", ("npm", "run", "build"), "machine-derived"),
    CommandStep(
        "catalog-recovery-evidence",
        (PYTHON, "scripts/measure_catalog_recovery.py"),
        "machine-derived",
    ),
    CommandStep(
        "catalog-hierarchy-evidence",
        (PYTHON, "scripts/measure_catalog_hierarchy_v2.py"),
        "machine-derived",
    ),
    CommandStep(
        "release-snapshot-lifecycle-evidence",
        (PYTHON, "scripts/measure_release_snapshot_lifecycle.py"),
        "machine-derived",
    ),
)

VERIFY_STEPS = (
    CommandStep(
        "cache-coherence",
        (PYTHON, "scripts/validate_cache_coherence.py"),
        "machine-derived",
    ),
    CommandStep(
        "catalog-delivery-budget",
        (PYTHON, "scripts/validate_catalog_delivery_budget.py"),
        "mixed-observational",
    ),
    CommandStep(
        "catalog-browser-measurement-decision",
        (PYTHON, "scripts/validate_catalog_browser_measurement_decision.py"),
        "mixed-observational",
    ),
    CommandStep(
        "catalog-scale-gates",
        (PYTHON, "scripts/validate_catalog_scale_gates.py"),
        "mixed-observational",
    ),
    CommandStep(
        "catalog-scale-masterplan",
        (PYTHON, "scripts/validate_catalog_scale_masterplan.py"),
        "mixed-observational",
    ),
    CommandStep(
        "catalog-recovery",
        (PYTHON, "scripts/validate_catalog_recovery.py"),
        "machine-derived",
    ),
    CommandStep(
        "catalog-hierarchy-browser",
        (PYTHON, "scripts/validate_catalog_hierarchy_browser_v2.py"),
        "mixed-observational",
    ),
    CommandStep(
        "catalog-hierarchy",
        (PYTHON, "scripts/validate_catalog_hierarchy_v2.py"),
        "machine-derived",
    ),
    CommandStep(
        "release-snapshot-lifecycle",
        (PYTHON, "scripts/validate_release_snapshot_lifecycle.py"),
        "machine-derived",
    ),
    CommandStep(
        "locale-release",
        (PYTHON, "scripts/validate_locale_release.py"),
        "human-review-bound",
    ),
)

# These artefacts contain observations, language-review evidence or editorial
# statements. Refresh mode must never rewrite them, even indirectly.
PROTECTED_EVIDENCE_PATHS = (
    Path("docs/evidence/catalog-delivery-benchmark-v1.json"),
    Path("docs/evidence/catalog-delivery-public-browser-smoke-v1.json"),
    Path("docs/evidence/catalog-hierarchy-browser-v2.json"),
    Path("docs/evidence/catalog-platform-scaling-v1.json"),
    Path("docs/evidence/locale-releases"),
)

DETERMINISTIC_OUTPUTS = {
    "catalog-recovery": Path("docs/evidence/catalog-recovery-scale-v1.json"),
    "catalog-hierarchy": Path("docs/evidence/catalog-hierarchy-v2.json"),
    "release-snapshot-lifecycle": Path("docs/evidence/release-snapshot-lifecycle-v1.json"),
}

Builder = Callable[[], object]


def _path_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(b"file\0")
        digest.update(path.read_bytes())
        return digest.hexdigest()
    if not path.is_dir():
        raise ValueError(f"protected evidence path is neither file nor directory: {path}")
    digest.update(b"tree\0")
    for child in sorted(
        (item for item in path.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(path).as_posix(),
    ):
        relative = child.relative_to(path).as_posix().encode("utf-8")
        payload = child.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def protected_snapshot(root: Path = ROOT) -> dict[str, str | None]:
    return {
        relative.as_posix(): _path_digest(root / relative)
        for relative in PROTECTED_EVIDENCE_PATHS
    }


def _git_output(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ("git", *args),
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def workspace_snapshot(root: Path = ROOT) -> str:
    """Hash the exact tracked/staged/untracked workspace state without mutating it."""

    digest = hashlib.sha256()
    for label, args in (
        ("unstaged", ("diff", "--no-ext-diff", "--binary", "--", ".")),
        ("staged", ("diff", "--cached", "--no-ext-diff", "--binary", "--", ".")),
    ):
        payload = _git_output(root, *args)
        digest.update(label.encode("utf-8") + b"\0")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)

    raw_untracked = _git_output(root, "ls-files", "--others", "--exclude-standard", "-z")
    for raw_relative in sorted(item for item in raw_untracked.split(b"\0") if item):
        relative = raw_relative.decode("utf-8", errors="strict")
        path = root / relative
        payload = path.read_bytes()
        digest.update(b"untracked\0")
        digest.update(len(raw_relative).to_bytes(4, "big"))
        digest.update(raw_relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _run_step(step: CommandStep, *, root: Path) -> bool:
    result = subprocess.run(
        step.argv,
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode == 0:
        print(f"PASS {step.name} [{step.evidence_class}]")
        return True
    print(f"FAIL {step.name} [{step.evidence_class}]", file=sys.stderr)
    if result.stdout.strip():
        print(result.stdout.rstrip(), file=sys.stderr)
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    return False


def _default_builders(root: Path) -> dict[str, Builder]:
    # Imports are intentionally lazy so --help and unit tests do not trigger
    # expensive fixture construction or Git-based lifecycle reproduction.
    if root != ROOT:
        raise ValueError("default deterministic builders are bound to this checkout")
    from scripts.measure_catalog_hierarchy_v2 import build_result as build_hierarchy
    from scripts.measure_catalog_recovery import build_result as build_recovery
    from scripts.measure_release_snapshot_lifecycle import build_evidence as build_lifecycle

    return {
        "catalog-recovery": lambda: build_recovery(root),
        "catalog-hierarchy": build_hierarchy,
        "release-snapshot-lifecycle": lambda: build_lifecycle(root),
    }


def check_deterministic_outputs(
    root: Path = ROOT,
    *,
    builders: dict[str, Builder] | None = None,
) -> list[str]:
    selected = builders if builders is not None else _default_builders(root)
    failures: list[str] = []
    for name, relative in DETERMINISTIC_OUTPUTS.items():
        builder = selected.get(name)
        if builder is None:
            failures.append(f"{name}: builder missing")
            continue
        path = root / relative
        if not path.is_file():
            failures.append(f"{name}: missing {relative.as_posix()}")
            continue
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
            recomputed = builder()
        except Exception as error:  # noqa: BLE001 - report all drift/check failures together.
            failures.append(f"{name}: recomputation failed: {error}")
            continue
        if committed != recomputed:
            failures.append(f"{name}: deterministic evidence drift")
        else:
            print(f"PASS {name}-deterministic-drift [machine-derived]")
    return failures


def verify(root: Path = ROOT, *, builders: dict[str, Builder] | None = None) -> int:
    before_workspace = workspace_snapshot(root)
    failures = check_deterministic_outputs(root, builders=builders)
    for step in VERIFY_STEPS:
        if not _run_step(step, root=root):
            failures.append(f"{step.name}: validator failed ({step.evidence_class})")
    after_workspace = workspace_snapshot(root)
    if before_workspace != after_workspace:
        failures.append("check mutated repository workspace")

    if not failures:
        print("catalog evidence check passed")
        return 0

    print("catalog evidence check failed:", file=sys.stderr)
    for failure in failures:
        print(f"- {failure}", file=sys.stderr)
    if any(
        "mixed-observational" in failure or "human-review-bound" in failure
        for failure in failures
    ):
        print(
            "Observed or human-review-bound evidence requires its canonical measurement/review flow; "
            "this refresh entrypoint will not synthesize or overwrite it.",
            file=sys.stderr,
        )
    return 1


def refresh(root: Path = ROOT, *, builders: dict[str, Builder] | None = None) -> int:
    before = protected_snapshot(root)
    for step in SAFE_REFRESH_STEPS:
        if not _run_step(step, root=root):
            return 1
    after = protected_snapshot(root)
    if before != after:
        changed = sorted(key for key in before if before[key] != after[key])
        print(
            "refresh aborted: protected observational/review evidence changed unexpectedly: "
            + ", ".join(changed),
            file=sys.stderr,
        )
        return 1
    return verify(root, builders=builders)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--refresh",
        action="store_true",
        help="Regenerate safe machine-derived artefacts, then run all evidence checks.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Read-only deterministic drift and evidence validation; writes nothing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.refresh:
        return refresh(ROOT)
    return verify(ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
