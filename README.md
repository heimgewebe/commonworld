# commonworld

`commonworld.net` ist die öffentliche Entdeckungsoberfläche für Commons.

## Kanonische Produktentscheidung

Commonworld beginnt mit dem vollständigen Globus. Durch Rotation, Auswahl und semantischen Zoom verdichten sich belegte Commons-Daten zu Regionen, lokalen Flächen, Beziehungen und konkreten Commons. Eine auswählbare digitale Sphäre integriert digitale Präsenzen ohne erfundene Koordinaten.

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

Die öffentliche Seite läuft als statische GitHub-Pages-Anwendung. Sie verwendet MapLibre GL JS 5.24.0 und die öffentliche OpenFreeMap-Instanz als nichtkritische Best-effort-Basiskarte. Der öffentliche Katalog enthält quellengebundene geografische und digitale Commons. Dieselben `CommonProject.id` erscheinen im Globus, in der Textansicht, im Fokuspanel und in der maschinenlesbaren JSON-Oberfläche.

Die Produktionsarchitektur und der Kartenanbieter sind für diesen begrenzten, kontolosen und statischen Umfang autorisiert. Nicht behauptet werden ein Anbieter-SLA, automatisches Failover, Backend-Bereitschaft, Android-Reduced-Motion-Abnahme, Screenreader-Produkttauglichkeit oder WCAG-Konformität.

Die menschlich lesbare Methode, Abdeckungs- und Datenschutzgrenze wird als `method.html` veröffentlicht.

## Internationalisierung

Englisch ist die öffentliche Standardsprache (`index.html`, `method.html`, `propose.html`). Deutsch bleibt als vollständig statische Alternative über `de.html`, `method.de.html` und `propose.de.html` erreichbar. Der Sprachwechsel funktioniert daher auch ohne JavaScript.

Die fachliche Katalogwahrheit bleibt ausschließlich in `catalog/projects/*.json`. Präsentationsübersetzungen liegen getrennt in `catalog/locales/<locale>.json` und dürfen nur sichtbare Texte wie Zusammenfassungen und Ortslabels ersetzen; IDs, URLs, Geometrien, Quellen, Aktivitäts- und Kurationszustände bleiben kanonisch. `npm run build` erzeugt daraus die statischen Sprachoberflächen und das Browser-Locale-Modul deterministisch neu. Die Suche indexiert in der englischen Oberfläche zusätzlich die deutschen kanonischen Präsentationstexte, damit englische und deutsche Suchbegriffe parallel nutzbar bleiben.

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

## Öffentlicher Vorschlags- und Redaktionsweg

`propose.html` ist ein statisches, datensparsames Vorschlagsformular. Es validiert Eingaben im Browser, speichert bei Commonworld keine Formulardaten und bereitet entweder ein öffentliches GitHub-Issue oder einen lokalen JSON-Download vor. Ein Vorschlag ist nur ein Kandidat und verändert niemals automatisch `catalog/projects/*.json`.

Maschinenlesbare Grenzen:

- `contracts/commonworld/proposal.schema.json`
- `contracts/commonworld/proposal-path.contract.json`
- `contracts/commonworld/editorial-review.contract.json`
- `contracts/commonworld/catalog-diversity.contract.json`

Die Katalogaufnahme erfordert weiterhin einen separat geprüften Repository-Commit, den bestehenden CommonProject-Vertrag und eine gesetzte Wiedervorlagefrist.
