# Commonworld – digitale Sphäre Real-Surface v1

Stand: 12. Juli 2026

## Urteil

Die lokal automatisierbaren Restpunkte für die reale digitale Schichtoberfläche sind als nichtöffentlicher Referenzbeleg umgesetzt und in einem privaten Browser-Release v6 ausgeführt. Die zwölf quellengebundenen CommonProject-v3-Referenzen werden schema-validiert, deterministisch in sechs digitale Präsentationsschichten abgeleitet, mit begrenzten sichtbaren Namen dargestellt und über ein gemeinsames Fokuspanel ausgewertet.

```text
engine_selected                    = false
production_architecture_authorized = false
```

quellengebundene Referenzprojekte != veröffentlichter Commonworld-Katalog. Die Referenzen sind Test- und Ableitungsbelege, keine redaktionelle Aufnahmeentscheidung und keine Veröffentlichung als Commonworld-Katalog.

## Daten- und Publikationsgrenze

Die Referenzmatrix liegt in `tests/cases/digital-sphere.reference-projects.json`. Sie bleibt aus der öffentlichen Shell ausgeschlossen und trägt eigene Sichtbarkeitsflags: nicht Produktinhalt, nicht Katalogwahrheit, nicht Publikationsprüfung.

Alle zwölf Datensätze validieren gegen CommonProject v3. Sie sind vollständig digital, besitzen eine belegte digitale Präsenz und enthalten keine geografische Geometrie. Für vollständig digitale Commons werden keine Koordinaten erzeugt.

Die redaktionelle Katalogaufnahme ist ein separater Prozess. Vor einer späteren öffentlichen Katalogverwendung müssten Quellen, Aktualität, Publikationszustand und redaktionelle Eignung neu geprüft werden.

## Schichtableitung

Die Schicht wird direkt aus `CommonProject.id`, `themes` und `presence.digital.available` abgeleitet:

- digitale Präsenz fehlt oder ist nicht verfügbar: keine digitale Schicht;
- genau eine höchste Themenpunktzahl: diese Schicht;
- Gleichstand oder keine erkannte Zuordnung: `mixed_other`.

Die zwölf Referenzen belegen alle sechs Schichten. OpenStreetMap und der Meta-Wiki-Langname fallen wegen Thementie in `mixed_other`.

## Namen und Fokus

Pro Schicht sind höchstens zwei Orbitnamen sichtbar. Die sichtbaren Orbitlabels dürfen gekürzt sein, besitzen aber eindeutigen zugänglichen Volltext. Der lange Meta-Wiki-Name bleibt als Stresstest vollständig über den zugänglichen Text und im Fokuspanel erhalten.

Seitenansicht und Fokuspanel nutzen `CommonProject.title` als Vollnamenquelle. Binärfragmente sind deterministische dekorative Zeichen aus der stabilen Identität, `aria-hidden` und kein Projektpayload, Qualitätswert oder Aktivitätssignal.

Das Fokuspanel wird aus demselben CommonProject-v3-Datensatz abgeleitet. Es enthält vollständigen Namen, Kurzbeschreibung, Commons-Art, Themen, Handlungen, digitale Präsenz, offizielle Links, Quellen, Kurationshinweis und einen deutlichen Hinweis auf den nichtöffentlichen Referenzdatensatz.

## Auswahlgleichheit

Der Beleg prüft dieselbe `CommonProject.id` und denselben Fokuspanel-Hash für Auswahl über digitalen Sphärenrand, Schichtbutton, lineare Ansicht, Suche, Deep Link und Browser-Zurück. Ein Ansichtswechsel ersetzt den Fokus nicht; es gibt genau einen aktiven Fokus.

Die geografische Auswahl ist für diesen Referenzsatz nicht anwendbar, weil alle zwölf Referenzen vollständig digital sind und keine öffentliche geografische Darstellung besitzen. Das wird ausdrücklich als nicht anwendbar ausgewiesen, statt digitale Projektkoordinaten zu erfinden.

## Seitliche Kamerafahrt

Die Seitenansicht ist kein unabhängiger Modus. Der Beleg modelliert eine MapLibre-Kamerafahrt mit gespeichertem Ausgangszustand, `bearing`, `pitch`, `zoom` und `padding`. Der Schichtstapel liegt seitlich neben dem gedämpften Globus. Neue Eingaben unterbrechen die Fahrt.

Schließen und Browser-Zurück werden getrennt geprüft und stellen jeweils den vorherigen Zustand exakt wieder her. Bei `prefers-reduced-motion: reduce` wird dieselbe Zielwahrheit mit `maplibre.jumpTo` und `0 ms` erreicht: gleiche Auswahl, gleiche URL und gleicher Fokus.

## Leistung und Leerlauf

Der öffentliche Repo-Slice ändert keine öffentliche Runtime. Der private, unveränderliche Acceptance-Release v6 wurde dagegen im Browser ausgeführt und als normalisierte Zusammenfassung gebunden: drei Software-WebGL-Läufe erreichten im Median 32,28 FPS in der Planetensicht und 56,95 FPS lokal; das Gate von 30 FPS bestand. Bei 50.000 Lastidentitäten blieben höchstens 15 Zeilen gleichzeitig gerendert, gegenüber einer berechneten Obergrenze von 23. Im 1.500-ms-Leerlauf wurden null Map-, Overlay- und Zustandsschreibvorgänge gemessen.

Die seitliche MapLibre-Fahrt lief mit `easeTo` in 260 ms und stellte den Ausgangszustand exakt wieder her. Reduced Motion nutzte dasselbe Ziel mit `jumpTo` in 0 ms. Der Release-Beweis enthielt keine unerwarteten Konsolenfehler.

Der Vergleich mit dem normalisierten v4-Softwarebeleg bleibt erhalten. Private Adresse, Rohbelege, Browserkennung und Bildmaterial werden nicht im Repository veröffentlicht; die zusammengefassten Messwerte autorisieren weder Engine noch Produktionsarchitektur.

## Offen

Android Chrome physisch mit dem v6-Paket nicht geprüft. Dieser Punkt bleibt offen.

Screenreader für diesen Prototyp entfallen, nicht bestanden. Das ist kein Pass und keine Behauptung produktionsreifer Screenreader-Unterstützung.

Weiter offen bleiben die spätere redaktionelle Katalogaufnahme, physische Android-Chrome-Prüfung und jede Produktionsentscheidung. Engine und Architektur bleiben nicht freigegeben.
