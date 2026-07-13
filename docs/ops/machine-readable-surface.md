# Commonworld: maschinenlesbare Oberfläche

## Zweck

Commonworld veröffentlicht dieselben kuratierten Commons, die im Globus und in der Textansicht erscheinen, zusätzlich als statische JSON-Dateien. Diese Oberfläche dient Lesewerkzeugen, Suchmaschinen, Skripten und späteren Integrationen.

Sie ist keine getrennte Datenwahrheit. `CommonProject.id` bleibt in Globus, Textansicht und JSON dieselbe Identität.

## Öffentliche Einstiegspunkte

- `catalog/catalog.json` ist das Manifest des veröffentlichten Katalogs.
- `catalog/projects/<CommonProject.id>.json` enthält genau einen öffentlichen CommonProject-v3-Datensatz.
- `contracts/commonworld/project.schema.json` beschreibt die Datenform.

Das Manifest nennt zusätzlich die Zugriffseigenschaften unter `machine_surface`.

## Betriebsgrenze

Die Oberfläche ist:

- statisch;
- ausschließlich lesend;
- über dieselbe GitHub-Pages-Veröffentlichung erreichbar wie die Webseite;
- ohne eigenes Backend, Konto oder Schreibverfahren.

Sie ist ausdrücklich keine laufende API. Es werden keine Verfügbarkeitsgarantie, kein Rate-Limit-Vertrag und keine automatische Aktualität behauptet. Die Datensätze tragen ihre redaktionellen Prüf- und nächsten Prüfdaten selbst.

## CLI-Entscheidung

Eine eigenständige Kommandozeilenanwendung wird nicht eingeführt. Die JSON-Dateien sind bereits mit üblichen Werkzeugen abruf- und verarbeitbar. Eine CLI benötigt zuerst einen belegten wiederkehrenden Anwendungsfall und einen eigenen geprüften Implementierungsball.

## Gleichheit der Ansichten

Die Browseroberfläche lädt genau das Manifest und die dort genannten Projektdateien. Suche, Schichtfilter und Fokus verändern keine Katalogdaten, sondern nur die Darstellung derselben Identitätsmenge.
