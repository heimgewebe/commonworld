# Öffentlicher MapLibre-Vertikalschnitt v1 – Globe-first Oberfläche

Stand: 13. Juli 2026

## Zweck

Dieser Schnitt macht den Globus zur unmittelbaren Commonworld-Oberfläche. Die bisher vorgeschaltete Einleitung, der Entwicklungsstatus und der lange Katalog konkurrieren nicht mehr mit der Erde. Die Root-Seite öffnet bildschirmfüllend mit genau einem MapLibre-Globus, einer daran gebundenen digitalen Commons-Sphäre, direkter Suche und genau einem Zahnrad für allgemeine Einstellungen.

## Laufzeit

- `maplibre-gl@5.24.0` bleibt exakt gepinnt.
- JavaScript und CSS von MapLibre werden lokal ausgeliefert; ein Floating-CDN ist ausgeschlossen.
- Es gibt einen MapLibre-Canvas und keinen zweiten WebGL-Globus.
- Three.js ist nicht Bestandteil der öffentlichen Laufzeit.
- OpenFreeMap bleibt der nichtkritische Kartenlieferant ohne behauptetes Service-Level.

## Globe-first Oberfläche

Dauerhaft sichtbar sind Commonworld-Zeichen, Suche und das Zahnrad. Das Zahnrad wechselt zwischen:

- **Globus:** räumliche Hauptansicht mit Karteninteraktion und digitaler Sphäre;
- **Text:** dieselben Commons, Filter, Auswahlen und Fokusinformationen ohne WebGL-Voraussetzung.

Der Wechsel erzeugt kein zweites Produkt. URL-Zustand und Browser-Historie führen Kamera, Darstellung, Suchbegriff, digitale Schicht und `CommonProject.id`. Die bevorzugte Darstellung kann zusätzlich lokal im Browser gespeichert werden.

## Digitale Sphäre und Schichtansicht

Der frühere Fehler entstand, weil MapLibre den Globus beim Öffnen des rechten Panels verschob, während das SVG am Bildschirmmittelpunkt stehen blieb. Die Sphäre wird jetzt aus vier Kartenwerten abgeleitet:

1. Abmessungen des Kartenbereichs;
2. von MapLibre projizierter Mittelpunkt;
3. aktives MapLibre-Padding;
4. Kartenmaß beziehungsweise Zoom.

Der berechnete Mittelpunkt wird als Prüfwert offengelegt. In der Seitenansicht tritt der Kreis zurück und sechs abgeflachte Schichtbahnen erscheinen über dem gedämpften Globus. Auf breiten Ansichten reserviert die Kamera rechts Platz für das Panel; auf schmalen Ansichten verschiebt sie Globus und Sphäre nach oben für das Bodenpanel.

## Gemeinsame Datenwahrheit

`catalog/catalog.json` und die zehn CommonProject-v3-Dateien bleiben die einzige Projektquelle. Dieselbe `CommonProject.id` trägt Sphärentext, Schichtansicht, Textkarte und Fokuspanel. Suche und Schichtfilter reduzieren in beiden Darstellungen dieselbe Identitätsmenge.

Die statische Maschinenoberfläche besteht aus:

- `catalog/catalog.json`;
- `catalog/projects/<CommonProject.id>.json`;
- `contracts/commonworld/project.schema.json`.

Sie ist ausschließlich lesend. Es werden keine API-Laufzeit, kein Schreibweg und keine eigenständige CLI eingeführt.

## Browserbeweis

Ein Chrome-Lauf mit SwiftShader-WebGL hat die gebaute Oberfläche in drei Größen ausgeführt:

| Szenario | Ausgangssphäre | Schichtansicht | Ergebnis |
| --- | --- | --- | --- |
| Desktop 1440 × 1000 | Mittelpunkt 720 / 500, Größe 980 | Mittelpunkt 510 / 500, Größe 890,88 | PASS |
| iPad-Klasse 1180 × 820 | Mittelpunkt 590 / 410, Größe 803,6 | Mittelpunkt 380 / 410, Größe 660,48 | PASS |
| Mobil 390 × 844 | Mittelpunkt 195 / 422, Größe 382,2 | Mittelpunkt 195 / 183,24, Größe 282,7 | PASS |

In allen drei Szenarien stimmten Sphärenmittelpunkt und von MapLibre projizierter Mittelpunkt exakt überein. Zusätzlich wurden belegt:

- bildschirmfüllender Globus ohne horizontalen Überlauf;
- genau ein Zahnrad;
- sechs sichtbare Schichtbahnen;
- Öffnen und Schließen mit `easeTo` und 260 ms;
- `jumpTo` und 0 ms bei reduzierter Bewegung;
- dieselbe Debian-Auswahl und derselbe Fokus nach Text-Globus-Wechsel;
- sichtbare Fokusrückgabe auf „Erde“ nach dem Schließen im Globus statt Rückgabe an ein verborgenes Textelement;
- genau ein Texttreffer für die Suche `Debian`;
- alle zehn Commons und ein eigener funktionierender Scrollbereich nach Lösen von Suche und Schichtfilter;
- ein bildschirmfüllender, scrollbarer Zehn-Einträge-Katalog bei vollständig deaktiviertem JavaScript;
- null Karten- und null SVG-Neuzeichnungen im gemessenen Leerlauf;
- keine Konsolenfehler, unbehandelten Ausnahmen oder ungeplanten Ressourcenursprünge.

Der maschinenlesbare Browserbeleg liegt außerhalb des Produkt-Repositories unter `/home/alex/.local/state/grabowski/evidence/commonworld/globe-first-surface-v1/browser-acceptance.json` und ist im Ergebnisdatensatz per SHA-256 gebunden.

## Releasegrenze

Der frühere physische Android-Chrome-Gegencheck bezog sich auf den vorherigen öffentlichen Runtime-Schnitt. Da dieser Ball Navigation, responsive Panels und die Sphärengeometrie sichtbar verändert, bleibt ein kurzer physischer Android-Chrome-Lauf auf dem aktuellen Globe-first-Stand vor Merge erforderlich.

Nicht behauptet werden:

- Android-spezifisches Reduced Motion;
- Screenreader-Produkttauglichkeit oder WCAG-Konformität;
- ein Backend oder Schreibweg;
- eine eigenständige CLI;
- eine Verfügbarkeitsgarantie für OpenFreeMap.

Nach dem Merge bleiben GitHub-Pflichtchecks, Pages-Deployment und ein strikter Live-Smoke erforderlich.
