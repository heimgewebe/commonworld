# Commonworld MapLibre Phase-2-Globusbeweis

Stand: 11. Juli 2026

## Urteil

Der lokal ausführbare Teil des Phase-2-Beweises ist erfolgreich. Die Engine- und Produktionsarchitekturentscheidung bleibt trotzdem gesperrt, bis physische Mobilgeräte, Hardware-GPU und reale Assistenztechnik geprüft sind.

MapLibre trägt im Beweis sowohl den geografischen Globus als auch eine abstrakte digitale Sphäre. Die digitale Sphäre läuft als eigener `CustomLayerInterface`-Layer im selben WebGL-Kontext und selben Canvas. Sie ignoriert die geografische Kartenprojektion bewusst, verwendet nur flüchtige Clip-Space-Vektoren aus Identität, Thema und Netzwerk und speichert keinerlei Darstellungskoordinate im CommonProject-Datensatz.

Damit entfällt für diesen Beweis eine zusätzliche Three.js-Laufzeitabhängigkeit. Das ist ein gemessener Architekturkandidat, keine Produktionsfestlegung.

## Nichtöffentlicher Harness

Der außerhalb des Produkt-Repositories ausgeführte Harness verwendete:

- MapLibre GL JS `5.24.0`;
- einen nativen WebGL2-Custom-Layer für die digitale Sphäre;
- lokale MVT-Vektorkacheln über `geojson-vt` und `vt-pbf`;
- 5.000 eindeutige synthetische Commons-Identitäten;
- 4.000 geografische und 2.000 digitale Darstellungen;
- darunter 1.000 hybride Identitäten mit derselben stabilen ID in beiden Kanälen;
- 24 Abdeckungsfelder, 235 Unsicherheitszonen und 320 belegte Beziehungen.

Harness, synthetische Daten, Screenshots, npm-Abhängigkeiten und Buildausgabe sind nicht Teil des Produkt-Repositories und werden nicht öffentlich ausgeliefert.

## Semantische Darstellungsbelege

| Aussage | Umsetzung | Ergebnis |
| --- | --- | --- |
| `assessed` | ruhige Vollfläche; Helligkeit nur für belegte Dichte | PASS |
| `partial` | gebrochene diagonale Schraffur, keine normalisierte Dichte | PASS |
| `unassessed` | offenes Punktraster, unbekannt statt leer | PASS |
| ungefähre Lage | transparenter Halo plus gestrichelter Rand | PASS |
| realistischer Datenpfad | 92 MVT-Anfragen über Zoom 1 bis 6 | PASS |

Im planetaren Ausschnitt wurden 23 Abdeckungsfeatures gerendert. Im lokalen Unsicherheitsausschnitt wurden acht Halo-/Randfeatures und sieben Projektfeatures gerendert. Der Haloradius stammt aus `uncertainty_meters_min`; er wird nicht nachträglich geschärft.

## Gemeinsame Identitätswahrheit

```text
4.000 geografische Repräsentationen
2.000 digitale Repräsentationen
1.000 davon hybrid in beiden Mengen
───────────────────────────────────
5.000 eindeutige CommonProject-IDs
```

Die digitale Sphäre umfasst 2.000 Punkte, aber keine geografischen Koordinaten. Ihr Custom-Layer meldet ausdrücklich:

```text
usesMapProjection           = false
usesGeographicCoordinates   = false
placementPersistedToCatalog = false
sharesIdentityIds           = true
```

Die Sphäre ist damit eine Darstellung derselben Identitäten, keine zweite Katalogwahrheit.

## Bedienung und Zustand

Lokal nachgewiesen wurden:

- exakte Deep-Link-Wiederherstellung von Zentrum, Zoom, Drehung, Neigung und gewählter Identität;
- vollständige Identitäts- und Auswahlparität mit einer linearen 5.000-Einträge-Ansicht;
- Tastatursteuerung für Zoom, horizontale Navigation und Home;
- zugängliche Namen im Chrome-Accessibility-Tree, einschließlich erstem und letztem Eintrag;
- Reduced Motion mit `0 ms` Kamerafahrt und identischem Zielzustand;
- null Map- und Custom-Layer-Frames während zwei Sekunden Leerlauf;
- Browser-Lifecycle-Freeze ohne kontinuierliches Rendering; über Freeze und Wiederaktivierung zusammen trat höchstens ein Übergangsframe je Layer auf;
- ein Anwendungshandler für Pause und Wiederaufnahme bei Sichtbarkeitswechsel.

Nicht bewiesen sind eine reale VoiceOver-/TalkBack-Sitzung, ein echter Hintergrundtab-Rundlauf auf physischer Hardware und eine produktionsreife Virtualisierung der linearen Großliste. Ein Accessibility-Tree ersetzt keinen praktischen Screenreader-Test.

## Wiederholte Leistungsmessung

Jeder Maßstab wurde pro Profil dreimal über 120 Rotationsframes gemessen.

| Profil | Planet median | Lokal median |
| --- | ---: | ---: |
| Desktop, Software-WebGL | 55,14 FPS | 60,47 FPS |
| Mobil emuliert, Software-WebGL | 44,98 FPS | 60,49 FPS |

Das kombinierte Beweisbundle umfasst rund `287 KiB` JavaScript gzip und `10 KiB` CSS gzip. Gegenüber dem früheren separaten Three.js-Overlay sank das JavaScript-Bundle deutlich, weil nur noch ein Canvas und ein WebGL-Kontext benötigt werden.

Die Werte stammen aus Chrome über ANGLE/SwiftShader. Sie sind reproduzierbare relative Messwerte, keine Aussage über reale Safari-, Chrome- oder GPU-Leistung auf Mobilgeräten.

## Offene Sperren

Vor einer Engine- oder Produktionsarchitekturentscheidung fehlen zwingend:

1. Safari auf physischem Mobilgerät;
2. Chrome auf physischem Mobilgerät;
3. Hardware-GPU-Messung;
4. reale VoiceOver- oder TalkBack-Sitzung;
5. echter Hintergrundtab-Rundlauf;
6. produktionsnahe Virtualisierung der linearen Großliste.

Bis dahin gelten unverändert:

```text
engine_selected                    = false
production_architecture_authorized = false
```

Der nächste zulässige Schritt ist ausschließlich eine physische Geräte- und Assistenztechnik-Abnahme.

## Belegbindung

- vollständiges Forschungsarchiv: `198b4f3d3e36074cfc9773374ac3403cf90ae6c705c29d36ed2ff7537898b22f`;
- autoritative Rohresultate: `ac574f124763c3c69a41fca656dcb09a6805d894f49224219aaee3d9b9eb9441`;
- normalisierte Auswertung: `360139fb40dc5dceac8a3dbb94e6082121cffaa203051a2341944f1dcd54e25e`;
- Screenshot-Integrität: `fa7ec48a166786f6a94ae4590e5846a4ffc9dcb9506f2e4f91a16adb208866fb`;
- Dateimanifest: `838c70a076f07499893068e34ac6d6862fc6cca71a2e045ba3434645e0a7a8ce`.
