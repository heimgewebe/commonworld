#!/usr/bin/env python3
"""Measure static Commonworld catalogue delivery costs deterministically."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATTERN = re.compile(r"export const BOOTSTRAP_RECORDS = (\[.*\]);\s*$", re.DOTALL)


class TagCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.start_tags = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start_tags += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start_tags += 1


def gzip_size(data: bytes) -> int:
    return len(gzip.compress(data, compresslevel=9, mtime=0))


def load_bootstrap_records(path: Path) -> tuple[bytes, list[dict]]:
    raw = path.read_bytes()
    match = BOOTSTRAP_PATTERN.search(raw.decode('utf-8'))
    if not match:
        raise ValueError(f'cannot parse BOOTSTRAP_RECORDS from {path}')
    records = json.loads(match.group(1))
    if not isinstance(records, list):
        raise ValueError('BOOTSTRAP_RECORDS is not an array')
    return raw, records


def measure(root: Path = ROOT) -> dict:
    manifest_path = root / 'catalog/catalog.json'
    bootstrap_path = root / 'assets/commonworld-bootstrap-catalog.mjs'
    app_path = root / 'assets/commonworld-app.js'
    html_path = root / 'index.html'

    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    project_paths = [root / 'catalog' / item for item in manifest['project_files']]
    project_raw = [path.read_bytes() for path in project_paths]
    project_records = [json.loads(raw) for raw in project_raw]
    bootstrap_raw, bootstrap_records = load_bootstrap_records(bootstrap_path)
    app_raw = app_path.read_bytes()
    html_raw = html_path.read_bytes()

    project_ids = [record['id'] for record in project_records]
    bootstrap_ids = [record['id'] for record in bootstrap_records]
    if project_ids != bootstrap_ids:
        raise ValueError('bootstrap identities do not match canonical project order')
    if project_records != bootstrap_records:
        raise ValueError('bootstrap records do not match canonical CommonProject content')

    parser = TagCounter()
    parser.feed(html_raw.decode('utf-8'))
    app_text = app_raw.decode('utf-8')
    runtime_project_fetch_enabled = bool(
        './catalog/catalog.json' in app_text
        or 'manifest.project_files.map' in app_text
        or '/catalog/projects/' in app_text
    )
    fetched_project_bytes = sum(len(raw) for raw in project_raw) if runtime_project_fetch_enabled else 0
    fetched_project_gzip_bytes = sum(gzip_size(raw) for raw in project_raw) if runtime_project_fetch_enabled else 0
    fetched_manifest_bytes = len(manifest_raw) if runtime_project_fetch_enabled else 0
    fetched_manifest_gzip_bytes = gzip_size(manifest_raw) if runtime_project_fetch_enabled else 0

    return {
        'schema_version': 1,
        'kind': 'commonworld_catalog_delivery_static_metrics',
        'entry_count': manifest['entry_count'],
        'identity_order_sha256': hashlib.sha256(json.dumps(project_ids, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest(),
        'bootstrap': {
            'raw_bytes': len(bootstrap_raw),
            'gzip_bytes': gzip_size(bootstrap_raw),
            'raw_bytes_per_record': round(len(bootstrap_raw) / len(project_ids), 2),
            'gzip_bytes_per_record': round(gzip_size(bootstrap_raw) / len(project_ids), 2),
        },
        'canonical_projects': {
            'file_count': len(project_paths),
            'raw_bytes': sum(len(raw) for raw in project_raw),
            'gzip_bytes_individual_files': sum(gzip_size(raw) for raw in project_raw),
        },
        'manifest': {
            'raw_bytes': len(manifest_raw),
            'gzip_bytes': gzip_size(manifest_raw),
        },
        'html': {
            'raw_bytes': len(html_raw),
            'gzip_bytes': gzip_size(html_raw),
            'start_tag_count': parser.start_tags,
            'catalog_card_instances': html_raw.count(b'class="catalog-card"'),
            'interactive_catalog_cards': html_raw.count(b'class="catalog-select"'),
            'noscript_catalogs': html_raw.count(b'class="noscript-catalog"'),
        },
        'runtime_verification_fetch': {
            'enabled': runtime_project_fetch_enabled,
            'project_request_count': len(project_paths) if runtime_project_fetch_enabled else 0,
            'duplicate_identity_payload_count': len(project_ids) if runtime_project_fetch_enabled else 0,
            'raw_bytes': fetched_project_bytes + fetched_manifest_bytes,
            'gzip_bytes': fetched_project_gzip_bytes + fetched_manifest_gzip_bytes,
        },
        'catalog_initial_delivery': {
            'raw_bytes': len(bootstrap_raw) + fetched_project_bytes + fetched_manifest_bytes,
            'gzip_bytes': gzip_size(bootstrap_raw) + fetched_project_gzip_bytes + fetched_manifest_gzip_bytes,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = measure(args.root.resolve())
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    print(payload, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
