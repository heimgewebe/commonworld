# Commonworld – physische Apple-WebKit-Abnahme v4

Stand: 11. Juli 2026

## Urteil

Der physische Apple-WebKit-Lauf von Abnahmepaket v4 wird für den nichtöffentlichen Prototyp als bestanden angenommen. Drei automatische Läufe, das 30-FPS-Gate, die geschichtete digitale Sphäre, Auswahlgleichheit, Hintergrundrundlauf und die übrigen visuellen Prüfungen sind belegt.

Der Rohbeleg trägt formal `incomplete`, weil Screenreader und Reduced Motion im damaligen Formular auf `not_run` blieben. Der Rohbeleg wird nicht umgeschrieben. Die Auswertung wendet stattdessen die anschließend festgelegte Produktentscheidung transparent an:

- ein physischer Screenreader-Test ist für diesen Prototyp kein Freigabekriterium;
- Screenreader-Unterstützung wird nicht als bestanden oder produktionsreif behauptet;
- Reduced Motion wird aufgrund aktiver Systemeinstellung am Anfang und Ende sowie der ausdrücklichen Nutzerbestätigung als bestanden angenommen;
- der im Rohbeleg fehlende Maschinenwert zur Bewegungsdauer bleibt ausdrücklich dokumentiert.

```text
engine_selected                    = false
production_architecture_authorized = false
```

## Physische Leistung

| Messwert | Ergebnis |
| --- | ---: |
| automatische Läufe | 3 |
| Planet, Median | 50,48 FPS |
| Lokal, Median | 50,93 FPS |
| schlechtester Planet-p95 | 25,00 ms |
| schlechtester Lokal-p95 | 23,00 ms |
| Kartenrender im Leerlauf | 0 |
| Sphärenrender im Leerlauf | 0 |
| URL-Schreibvorgänge im Leerlauf | 0 |

Der Lauf verwendete Apple WebKit, Apple-GPU, Touchbedienung, Gerätefaktor 2 und eine interne Kartenauflösung von 1,5. Das automatische Leistungs-Gate von 30 FPS besteht in beiden Ansichten.

## Direkt bestandene manuelle Prüfungen

Bestanden wurden:

1. Globus drehen und zoomen;
2. Abdeckungsmuster;
3. Unsicherheitshalo und gestrichelter Rand;
4. geschichtete digitale Sphäre;
5. dieselbe Commons-Auswahl in Schicht- und Listenansicht;
6. Hintergrundrundlauf.

Der Browser war 32,608 Sekunden verborgen. Damit ist die Mindestdauer von zehn Sekunden deutlich überschritten.

## Reduced Motion

Der Rohbeleg meldet `prefers-reduced-motion` sowohl beim Start als auch beim Abschluss als aktiv. Der manuelle Formularpunkt blieb dennoch offen, weil v4 keinen `last_motion_duration_ms` aufzeichnete. Der Nutzer bestätigte nach dem Lauf ausdrücklich, dass Bewegung reduzieren funktioniert.

Die normalisierte Wertung lautet daher:

```text
reduced_motion = pass_by_attestation_with_machine_gap_disclosed
```

Das ist kein nachträglich erfundener Maschinenwert. Abnahmepaket v5 löst beim Bestätigen selbst eine Sofortbewegung aus und speichert künftig den Wert `0 ms`.

## Screenreader-Entscheidung

Der Screenreader-Punkt wird für die nichtöffentliche Prototypabnahme bewusst entfallen gelassen. Das bedeutet nicht, dass VoiceOver, TalkBack oder allgemeine Screenreader-Unterstützung bewiesen wären.

Weiterhin verpflichtend bleiben:

- semantische Bedienelemente;
- Tastaturpfad;
- lineare Textalternative;
- identische Commons-ID und Bezeichnung in den Ansichten;
- keine falsche Behauptung physisch getesteter Screenreader-Unterstützung.

## Abnahmepaket v5

v5 ist installiert und ersetzt v4. Es enthält sieben verpflichtende manuelle Prüfungen. Der Screenreader-Punkt ist als optional und `Entfällt` vorbelegt. Reduced Motion erzeugt beim Bestätigen selbst eine sofortige Kamerabewegung und speichert den Maschinenwert.

Installiertes Manifest:

```text
3e4eb9b92e21357a87368a674609e5b49199fad6ed75963bbfad1aa20a8280f5
```

Der installierte v5-Softwarebeweis bestand erneut drei Leistungsläufe, das 30-FPS-Gate und das Leerlauf-Gate.

## Noch offen

- unabhängiger physischer Lauf mit Android Chrome;
- reale CommonProject-Schichtableitung;
- Lesbarkeit mit echten Commons-Namen;
- vollständige Fokuspanel-Parität;
- räumliche seitliche Kamerafahrt.

## Belegbindung

- Rohbeleg: `6a0c4d2897ffb438756535694ba13ad04ab1f373d25247451ef20a4a6e9e8805`;
- v5-Forschungsarchiv: `87175f3059ad9c7d9aeb8a260dc3381d8a182f9e186817a76b82d68714f9147d`;
- installierter v5-Beweis: `2dac4b14174a973624da46b12f8b934dd85340d7a0148c2fba5273b1ddafa31c`;
- v5-Vorbereitungsbeweis: `001aa5a70261700f84ecf84b2509d596145e8c6e9ee9bfe9c351e6501798a068`;
- v5-Archivmanifest: `a76d2fb556101385f7196b4a876ef3c9193e7c99988b62983b35ac2f531ebde3`.
