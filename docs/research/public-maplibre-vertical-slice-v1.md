# Erster öffentlicher MapLibre-Vertikalschnitt v1

Stand: 12. Juli 2026

## Zweck

Dieser Schnitt überführt die zuvor getrennt bewiesene Rendererentscheidung in eine kleine öffentliche Laufzeit. Er beweist noch keine vollständige Produktionsarchitektur. Er verbindet genau einen MapLibre-Globus mit dem bestehenden öffentlichen Zehnerkatalog, der linearen Ansicht, einem gemeinsamen Fokuspanel und einer begrenzten digitalen SVG-Sphäre.

## Laufzeit

- `maplibre-gl@5.24.0` ist exakt gepinnt.
- `package-lock.json` bindet den aufgelösten Abhängigkeitsbaum.
- JavaScript und CSS von MapLibre werden lokal ausgeliefert; ein Floating-CDN ist ausgeschlossen.
- Die vollständige vom npm-Paket gelieferte Lizenz- und Drittcode-Notiz wird unverändert mit ausgeliefert.
- Es gibt einen MapLibre-Canvas und keinen zweiten WebGL-Globus.
- Three.js ist nicht Bestandteil der öffentlichen Laufzeit.

## Daten- und Identitätsgrenze

`catalog/catalog.json` und seine zehn CommonProject-v3-Dateien sind die einzige Projektquelle. Alle zehn Einträge bleiben vollständig digital und besitzen eine leere geografische Präsenz. Dieselbe `CommonProject.id` trägt lineare Karte, Schichtansicht, Fokuspanel und Sphärentext. Die sechs digitalen Schichten werden aus Katalogthemen und digitaler Präsenz abgeleitet und nicht in den Katalog zurückgeschrieben.

## Basiskarte und Attribution

Der Schnitt verwendet einen kontrollierten Snapshot des OpenFreeMap-Liberty-Stils. Karten-, Sprite-, Font- und Kachelressourcen dürfen ausschließlich von `tiles.openfreemap.org` geladen werden. Die sichtbare Attribution nennt OpenFreeMap, OpenMapTiles und OpenStreetMap. Für die öffentliche OpenFreeMap-Instanz wird kein Service-Level oder Produktionsversprechen behauptet. Bei Ausfall bleiben Katalog, Auswahl und Fokus linear nutzbar.

## Zustands- und Zugänglichkeitsverhalten

- Deep Links binden Kamera, Ansicht, Schicht und Projektidentität.
- Browser-Zurück stellt Auswahl und Ansicht wieder her.
- Die normale seitliche Kamerafahrt verwendet `easeTo` mit 260 ms.
- Bei aktiver Reduced-Motion-Präferenz wird derselbe Zustand mit `jumpTo` und 0 ms hergestellt.
- Eine Sprungmarke führt direkt zur vollständigen linearen Ansicht.
- Schichtauswahl, Projektkarten und Fokuspanel sind tastaturbedienbar; beim Schließen kehrt der Fokus zum Auslöser oder zur entsprechenden linearen Projektkarte zurück.
- Screenreader-Produkttauglichkeit wird nicht behauptet.

## Browserbeweis

Ein lokaler Chrome-Lauf mit SwiftShader-WebGL hat die gebaute öffentliche Oberfläche tatsächlich ausgeführt. Er bewies:

- WebGL-Canvas und geladene MapLibre-Globusprojektion;
- zehn eindeutige Katalogidentitäten in Sphäre und linearer Ansicht;
- Deep-Link-Fokus auf Debian und identische Auswahl;
- Wiederherstellung durch Browser-Zurück;
- `jumpTo` mit 0 ms bei Reduced Motion;
- `easeTo` mit 260 ms bei normaler Bewegungseinstellung;
- keine ungeplanten Ressourcendomänen;
- keine ungefangenen JavaScript-Ausnahmen;
- null Karten- und null SVG-Neuzeichnungen im gemessenen Leerlauf von 3,5 Sekunden.

Der Browserbeweis nutzt Software-WebGL. Er ersetzt keinen physischen Android-Chrome-Hardwarelauf.

## Offene Releasegates

Vor Merge und öffentlicher Auslieferung bleibt ein physischer Android-Chrome-Lauf auf genau diesem Runtime-Schnitt erforderlich. Android-spezifisches Reduced Motion wird weiterhin nicht als bestanden behauptet. Nach einem Merge müssen GitHub-Pflichtcheck, Pages-Deployment und strikter Live-Smoke einschließlich Runtime-Artefakthashes belegt werden.

## Nichtbehauptungen

Dieser Schnitt behauptet nicht:

- eine freigegebene Produktionsarchitektur;
- einen vertraglich belastbaren Produktions-Kartenanbieter;
- geografische Commons oder erfundene Koordinaten;
- Android-spezifisches Reduced-Motion-PASS;
- Screenreader-Produktsupport;
- abgeschlossenes GitHub-Pages-Deployment vor dem Merge.
