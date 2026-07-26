# Commonworld-Katalogauslieferung: gemessene Optionen

## Entscheidung

Commonworld verwendet einen **kompakten buildgebundenen Bootstrap**. Die interaktive Anwendung erhält beim Start alle Felder, die sie für Suche, Filter, Karte, Aktionen, Quellenlinks und Prüfdaten benötigt. Interne redaktionelle Notizen, Quellen-IDs und Handoff-Metadaten bleiben ausschließlich in den vollständigen kanonischen `CommonProject`-Dateien unter `catalog/projects/`.

Ein *Bootstrap* ist der Datensatz, mit dem die Anwendung unmittelbar startet. *Buildgebunden* bedeutet: Er wird vor der Veröffentlichung deterministisch aus den kanonischen Projektdateien erzeugt und in CI auf die festgelegte Projektion geprüft.

Die interaktiven Karten werden zur Laufzeit aus diesem Bootstrap erzeugt. Eine vollständige lineare Recovery-Liste bleibt genau einmal außerhalb der Bootstrap-Modulabhängigkeit im HTML. Sie wird erst nach erfolgreichem interaktivem Start entfernt und bleibt bei deaktiviertem JavaScript oder einem fehlenden Bootstrap-Asset lesbar. Öffentliche Manifest-, Runtime- und Projekt-JSON-Dateien bleiben für Menschen, Prüfwerkzeuge und Suchmaschinen erreichbar.

## Gemessener Anlass und Ergebnis

Mit 65 Einträgen überschritt ein vollständiger Bootstrap die harte Grenze von 32 KiB gzip. Eine bloße Anhebung der Grenze wurde verworfen.

Die kompakte Projektion enthält weiterhin Titel, Zusammenfassung, Themen, Aktionen, Präsenz, Aktivitätsstatus, offizielle Links, Quellenlinks sowie Prüfdatum und nächsten Prüftermin. Entfernt werden nur nicht startrelevante Transportfelder. Gleichzeitig entfällt die zweite statische interaktive Kartenliste im HTML; die Anwendung erzeugt sie bereits aus dem Bootstrap.

Gemessener Stand vom 26. Juli 2026:

- Bootstrap: 105.072 rohe Bytes, 20.132 gzip-Bytes
- HTML: 114.732 rohe Bytes, 16.351 gzip-Bytes
- HTML-Starttags: 1.293
- statische Katalogkarten: 65, ausschließlich in der einmaligen linearen Recovery-Oberfläche
- Projekt-JSON-Anfragen beim Start: 0
- doppelte Identitätspayloads beim Start: 0

## Vergleich der statischen Entwürfe

| Entwurf | Barrierefreiheit und No-JS | SEO | Datenschutz | Caching | Bewertung |
|---|---|---|---|---|---|
| Generierter vollständiger Bootstrap | Interaktive Ansicht startet sofort; die lineare Recovery-Liste bleibt vollständig. | Gut. | Rein statisch. | Einfach. | Bei 65 Einträgen über dem harten Payload-Budget. |
| **Kompakter Bootstrap** | Interaktive Felder und Quellenlinks bleiben vollständig nutzbar; die bootstrap-unabhängige Recovery-Liste enthält den vollständigen Katalog. | Öffentliche Projekt-JSON und statische lineare Karten bleiben indexierbar. | Rein statisch, keine Telemetrie oder API. | Kleiner gemeinsamer Startcache; vollständige Einzeldateien bleiben separat cachebar. | **Gewählt.** |
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

Manifest, Offline-Weltindex, SHA-256-Präfix-Shards und Einzeldateien werden weiterhin beobachtend und hashgebunden geladen. Der sichtbare Katalog bleibt auf dem kompakten Bootstrap, solange ein bedarfsgeladener Detailpfad nicht separat mit Fehlerzuständen, Deep Links und Browserbelegen freigegeben wurde.
