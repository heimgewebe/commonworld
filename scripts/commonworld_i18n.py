"""Presentation-only localization helpers for Commonworld public generators.

Canonical catalog facts stay in catalog/projects/*.json. Locale overlays may only
replace human-facing presentation text and are validated against canonical ids.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_LOCALES = ("en", "de")
DEFAULT_LOCALE = "en"
FALLBACK_LOCALE = "de"

ACTION_LABELS_EN = {
    "homepage": "Official website",
    "visit": "Visit",
    "use": "Use",
    "borrow": "Borrow",
    "learn": "Learn",
    "contribute": "Contribute",
    "volunteer": "Volunteer",
    "donate": "Donate",
    "contact": "Contact",
    "replicate": "Replicate",
}


def normalize_locale(value: str | None) -> str:
    primary = str(value or "").strip().lower().split("-", 1)[0]
    return primary if primary in SUPPORTED_LOCALES else DEFAULT_LOCALE


def load_locale(locale: str = DEFAULT_LOCALE, root: Path = ROOT) -> dict[str, Any]:
    normalized = normalize_locale(locale)
    if normalized == FALLBACK_LOCALE:
        return {"schema_version": 1, "locale": "de", "fallback_locale": "de", "projects": {}, "taxonomy_labels": {}}
    path = root / "catalog" / "locales" / f"{normalized}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("locale") != normalized:
        raise ValueError(f"invalid locale overlay contract: {path}")
    return payload


def localize_records(records: list[dict[str, Any]], locale: str = DEFAULT_LOCALE, root: Path = ROOT) -> list[dict[str, Any]]:
    normalized = normalize_locale(locale)
    if normalized == FALLBACK_LOCALE:
        return records
    overlay = load_locale(normalized, root)
    translations = overlay.get("projects", {})
    canonical_ids = {record.get("id") for record in records}
    if set(translations) != canonical_ids:
        missing = sorted(canonical_ids - set(translations))
        extra = sorted(set(translations) - canonical_ids)
        raise ValueError(f"locale {normalized} project coverage mismatch: missing={missing}, extra={extra}")
    localized: list[dict[str, Any]] = []
    for canonical in records:
        record = copy.deepcopy(canonical)
        translation = translations[record["id"]]
        summary = translation.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError(f"locale {normalized} lacks summary for {record['id']}")
        record["summary"] = summary
        if isinstance(translation.get("title"), str) and translation["title"].strip():
            record["title"] = translation["title"]
        geographic = record.get("presence", {}).get("geographic", [])
        labels = translation.get("geographic_labels")
        location_ids = {location.get("id") for location in geographic}
        if not isinstance(labels, dict) or set(labels) != location_ids:
            raise ValueError(f"locale {normalized} geographic label coverage mismatch for {record['id']}")
        for location in geographic:
            label = labels.get(location.get("id"))
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"locale {normalized} has invalid geographic label for {record['id']}:{location.get('id')}")
            location["label"] = label
        digital = record.get("presence", {}).get("digital", {})
        if digital.get("available") is True:
            label = translation.get("digital_label")
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"locale {normalized} lacks digital label for {record['id']}")
            digital["label"] = label
        for link in record.get("links", []):
            link_type = link.get("type")
            if link_type in ACTION_LABELS_EN:
                link["label"] = ACTION_LABELS_EN[link_type]
        for index, source in enumerate(record.get("provenance", {}).get("sources", []), start=1):
            hostname = urlparse(source.get("url", "")).hostname or source.get("url", "")
            canonical_label = str(source.get("label") or "").strip()
            source["label"] = f"{canonical_label} · {hostname.removeprefix('www.')}" if canonical_label else f"Source {index} · {hostname.removeprefix('www.')}"
        localized.append(record)
    return localized


def taxonomy_label(node_id: str, german_fallback: str, locale: str = DEFAULT_LOCALE, root: Path = ROOT) -> str:
    normalized = normalize_locale(locale)
    if normalized == FALLBACK_LOCALE:
        return german_fallback
    return load_locale(normalized, root).get("taxonomy_labels", {}).get(node_id, german_fallback)


def replace_exact(markup: str, replacements: dict[str, str], *, surface: str = "markup") -> str:
    missing = [source for source in replacements if source not in markup]
    if missing:
        preview = ", ".join(repr(source) for source in missing[:3])
        suffix = "" if len(missing) <= 3 else f" (+{len(missing) - 3} more)"
        raise ValueError(f"{surface} locale replacement contract drift: missing {preview}{suffix}")
    for source, target in replacements.items():
        markup = markup.replace(source, target)
    return markup


SHELL_REPLACEMENTS_EN = {
    '<html lang="de">': '<html lang="en">',
    'content="Commonworld macht Commons weltweit, regional, lokal und digital auf einem gemeinsamen Globus sichtbar."': 'content="Commonworld makes Commons discoverable worldwide, regionally, locally and digitally on one shared globe."',
    '<title>commonworld — Commons entdecken</title>': '<title>commonworld — Discover Commons</title>',
    'title="Commonworld-Katalog"': 'title="Commonworld catalog"',
    'title="CommonProject-Schema"': 'title="CommonProject schema"',
    '>Zur Textansicht springen<': '>Skip to text view<',
    'aria-label="commonworld – Globus zurücksetzen"': 'aria-label="commonworld – reset globe"',
    '>Commons suchen<': '>Search Commons<',
    'placeholder="Was möchtest du tun oder finden?"': 'placeholder="What would you like to do or find?"',
    'aria-label="Suche leeren"': 'aria-label="Clear search"',
    'aria-label="Suchergebnisse und Filter öffnen"': 'aria-label="Open search results and filters"',
    '<span class="filter-toggle-label">Filter</span>': '<span class="filter-toggle-label">Filters</span>',
    '<span class="proposal-label">Commons vorschlagen</span>': '<span class="proposal-label">Suggest a Commons</span>',
    'aria-label="Einstellungen öffnen"': 'aria-label="Open settings"',
    '<p class="kicker">Entdecken</p><h2 id="discovery-title">Passende Commons</h2>': '<p class="kicker">Discover</p><h2 id="discovery-title">Matching Commons</h2>',
    'aria-label="Suchergebnisse schließen"': 'aria-label="Close search results"',
    'aria-label="Aktive Filter"': 'aria-label="Active filters"',
    '<span>Filter</span></button>': '<span>Filters</span></button>',
    '<legend>Was?</legend>': '<legend>What?</legend>',
    '<span>Commons-Art</span>': '<span>Commons type</span>',
    '<option value="">Alle Arten</option>': '<option value="">All types</option>',
    '<option value="knowledge">Wissen und Daten</option>': '<option value="knowledge">Knowledge and Data</option>',
    '<option value="software">Software und Infrastruktur</option>': '<option value="software">Software and Infrastructure</option>',
    '<option value="culture">Kultur und Medien</option>': '<option value="culture">Culture and Media</option>',
    '<option value="food-seeds">Saatgut und Ernährung</option>': '<option value="food-seeds">Seeds and Food</option>',
    '<option value="water">Wasser und Bewässerung</option>': '<option value="water">Water and Irrigation</option>',
    '<option value="energy">Energie</option>': '<option value="energy">Energy</option>',
    '<option value="housing-land">Boden und Wohnen</option>': '<option value="housing-land">Land and Housing</option>',
    '<option value="health-care">Pflege und Gesundheit</option>': '<option value="health-care">Care and Health</option>',
    '<option value="tools-repair">Werkzeuge, Reparatur und Fertigung</option>': '<option value="tools-repair">Tools, Repair and Making</option>',
    '<option value="community-network">Gemeinschaftsnetz</option>': '<option value="community-network">Community Network</option>',
    '<option value="other">Andere</option>': '<option value="other">Other</option>',
    '<span>Aktion</span>': '<span>Action</span>',
    '<option value="">Alle Aktionen</option>': '<option value="">All actions</option>',
    '<option value="use">Nutzen</option>': '<option value="use">Use</option>',
    '<option value="borrow">Ausleihen</option>': '<option value="borrow">Borrow</option>',
    '<option value="learn">Lernen</option>': '<option value="learn">Learn</option>',
    '<option value="contribute">Mitmachen</option>': '<option value="contribute">Contribute</option>',
    '<option value="volunteer">Ehrenamtlich helfen</option>': '<option value="volunteer">Volunteer</option>',
    '<option value="donate">Spenden</option>': '<option value="donate">Donate</option>',
    '<option value="visit">Besuchen</option>': '<option value="visit">Visit</option>',
    '<option value="contact">Kontaktieren</option>': '<option value="contact">Contact</option>',
    '<option value="replicate">Übertragen</option>': '<option value="replicate">Replicate</option>',
    '<legend>Wo?</legend>': '<legend>Where?</legend>',
    '<legend>Präsenz</legend>': '<legend>Presence</legend>',
    '> Vor Ort</label>': '> On site</label>',
    '> Digital</label>': '> Digital</label>',
    'Beide gewählt = nur Commons mit Vor-Ort- und digitaler Präsenz.': 'Both selected = only Commons with both on-site and digital presence.',
    '>Ort oder Land suchen</label>': '>Search place or country</label>',
    'placeholder="Ort, Region oder Land"': 'placeholder="Place, region or country"',
    'aria-label="Ortsvorschläge"': 'aria-label="Place suggestions"',
    '<span>Land</span>': '<span>Country</span>',
    '<option value="">Alle Länder</option>': '<option value="">All countries</option>',
    '<span>Umkreis</span>': '<span>Radius</span>',
    '<option value="">Kein Umkreis</option>': '<option value="">No radius</option>',
    '>Meinen Standort verwenden</button>': '>Use my location</button>',
    'Die Ortssuche deckt Länder und veröffentlichte Commonworld-Orte ab, nicht eine vollständige Weltadresssuche.': 'Place search covers countries and published Commonworld locations, not a complete worldwide address search.',
    '<legend>Weitere Filter</legend>': '<legend>More filters</legend>',
    '<span>Zugang</span>': '<span>Access</span>',
    '<option value="">Alle Zugänge</option>': '<option value="">All access types</option>',
    '<option value="public">Öffentlich</option>': '<option value="public">Public</option>',
    '<option value="membership">Mitgliedschaft</option>': '<option value="membership">Membership</option>',
    '<option value="restricted">Beschränkt</option>': '<option value="restricted">Restricted</option>',
    '<option value="unknown">Nicht angegeben</option>': '<option value="unknown">Not specified</option>',
    '<span>Sprache</span>': '<span>Language</span>',
    '<option value="">Alle Angaben</option>': '<option value="">All entries</option>',
    '<option value="de">Deutsch</option>': '<option value="de">German</option>',
    '<span>Aktualität</span>': '<span>Freshness</span>',
    '<option value="">Jede Aktualität</option>': '<option value="">Any freshness</option>',
    '<option value="current">Aktuell geprüft</option>': '<option value="current">Currently reviewed</option>',
    '<option value="stale">Prüfung fällig</option>': '<option value="stale">Review due</option>',
    '<span>Kuration</span>': '<span>Curation</span>',
    '<option value="">Jeder Status</option>': '<option value="">Any status</option>',
    '<option value="listed">Gelistet</option>': '<option value="listed">Listed</option>',
    '<option value="verified">Verifiziert</option>': '<option value="verified">Verified</option>',
    '<option value="featured">Hervorgehoben</option>': '<option value="featured">Featured</option>',
    '>Filter zurücksetzen</button>': '>Reset filters</button>',
    '>Keine Commons entsprechen dieser Suche und Filterkombination.</p>': '>No Commons match this search and filter combination.</p>',
    'aria-label="Rangfolge der Commons-Suchergebnisse"': 'aria-label="Ranked Commons search results"',
    '>Alle Treffer in der Textansicht anzeigen</button>': '>Show all results in the text view</button>',
    'aria-label="Commonworld-Globus"': 'aria-label="Commonworld globe"',
    'aria-label="Interaktiver Commonworld-Globus"': 'aria-label="Interactive Commonworld globe"',
    '<title id="sphere-title">Digitale Commons-Sphäre aus Namen und Kategorien</title>': '<title id="sphere-title">Digital Commons Sphere built from names and categories</title>',
    'aria-label="Digitale Ringbündel öffnen. Antippen oder Eingabetaste drücken."': 'aria-label="Open digital ring bundles. Tap or press Enter."',
    '>Digitale Sphäre</button>': '>Digital Sphere</button>',
    'aria-label="Länderkontext"': 'aria-label="Country context"',
    '>Commons in diesem Land anzeigen</button>': '>Show Commons in this country</button>',
    'aria-label="Länderkontext schließen"': 'aria-label="Close country context"',
    'aria-label="Globusorientierung"': 'aria-label="Globe orientation"',
    '>Erde</button>': '>Earth</button>',
    '<span id="semantic-level">Gesamtansicht</span>': '<span id="semantic-level">Overview</span>',
    '<span id="semantic-summary" class="semantic-summary">Katalogauszug · Abdeckung nicht bewertet</span>': '<span id="semantic-summary" class="semantic-summary">Catalog sample · coverage not assessed</span>',
    '<summary>Kartenlegende</summary>': '<summary>Map legend</summary>',
    'Farben zeigen die Commons-Art. In der Weltansicht werden Länder mit den Farben der dort über veröffentlichte Ortsbezüge belegten Commons-Arten anteilig gestreift. Beim Hineinzoomen wird die Darstellung regionaler und schließlich ortsgenau. Die Katalogabdeckung ist nicht bewertet; die Karte zeigt weder Dichte noch nachgewiesene Leere.': 'Colors show the Commons type. In the world view, countries are striped proportionally with the colors of Commons types evidenced there through published location references. As you zoom in, the display becomes regional and eventually location-specific. Catalog coverage is not assessed; the map shows neither density nor evidenced absence.',
    'aria-label="Commons-Arten und Kartenzeichen"': 'aria-label="Commons types and map symbols"',
    'Länderstreifen: relative Verteilung der dokumentierten Commons-Arten im jeweiligen Land': 'Country stripes: relative distribution of documented Commons types in each country',
    'Farbige Kreise: gröbere regionale Bündelung beim Hineinzoomen': 'Colored circles: broader regional grouping while zooming in',
    'Versteckte Ortsbezüge fließen nicht in die räumliche Darstellung ein': 'Hidden location references are not included in the spatial display',
    '<strong>Ortsgenauigkeit:</strong> Punkt = exakt, gestrichelte Fläche = ungefähr, durchgezogene Fläche = veröffentlichte Ausdehnung.': '<strong>Location precision:</strong> point = exact, dashed area = approximate, solid area = published extent.',
    'Globus wird geladen. Die Textansicht bleibt verfügbar.': 'Loading globe. The text view remains available.',
    'Commons im aktuellen Katalog.': 'Commons in the current catalog.',
    'Digitale Commons aus der Nähe': 'Digital Commons up close',
    'Dieselben digitalen Commons erscheinen als hierarchische Ringbündel mit direktem Elternpfad und Namen.': 'The same digital Commons appear as hierarchical ring bundles with their direct parent path and names.',
    'aria-label="Commons suchen und Ringbündel filtern"': 'aria-label="Search Commons and filter ring bundles"',
    'aria-label="Zur Globusansicht zurückkehren"': 'aria-label="Return to globe view"',
    'aria-label="Digitaler Pfad"': 'aria-label="Digital path"',
    '<p id="layer-current" class="digital-current" role="status">Digitale Commons-Sphäre</p>': '<p id="layer-current" class="digital-current" role="status">Digital Commons Sphere</p>',
    '>Commons in den digitalen Ringbündeln suchen</label>': '>Search Commons in the digital ring bundles</label>',
    'placeholder="Commons suchen"': 'placeholder="Search Commons"',
    'aria-label="Hierarchische digitale Commons-Ringbündel"': 'aria-label="Hierarchical digital Commons ring bundles"',
    'Erde → Großregion → Region → lokaler Zusammenhang → Commons': 'Earth → macroregion → region → local context → Commons',
    '<p class="kicker">Textansicht</p>': '<p class="kicker">Text view</p>',
    '<h1 id="text-title">Commons direkt durchsuchen</h1>': '<h1 id="text-title">Browse Commons directly</h1>',
    'Dieselben Identitäten, Filter und Auswahlen wie im Globus – ohne räumliche Darstellung.': 'The same identities, filters and selections as on the globe — without the spatial display.',
    '<h2 id="text-filter-title">Filter und digitale Ringbündel</h2>': '<h2 id="text-filter-title">Filters and digital ring bundles</h2>',
    '>Suchfilter öffnen</button>': '>Open search filters</button>',
    'aria-label="Digitaler Pfad in der Textansicht"': 'aria-label="Digital path in the text view"',
    '<p id="text-layer-current" class="digital-current" role="status">Digitale Commons-Sphäre</p>': '<p id="text-layer-current" class="digital-current" role="status">Digital Commons Sphere</p>',
    'Maschinenlesbar:': 'Machine-readable:',
    '>Katalogmanifest</a>': '>Catalog manifest</a>',
    '>Datenschema</a>': '>Data schema</a>',
    '>Keine Commons entsprechen dieser Auswahl.</p>': '>No Commons match this selection.</p>',
    '>Weitere Commons anzeigen</button>': '>Show more Commons</button>',
    'Darstellung wählen und Informationen zu Daten, Methode und Lizenzen öffnen.': 'Choose a presentation and open information about data, method and licenses.',
    '<p class="kicker">Einstellungen</p><h2 id="settings-title">Darstellung</h2>': '<p class="kicker">Settings</p><h2 id="settings-title">Presentation</h2>',
    'aria-label="Einstellungen schließen"': 'aria-label="Close settings"',
    'aria-label="Darstellung wählen"': 'aria-label="Choose presentation"',
    '<strong>Globus</strong><span>Räumlich entdecken und zoomen</span>': '<strong>Globe</strong><span>Explore spatially and zoom</span>',
    '<strong>Text</strong><span>Dieselben Commons als Liste</span>': '<strong>Text</strong><span>The same Commons as a list</span>',
    '<h3>Bedienung</h3>': '<h3>Interaction</h3>',
    'Die Systemeinstellung für reduzierte Bewegung wird automatisch respektiert.': 'The system setting for reduced motion is respected automatically.',
    '<h3>Daten und Methode</h3>': '<h3>Data and method</h3>',
    '>Ein Commons vorschlagen</a>': '>Suggest a Commons</a>',
    '>Öffentliches Katalogmanifest</a>': '>Public catalog manifest</a>',
    '>CommonProject-Schema</a>': '>CommonProject schema</a>',
    '>Methode, Abdeckung und Datenschutz</a>': '>Method, coverage and privacy</a>',
    '>Aktueller Betriebsstand</a>': '>Current operational state</a>',
    '>Code-Lizenz</a>': '>Code license</a>',
    '>Datenlizenz</a>': '>Data license</a>',
    'Statische, lesende JSON-Oberfläche. Das Vorschlagsformular speichert nichts bei Commonworld und bereitet nur einen öffentlichen GitHub-Kandidaten oder lokalen JSON-Download vor. Keine API-Laufzeit, kein Schreibweg und keine eigenständige CLI.': 'Static, read-only JSON surface. The suggestion form stores nothing at Commonworld and only prepares a public GitHub candidate or a local JSON download. No API runtime, no write path and no standalone CLI.',
    'Der Code wird ohne Gewährleistung unter AGPL-3.0-only weitergegeben.': 'The code is provided without warranty under AGPL-3.0-only.',
    '>Quellcode</a>': '>Source code</a>',
    '>Lizenztext</a>': '>License text</a>',
    'aria-label="Fokus schließen"': 'aria-label="Close focus"',
    '<section><h3>Themen</h3>': '<section><h3>Themes</h3>',
    '<section><h3>Möglichkeiten</h3>': '<section><h3>Ways to engage</h3>',
    '<section><h3>Orte</h3>': '<section><h3>Locations</h3>',
    '<section><h3>Digitale Präsenz</h3>': '<section><h3>Digital presence</h3>',
    '<section><h3>Beziehungen</h3>': '<section><h3>Relationships</h3>',
    '<section><h3>Offizielle Links</h3>': '<section><h3>Official links</h3>',
    '<section><h3>Quellen</h3>': '<section><h3>Sources</h3>',
    '<section><h3>Kuration</h3>': '<section><h3>Curation</h3>',
    '<h1 id="noscript-title">Commonworld ohne JavaScript</h1>': '<h1 id="noscript-title">Commonworld without JavaScript</h1>',
    'Der Globus benötigt JavaScript. Alle geprüften Commons und ihre Daten bleiben hier erreichbar.': 'The globe requires JavaScript. All reviewed Commons and their data remain accessible here.',
}

METHOD_REPLACEMENTS_EN = {
    '<html lang="de">': '<html lang="en">',
    'content="Methode, Abdeckung, Datenschutz und Betriebsgrenzen von Commonworld."': 'content="Method, coverage, privacy and operational boundaries of Commonworld."',
    '<title>Commonworld — Methode und Grenzen</title>': '<title>Commonworld — Method and boundaries</title>',
    '<h1>Methode, Abdeckung und Datenschutz</h1>': '<h1>Method, coverage and privacy</h1>',
    '← Zurück zum Globus': '← Back to the globe',
    '<h2>Was Commonworld zeigt</h2>': '<h2>What Commonworld shows</h2>',
    'Commonworld veröffentlicht kuratierte Commons als eine gemeinsame Entdeckungsoberfläche.': 'Commonworld publishes curated Commons through one shared discovery surface.',
    'Der aktuelle Startkatalog enthält': 'The current initial catalog contains',
    'Commons mit digitaler und/oder öffentlich verortbarer Präsenz. Er ist ein begrenzter redaktioneller Ausschnitt und keine vollständige Weltstatistik.': 'Commons with digital and/or publicly mappable presence. It is a limited editorial selection, not a complete global statistic.',
    '<h2>Daten und Quellen</h2>': '<h2>Data and sources</h2>',
    'Jeder Eintrag besitzt eine stabile': 'Each entry has a stable',
    ', Quellen, Abrufdaten, Aktivitäts- und Kurationsangaben. Die JSON-Dateien sind dieselbe Datenwahrheit wie Globus und Textansicht. Fehlende Katalogeinträge bedeuten nicht, dass in einer Region keine Commons existieren.': ', sources, retrieval dates, activity information and curation information. The JSON files are the same data truth used by the globe and text view. Missing catalog entries do not mean that no Commons exist in a region.',
    '<h2>Vorschläge und Redaktion</h2>': '<h2>Suggestions and editorial review</h2>',
    'Über <a href="./propose.html">Commons vorschlagen</a> können öffentliche Kandidaten vorbereitet werden. Commonworld speichert das Formular nicht. Der bevorzugte Eingang ist ein öffentliches GitHub-Issue; alternativ entsteht eine lokale JSON-Datei. Vorschläge werden nie automatisch veröffentlicht. Die Redaktion prüft Identität, primärnahe Quellen, Commons-Eigenschaft, Handlungswege, Datenschutz, Ortsgenauigkeit, Dubletten und Aktualität nach dem': 'Public candidates can be prepared through <a href="./propose.html">Suggest a Commons</a>. Commonworld does not store the form. The preferred intake path is a public GitHub issue; alternatively, a local JSON file is produced. Suggestions are never published automatically. Editorial review checks identity, primary-near sources, Commons characteristics, ways to engage, privacy, location precision, duplicates and freshness under the',
    '>Redaktionsvertrag</a>.': '>editorial review contract</a>.',
    '<h2>Orte und Privatsphäre</h2>': '<h2>Locations and privacy</h2>',
    'Digitale Commons erhalten keine erfundenen Kartenkoordinaten. Geografische Angaben können exakt, angenähert oder verborgen sein. Verborgene Orte erhalten keine Geometrie und werden nicht aus anderen Angaben rekonstruiert.': 'Digital Commons are not assigned invented map coordinates. Geographic information may be exact, approximate or hidden. Hidden locations have no geometry and are not reconstructed from other information.',
    '<h2>Technischer Betrieb</h2>': '<h2>Technical operation</h2>',
    'Die Seite läuft statisch über GitHub Pages. MapLibre wird lokal ausgeliefert. Die Basiskarte kommt von der öffentlichen OpenFreeMap-Instanz als nichtkritische Best-effort-Abhängigkeit ohne behauptetes SLA. Bei Kartenfehlern bleiben Katalog und Textansicht verfügbar.': 'The site runs statically on GitHub Pages. MapLibre is served locally. The basemap comes from the public OpenFreeMap instance as a non-critical best-effort dependency with no claimed SLA. If the map fails, the catalog and text view remain available.',
    '<h2>Datenschutz</h2>': '<h2>Privacy</h2>',
    'Commonworld besitzt keine Konten, eigene Telemetrie, Cookies oder schreibende API. Kartenabrufe gehen direkt an OpenFreeMap; dort kann technisch die IP-Adresse verarbeitet und zeitweise zur Sicherheit protokolliert werden.': 'Commonworld has no accounts, first-party telemetry, cookies or write API. Map requests go directly to OpenFreeMap; the IP address may technically be processed there and temporarily logged for security.',
    '<h2>Barrierefreiheit</h2>': '<h2>Accessibility</h2>',
    'Textansicht, Tastaturpfad, reduzierte Bewegung und No-JavaScript-Katalog sind vorhanden. Eine vollständige Screenreader-Produkttauglichkeit oder WCAG-Konformität wird noch nicht behauptet.': 'A text view, keyboard path, reduced-motion handling and a no-JavaScript catalog are available. Full screen-reader product suitability or WCAG conformance is not yet claimed.',
    '<h2>Lizenzen und maschinenlesbare Grenzen</h2>': '<h2>Licenses and machine-readable boundaries</h2>',
    'Der <a href="https://github.com/heimgewebe/commonworld" rel="external noreferrer">Commonworld-Quellcode</a> wird ohne Gewährleistung unter AGPL-3.0-only bereitgestellt; der <a href="./LICENSE">vollständige Lizenztext</a> ist öffentlich. Von Commonworld erstellte Katalogdaten stehen unter CC0-1.0. Fremde Marken, Karten- und Quelldaten behalten ihre eigenen Rechte. Der <a href="./contracts/commonworld/current-state.contract.json">aktuelle Betriebsstand</a>, das <a href="./catalog/catalog.json">Katalogmanifest</a> und das <a href="./contracts/commonworld/project.schema.json">Datenschema</a> sind öffentlich lesbar.': 'The <a href="https://github.com/heimgewebe/commonworld" rel="external noreferrer">Commonworld source code</a> is provided without warranty under AGPL-3.0-only; the <a href="./LICENSE">full license text</a> is public. Catalog data created by Commonworld is released under CC0-1.0. Third-party trademarks, map data and source data retain their own rights. The <a href="./contracts/commonworld/current-state.contract.json">current operational state</a>, <a href="./catalog/catalog.json">catalog manifest</a> and <a href="./contracts/commonworld/project.schema.json">data schema</a> are publicly readable.'
}


def translate_shell(markup: str, locale: str) -> str:
    return replace_exact(markup, SHELL_REPLACEMENTS_EN, surface="public shell") if normalize_locale(locale) == "en" else markup


def translate_method(markup: str, locale: str) -> str:
    return replace_exact(markup, METHOD_REPLACEMENTS_EN, surface="method page") if normalize_locale(locale) == "en" else markup


def inject_locale_navigation(markup: str, locale: str, surface: str = "index") -> str:
    normalized = normalize_locale(locale)
    hrefs = {
        "index": ("./", "./de.html"),
        "method": ("./method.html", "./method.de.html"),
        "propose": ("./propose.html", "./propose.de.html"),
    }
    en_href, de_href = hrefs.get(surface, hrefs["index"])
    if surface == "index":
        section = (
            '<section class="settings-section language-settings"><h3>'
            + ("Language" if normalized == "en" else "Sprache")
            + '</h3><p class="language-switch" aria-label="'
            + ("Choose language" if normalized == "en" else "Sprache wählen")
            + '"><a href="' + en_href + '" lang="en"' + (' aria-current="page"' if normalized == "en" else '') + '>English</a> · '
            + '<a href="' + de_href + '" lang="de"' + (' aria-current="page"' if normalized == "de" else '') + '>Deutsch</a></p></section>\n        '
        )
        marker = '<section class="settings-section">\n          <h3>' + ("Interaction" if normalized == "en" else "Bedienung") + '</h3>'
        markup = markup.replace(marker, section + marker, 1)
    else:
        switch = (
            '<p class="language-switch" aria-label="'
            + ("Choose language" if normalized == "en" else "Sprache wählen")
            + '"><a href="' + en_href + '" lang="en"' + (' aria-current="page"' if normalized == "en" else '') + '>English</a> · '
            + '<a href="' + de_href + '" lang="de"' + (' aria-current="page"' if normalized == "de" else '') + '>Deutsch</a></p>'
        )
        marker = '<p><a class="secondary-back-link"'
        position = markup.find(marker)
        if position >= 0:
            end = markup.find('</p>', position)
            if end >= 0:
                end += 4
                markup = markup[:end] + '\n      ' + switch + markup[end:]
    return markup


def german_surface_links(markup: str, locale: str, surface: str = "index") -> str:
    if normalize_locale(locale) != "de":
        return markup
    if surface == "index":
        return markup.replace('href="./propose.html"', 'href="./propose.de.html"').replace('href="./method.html"', 'href="./method.de.html"')
    if surface == "method":
        return markup.replace('href="./">', 'href="./de.html">').replace('href="./propose.html"', 'href="./propose.de.html"')
    if surface == "propose":
        return markup.replace('href="./">', 'href="./de.html">').replace('href="./method.html"', 'href="./method.de.html"')
    return markup
