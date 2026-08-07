#!/usr/bin/env python3
"""Build one path-keyed public release snapshot and its fresh 404 probe manifest."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.locale_registry import locales_with_status, surface_file
from scripts.public_cache import (
    RELEASE_ID_PLACEHOLDER,
    canonicalize_page_release,
    finalize_page_release,
    page_build_metadata,
    page_release_id,
)

PUBLIC_PAGES = tuple(
    surface_file(locale, surface, ROOT)
    for locale in locales_with_status("released", "candidate", root=ROOT)
    for surface in ("index", "method", "proposal")
)
SNAPSHOT_ROOT_FILES = PUBLIC_PAGES + ("index.css", "LICENSE", "LICENSE-DATA.md")
SNAPSHOT_TREES = ("assets", "catalog", "contracts/commonworld", ".well-known")
MANIFEST_RELATIVE = "assets/commonworld-page-builds.json"
TARGET = ROOT / MANIFEST_RELATIVE
RELEASES_ROOT = ROOT / "releases"
NOT_FOUND_TARGET = ROOT / "404.html"
RELEASE_HASH_DOMAIN = b"commonworld.release_snapshot.v1\0"


def snapshot_files(root: Path = ROOT, *, include_manifest: bool = True) -> tuple[Path, ...]:
    files: set[Path] = set()
    for relative in SNAPSHOT_ROOT_FILES:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing public snapshot file: {relative}")
        files.add(path)
    for relative in SNAPSHOT_TREES:
        directory = root / relative
        if not directory.is_dir():
            raise ValueError(f"missing public snapshot tree: {relative}")
        files.update(path for path in directory.rglob("*") if path.is_file())
    if not include_manifest:
        files.discard(root / MANIFEST_RELATIVE)
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def compute_release_id(root: Path = ROOT) -> str:
    digest = hashlib.sha256(RELEASE_HASH_DOMAIN)
    for path in snapshot_files(root, include_manifest=False):
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if relative in PUBLIC_PAGES:
            data = canonicalize_page_release(data.decode("utf-8")).encode("utf-8")
        encoded = relative.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()[:20]


def build_manifest(root: Path = ROOT, release_id: str | None = None) -> dict[str, object]:
    pages: dict[str, str] = {}
    releases: set[str] = set()
    for relative in PUBLIC_PAGES:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"missing rendered public page: {relative}")
        markup = path.read_text(encoding="utf-8")
        declared_page, build = page_build_metadata(markup)
        if declared_page != relative:
            raise ValueError(f"public page identity mismatch: {relative} declares {declared_page}")
        pages[relative] = build
        releases.add(page_release_id(markup))
    if len(releases) != 1:
        raise ValueError("public pages do not share one release identity")
    declared_release = releases.pop()
    if release_id is not None and declared_release != release_id:
        raise ValueError("public page release identity does not match computed snapshot")
    return {
        "kind": "commonworld.release_manifest",
        "pages": pages,
        "release_id": declared_release,
        "schema_version": 2,
    }


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def render_not_found(manifest: dict[str, object]) -> str:
    payload = canonical_json(manifest)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="robots" content="noindex" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none';" />
    <title>Commonworld — release recovery</title>
    <style>body{{font:16px/1.5 system-ui,sans-serif;max-width:42rem;margin:4rem auto;padding:0 1rem}}a{{color:inherit}}</style>
  </head>
  <body>
    <main>
      <h1>Commonworld</h1>
      <p>This path is not a public page. Return to the current globe release.</p>
      <p><a href="/">Open Commonworld</a></p>
    </main>
    <!-- commonworld-release-manifest:{payload} -->
  </body>
</html>
"""


def finalize_pages(root: Path, release_id: str) -> None:
    for relative in PUBLIC_PAGES:
        path = root / relative
        markup = path.read_text(encoding="utf-8")
        if page_release_id(markup) != RELEASE_ID_PLACEHOLDER:
            raise ValueError(f"public page was not rendered with a release placeholder: {relative}")
        path.write_text(finalize_page_release(markup, release_id), encoding="utf-8")


def _snapshot_sources(root: Path) -> dict[Path, Path]:
    return {
        source.relative_to(root): source
        for source in snapshot_files(root, include_manifest=True)
    }


def assert_current_snapshot_immutable(root: Path, target_root: Path) -> None:
    """Fail closed if a content-addressed release path already contains different bytes."""
    expected = _snapshot_sources(root)
    actual = {
        path.relative_to(target_root)
        for path in target_root.rglob("*")
        if path.is_file()
    }
    expected_paths = set(expected)
    if actual != expected_paths:
        missing = sorted(path.as_posix() for path in expected_paths - actual)
        extra = sorted(path.as_posix() for path in actual - expected_paths)
        raise ValueError(
            "immutable release snapshot file set drift: "
            f"missing={missing[:5]} extra={extra[:5]}"
        )
    for relative, source in expected.items():
        target = target_root / relative
        if target.read_bytes() != source.read_bytes():
            raise ValueError(
                f"immutable release snapshot content drift: {relative.as_posix()}"
            )


def build_snapshot(root: Path, release_id: str) -> Path:
    """Materialize one immutable snapshot without deleting historical releases.

    Hash-named releases are append-only Git artifacts. Keeping the common ancestor
    snapshot prevents independent branches from turning every release file into a
    competing rename/delete pair when they are later combined.
    """
    releases_root = root / "releases"
    releases_root.mkdir(parents=True, exist_ok=True)
    target_root = releases_root / release_id
    if target_root.exists():
        if not target_root.is_dir():
            raise ValueError(f"release snapshot path is not a directory: {release_id}")
        assert_current_snapshot_immutable(root, target_root)
        return target_root

    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{release_id}.staging-", dir=releases_root)
    )
    try:
        for relative, source in _snapshot_sources(root).items():
            target = staging_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        staging_root.rename(target_root)
    except BaseException:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
    return target_root


def main() -> int:
    release_id = compute_release_id(ROOT)
    finalize_pages(ROOT, release_id)
    if compute_release_id(ROOT) != release_id:
        raise ValueError("release id is not stable after self-reference finalization")
    manifest = build_manifest(ROOT, release_id)
    TARGET.write_text(f"{canonical_json(manifest)}\n", encoding="utf-8")
    NOT_FOUND_TARGET.write_text(render_not_found(manifest), encoding="utf-8")
    snapshot = build_snapshot(ROOT, release_id)
    print(f"commonworld path-keyed public release {release_id} generated at {snapshot.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
