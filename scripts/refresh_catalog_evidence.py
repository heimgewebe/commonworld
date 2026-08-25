#!/usr/bin/env python3
"""Refresh or check Commonworld catalogue evidence in one fail-closed order.

Public refresh/check operations execute in an isolated local clone of the caller's
exact working-tree contents. Check never writes back. Refresh only copies explicitly
allowed machine-derived outputs back after every protected-evidence and validation
gate passes.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PYTHON = sys.executable
ISOLATED_ENV = "COMMONWORLD_CATALOG_EVIDENCE_ISOLATED_V1"


@dataclass(frozen=True)
class CommandStep:
    name: str
    argv: tuple[str, ...]
    evidence_class: str


@dataclass(frozen=True)
class FileState:
    kind: str
    mode: int
    sha256: str


@dataclass(frozen=True)
class WorkspaceEntry:
    state: FileState | None
    tracked: bool


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
# statements. Refresh mode must never publish changes to them.
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

ALLOWED_REFRESH_OUTPUT_FILES = frozenset(
    {
        "404.html",
        "assets/commonworld-bootstrap-catalog.mjs",
        "assets/commonworld-en-locale.mjs",
        "assets/commonworld-locale-registry.mjs",
        "assets/commonworld-page-builds.json",
        "assets/commonworld-wave1-locales.mjs",
        "assets/map/commonworld-country-boundaries.geojson",
        "docs/evidence/catalog-hierarchy-v2.json",
        "docs/evidence/catalog-recovery-scale-v1.json",
        "docs/evidence/release-snapshot-lifecycle-v1.json",
    }
)
ALLOWED_REFRESH_OUTPUT_PREFIXES = (
    "assets/vendor/",
    "catalog/runtime/",
    "releases/",
)
CATALOG_RECOVERY_HTML = re.compile(
    r"^catalog/(?:de/)?(?:index|pages/[1-9][0-9]*|projects/[a-z][a-z0-9-]{2,95})\.html$"
)

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


def _git_paths(root: Path, *args: str) -> set[str]:
    payload = _git_output(root, *args)
    return {
        raw.decode("utf-8", errors="strict")
        for raw in payload.split(b"\0")
        if raw
    }


def _file_state(path: Path) -> FileState | None:
    try:
        linked = path.lstat()
    except FileNotFoundError:
        return None
    mode = stat.S_IMODE(linked.st_mode)
    digest = hashlib.sha256()
    if stat.S_ISLNK(linked.st_mode):
        target = os.readlink(path).encode("utf-8", errors="surrogateescape")
        digest.update(b"symlink\0")
        digest.update(target)
        return FileState("symlink", mode, digest.hexdigest())
    if stat.S_ISREG(linked.st_mode):
        digest.update(b"file\0")
        digest.update(path.read_bytes())
        return FileState("file", mode, digest.hexdigest())
    raise ValueError(f"workspace path is neither regular file nor symlink: {path}")


def workspace_entries(root: Path = ROOT) -> dict[str, WorkspaceEntry]:
    tracked = _git_paths(root, "ls-files", "-z")
    untracked = _git_paths(root, "ls-files", "--others", "--exclude-standard", "-z")
    return {
        relative: WorkspaceEntry(
            state=_file_state(root / relative),
            tracked=relative in tracked,
        )
        for relative in sorted(tracked | untracked)
    }


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

    for relative, entry in workspace_entries(root).items():
        if entry.tracked:
            continue
        raw_relative = relative.encode("utf-8")
        digest.update(b"untracked\0")
        digest.update(len(raw_relative).to_bytes(4, "big"))
        digest.update(raw_relative)
        state = entry.state
        if state is None:
            digest.update(b"absent")
        else:
            digest.update(state.kind.encode("ascii") + b"\0")
            digest.update(state.mode.to_bytes(4, "big"))
            digest.update(state.sha256.encode("ascii"))
    return digest.hexdigest()


def _copy_untracked(source: Path, destination: Path, entries: dict[str, WorkspaceEntry]) -> None:
    for relative, entry in entries.items():
        if entry.tracked or entry.state is None:
            continue
        source_path = source / relative
        destination_path = destination / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if entry.state.kind == "symlink":
            os.symlink(os.readlink(source_path), destination_path)
        elif entry.state.kind == "file":
            shutil.copy2(source_path, destination_path, follow_symlinks=False)
        else:
            raise ValueError(f"unsupported untracked workspace entry: {relative}")


@contextmanager
def isolated_workspace(
    root: Path = ROOT,
    *,
    source_entries: dict[str, WorkspaceEntry] | None = None,
) -> Iterator[Path]:
    """Mirror current non-ignored workspace contents without mutating source Git metadata."""

    entries = source_entries if source_entries is not None else workspace_entries(root)
    head = _git_output(root, "rev-parse", "HEAD").decode("ascii").strip()
    working_patch = _git_output(
        root,
        "diff",
        "--no-ext-diff",
        "--binary",
        "HEAD",
        "--",
        ".",
    )
    with tempfile.TemporaryDirectory(prefix="commonworld-catalog-evidence-") as directory:
        isolated = Path(directory) / "checkout"
        clone = subprocess.run(
            ("git", "clone", "--quiet", "--shared", "--no-checkout", str(root), str(isolated)),
            cwd=root.parent,
            check=False,
            text=True,
            capture_output=True,
        )
        if clone.returncode != 0:
            raise RuntimeError(f"isolated clone failed: {clone.stderr.strip()}")
        checkout = subprocess.run(
            ("git", "checkout", "--quiet", "--detach", head),
            cwd=isolated,
            check=False,
            text=True,
            capture_output=True,
        )
        if checkout.returncode != 0:
            raise RuntimeError(f"isolated checkout failed: {checkout.stderr.strip()}")
        if working_patch:
            apply = subprocess.run(
                ("git", "apply", "--binary", "--whitespace=nowarn"),
                cwd=isolated,
                input=working_patch,
                check=False,
                capture_output=True,
            )
            if apply.returncode != 0:
                detail = apply.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"isolated workspace overlay failed: {detail}")
        _copy_untracked(root, isolated, entries)

        source_node_modules = root / "node_modules"
        isolated_node_modules = isolated / "node_modules"
        if source_node_modules.is_dir() and not isolated_node_modules.exists():
            os.symlink(
                str(source_node_modules.resolve()),
                isolated_node_modules,
                target_is_directory=True,
            )
        yield isolated


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
            import json

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


def _verify_in_place(
    root: Path = ROOT,
    *,
    builders: dict[str, Builder] | None = None,
) -> int:
    before_workspace = workspace_snapshot(root)
    failures = check_deterministic_outputs(root, builders=builders)
    for step in VERIFY_STEPS:
        if not _run_step(step, root=root):
            failures.append(f"{step.name}: validator failed ({step.evidence_class})")
    after_workspace = workspace_snapshot(root)
    if before_workspace != after_workspace:
        failures.append("check mutated isolated repository workspace")

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


def _refresh_in_place(
    root: Path = ROOT,
    *,
    builders: dict[str, Builder] | None = None,
) -> int:
    before = protected_snapshot(root)
    for step in SAFE_REFRESH_STEPS:
        if not _run_step(step, root=root):
            return 1
    after = protected_snapshot(root)
    if before != after:
        changed = sorted(key for key in before if before[key] != after[key])
        print(
            "refresh aborted: protected observational/review evidence changed in isolation: "
            + ", ".join(changed),
            file=sys.stderr,
        )
        return 1
    return _verify_in_place(root, builders=builders)


def _run_isolated_mode(root: Path, mode: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment[ISOLATED_ENV] = "1"
    return subprocess.run(
        (sys.executable, "scripts/refresh_catalog_evidence.py", mode),
        cwd=root,
        env=environment,
        check=False,
        text=True,
        capture_output=True,
    )


def _forward_result(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)


def _changed_paths(
    before: dict[str, WorkspaceEntry],
    after: dict[str, WorkspaceEntry],
) -> list[str]:
    paths = sorted(set(before) | set(after))
    return [
        relative
        for relative in paths
        if (before.get(relative).state if relative in before else None)
        != (after.get(relative).state if relative in after else None)
    ]


def _is_allowed_refresh_output(relative: str) -> bool:
    if relative in ALLOWED_REFRESH_OUTPUT_FILES:
        return True
    if any(relative.startswith(prefix) for prefix in ALLOWED_REFRESH_OUTPUT_PREFIXES):
        return True
    if "/" not in relative and relative.endswith(".html"):
        return True
    return CATALOG_RECOVERY_HTML.fullmatch(relative) is not None


def _write_output(source: Path, destination: Path, state: FileState | None) -> None:
    if state is None:
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.exists():
            raise RuntimeError(f"cannot delete non-file refresh output: {destination}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    if state.kind == "file":
        payload = source.read_bytes()
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.catalog-evidence-",
            dir=destination.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, state.mode)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        return
    if state.kind == "symlink":
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.catalog-evidence-",
            dir=destination.parent,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        temporary.unlink()
        try:
            os.symlink(os.readlink(source), temporary)
            os.replace(temporary, destination)
        finally:
            if temporary.is_symlink() or temporary.exists():
                temporary.unlink()
        return
    raise RuntimeError(f"unsupported refresh output kind: {state.kind}")


def _publish_refresh_outputs(
    source_root: Path,
    isolated_root: Path,
    source_before: dict[str, WorkspaceEntry],
    isolated_before: dict[str, WorkspaceEntry],
    isolated_after: dict[str, WorkspaceEntry],
    source_workspace_sha256: str,
) -> bool:
    if workspace_snapshot(source_root) != source_workspace_sha256:
        print("refresh output publication refused: source workspace changed concurrently", file=sys.stderr)
        return False

    changed = _changed_paths(isolated_before, isolated_after)
    problems: list[str] = []
    for relative in changed:
        if not _is_allowed_refresh_output(relative):
            problems.append(f"unexpected refresh output path: {relative}")
            continue
        source_entry = source_before.get(relative)
        if source_entry is not None and not source_entry.tracked and source_entry.state is not None:
            problems.append(f"refresh attempted to rewrite pre-existing untracked path: {relative}")
            continue
        expected = source_entry.state if source_entry is not None else None
        if _file_state(source_root / relative) != expected:
            problems.append(f"source workspace changed concurrently: {relative}")

    if problems:
        print("refresh output publication refused:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return False

    for relative in changed:
        final_entry = isolated_after.get(relative)
        final_state = final_entry.state if final_entry is not None else None
        _write_output(
            isolated_root / relative,
            source_root / relative,
            final_state,
        )
    return True


def verify(root: Path = ROOT) -> int:
    source_before = workspace_entries(root)
    with isolated_workspace(root, source_entries=source_before) as isolated:
        result = _run_isolated_mode(isolated, "--check")
        _forward_result(result)
        return result.returncode


def refresh(root: Path = ROOT) -> int:
    source_workspace_sha256 = workspace_snapshot(root)
    source_before = workspace_entries(root)
    with isolated_workspace(root, source_entries=source_before) as isolated:
        isolated_before = workspace_entries(isolated)
        result = _run_isolated_mode(isolated, "--refresh")
        _forward_result(result)
        if result.returncode != 0:
            return result.returncode
        isolated_after = workspace_entries(isolated)
        return 0 if _publish_refresh_outputs(
            root,
            isolated,
            source_before,
            isolated_before,
            isolated_after,
            source_workspace_sha256,
        ) else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--refresh",
        action="store_true",
        help="Regenerate safe machine-derived artefacts in isolation, verify them, then publish allowed outputs.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Run deterministic drift and evidence validation in isolation without changing the caller workspace.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    isolated = os.environ.get(ISOLATED_ENV) == "1"
    if args.refresh:
        return _refresh_in_place(ROOT) if isolated else refresh(ROOT)
    return _verify_in_place(ROOT) if isolated else verify(ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
