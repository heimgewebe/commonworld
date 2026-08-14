# Commonworld-Katalogauslieferung: gemessene Optionen

## Entscheidung

Commonworld verwendet einen **kompakten buildgebundenen Bootstrap mit bedarfsgeladener Vollprovenienz**. Die interaktive Anwendung erhält beim Start alle Felder für Suche, Filter, Karte, Aktionen und Prüfdaten sowie genau eine Quellen-URL pro Projekt als degradationsfesten Fallback. Die vollständige Provenienz wird nur für das ausgewählte Projekt aus dem bereits vorhandenen content-addressed Detailrecord geladen und erst nach Generation-, Byte- und SHA-256-Prüfung angezeigt. Interne redaktionelle Notizen, Quellen-IDs und Handoff-Metadaten bleiben außerhalb des Startpayloads.

Ein *Bootstrap* ist der Datensatz, mit dem die Anwendung unmittelbar startet. *Buildgebunden* bedeutet: Er wird vor der Veröffentlichung deterministisch aus den kanonischen Projektdateien erzeugt und in CI auf die festgelegte Projektion geprüft.

Die interaktiven Karten werden zur Laufzeit aus diesem Bootstrap erzeugt. Eine begrenzte lineare Recovery-Einstiegsseite mit höchstens 24 Einträgen bleibt genau einmal außerhalb der Bootstrap-Modulabhängigkeit im HTML. Sie wird erst nach erfolgreichem interaktivem Start entfernt und bleibt bei deaktiviertem JavaScript oder einem fehlenden Bootstrap-Asset lesbar. Vollständige deutsche und englische Zugriffe führen über paginierte Indizes und je eine statische Projektseite; öffentliche Manifest-, Runtime- und Projekt-JSON-Dateien bleiben für Menschen, Prüfwerkzeuge und Suchmaschinen erreichbar.

## Gemessener Anlass und Ergebnis

Mit 65 Einträgen überschritt ein vollständiger Bootstrap die harte Grenze von 32 KiB gzip. Eine bloße Anhebung der Grenze wurde verworfen.

Die kompakte Projektion enthält weiterhin Titel, Zusammenfassung, Themen, Aktionen, Präsenz, Aktivitätsstatus, offizielle Links, eine Quellen-URL als Fallback sowie Prüfdatum und nächsten Prüftermin. `activity.observed_at` bleibt im Bootstrap nur dann erhalten, wenn der Status `unknown` ist und der Hinweis es tatsächlich benötigt. Vollständige Quellenlisten kommen aus dem hashgebundenen Detailrecord der ausgewählten Identität. Gleichzeitig entfällt die zweite statische interaktive Kartenliste im HTML; die Anwendung erzeugt sie bereits aus dem Bootstrap.

Gemessener Stand vom 26. Juli 2026:

- Bootstrap: 105.072 rohe Bytes, 20.132 gzip-Bytes
- HTML: 114.732 rohe Bytes, 16.352 gzip-Bytes
- HTML-Starttags: 1.293
- statische Katalogkarten: 65, ausschließlich in der einmaligen linearen Recovery-Oberfläche
- Projekt-JSON-Anfragen beim Start: 0
- doppelte Identitätspayloads beim Start: 0

### T045: Wachstumsreserve bei 94 Commons

Nach dem Ausbau auf 94 Commons lag der bisherige kompakte Bootstrap bei 147.823 rohen Bytes und 28.572 gzip-Bytes, also nur 100 Bytes unter der Warnschwelle von 28.672 Bytes. Die Warn- und Hartgrenze wurden nicht angehoben.

Zwei bedarfsgeladene Varianten wurden auf demselben 94-Einträge-Bestand gemessen:

- **keine Provenienz im Bootstrap:** 25.733 gzip-Bytes, 2.939 Bytes Warnreserve; im Degradationsfall wäre in der Fokusansicht jedoch keine Quellenreferenz mehr garantiert.
- **eine Fallback-Quelle + verifizierte Vollprovenienz:** 26.434 gzip-Bytes, 2.238 Bytes Warnreserve; vollständige Quellen werden nur für das ausgewählte Projekt aus dem bereits vorhandenen content-addressed Detailrecord ergänzt.

Gewählt wurde die zweite Variante. Sie kostet gegenüber der Null-Provenienz-Variante 701 gzip-Bytes, erhält dafür bei einem Ausfall der Catalog Platform eine sichtbare Quellenreferenz. Ein Browserbeleg mit GBIF zeigt den Übergang von einer eingebetteten Fallback-Quelle zu sechs vollständigen Quellen nach genau einem verifizierten Detailrequest. Beim Start bleiben Projekt-JSON-Anfragen bei 0.

## Vergleich der statischen Entwürfe

| Entwurf | Barrierefreiheit und No-JS | SEO | Datenschutz | Caching | Bewertung |
|---|---|---|---|---|---|
| Generierter vollständiger Bootstrap | Interaktive Ansicht startet sofort; die lineare Recovery-Liste bleibt vollständig. | Gut. | Rein statisch. | Einfach. | Bei 65 Einträgen über dem harten Payload-Budget. |
| **Kompakter Bootstrap + verifizierte Detailprovenienz** | Interaktive Startfelder bleiben sofort nutzbar; eine Quellen-URL bleibt als Fallback eingebettet, vollständige Quellen erscheinen nach Detailprüfung; DE/EN-Recovery bleibt bootstrap-unabhängig. | Öffentliche Projekt-JSON und kanonische statische Projektseiten bleiben indexierbar. | Rein statisch, keine Telemetrie oder API. | Kleiner gemeinsamer Startcache; content-addressed Detailrecords und vollständige Einzeldateien bleiben separat cachebar. | **Gewählt.** |
| HTML-Hydration | Könnte statische Karten wiederverwenden, würde das DOM zur Datenquelle machen. | Gut. | Statisch möglich. | HTML wird stärker gekoppelt. | Höhere Komplexität und zweite Wahrheitsoberfläche. |
| Segmentiertes statisches JSON | Ein kompakter Weltindex startet Suche und Karte; Segmente liefern weitere Projektionen. | Öffentliche Detaildateien bleiben indexierbar. | Rein statisch möglich. | Gute Teilcaches. | Zusätzliche Segment- und Fehlerverträge; derzeit nur als beobachtender Catalog-Platform-Pfad genutzt. |
| Bedarfsgeladene schreibgeschützte statische Lieferung | Kleinster Startindex, Details erst bei Auswahl. | Erfordert stabile statische Verweise. | Statisch möglich. | Gute Teilcaches. | Bleibt nächster Pfad, falls auch die kompakte Projektion die Grenze erreicht. |

## Schwellenwerte

Ein Umbau wird nicht durch eine feste Zahl von Commons ausgelöst. Entscheidend sind übertragene und verarbeitete Arbeit: Bootstrap-Größe, Doppelabrufe, DOM-Knoten sowie repräsentative Start-, Skript- und Task-Zeit unter vierfach gedrosselter CPU.

- **Unter 28 KiB gzip:** Normalbetrieb.
- **Ab 28 KiB gzip:** CI-Warnung und erneute Messung der Lieferoptionen.
- **Über 32 KiB gzip:** deterministischer Fehler; keine stillschweigende Budgeterhöhung.
- **Bei weiterem Wachstum:** zuerst Projektion weiter prüfen, danach bedarfsgeladene statische Details gegen den kompakten Bootstrap messen.
- **Keine Katalogzahl als Auslöser:** Migrationen erfolgen anhand gemessener Payload-, Request-, DOM- und Laufzeitwerte.

## Grenzen der Aussage

Die Messung belegt Payload-, Request- und DOM-Eigenschaften der geprüften Oberfläche. Einzelne Zeitwerte hängen zusätzlich von Browser, Rechner und Scheduling ab und beweisen allein keine Beschleunigung. Die vollständigen kanonischen Projektdateien bleiben die einzige Katalogwahrheit; der Bootstrap ist eine deterministische, ausdrücklich unvollständige Startprojektion.

## GitHub Pages und Catalog Platform v1

Manifest, Offline-Weltindex, SHA-256-Präfix-Shards und Einzeldateien werden weiterhin hashgebunden geladen. Suche, Filter, Karte und Karten-/Listenpräsentation bleiben auf dem kompakten Bootstrap. Für die aktuell ausgewählte Identität darf die bereits vorhandene Detailprüfung nach erfolgreicher Parität die vollständige Provenienz in der Fokusansicht ergänzen; bei Fehlern bleibt die eingebettete einzelne Quellen-URL als Fallback sichtbar.
