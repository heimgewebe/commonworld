# Commonworld – Geräteabnahme und Leistungsnachlauf v4

Stand: 11. Juli 2026

## Urteil

Der physische v3-Lauf hat einen realen Leistungsfehler sichtbar gemacht, aber keine vollständige Geräteabnahme erzeugt. Nur einer von drei automatischen Läufen wurde ausgeführt; Hintergrundtab, VoiceOver oder TalkBack und der konkrete Reduced-Motion-Schritt blieben offen. Der einzelne Lauf erreichte 8,81 FPS in der Totalen und 4,42 FPS lokal.

Diese Werte dürfen nicht direkt mit v4 verglichen werden, weil v3 eine andere und teilweise ungeeignete Messung verwendete. Deshalb wurde zusätzlich ein A/B-Test mit exakt derselben Bewegung und derselben Taktung für v3 und v4 durchgeführt.

v4 ist installiert und im großen Software-WebGL-Profil deutlich effizienter. Die physische Wiederholung auf Apple WebKit und danach Android Chrome bleibt zwingend.

```text
engine_selected                    = false
production_architecture_authorized = false
```

## Was der physische v3-Beleg tatsächlich sagt

Bestanden wurden Drehen und Zoomen, Abdeckungsmuster, Unsicherheit, die geschichtete digitale Sphäre sowie dieselbe ID und Markierung zwischen den Ansichten. Offen blieben Hintergrundtab, Assistenztechnik und der konkrete Reduced-Motion-Schritt. Die 510 Karten- und 509 Sphärenrender sind kein Beweis für einen Dauerloop, weil sie die Benchmarkarbeit selbst enthalten und kein getrenntes Leerlauffenster gemessen wurde.

Der Leistungsfehler ist trotzdem real: 113,47 ms je Planetenschritt und 226,13 ms je Lokalschritt sind für eine flüssige Bedienung unbrauchbar. Der Rohbeleg bleibt außerhalb des Repositories; sein SHA-256 ist `e7b20d1d923ed43201b5b173c4bd1f7f717a6f3fcd7bcdc9c1c4826ee07fddaf`.

## Fehler in v3

v3 drehte auch die Lokalansicht bei Zoom 6 vollständig um 360 Grad. Das ist keine typische lokale Bedienhandlung und löst unnötige Kartenarbeit aus. Außerdem wartete die Messung nur auf einen allgemeinen Browserframe, nicht auf einen bestätigten MapLibre-Render.

Bei jeder abgeschlossenen Kartenbewegung wurde sofort der gesamte Deep Link über `history.replaceState` geschrieben. Gleichzeitig wurden die sechs SVG-Bahnen auch dann neu gesetzt, wenn ihre Geometrie unverändert war oder die Sphäre lokal bereits unsichtbar war. Die Karte nutzte die volle Geräte-Pixeldichte 2.

## Änderungen in v4

v4 misst zwei begrenzte Interaktionen:

- Totalansicht: 90 Schritte über 90 Grad Drehung;
- Lokalansicht: 90 Schritte einer kleinen lokalen Bewegung.

Jeder Schritt beginnt auf einem Browserframe und zählt erst, wenn MapLibre den dazugehörigen Render bestätigt. Drei vollständige Läufe sind Pflicht. Das automatische Gate verlangt mindestens 30 FPS im Median, höchstens zwei Kartenrender und null Sphärenrender in einem 1,5-Sekunden-Leerlauffenster.

Weitere Änderungen:

- Deep-Link-Schreibvorgänge werden 140 ms gebündelt;
- identische SVG-Geometrie wird nicht erneut geschrieben;
- die lokal verborgene Sphäre überspringt Pfadberechnungen;
- die interne Kartenauflösung ist auf Faktor 1,5 begrenzt;
- das große Abnahmepanel wird während der Messung ausgeblendet;
- ein automatischer Leistungsfehler wird als `fail` gespeichert und nicht durch manuelle Häkchen verdeckt.

## Fairer A/B-Vergleich

Beide Versionen erhielten im selben Software-WebGL-Browser dieselben 90 Planetenschritte und dieselben 90 Lokalschritte:

| Messwert | v3 | v4 |
| --- | ---: | ---: |
| Planet | 21,81 FPS | 34,12 FPS |
| Lokal | 21,92 FPS | 56,92 FPS |
| interne Karten-Pixeldichte | 2,0 | 1,5 |
| SVG-Geometrieschreibvorgänge | 385 | 0 |
| URL-Zustandsschreibvorgänge | 183 | 3 |
| Leerlauf-Kartenrender | 0 | 0 |
| Leerlauf-Sphärenrender | 0 | 0 |

Damit steigt die planetare Rate um den Faktor 1,56 und die lokale Rate um den Faktor 2,60. URL-Schreibvorgänge sinken um 98,36 Prozent; unveränderte SVG-Geometrieschreibvorgänge sinken in diesem Arbeitspaket auf null.

Der A/B-Test verwendet Software-WebGL. Er vergleicht die Pakete als Ganzes, einschließlich der niedrigeren internen Pixeldichte von v4. Er isoliert daher nicht den Anteil jeder einzelnen Optimierung. Er ist ein relativer Technikbeleg, kein Ersatz für die physische Messung.

## Installierter v4-Beweis

Der installierte Tailnet-Dienst erreichte bei 1180 × 684 CSS-Pixeln und Gerätefaktor 2 mit interner Kartenauflösung 1,5:

| Messwert | Ergebnis |
| --- | ---: |
| Planet, Median aus drei Läufen | 47,54 FPS |
| Lokal, Median aus drei Läufen | 56,12 FPS |
| schlechtester Planet-p95 | 38,90 ms |
| schlechtester Lokal-p95 | 18,70 ms |
| Kartenrender im Leerlauf | 0 |
| Sphärenrender im Leerlauf | 0 |
| URL-Schreibvorgänge im Leerlauf | 0 |

Das 30-FPS-Gate besteht im installierten Softwareprofil. Die 50.000er Liste erzeugte höchstens 15 Zeilen bei einer theoretischen Obergrenze von 23. Die Auswahl-ID und der Name blieben zwischen Schicht- und Listenansicht gleich.

## Weiter offene Abnahme

Noch erforderlich sind:

1. drei vollständige v4-Läufe auf dem physischen Apple-WebKit-Gerät;
2. drei vollständige v4-Läufe auf Android Chrome;
3. mindestens zehn Sekunden Hintergrundtab und korrekte Rückkehr;
4. tatsächliche Bedienung mit VoiceOver oder TalkBack;
5. tatsächlicher Reduced-Motion-Schritt;
6. reale Schichtableitung und echte Commons-Namen;
7. Fokuspanel-Parität und seitliche Kamerafahrt.

## Lokale Belegbindung

- Forschungsarchiv: `a0475f929b9eba749a524f4928c8cd9a3aa115e9b7143c3de3c60d2ccbca8cce`;
- normalisierte v3-Auswertung: `5c99791d100197beb23f9d3900ad6a7d2b53d2278b851fa9179452e45e5abd12`;
- gleicher A/B-Workload: `2d96aa7d8b484c0c428d28d3633f8f804b74c7f11065d85132dd6b54595c2eeb`;
- installierter v4-Beweis: `93d854562179a93a0675e755b6c38e715e75450d411a7cfac573398bb37f78e2`;
- v4-Vorbereitungsbeweis: `2947c4de8dc3285a37b87f003cb45976f6e40a60e5312b089d006c92858db248`;
- Archivmanifest: `b497145d91d22ee130ab731aac0e5dcd8e2359dd86d49b2fd2c02e584cecaffc`;
- installierter Release: `6516be94b78c1b432c92b0d2ec1b248bbe8d18f4ca8d2af92a8963bd96daad89`.
