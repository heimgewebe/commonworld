# Commonworld Renderer-Engine-Spike

Stand: 11. Juli 2026

## Zweck

Dieser Spike vergleicht vier aktuelle Renderingansätze gegen die bereits kanonischen Commonworld-Verträge. Er wählt noch keine Produktionsengine. Er beantwortet nur die Frage, welcher Kandidat als kleinster nächster Beweis weiterverfolgt werden soll.

Die maschinenlesbare Auswertung liegt in `renderer-engine-spike.result.json`. Der vollständige Harness, Rohmessungen und Screenshots bleiben als lokales Forschungsarchiv außerhalb des Produkts erhalten. Weder synthetische Daten noch Spike-Oberflächen werden veröffentlicht.

## Gemeinsame Last

Alle Kandidaten erhielten denselben deterministischen Datensatz:

- 5.000 Punkte;
- 200 Fäden;
- 20 Flächen;
- 120 rotierte Messframes;
- Desktopprofil mit 1.280 × 800 CSS-Pixeln;
- emuliertes Mobilprofil mit 390 × 844 CSS-Pixeln und Faktor 2.

Getestet wurde in Google Chrome über ANGLE/SwiftShader. Das erzeugt eine reproduzierbare Software-WebGL-Basis. Die Werte vergleichen deshalb Kandidaten untereinander; sie sind keine Vorhersage realer Geräte-FPS.

Jeder Spike besaß dieselben vier Tastaturknöpfe, las einen Deep-Link-Zustand, öffnete dieselbe lineare Zehnerliste und trug denselben zugänglichen Namen. `prefers-reduced-motion` wurde gesondert nachgewiesen.

## Messergebnis

| Kandidat | Version | JS gzip | Desktop FPS | Mobil emuliert FPS | Desktop p95 | Mobil p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MapLibre GL JS | 5.24.0 | 284.802 B | 33,09 | 31,00 | 33,4 ms | 33,4 ms |
| deck.gl | 9.3.6 | 198.430 B | 19,79 | 21,37 | 66,6 ms | 50,1 ms |
| Three.js | 0.185.1 | 140.167 B | 18,18 | 18,00 | 66,7 ms | 66,7 ms |
| CesiumJS | 1.143.0 | 1.113.604 B | 10,93 | 11,23 | 100,1 ms | 100,1 ms |

Cesium benötigt im Spike zusätzlich rund 7,3 MB statische Engine-Assets. Ein anfänglicher Cesium-Harnessfehler übergab einer Linienkollektion eine Farbe statt eines Materials. Die Tabelle verwendet ausschließlich den korrigierten fehlerfreien Wiederholungslauf.

Einzelne Favicon-404-Meldungen wurden als Serverrauschen, nicht als Enginefehler gewertet. Alle autoritativen Kandidatenläufe endeten ohne fatalen Runtimefehler.

## Fachliche Bewertung

### MapLibre GL JS

MapLibre erreichte auf beiden Profilen die höchste Bildrate. Der Spike nutzte die native Globusprojektion und denselben GeoJSON-Stilpfad für Punkte, Linien und Flächen. Damit passt MapLibre am direktesten zum semantischen Zoomvertrag und zu späteren Kachel- oder Clusterpfaden.

Noch nicht bewiesen sind:

- vollständige Zustandswiederherstellung sowie Pausieren im Ruhezustand und unsichtbaren Tab;
- Innenmuster für `partial` und `unassessed` ohne Kanalvermischung;
- gestrichelte Unsicherheitsränder und maßstabstreue Halos;
- eine digitale Außensphäre außerhalb der Erdoberfläche;
- physische Mobilgeräte und Hardware-GPU;
- Screenreader-Parität und realistische Vektorkacheln.

Ergebnis: **konditionaler Primärkandidat**, keine Engine-Festlegung.

### Three.js

Three.js lieferte das kleinste Bundle und den geringsten gemessenen Heap. Es kann frei gestaltete äußere Sphären und ungewöhnliche 3D-Formen gut tragen. Im Spike mussten Globus, Koordinatenabbildung, Punktinstanzen, Fäden, Flächen und Navigation jedoch manuell aufgebaut werden.

Das bedeutet: hohe Freiheit, aber auch hohe Eigenverantwortung für Projektion, Antimeridian, Picking, Kachelung, Cluster, Zustandswiederherstellung und semantischen Zoom.

Ergebnis: **möglicher eng begrenzter Overlay- oder Rückfallkandidat**, nicht Primärengine.

### CesiumJS

Cesium besitzt einen ausgereiften geospatialen Globus und umfangreiche Szenenfunktionen. Für den aktuellen Commonworld-Scope ist der gemessene Lieferumfang jedoch wesentlich größer und die standardisierte Last deutlich langsamer. Gelände, 3D Tiles, Zeitachsen und schwere Geoszenen sind gegenwärtig keine Kernanforderung.

Ergebnis: **für die aktuelle Phase verworfen**, nicht grundsätzlich ungeeignet.

### deck.gl

deck.gl war kompakter als MapLibre und schneller als Three.js im emulierten Mobilprofil. Die offizielle GlobeView-Dokumentation bezeichnet den Pfad jedoch als experimentell und nennt Einschränkungen bei Rotation, Layern und hoher Vergrößerung. Das kollidiert mit den lokalen und Fokus-Ebenen des Commonworld-Vertrags.

Ergebnis: **nicht als Primärengine weiterverfolgen, solange GlobeView diese Vertragsgrenzen besitzt**.

## Farbsehprüfung

Die kanonischen Familienfarben wurden mit dem Machado-2009-Modell bei voller Protan-, Deutan- und Tritan-Ausprägung simuliert.

Der kleinste mit Colorspacious über CAM02-UCS berechnete perceptual DeltaE-Farbabstand sank:

- normal: `ΔE 19,497`;
- Protan: `ΔE 6,580`;
- Deutan: `ΔE 2,910`;
- Tritan: `ΔE 6,505`.

Insbesondere unter Deutan-Simulation können Pflaume und Neutralgrau praktisch zusammenfallen. Das bestätigt den bestehenden Vertrag: Farbe allein darf keine Familie tragen. Symbol, Text und geometrischer beziehungsweise linearer Kontext bleiben verpflichtend.

## Empfehlung

MapLibre GL JS wird als einziger Primärkandidat in einen **begrenzten Phase-2-Globusbeweis** überführt. Das ist eine Entscheidung über den nächsten Test, nicht über die Produktionsarchitektur.

Vor einer Engine-Festlegung müssen sieben Bedingungen erfüllt sein:

1. Abdeckungsmuster `assessed`, `partial` und `unassessed` ohne Kanalcollision;
2. gestrichelte Ränder und Halos für ungefähre Lage;
3. digitale Außensphäre ohne doppelte Commons-Identität;
4. physische Tests mit Safari und Chrome auf Mobilhardware;
5. Pausieren im Ruhezustand und unsichtbaren Tab sowie reduzierte Bewegung;
6. Tastatur- und Screenreader-Parität mit der linearen Ansicht;
7. erneute Messung mit realistisch aggregierten Vektorkacheln.

Scheitert die digitale Außensphäre innerhalb MapLibre, wird zuerst ein eng isoliertes Three.js-Overlay geprüft. Erst danach wird die Primärengine erneut grundsätzlich hinterfragt.

## Nicht behauptet

Dieser Spike beweist nicht:

- dass MapLibre bereits die Produktionsengine ist;
- dass SwiftShader-FPS echten Mobilgeräten entsprechen;
- dass Farben ohne Symbole zugänglich sind;
- dass der synthetische In-Memory-Datensatz reale Kataloglast ersetzt;
- dass der Forschungs-Harness veröffentlicht werden darf.

## Lokale Belegbindung

Das lokale Forschungsarchiv ist nicht Teil des Repositories. Seine Inhalte sind über folgende SHA-256-Werte gebunden:

- vollständiges Archiv: `70106b8f1f0f2ad253290482a03e564bca629ed9497ac1916308ef073fde7f04`;
- autoritative Rohresultate: `9123110eca19a227691478a7cb05a63f8b71a458f0c031afa5cafaa9087985c1`;
- Farbsehresultate: `90186f8eec7701435c2eb52424c4e077859b516cd3d6724906f7846890368fbe`.
