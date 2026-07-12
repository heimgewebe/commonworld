# Commonworld Rendererentscheidung v1

Stand: 12. Juli 2026

## Entscheidung

**MapLibre GL JS 5.24.0 wird die kanonische Primärengine von Commonworld.**

MapLibre verantwortet künftig den Globus, die Kamera, den semantischen Zoom, geografische Vektorquellen, Kartenstile und das Picking geografischer Objekte. Die Auswahl ist eine technische Produktentscheidung. Sie ist noch keine Freigabe der vollständigen Produktionsarchitektur und bedeutet nicht, dass die derzeitige öffentliche statische Seite bereits MapLibre ausführt.

## Warum die Entscheidung jetzt tragfähig ist

Der ursprüngliche Vierer-Spike verglich MapLibre GL JS, CesiumJS, Three.js und deck.gl unter derselben Last. MapLibre erreichte auf Desktop und emuliertem Mobilprofil die höchste gemessene Bildrate. Danach wurden die damals offenen Bedingungen schrittweise geschlossen:

- Abdeckungsmuster, Unsicherheitsrand und Halo: bestanden;
- realistischer Vektorkachelpfad: bestanden;
- digitale Sphäre ohne geografische Katalogkoordinaten: bestanden;
- Identitätsdeduplizierung und Zustandswiederherstellung: bestanden;
- Reduced Motion, Leerlaufpause und Hintergrundrundlauf: bestanden beziehungsweise begrenzt belegt;
- Apple-WebKit auf echter Hardware-GPU: 50,48 FPS planetar und 50,93 FPS lokal, bestanden;
- reale Namen, gemeinsames Fokuspanel und echte MapLibre-Seitenkamera: bestanden;
- 50.000er lineare Ansicht: virtualisiert bestanden;
- öffentlicher Zehnerkatalog: CommonProject v3, alle sechs digitalen Schichten, keine erfundenen Orte.

Damit ist die Enginefrage ausreichend beantwortet. Weitere Kandidatenvergleiche würden voraussichtlich Wiederholung statt Erkenntnisgewinn erzeugen.

## Integrationsmodell

Commonworld verwendet **eine primäre Globe-Engine und einen Kamerazustand**:

```text
MapLibre GL JS
├── Globusprojektion und Kamera
├── semantischer Zoom
├── geografische Vektorquellen und Style-Layer
├── Auswahl geografischer Features
└── synchronisierter digitaler Overlay-Kanal
    └── begrenzte SVG-Bahnen mit derselben CommonProject.id
```

Die geschichtete digitale Sphäre bleibt vorerst ein begrenztes SVG-Overlay über demselben Globuszustand. Sie ist keine zweite Anwendung und keine zweite Katalogwahrheit. Eine MapLibre-Custom-Layer-Umsetzung darf später geprüft werden, wenn sie denselben Vertrag mindestens gleich gut erfüllt. Eine zusätzliche Three.js-Laufzeit und ein zweiter unabhängiger WebGL-Kontext sind nicht autorisiert.

## Was nicht entschieden wurde

`production_architecture_authorized` bleibt `false`. Noch offen sind:

1. der erste öffentliche MapLibre-Vertikalschnitt mit dem echten Startkatalog;
2. ein physischer Android-Chrome-Gegencheck;
3. Kachel- und Basiskartenanbieter einschließlich Attribution und Ausfallsicherheit;
4. CSP- und Worker-Auslieferung;
5. öffentliche Barrierefreiheits- und lineare Parität;
6. eine exakt gepinnte Laufzeitabhängigkeit samt Lockfile.

Der Android-Gegencheck bleibt ein Freigabe- und Kompatibilitätsgate. Er blockiert nicht länger die Wahl der Primärengine, weil MapLibre bereits relativ gegen drei Alternativen, in Software-WebGL, auf echter Apple-Hardware und in den konkreten Commonworld-Interaktionen belegt ist.

## Versionsregel

Die Auswahl ist an die getestete Version `5.24.0` gebunden. Der erste Runtime-Slice muss `maplibre-gl` exakt pinnen und ein Lockfile einchecken. Floating-CDN-Versionen sind verboten. Jedes Upgrade muss die Vertrags-, Geräte- und Regressionssuite erneut bestehen.

## Nächster Ball

Der nächste abgegrenzte Schritt ist ein **öffentlicher MapLibre-Globus-Vertikalschnitt**. Er liest den bestehenden öffentlichen Katalog, zeigt die zehn digitalen Commons in der linearen Ansicht und in der digitalen Sphäre, behält dieselbe Identität und führt noch keine geografischen Inhalte oder Anbieterentscheidungen ein.

## Beleggrenze

Die maschinenlesbare Entscheidung liegt in `renderer-selection-v1.result.json`; der ausführbare Vertrag liegt in `contracts/commonworld/renderer-selection.contract.json`. Beide werden gegen die hashgebundenen Forschungsbelege und den öffentlichen Katalog validiert.
