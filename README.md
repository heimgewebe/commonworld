# commonworld

`commonworld.net` ist die öffentliche Entdeckungsoberfläche für Commons.

## Kanonische Produktentscheidung

Commonworld beginnt mit dem vollständigen Globus. Durch Rotation, Auswahl und semantischen Zoom verdichten sich belegte Commons-Daten zu Regionen, lokalen Flächen, Beziehungen und konkreten Commons. Eine auswählbare digitale Sphäre integriert digitale und hybride Commons ohne erfundene Koordinaten.

Der kanonische Produktplan ist:

- [`docs/blueprints/commonworld-masterplan.md`](docs/blueprints/commonworld-masterplan.md)

Die kompakte gegenwärtige Betriebswahrheit ist:

- [`contracts/commonworld/current-state.contract.json`](contracts/commonworld/current-state.contract.json)

Der Current-State-Vertrag hat für den heutigen Betriebsstand Vorrang vor älteren Entscheidungs- und Beweisdateien. Historische Verträge bleiben unverändert als Beleg ihrer damaligen Entscheidung erhalten.

## Produktgrenze

```text
Commonworld = entdecken, einordnen, verstehen, weitergehen
Weltgewebe  = vorschlagen, teilnehmen, koordinieren, verwalten, entscheiden
```

Commonworld führt keine eigene Mitgliedschaft, Projektverwaltung oder ungeprüfte Veröffentlichung ein.

## Aktueller Stand

Die öffentliche Seite läuft als statische GitHub-Pages-Anwendung. Sie verwendet MapLibre GL JS 5.24.0 und die öffentliche OpenFreeMap-Instanz als nichtkritische Best-effort-Basiskarte. Der Startkatalog enthält zehn quellengebundene digitale Commons. Dieselben `CommonProject.id` erscheinen im Globus, in der Textansicht, im Fokuspanel und in der maschinenlesbaren JSON-Oberfläche.

Die Produktionsarchitektur und der Kartenanbieter sind für diesen begrenzten, kontolosen und statischen Umfang autorisiert. Nicht behauptet werden ein Anbieter-SLA, automatisches Failover, Backend-Bereitschaft, Android-Reduced-Motion-Abnahme, Screenreader-Produkttauglichkeit oder WCAG-Konformität.

Die menschlich lesbare Methode, Abdeckungs- und Datenschutzgrenze wird als `method.html` veröffentlicht.

## Lizenzen

- Quellcode: GNU Affero General Public License v3, siehe [`LICENSE`](LICENSE).
- Von Commonworld erstellte Katalogdaten: CC0 1.0, siehe [`LICENSE-DATA.md`](LICENSE-DATA.md).
- Fremde Karten-, Projekt-, Marken- und Quelldaten behalten ihre jeweiligen Rechte und Lizenzen.

## Validierung

```bash
npm ci
npm run build
make validate
npm run smoke:browser
```

Operator-Prüfungen:

```bash
make smoke-pages-live
make check-pages-dns-target
```
