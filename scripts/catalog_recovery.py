#!/usr/bin/env python3
"""Deterministic, bounded no-JavaScript catalogue recovery surfaces."""

from __future__ import annotations

import copy
import gzip
import hashlib
import html
import json
import math
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from scripts.commonworld_geo import public_locations
from scripts.commonworld_i18n import ACTION_LABELS_EN, action_label, localize_records
from scripts.public_cache import asset_version

ROOT = Path(__file__).resolve().parents[1]
PAGE_SIZE = 24
RECOVERY_LOCALES = ("de", "en")
GENERATED_MARKER = "commonworld.catalog_recovery.v1"


class TagCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.start_tags = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start_tags += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.start_tags += 1


def gzip_size(payload: bytes) -> int:
    return len(gzip.compress(payload, compresslevel=9, mtime=0))


def page_count(entry_count: int) -> int:
    if not isinstance(entry_count, int) or entry_count < 1:
        raise ValueError("catalogue recovery requires a positive entry count")
    return math.ceil(entry_count / PAGE_SIZE)


def page_records(records: list[dict], number: int) -> list[dict]:
    count = page_count(len(records))
    if not isinstance(number, int) or number < 1 or number > count:
        raise ValueError(f"catalogue recovery page must be between 1 and {count}")
    start = (number - 1) * PAGE_SIZE
    return records[start:start + PAGE_SIZE]


def index_relative_path(locale: str, number: int) -> Path:
    if locale not in RECOVERY_LOCALES:
        raise ValueError(f"unsupported recovery locale: {locale}")
    prefix = Path("catalog") if locale == "en" else Path("catalog/de")
    return prefix / "index.html" if number == 1 else prefix / "pages" / f"{number}.html"


def project_relative_path(locale: str, identifier: str) -> Path:
    if locale not in RECOVERY_LOCALES or re.fullmatch(r"[a-z][a-z0-9-]{2,95}", identifier) is None:
        raise ValueError("invalid recovery project path")
    prefix = Path("catalog/projects") if locale == "en" else Path("catalog/de/projects")
    return prefix / f"{identifier}.html"


def index_url(locale: str, number: int) -> str:
    if number < 1:
        raise ValueError("recovery page number must be positive")
    prefix = "/catalog" if locale == "en" else "/catalog/de"
    return f"{prefix}/" if number == 1 else f"{prefix}/pages/{number}.html"


def project_url(locale: str, identifier: str) -> str:
    relative = project_relative_path(locale, identifier)
    return f"/{relative.as_posix()}"


def _page_copy(locale: str) -> dict[str, str]:
    if locale == "de":
        return {
            "catalog": "Commonworld-Katalog",
            "description": "Begrenzte, statische Katalogseiten für den Zugriff ohne JavaScript.",
            "back": "← Zum Globus",
            "page": "Seite {number} von {count}",
            "previous": "← Vorherige Seite",
            "next": "Nächste Seite →",
            "project": "Projektseite",
            "json": "Kanonisches JSON",
            "sources": "Quellen",
            "details": "Katalogangaben",
            "themes": "Themen",
            "actions": "Möglichkeiten",
            "locations": "Öffentliche Orte",
            "no_public_location": "Keine öffentliche Geometrie",
            "activity": "Betriebszustand",
            "reviewed": "Redaktionell geprüft",
            "next_review": "Nächste Prüfung",
            "official": "Offizielle und belegte Links",
            "all_entries": "Alle Einträge sind alphabetisch nach stabiler CommonProject-ID verteilt. Jede Seite enthält höchstens 24 Einträge.",
        }
    return {
        "catalog": "Commonworld catalog",
        "description": "Bounded static catalog pages for access without JavaScript.",
        "back": "← Back to the globe",
        "page": "Page {number} of {count}",
        "previous": "← Previous page",
        "next": "Next page →",
        "project": "Project page",
        "json": "Canonical JSON",
        "sources": "Sources",
        "details": "Catalog details",
        "themes": "Themes",
        "actions": "Ways to engage",
        "locations": "Public locations",
        "no_public_location": "No public geometry",
        "activity": "Operating status",
        "reviewed": "Editorially reviewed",
        "next_review": "Next review",
        "official": "Official and evidenced links",
        "all_entries": "All entries are distributed alphabetically by stable CommonProject ID. Each page contains at most 24 entries.",
    }


def _document(*, locale: str, title: str, description: str, canonical_url: str, body: str, root: Path) -> str:
    alternate_locale = "de" if locale == "en" else "en"
    if canonical_url.startswith("/catalog/projects/"):
        alternate_url = canonical_url.replace("/catalog/projects/", "/catalog/de/projects/")
    elif canonical_url.startswith("/catalog/de/projects/"):
        alternate_url = canonical_url.replace("/catalog/de/projects/", "/catalog/projects/")
    else:
        alternate_url = "/catalog/de/" if locale == "en" else "/catalog/"
    return f'''<!doctype html>
<html lang="{locale}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="dark" />
    <meta name="referrer" content="strict-origin-when-cross-origin" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'none';" />
    <meta name="description" content="{html.escape(description, quote=True)}" />
    <link rel="canonical" href="{html.escape(canonical_url, quote=True)}" />
    <link rel="alternate" hreflang="{alternate_locale}" href="{html.escape(alternate_url, quote=True)}" />
    <link rel="icon" href="/assets/commonworld-mark.svg?v={asset_version('assets/commonworld-mark.svg', root)}" type="image/svg+xml" />
    <link rel="stylesheet" href="/index.css?v={asset_version('index.css', root)}" />
    <title>{html.escape(title)}</title>
  </head>
  <body class="method-page" data-catalog-recovery="{GENERATED_MARKER}">
{body}
  </body>
</html>
'''


def render_index(records: list[dict], locale: str, number: int, root: Path = ROOT) -> str:
    from scripts.render_public_shell import render_cards

    copy_text = _page_copy(locale)
    total_pages = page_count(len(records))
    selected = page_records(records, number)
    cards = render_cards(
        selected,
        interactive=False,
        locale=locale,
        project_page_url=lambda identifier: project_url(locale, identifier),
        project_json_url=lambda identifier: f"/catalog/projects/{identifier}.json",
    )
    nav_links = []
    if number > 1:
        nav_links.append(f'<a rel="prev" href="{index_url(locale, number - 1)}">{copy_text["previous"]}</a>')
    if number < total_pages:
        nav_links.append(f'<a rel="next" href="{index_url(locale, number + 1)}">{copy_text["next"]}</a>')
    navigation = " · ".join(nav_links)
    page_label = copy_text["page"].format(number=number, count=total_pages)
    body = f'''    <main>
      <p class="kicker">Commonworld</p>
      <h1>{copy_text["catalog"]}</h1>
      <p><a class="secondary-back-link" href="{'/de.html' if locale == 'de' else '/'}">{copy_text["back"]}</a></p>
      <p>{copy_text["all_entries"]}</p>
      <nav aria-label="{html.escape(page_label, quote=True)}"><p><strong>{html.escape(page_label)}</strong>{' · ' + navigation if navigation else ''}</p></nav>
      <div class="catalog-grid" data-recovery-page="{number}" data-recovery-page-size="{PAGE_SIZE}">
{cards}
      </div>
      <nav aria-label="{html.escape(page_label, quote=True)}"><p>{navigation}</p></nav>
    </main>'''
    return _document(
        locale=locale,
        title=f'{copy_text["catalog"]} — {page_label}',
        description=copy_text["description"],
        canonical_url=index_url(locale, number),
        body=body,
        root=root,
    )


def _list(values: list[str]) -> str:
    return "".join(f"<li>{html.escape(str(value))}</li>" for value in values)


def render_project(record: dict, locale: str, root: Path = ROOT) -> str:
    copy_text = _page_copy(locale)
    identifier = record["id"]
    locations = public_locations(record)
    location_items = [location.get("label", "") for location in locations if location.get("label")]
    links = [
        link for link in record.get("links", [])
        if isinstance(link, dict) and isinstance(link.get("url"), str) and link["url"].startswith("https://")
    ]
    sources = [
        source for source in record.get("provenance", {}).get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("url"), str) and source["url"].startswith("https://")
    ]
    link_markup = "".join(
        f'<li><a href="{html.escape(link["url"], quote=True)}" rel="external noreferrer">{html.escape(link.get("label", link["url"]))}</a></li>'
        for link in links
    )
    source_markup = "".join(
        f'<li><a href="{html.escape(source["url"], quote=True)}" rel="external noreferrer">{html.escape(source.get("label", source["url"]))}</a>'
        f'{" — " + html.escape(source["retrieved_at"]) if source.get("retrieved_at") else ""}</li>'
        for source in sources
    )
    curation = record.get("curation", {})
    activity = record.get("activity", {})
    body = f'''    <main>
      <p class="kicker">Commonworld · {copy_text["project"]}</p>
      <h1>{html.escape(record["title"])}</h1>
      <p><a class="secondary-back-link" href="{index_url(locale, 1)}">← {copy_text["catalog"]}</a></p>
      <p>{html.escape(record["summary"])}</p>
      <section>
        <h2>{copy_text["details"]}</h2>
        <dl>
          <dt>CommonProject.id</dt><dd><code>{html.escape(identifier)}</code></dd>
          <dt>{copy_text["activity"]}</dt><dd>{html.escape(activity.get("status", "unknown"))}</dd>
          <dt>{copy_text["reviewed"]}</dt><dd>{html.escape(curation.get("reviewed_at", ""))}</dd>
          <dt>{copy_text["next_review"]}</dt><dd>{html.escape(curation.get("next_review_at", ""))}</dd>
        </dl>
      </section>
      <section><h2>{copy_text["themes"]}</h2><ul>{_list(record.get("themes", []))}</ul></section>
      <section><h2>{copy_text["actions"]}</h2><ul>{_list(record.get("actions", []))}</ul></section>
      <section><h2>{copy_text["locations"]}</h2><ul>{_list(location_items) if location_items else f'<li>{copy_text["no_public_location"]}</li>'}</ul></section>
      <section><h2>{copy_text["official"]}</h2><ul>{link_markup}</ul></section>
      <section><h2>{copy_text["sources"]}</h2><ul>{source_markup}</ul></section>
      <p><a href="/catalog/projects/{html.escape(identifier, quote=True)}.json" type="application/json">{copy_text["json"]}</a></p>
    </main>'''
    canonical = project_url(locale, identifier)
    return _document(
        locale=locale,
        title=f'{record["title"]} — Commonworld',
        description=record["summary"],
        canonical_url=canonical,
        body=body,
        root=root,
    )


def load_records(root: Path = ROOT) -> list[dict]:
    manifest = json.loads((root / "catalog/catalog.json").read_text(encoding="utf-8"))
    records = [
        json.loads((root / "catalog" / relative).read_text(encoding="utf-8"))
        for relative in manifest["project_files"]
    ]
    records.sort(key=lambda record: record["id"])
    if len(records) != manifest.get("entry_count"):
        raise ValueError("catalogue recovery manifest count mismatch")
    return records


def _clear_generated(root: Path) -> None:
    targets = [root / "catalog/index.html"]
    targets.extend((root / "catalog/pages").glob("*.html") if (root / "catalog/pages").is_dir() else [])
    targets.extend((root / "catalog/projects").glob("*.html"))
    targets.extend((root / "catalog/de").rglob("*.html") if (root / "catalog/de").is_dir() else [])
    for path in targets:
        if path.is_file():
            path.unlink()


def build_recovery(root: Path = ROOT) -> tuple[Path, ...]:
    records = load_records(root)
    _clear_generated(root)
    written: list[Path] = []
    for locale in RECOVERY_LOCALES:
        localized = localize_records(records, locale, root)
        localized.sort(key=lambda record: record["id"])
        for number in range(1, page_count(len(localized)) + 1):
            path = root / index_relative_path(locale, number)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_index(localized, locale, number, root), encoding="utf-8")
            written.append(path)
        for record in localized:
            path = root / project_relative_path(locale, record["id"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_project(record, locale, root), encoding="utf-8")
            written.append(path)
    return tuple(sorted(written))


def localize_fixture_records(records: list[dict], overlay: dict, locale: str, root: Path = ROOT) -> list[dict]:
    localized = copy.deepcopy(records)
    translations = overlay.get("projects", {}) if locale == "en" else {}
    for record in localized:
        translation = translations.get(record["id"], {})
        if locale == "en":
            record["title"] = translation["title"]
            record["summary"] = translation["summary"]
            labels = translation.get("geographic_labels", {})
            for location in record.get("presence", {}).get("geographic", []):
                if location.get("id") in labels:
                    location["label"] = labels[location["id"]]
            digital = record.get("presence", {}).get("digital", {})
            if digital.get("available") is True and translation.get("digital_label"):
                digital["label"] = translation["digital_label"]
            for link in record.get("links", []):
                if link.get("type") in ACTION_LABELS_EN:
                    link["label"] = action_label(link["type"], "en", str(link.get("label") or ""), root)
            for index, source in enumerate(record.get("provenance", {}).get("sources", []), start=1):
                hostname = (urlparse(source.get("url", "")).hostname or "").removeprefix("www.")
                source["label"] = f'{source.get("label") or f"Source {index}"} · {hostname}'
        record["_content_locale"] = locale
        record["_title_locale"] = locale
    localized.sort(key=lambda record: record["id"])
    return localized


def payload_metrics(markup: str) -> dict[str, int]:
    payload = markup.encode("utf-8")
    parser = TagCounter()
    parser.feed(markup)
    return {
        "raw_bytes": len(payload),
        "gzip_bytes": gzip_size(payload),
        "start_tags": parser.start_tags,
        "catalog_cards": markup.count('class="catalog-card"'),
    }


def inventory_digest(paths: list[str]) -> str:
    payload = (json.dumps(paths, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
