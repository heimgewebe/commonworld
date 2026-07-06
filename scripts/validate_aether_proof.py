#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.validate_contracts import iter_project_examples, validate_all
import json

def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)

def proof_dir(root: Path = ROOT) -> Path:
    return root / 'proofs' / 'aether'

def expected_proof_files(root: Path = ROOT) -> tuple[Path, ...]:
    directory = proof_dir(root)
    return (directory / 'index.html', directory / 'aether.css', directory / 'aether.js', directory / 'README.md')

def load_projects(root: Path = ROOT) -> list[dict[str, Any]]:
    return [load_json(path) for path in iter_project_examples(root)]

def is_aether_project(project: dict[str, Any]) -> bool:
    return project.get('sphere') == 'digital' or project.get('location', {}).get('mode') == 'hidden'

def aether_projects(root: Path = ROOT) -> list[dict[str, Any]]:
    return [project for project in load_projects(root) if is_aether_project(project)]

def validate_aether_projection(projects: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    aether_project_list = [project for project in projects if is_aether_project(project)]
    if not aether_project_list:
        errors.append('aether proof must have at least one digital or hidden-location project')
        return errors
    by_id = {project['id']: project for project in aether_project_list}
    if 'openstreetmap' not in by_id:
        errors.append('openstreetmap must appear in the Aether proof')
    if 'neighborhood-repair-circle-fixture' in by_id:
        errors.append('place fixture must stay out of the Aether proof')
    for project in aether_project_list:
        location = project.get('location', {})
        if location.get('mode') == 'hidden' and 'coordinates' in location:
            errors.append(f"{project['id']} hidden Aether project must not include coordinates")
        if project.get('sphere') == 'digital' and location.get('precision') != 'none':
            errors.append(f"{project['id']} digital Aether project must use precision none")
        if project.get('handoff', {}).get('enabled') is not False:
            errors.append(f"{project['id']} Aether handoff must stay disabled in the proof")
    return errors

def validate_proof_surface(html: str, css: str, js: str, readme: str) -> list[str]:
    errors: list[str] = []
    html_tokens = ('Focused digital Commons proof','data-breadcrumb','data-aether-list','data-aether-count','data-active-branch','data-active-handoff','one active branch','no hairball','no map route','weltgewebe write path')
    css_tokens = ('.aether-shell','.aether-breadcrumb','.branch-rail','.active-branch','.aether-card','.evidence-pill','.handoff-lock')
    js_tokens = ('SEED_MANIFEST_URL','../mixed-node/seed-projects.json','filterAetherProjects','project.sphere === "digital"','project.location?.mode === "hidden"','sortAetherProjects','setActiveBranch','aria-current','aria-expanded','handoffLabel','Locked until weltgewebe project identity exists','renderSources')
    for token in html_tokens:
        if token not in html:
            errors.append(f'aether proof HTML missing {token}')
    for token in css_tokens:
        if token not in css:
            errors.append(f'aether proof CSS missing {token}')
    for token in js_tokens:
        if token not in js:
            errors.append(f'aether proof JS missing {token}')
    for boundary in ('No backend','No public submissions','No map route','No weltgewebe write path'):
        if boundary not in readme:
            errors.append(f'aether proof README must state boundary: {boundary}')
    if 'maplibre' in js.casefold():
        errors.append('aether proof JS must not depend on MapLibre')
    return errors

def validate_aether_proof(root: Path = ROOT) -> list[str]:
    errors = validate_all(root)
    missing_files: list[Path] = []
    for path in expected_proof_files(root):
        if not path.is_file():
            errors.append(f'missing aether proof file: {path.relative_to(root)}')
            missing_files.append(path)
    if missing_files:
        return errors
    directory = proof_dir(root)
    html = (directory / 'index.html').read_text(encoding='utf-8')
    css = (directory / 'aether.css').read_text(encoding='utf-8')
    js = (directory / 'aether.js').read_text(encoding='utf-8')
    readme = (directory / 'README.md').read_text(encoding='utf-8')
    errors.extend(validate_proof_surface(html, css, js, readme))
    errors.extend(validate_aether_projection(load_projects(root)))
    return errors

def main() -> int:
    errors = validate_aether_proof(ROOT)
    if errors:
        for error in errors:
            print(f'ERROR: {error}', file=sys.stderr)
        return 1
    print('commonworld Aether proof validation ok')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
