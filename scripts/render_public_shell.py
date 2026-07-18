#!/usr/bin/env python3
"""Render the public Commonworld globe-first shell from the canonical catalog."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ACTION_LINK_TYPES = {"visit", "use", "borrow", "learn", "contribute", "volunteer", "donate", "contact", "replicate"}

LAYER_LABELS = {
    "knowledge_data": "Wissen und offene Daten",
    "software_infrastructure": "Freie Software und Infrastruktur",
    "media_culture": "Offene Medien und Kultur",
    "learning_education": "Freies Lernen und Bildung",
    "communication_networks": "Kommunikation und Netze",
    "mixed_other": "Gemischte und weitere digitale Commons",
}

ORBIT_PROFILES = (
    ("knowledge_data", 316, 300, -8),
    ("software_infrastructure", 310, 282, 20),
    ("media_culture", 304, 268, 43),
    ("learning_education", 298, 288, -31),
    ("communication_networks", 292, 274, 63),
    ("mixed_other", 286, 294, -62),
)

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


def _valid_position(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(number, (int, float)) and not isinstance(number, bool) for number in value)
        and -180 <= value[0] <= 180
        and -90 <= value[1] <= 90
    )


def _valid_ring(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) >= 4
        and all(_valid_position(position) for position in value)
        and value[0] == value[-1]
    )


def _public_location(location: object) -> bool:
    if not isinstance(location, dict) or location.get("mode") == "hidden":
        return False
    geometry = location.get("geometry")
    if not isinstance(geometry, dict):
        return False
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    valid_geometry = (
        (geometry_type == "Point" and _valid_position(coordinates))
        or (geometry_type == "Polygon" and isinstance(coordinates, list) and bool(coordinates) and all(_valid_ring(ring) for ring in coordinates))
        or (
            geometry_type == "MultiPolygon"
            and isinstance(coordinates, list)
            and bool(coordinates)
            and all(isinstance(polygon, list) and bool(polygon) and all(_valid_ring(ring) for ring in polygon) for polygon in coordinates)
        )
    )
    if not valid_geometry:
        return False
    if location.get("mode") == "approximate":
        uncertainty = location.get("uncertainty_meters_min")
        return (
            geometry_type == "Point"
            and isinstance(uncertainty, (int, float))
            and not isinstance(uncertainty, bool)
            and uncertainty > 0
        )
    return location.get("mode") == "exact"


def public_locations(record: dict) -> list[dict]:
    locations = record.get("presence", {}).get("geographic", [])
    if not isinstance(locations, list):
        return []
    return [location for location in locations if _public_location(location)]


def presentation_label(record: dict) -> str:
    has_geo = bool(public_locations(record))
    has_digital = record.get("presence", {}).get("digital", {}).get("available") is True
    if has_geo and has_digital:
        return f"Vor Ort · Digital · {LAYER_LABELS[derive_layer(record)]}"
    if has_geo:
        return "Vor Ort"
    if has_digital:
        return f"Digital · {LAYER_LABELS[derive_layer(record)]}"
    return "Commons"


def location_summary(record: dict) -> str:
    locations = record.get("presence", {}).get("geographic", [])
    if not isinstance(locations, list) or not locations:
        return "Ortsunabhängige digitale Präsenz"
    public_count = len(public_locations(record))
    hidden_count = sum(1 for location in locations if location.get("mode") == "hidden")
    parts = []
    if public_count:
        parts.append(f"{public_count} {'öffentlicher Ort' if public_count == 1 else 'öffentliche Orte'}")
    if hidden_count:
        parts.append(f"{hidden_count} {'verborgener Ort' if hidden_count == 1 else 'verborgene Orte'}")
    return " · ".join(parts) or "Keine öffentliche Geometrie"


def load_records(root: Path = ROOT) -> list[dict]:
    manifest = json.loads((root / "catalog/catalog.json").read_text(encoding="utf-8"))
    records = [
        json.loads((root / "catalog" / relative).read_text(encoding="utf-8"))
        for relative in manifest["project_files"]
    ]
    if len(records) != manifest["entry_count"]:
        raise ValueError("catalog manifest entry count mismatch")
    return records


def render_cards(records: list[dict], *, interactive: bool = True) -> str:
    cards: list[str] = []
    for record in records:
        identifier = html.escape(record["id"], quote=True)
        title = html.escape(record["title"])
        summary = html.escape(record["summary"])
        label = html.escape(presentation_label(record))
        place = html.escape(location_summary(record))
        url = html.escape(homepage(record), quote=True)
        action_links = "\n".join(
            '              <a class="catalog-action-link" data-action-type="{}" href="{}" rel="external noreferrer">{} <span aria-hidden="true">↗</span></a>'.format(
                html.escape(link["type"], quote=True),
                html.escape(link["url"], quote=True),
                html.escape(link["label"]),
            )
            for link in record.get("links", [])
            if link.get("type") in ACTION_LINK_TYPES and link.get("type") in record.get("actions", [])
        )
        if action_links:
            action_links += "\n"
        action = (
            f'              <button class="catalog-select" type="button" '
            f'data-commonproject-id="{identifier}" aria-pressed="false">Öffnen</button>\n'
            if interactive
            else ""
        )
        cards.append(
            f'''          <article class="catalog-card" id="project-{identifier}" data-commonproject-id="{identifier}">
            <p class="catalog-kind">{label}</p>
            <h2>{title}</h2>
            <p>{summary}</p>
            <p class="catalog-location">{place}</p>
            <div class="catalog-actions">
{action}{action_links}              <a href="{url}" rel="external noreferrer">Offizielle Seite <span aria-hidden="true">↗</span></a>
              <a href="./catalog/projects/{identifier}.json" type="application/json">JSON</a>
            </div>
          </article>'''
        )
    return "\n".join(cards)


def render_shell(root: Path = ROOT) -> str:
    records = load_records(root)
    bootstrap = html.escape(json.dumps(records, ensure_ascii=False, separators=(",", ":")))
    paths = "\n".join(
        f'              <ellipse id="sphere-path-{index}" cx="320" cy="320" rx="{rx}" ry="{ry}" transform="rotate({rotation} 320 320)" />'
        for index, (_, rx, ry, rotation) in enumerate(ORBIT_PROFILES, start=1)
    )
    planes = "\n".join(
        f'              <g class="sphere-ring-plane" data-layer-id="{layer_id}" data-ring-index="{index - 1}">\n'
        f'                <use href="#sphere-path-{index}" class="sphere-layer-guide" data-layer-id="{layer_id}"></use>\n'
        f'              </g>'
        for index, (layer_id, _, _, _) in enumerate(ORBIT_PROFILES, start=1)
    )
    cards = render_cards(records)
    noscript_cards = render_cards(records, interactive=False)
    return f'''<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="color-scheme" content="dark" />
    <meta name="referrer" content="strict-origin-when-cross-origin" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob: https://tiles.openfreemap.org; connect-src 'self' https://tiles.openfreemap.org; font-src 'self' data: https://tiles.openfreemap.org; worker-src 'self' blob:; child-src blob:; object-src 'none'; base-uri 'self'; form-action 'none';" />
    <meta name="description" content="Commonworld macht Commons weltweit, regional, lokal und digital auf einem gemeinsamen Globus sichtbar." />
    <title>commonworld — Commons entdecken</title>
    <link rel="icon" href="./assets/commonworld-mark.svg" type="image/svg+xml" />
    <link rel="alternate" type="application/json" href="./catalog/catalog.json" title="Commonworld-Katalog" />
    <link rel="alternate" type="application/schema+json" href="./contracts/commonworld/project.schema.json" title="CommonProject-Schema" />
    <link rel="stylesheet" href="./assets/vendor/maplibre-gl.css" />
    <link rel="stylesheet" href="./index.css" />
    <script src="./assets/vendor/maplibre-gl.js" defer></script>
    <script type="module" src="./assets/commonworld-app.js"></script>
  </head>
  <body data-presentation="globe">
    <a class="skip-link" href="#text-view">Zur Textansicht springen</a>
    <template id="catalog-bootstrap">{bootstrap}</template>
    <main class="app-shell">
      <header class="topbar">
        <a class="brand" href="./" aria-label="commonworld – Globus zurücksetzen">
          <span class="brand-mark" aria-hidden="true"></span>
          <span>commonworld</span>
        </a>
        <div class="discovery-control">
          <div class="search-control" role="search">
            <label class="visually-hidden" for="commons-search">Commons suchen</label>
            <span class="search-symbol" aria-hidden="true">⌕</span>
            <input id="commons-search" type="search" inputmode="search" autocomplete="off" placeholder="Was möchtest du tun oder finden?" aria-controls="discovery-list" aria-expanded="false" />
            <button id="search-clear" class="search-clear" type="button" aria-label="Suche leeren" hidden>×</button>
          </div>
          <button id="filter-toggle" class="icon-button filter-toggle" type="button" aria-label="Suchergebnisse und Filter öffnen" aria-controls="discovery-panel" aria-expanded="false"><span aria-hidden="true">≡</span><span class="filter-toggle-label">Filter</span></button>
        </div>
        <a class="proposal-link" href="./propose.html"><span class="proposal-symbol" aria-hidden="true">+</span><span class="proposal-label">Commons vorschlagen</span></a>
        <button id="settings-toggle" class="icon-button settings-toggle" type="button" aria-label="Einstellungen öffnen" aria-controls="settings-panel" aria-expanded="false"><span aria-hidden="true">⚙</span></button>
      </header>

      <section id="discovery-panel" class="discovery-panel" aria-labelledby="discovery-title" hidden>
        <div class="discovery-heading">
          <div><p class="kicker">Entdecken</p><h2 id="discovery-title">Passende Commons</h2></div>
          <button id="discovery-close" class="icon-button" type="button" aria-label="Suchergebnisse schließen">×</button>
        </div>
        <div class="intent-filter-grid" aria-label="Commons filtern">
          <fieldset class="filter-presence-group"><legend>Präsenz</legend><label><input type="checkbox" id="filter-presence-geographic" name="presence" value="geographic" data-intent-filter="presence"> Vor Ort</label><label><input type="checkbox" id="filter-presence-digital" name="presence" value="digital" data-intent-filter="presence"> Digital</label></fieldset>
          <label><span>Aktion</span><select id="filter-action" data-intent-filter="action"><option value="">Alle Aktionen</option><option value="use">Nutzen</option><option value="borrow">Ausleihen</option><option value="learn">Lernen</option><option value="contribute">Mitmachen</option><option value="volunteer">Ehrenamtlich helfen</option><option value="donate">Spenden</option><option value="visit">Besuchen</option><option value="contact">Kontaktieren</option><option value="replicate">Übertragen</option></select></label>
          <label><span>Sprache</span><select id="filter-language" data-intent-filter="language"><option value="">Alle Angaben</option><option value="de">Deutsch</option><option value="unknown">Nicht angegeben</option></select></label>
          <label><span>Zugang</span><select id="filter-access" data-intent-filter="access"><option value="">Alle Zugänge</option><option value="public">Öffentlich</option><option value="membership">Mitgliedschaft</option><option value="restricted">Beschränkt</option><option value="unknown">Nicht angegeben</option></select></label>
          <label><span>Aktualität</span><select id="filter-freshness" data-intent-filter="freshness"><option value="">Jede Aktualität</option><option value="current">Aktuell geprüft</option><option value="stale">Prüfung fällig</option><option value="unknown">Nicht angegeben</option></select></label>
          <label><span>Kuration</span><select id="filter-curation" data-intent-filter="curation"><option value="">Jeder Status</option><option value="listed">Gelistet</option><option value="verified">Verifiziert</option><option value="featured">Hervorgehoben</option><option value="unknown">Nicht angegeben</option></select></label>
        </div>
        <div class="discovery-summary-row">
          <p id="discovery-count" class="discovery-count" role="status">{len(records)} Commons</p>
          <button id="filter-clear" class="quiet-button" type="button">Filter zurücksetzen</button>
        </div>
        <p id="discovery-empty" class="discovery-empty" hidden>Keine Commons entsprechen dieser Suche und Filterkombination.</p>
        <ol id="discovery-list" class="discovery-list" aria-label="Rangfolge der Commons-Suchergebnisse"></ol>
      </section>

      <section id="globe-surface" class="globe-surface" aria-label="Commonworld-Globus">
        <figure class="globe-stage" aria-labelledby="globe-caption" data-runtime-state="loading" data-visual-ready="false" data-view-phase="overview" data-map-renders="0" data-overlay-renders="0">
          <div id="map" class="globe-map" role="region" aria-label="Interaktiver Commonworld-Globus"></div>
          <svg id="digital-sphere" class="digital-sphere" viewBox="0 0 640 640" role="group" aria-labelledby="sphere-title">
            <title id="sphere-title">Digitale Commons-Sphäre aus Namen und deren Binärcode</title>
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
            <g id="sphere-rings" mask="url(#sphere-mask)" aria-hidden="true">
{planes}
            </g>
            <circle id="sphere-edge-control" class="sphere-edge-control" cx="320" cy="320" r="309" fill="none" stroke="transparent" stroke-width="34" pointer-events="stroke" role="button" tabindex="0" aria-label="Digitale Ebenen öffnen. Antippen oder Eingabetaste drücken."></circle>
            <circle class="sphere-edge-focus" cx="320" cy="320" r="309" aria-hidden="true"></circle>
          </svg>
          <div id="layer-stack-visual" class="layer-stack-visual" aria-hidden="true"></div>

          <button id="layer-view-button" class="layer-view-button" type="button" aria-controls="layer-panel" aria-expanded="false">Digitale Sphäre</button>

          <div class="orientation-bar" aria-label="Globusorientierung">
            <button id="globe-reset" type="button">Erde</button>
            <span aria-hidden="true">›</span>
            <span id="semantic-level">Gesamtansicht</span>
            <span id="semantic-summary" class="semantic-summary">Räumlich belegte Commons werden aus dem Katalog abgeleitet.</span>
          </div>

          <p id="map-status" class="map-status" role="status">Globus wird geladen. Die Textansicht bleibt verfügbar.</p>
          <p id="globe-results" class="globe-results" role="status">{len(records)} Commons im aktuellen Katalog.</p>

          <aside id="layer-panel" class="layer-panel" aria-labelledby="layer-title" hidden>
            <h2 id="layer-title" class="visually-hidden">Digitale Commons aus der Nähe</h2>
            <p class="visually-hidden">Dieselben Commons erscheinen mit ihren Namen und Binärcodes auf sechs horizontal wischbaren Bahnen.</p>
            <div class="layer-panel-controls">
              <button id="layer-search-toggle" class="icon-button layer-search-toggle" type="button" aria-label="Commons suchen und Bahnen filtern" aria-controls="layer-discovery" aria-expanded="false">⌕</button>
              <button id="layer-close" class="icon-button layer-close" type="button" aria-label="Zur Globusansicht zurückkehren">×</button>
            </div>
            <div id="layer-discovery" class="layer-discovery" hidden>
              <label for="layer-search">Commons in den digitalen Bahnen suchen</label>
              <div class="layer-search-field"><span aria-hidden="true">⌕</span><input id="layer-search" type="search" inputmode="search" autocomplete="off" placeholder="Commons suchen" /></div>
              <div id="layer-buttons" class="layer-buttons"></div>
            </div>
            <div id="layer-track-deck" class="layer-track-deck" aria-label="Horizontal wischbare digitale Commons-Bahnen"></div>
            <div id="layer-projects" class="layer-projects" hidden></div>
          </aside>

          <figcaption id="globe-caption" class="visually-hidden">Erde → Großregion → Region → lokaler Zusammenhang → Commons</figcaption>
        </figure>
      </section>

      <section id="text-view" class="text-view" tabindex="-1" aria-labelledby="text-title" hidden>
        <header class="text-header">
          <p class="kicker">Textansicht</p>
          <h1 id="text-title">Commons direkt durchsuchen</h1>
          <p>Dieselben Identitäten, Filter und Auswahlen wie im Globus – ohne räumliche Darstellung.</p>
          <p id="text-count" class="text-count">{len(records)} Commons</p>
        </header>
        <div class="text-layout">
          <aside class="text-filters" aria-labelledby="text-filter-title">
            <h2 id="text-filter-title">Filter und Schichten</h2>
            <button class="quiet-button text-discovery-open" type="button" data-open-discovery>Suchfilter öffnen</button>
            <div id="text-layer-buttons" class="layer-buttons"></div>
            <p class="machine-note">Maschinenlesbar: <a href="./catalog/catalog.json" type="application/json">Katalogmanifest</a> · <a href="./contracts/commonworld/project.schema.json" type="application/schema+json">Datenschema</a></p>
          </aside>
          <div>
            <p id="text-empty" class="text-empty" hidden>Keine Commons entsprechen dieser Auswahl.</p>
            <div id="catalog" class="catalog-grid" aria-live="polite">
{cards}
            </div>
          </div>
        </div>
      </section>

      <aside id="settings-panel" class="settings-panel" role="dialog" aria-modal="false" aria-labelledby="settings-title" hidden>
        <div class="panel-heading">
          <div><p class="kicker">Einstellungen</p><h2 id="settings-title">Darstellung</h2></div>
          <button id="settings-close" class="icon-button" type="button" aria-label="Einstellungen schließen">×</button>
        </div>
        <div class="presentation-choices" role="radiogroup" aria-label="Darstellung wählen">
          <button type="button" role="radio" aria-checked="true" data-presentation-choice="globe"><strong>Globus</strong><span>Räumlich entdecken und zoomen</span></button>
          <button type="button" role="radio" aria-checked="false" data-presentation-choice="text"><strong>Text</strong><span>Dieselben Commons als Liste</span></button>
        </div>
        <section class="settings-section">
          <h3>Bedienung</h3>
          <p>Die Systemeinstellung für reduzierte Bewegung wird automatisch respektiert.</p>
        </section>
        <section class="settings-section">
          <h3>Daten und Methode</h3>
          <ul>
            <li><a href="./propose.html">Ein Commons vorschlagen</a></li>
            <li><a href="./catalog/catalog.json" type="application/json">Öffentliches Katalogmanifest</a></li>
            <li><a href="./contracts/commonworld/project.schema.json" type="application/schema+json">CommonProject-Schema</a></li>
            <li><a href="./method.html">Methode, Abdeckung und Datenschutz</a></li>
            <li><a href="./contracts/commonworld/current-state.contract.json" type="application/json">Aktueller Betriebsstand</a></li>
            <li><a href="./LICENSE">Code-Lizenz</a> · <a href="./LICENSE-DATA.md">Datenlizenz</a></li>
          </ul>
          <p>Statische, lesende JSON-Oberfläche. Das Vorschlagsformular speichert nichts bei Commonworld und bereitet nur einen öffentlichen GitHub-Kandidaten oder lokalen JSON-Download vor. Keine API-Laufzeit, kein Schreibweg und keine eigenständige CLI.</p>
          <p class="legal-note">© 2026 Commonworld contributors. Der Code wird ohne Gewährleistung unter AGPL-3.0-only weitergegeben. <a href="https://github.com/heimgewebe/commonworld" rel="external noreferrer">Quellcode</a> · <a href="./LICENSE">Lizenztext</a></p>
        </section>
      </aside>

      <section id="project-focus" class="project-focus" tabindex="-1" aria-labelledby="focus-title" hidden>
        <div class="panel-heading"><div><p id="focus-presence" class="kicker"></p><h2 id="focus-title"></h2></div><button id="focus-close" class="icon-button" type="button" aria-label="Fokus schließen">×</button></div>
        <p id="focus-summary" class="focus-summary"></p>
        <div class="focus-grid">
          <section><h3>Themen</h3><ul id="focus-themes"></ul></section>
          <section><h3>Möglichkeiten</h3><ul id="focus-actions"></ul></section>
          <section><h3>Orte</h3><ul id="focus-locations"></ul></section>
          <section><h3>Digitale Präsenz</h3><p id="focus-digital"></p></section>
          <section><h3>Beziehungen</h3><ul id="focus-relations"></ul></section>
          <section><h3>Offizielle Links</h3><ul id="focus-links"></ul></section>
          <section><h3>Quellen</h3><ul id="focus-sources"></ul></section>
          <section><h3>Kuration</h3><p id="focus-curation"></p></section>
        </div>
      </section>

      <noscript>
        <section class="noscript-catalog" aria-labelledby="noscript-title">
          <p class="kicker">Textansicht</p>
          <h1 id="noscript-title">Commonworld ohne JavaScript</h1>
          <p>Der Globus benötigt JavaScript. Alle geprüften Commons und ihre Daten bleiben hier erreichbar.</p>
          <div class="catalog-grid">
{noscript_cards}
          </div>
        </section>
      </noscript>
    </main>
  </body>
</html>
'''


def render_method(root: Path = ROOT) -> str:
    manifest = json.loads((root / "catalog/catalog.json").read_text(encoding="utf-8"))
    count = manifest["entry_count"]
    return f"""<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="dark" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'none';" />
    <meta name="description" content="Methode, Abdeckung, Datenschutz und Betriebsgrenzen von Commonworld." />
    <title>Commonworld — Methode und Grenzen</title>
    <link rel="icon" href="./assets/commonworld-mark.svg" type="image/svg+xml" />
    <link rel="stylesheet" href="./index.css" />
  </head>
  <body class="method-page">
    <main>
      <p class="kicker">Commonworld</p>
      <h1>Methode, Abdeckung und Datenschutz</h1>
      <p><a class="secondary-back-link" href="./">← Zurück zum Globus</a></p>
      <section><h2>Was Commonworld zeigt</h2><p>Commonworld veröffentlicht kuratierte Commons als eine gemeinsame Entdeckungsoberfläche. Der aktuelle Startkatalog enthält {count} Commons mit digitaler und/oder öffentlich verortbarer Präsenz. Er ist ein begrenzter redaktioneller Ausschnitt und keine vollständige Weltstatistik.</p></section>
      <section><h2>Daten und Quellen</h2><p>Jeder Eintrag besitzt eine stabile <code>CommonProject.id</code>, Quellen, Abrufdaten, Aktivitäts- und Kurationsangaben. Die JSON-Dateien sind dieselbe Datenwahrheit wie Globus und Textansicht. Fehlende Katalogeinträge bedeuten nicht, dass in einer Region keine Commons existieren.</p></section>
      <section><h2>Vorschläge und Redaktion</h2><p>Über <a href="./propose.html">Commons vorschlagen</a> können öffentliche Kandidaten vorbereitet werden. Commonworld speichert das Formular nicht. Der bevorzugte Eingang ist ein öffentliches GitHub-Issue; alternativ entsteht eine lokale JSON-Datei. Vorschläge werden nie automatisch veröffentlicht. Die Redaktion prüft Identität, primärnahe Quellen, Commons-Eigenschaft, Handlungswege, Datenschutz, Ortsgenauigkeit, Dubletten und Aktualität nach dem <a href="./contracts/commonworld/editorial-review.contract.json">Redaktionsvertrag</a>.</p></section>
      <section><h2>Orte und Privatsphäre</h2><p>Digitale Commons erhalten keine erfundenen Kartenkoordinaten. Geografische Angaben können exakt, angenähert oder verborgen sein. Verborgene Orte erhalten keine Geometrie und werden nicht aus anderen Angaben rekonstruiert.</p></section>
      <section><h2>Technischer Betrieb</h2><p>Die Seite läuft statisch über GitHub Pages. MapLibre wird lokal ausgeliefert. Die Basiskarte kommt von der öffentlichen OpenFreeMap-Instanz als nichtkritische Best-effort-Abhängigkeit ohne behauptetes SLA. Bei Kartenfehlern bleiben Katalog und Textansicht verfügbar.</p></section>
      <section><h2>Datenschutz</h2><p>Commonworld besitzt keine Konten, eigene Telemetrie, Cookies oder schreibende API. Kartenabrufe gehen direkt an OpenFreeMap; dort kann technisch die IP-Adresse verarbeitet und zeitweise zur Sicherheit protokolliert werden.</p></section>
      <section><h2>Barrierefreiheit</h2><p>Textansicht, Tastaturpfad, reduzierte Bewegung und No-JavaScript-Katalog sind vorhanden. Eine vollständige Screenreader-Produkttauglichkeit oder WCAG-Konformität wird noch nicht behauptet.</p></section>
      <section><h2>Lizenzen und maschinenlesbare Grenzen</h2><p>© 2026 Commonworld contributors. Der <a href="https://github.com/heimgewebe/commonworld" rel="external noreferrer">Commonworld-Quellcode</a> wird ohne Gewährleistung unter AGPL-3.0-only bereitgestellt; der <a href="./LICENSE">vollständige Lizenztext</a> ist öffentlich. Von Commonworld erstellte Katalogdaten stehen unter CC0-1.0. Fremde Marken, Karten- und Quelldaten behalten ihre eigenen Rechte. Der <a href="./contracts/commonworld/current-state.contract.json">aktuelle Betriebsstand</a>, das <a href="./catalog/catalog.json">Katalogmanifest</a> und das <a href="./contracts/commonworld/project.schema.json">Datenschema</a> sind öffentlich lesbar.</p></section>
    </main>
  </body>
</html>
"""


def main() -> int:
    (ROOT / "index.html").write_text(render_shell(ROOT), encoding="utf-8")
    (ROOT / "method.html").write_text(render_method(ROOT), encoding="utf-8")
    print("commonworld globe-first shell and method page rendered from public contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
