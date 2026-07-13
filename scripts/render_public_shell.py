#!/usr/bin/env python3
"""Render the public Commonworld shell from the canonical seed catalog."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LAYER_LABELS = {
    "knowledge_data": "Wissen und offene Daten",
    "software_infrastructure": "Freie Software und Infrastruktur",
    "media_culture": "Offene Medien und Kultur",
    "learning_education": "Freies Lernen und Bildung",
    "communication_networks": "Kommunikation und Netze",
    "mixed_other": "Gemischte und weitere digitale Commons",
}

THEME_LAYERS = {
    "knowledge_data": {"knowledge", "open-data", "research", "documentation"},
    "software_infrastructure": {"free-software", "open-source", "infrastructure", "platform"},
    "media_culture": {"open-media", "culture", "archives", "creative-commons"},
    "learning_education": {"education", "open-educational-resources", "learning"},
    "communication_networks": {"communication", "community-network", "federation", "protocol"},
}


def derive_layer(record: dict) -> str:
    themes = set(record.get("themes", []))
    scores = {layer: len(themes & values) for layer, values in THEME_LAYERS.items()}
    maximum = max(scores.values(), default=0)
    winners = [layer for layer, score in scores.items() if score == maximum and score > 0]
    return winners[0] if len(winners) == 1 else "mixed_other"


def homepage(record: dict) -> str:
    values = [link.get("url") for link in record.get("links", []) if link.get("type") == "homepage"]
    if len(values) != 1 or not values[0].startswith("https://"):
        raise ValueError(f"{record.get('id')}: exactly one HTTPS homepage required")
    return values[0]


def load_records(root: Path = ROOT) -> list[dict]:
    manifest = json.loads((root / "catalog/catalog.json").read_text(encoding="utf-8"))
    records = [json.loads((root / "catalog" / path).read_text(encoding="utf-8")) for path in manifest["project_files"]]
    if len(records) != manifest["entry_count"]:
        raise ValueError("catalog manifest entry count mismatch")
    return records


def render_cards(records: list[dict]) -> str:
    cards: list[str] = []
    for record in records:
        identifier = html.escape(record["id"], quote=True)
        title = html.escape(record["title"])
        summary = html.escape(record["summary"])
        label = html.escape(LAYER_LABELS[derive_layer(record)])
        url = html.escape(homepage(record), quote=True)
        cards.append(
            f'''        <article class="catalog-card" id="project-{identifier}" data-commonproject-id="{identifier}">
          <p class="catalog-kind">Digital · {label}</p>
          <h3>{title}</h3>
          <p>{summary}</p>
          <div class="catalog-actions">
            <button class="catalog-select" type="button" data-commonproject-id="{identifier}" aria-pressed="false">Im Fokus öffnen</button>
            <a href="{url}" rel="external noreferrer">Offizielle Seite <span aria-hidden="true">↗</span></a>
          </div>
        </article>'''
        )
    return "\n".join(cards)


def render_shell(root: Path = ROOT) -> str:
    records = load_records(root)
    paths = "\n".join(
        f'              <circle id="sphere-path-{index}" cx="320" cy="320" r="{radius}" />'
        for index, radius in enumerate((268, 252, 236, 220, 204, 188), start=1)
    )
    return f'''<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="dark" />
    <meta name="referrer" content="strict-origin-when-cross-origin" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob: https://tiles.openfreemap.org; connect-src 'self' https://tiles.openfreemap.org; font-src 'self' data: https://tiles.openfreemap.org; worker-src 'self' blob:; child-src blob:; object-src 'none'; base-uri 'self'; form-action 'none';" />
    <meta name="description" content="Commonworld macht Commons weltweit, regional, lokal und digital auf einem gemeinsamen Globus sichtbar." />
    <title>commonworld — Commons entdecken</title>
    <link rel="stylesheet" href="./assets/vendor/maplibre-gl.css" />
    <link rel="stylesheet" href="./index.css" />
    <script src="./assets/vendor/maplibre-gl.js" defer></script>
    <script type="module" src="./assets/commonworld-app.js"></script>
  </head>
  <body>
    <a class="skip-link" href="#catalog">Zur linearen Commons-Ansicht springen</a>
    <main class="shell">
      <header class="brand" aria-label="commonworld">
        <span class="brand-mark" aria-hidden="true"></span>
        <span>commonworld</span>
      </header>

      <section class="intro" aria-labelledby="title">
        <p class="kicker">Commons weltweit entdecken</p>
        <h1 id="title">Die gemeinsame Welt wird sichtbar.</h1>
        <p class="lede">Drehe und zoome den Globus. Die digitale Sphäre zeigt ortsunabhängige Commons, ohne ihnen erfundene Orte zu geben. Jede Auswahl bleibt im Globus, in den Schichten und in der linearen Ansicht dieselbe CommonProject-ID.</p>
      </section>

      <figure class="globe-stage" aria-labelledby="globe-caption" data-runtime-state="loading" data-map-renders="0" data-overlay-renders="0">
        <div id="map" class="globe-map" role="application" aria-label="Interaktiver Commonworld-Globus"></div>
        <svg id="digital-sphere" class="digital-sphere" viewBox="0 0 640 640" role="group" aria-labelledby="sphere-title">
          <title id="sphere-title">Digitale Commons-Sphäre mit sechs abgeleiteten Schichten</title>
          <defs>
            <radialGradient id="sphere-center-fade">
              <stop offset="0%" stop-color="black" />
              <stop offset="58%" stop-color="black" />
              <stop offset="78%" stop-color="white" />
              <stop offset="100%" stop-color="white" />
            </radialGradient>
            <mask id="sphere-mask"><rect width="640" height="640" fill="url(#sphere-center-fade)" /></mask>
            <g id="sphere-paths" fill="none">
{paths}
            </g>
          </defs>
          <g id="sphere-streams" mask="url(#sphere-mask)" aria-hidden="true"></g>
          <circle id="sphere-edge-control" class="sphere-edge-control" cx="320" cy="320" r="276" fill="none" stroke="transparent" stroke-width="28" pointer-events="stroke" role="button" tabindex="0" aria-label="Digitale Commons-Schichten öffnen"></circle>
        </svg>
        <button id="layer-view-button" class="layer-view-button" type="button" aria-controls="layer-panel" aria-expanded="false">Digitale Schichten</button>
        <p id="map-status" class="map-status" role="status">Interaktiver Globus wird geladen. Die lineare Ansicht bleibt jederzeit verfügbar.</p>
        <noscript><p class="map-status map-status-static">JavaScript ist deaktiviert. Alle zehn Commons sind in der linearen Ansicht vollständig erreichbar.</p></noscript>

        <aside id="layer-panel" class="layer-panel" aria-labelledby="layer-title" hidden>
          <div class="panel-heading">
            <div><p class="kicker">Digitale Sphäre</p><h2 id="layer-title">Sechs Schichten, zehn Identitäten</h2></div>
            <button id="layer-close" class="icon-button" type="button" aria-label="Schichtansicht schließen">×</button>
          </div>
          <p>Die Schichten werden aus Themen und digitaler Präsenz abgeleitet. Sie sind keine zweite Katalogwahrheit.</p>
          <div id="layer-buttons" class="layer-buttons" aria-label="Digitale Schichten filtern"></div>
          <div id="layer-projects" class="layer-projects" aria-label="Commons in der gewählten Schicht"></div>
        </aside>
        <figcaption id="globe-caption">Erde → Großregion → Region → lokaler Zusammenhang → Commons</figcaption>
      </figure>

      <section class="status" aria-labelledby="status-title">
        <h2 id="status-title">Der erste interaktive Globus ist gebaut.</h2>
        <p>MapLibre GL JS 5.24.0 trägt Globus, Kamera und semantischen Zoom. OpenFreeMap liefert die Basiskarte; die zehn digitalen Commons bleiben bewusst ohne geografische Koordinaten und sind vollständig in der linearen Ansicht erreichbar.</p>
      </section>

      <section id="project-focus" class="project-focus" tabindex="-1" aria-labelledby="focus-title" hidden>
        <div class="panel-heading"><div><p id="focus-kind" class="kicker"></p><h2 id="focus-title"></h2></div><button id="focus-close" class="icon-button" type="button" aria-label="Fokus schließen">×</button></div>
        <p id="focus-summary" class="focus-summary"></p>
        <div class="focus-grid">
          <section><h3>Themen</h3><ul id="focus-themes"></ul></section>
          <section><h3>Möglichkeiten</h3><ul id="focus-actions"></ul></section>
          <section><h3>Digitale Präsenz</h3><p id="focus-digital"></p></section>
          <section><h3>Offizielle Links</h3><ul id="focus-links"></ul></section>
          <section><h3>Quellen</h3><ul id="focus-sources"></ul></section>
          <section><h3>Kuration</h3><p id="focus-curation"></p></section>
        </div>
      </section>

      <section class="catalog" id="catalog" aria-labelledby="catalog-title">
        <div class="catalog-heading">
          <p class="kicker">10 geprüfte Startdatensätze</p>
          <h2 id="catalog-title">Erste öffentliche Commons</h2>
          <p>Diese Einträge werden direkt aus dem kanonischen öffentlichen Katalog gerendert. Digitale Commons erhalten keine erfundenen Orte.</p>
        </div>
        <div class="catalog-grid">
{render_cards(records)}
        </div>
        <p class="catalog-meta">Kanonische Daten: <a href="./catalog/catalog.json">öffentlichen Katalog öffnen</a> · Nächste Quellenprüfung: 12. Oktober 2026</p>
      </section>
    </main>
  </body>
</html>
'''


def main() -> int:
    target = ROOT / "index.html"
    target.write_text(render_shell(ROOT), encoding="utf-8")
    print("commonworld public shell rendered from seed catalog")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
