# commonworld

`commonworld.net` ist die öffentliche Entdeckungsoberfläche für Commons.

## Kanonische Produktentscheidung

Commonworld beginnt mit dem vollständigen Globus. Durch Rotation, Auswahl und semantischen Zoom verdichten sich aggregierte Commons-Felder zu Regionen, lokalen Flächen, Fäden und Markern. Eine auswählbare digitale Sphäre um die Erde integriert digitale und hybride Commons ohne erfundene Koordinaten.

Der einzige kanonische Produktplan ist:

- [`docs/blueprints/commonworld-masterplan.md`](docs/blueprints/commonworld-masterplan.md)

Andere historische UI- und Entwicklungsansätze sind aus dem aktiven Repository entfernt. Ihre Entwicklung bleibt in der Git-Historie nachvollziehbar.

## Produktgrenze

```text
Commonworld = entdecken, einordnen, verstehen, weitergehen
Weltgewebe  = vorschlagen, teilnehmen, koordinieren, verwalten, entscheiden
```

Commonworld führt keine eigene Mitgliedschaft, Projektverwaltung oder ungeprüfte Veröffentlichung ein.

## Aktueller Stand

Die öffentliche Seite zeigt den ersten quellengebundenen Startkatalog mit zehn digitalen Commons. MapLibre GL JS 5.24.0 ist als kanonische Primärengine gewählt; die öffentliche Seite ist noch statisch und die Produktionsarchitektur bleibt bis zum ersten MapLibre-Vertikalschnitt gesperrt.

## Validierung

```bash
make validate
```

Operator-Prüfungen:

```bash
make smoke-pages-live
make check-pages-dns-target
```
