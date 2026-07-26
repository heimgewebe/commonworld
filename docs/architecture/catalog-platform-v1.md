# Commonworld Catalog Platform v1

## Entscheidung

Commonworld trennt ab jetzt Anwendung, Katalogwahrheit und öffentliche Projektion.

- **Commonworld** bleibt eine konto- und schreibfreie Entdeckungsoberfläche.
- **Weltgewebe** ist die geplante Erfassungs-, Vorschlags-, Moderations- und Administrationsgrenze.
- **PostgreSQL** ist perspektivisch die einzige veränderbare Katalogwahrheit.
- **PostGIS** ergänzt räumliche Filter, Kacheln und regionale Aggregationen, sobald der Weltgewebe-Cutover belegt ist.
- **Rust/Axum** liefert dieselben öffentlichen, sichtbarkeitsgeprüften Projektionen als API und Snapshot-Exporter.
- **Statische, immutable Snapshots** bleiben der primäre Commonworld-Lesepfad und können über GitHub Pages oder später ein CDN ausgeliefert werden.

Der Browser erhält niemals den vollständigen redaktionellen Datensatz. Er lädt eine kompakte Weltprojektion, danach räumliche oder semantische Shards und vollständige Details nur bei Auswahl.

## Warum diese Grundlage zum Weltgewebe passt

Weltgewebe verwendet bereits SvelteKit 2/Svelte 5, TypeScript/Vite, Rust/Axum, PostgreSQL, MapLibre/PMTiles und plant PostGIS, Kubernetes/GitOps, NATS JetStream und eine Transactional Outbox. Commonworld übernimmt davon nur die stabilen Plattformgrenzen, nicht die gesamte Runtime.

Die gemeinsame Linie lautet:

1. Weltgewebe mutiert und moderiert kanonische Datensätze.
2. Eine Outbox beziehungsweise revisionsgebundene Projektionspipeline erzeugt öffentliche Generationen.
3. Axum exportiert dieselbe Projektion als API und immutable Snapshot.
4. Commonworld konsumiert bevorzugt Snapshots; API-Abfragen dienen später Suche, Deep-Links und sehr frischen Teilmengen.
5. CDN, Pages oder Object Storage dürfen austauschbar sein, weil Dateiformat, Hashbindung und Generations-ID unabhängig vom Auslieferer sind.

## Datenebenen

### Ebene 0: Manifest

Klein, cachebar und atomar austauschbar. Enthält Generation, Schema, Anzahl, Hashes, Shardstrategie und URL-Vorlagen.

### Ebene 1: Weltindex

Nur startrelevante Felder: Identität, Titel, Themen, Präsenzbits, grobe öffentliche Geometrie, Aktivitätsstatus und Detailreferenz. Keine Quellenlisten, langen Beschreibungen oder internen Moderationsdaten.

### Ebene 2: Shards

- räumlich: PMTiles oder deterministische H3-/Kachel-Shards;
- digital: Taxonomie-/Themen-Shards;
- Suche: lexikalische Präfix-/Sprach-Shards als Offline-Fallback;
- Länder-/Regionenaggregate für die Totalansicht.

### Ebene 3: Details

Vollständige öffentliche CommonProject-Projektion, einzeln cachebar. Quellen und Provenienz bleiben hier erhalten.

## Skalierungsweg

- Bis etwa 10.000 veröffentlichte Commons: statische Weltprojektion plus Detaildateien.
- Ab gemessenem Payload- oder Renderengpass: räumliche und semantische Shards.
- Bei globaler Volltextsuche: serverseitige PostgreSQL-FTS/`pg_trgm`-Suche über Axum; semantische Ergänzung nur nach Weltgewebe-Qualitätsvertrag.
- Bei sehr großen Geometrien: PMTiles aus PostGIS-Projektionen, nicht GeoJSON-Volltransfer.
- ANN/HNSW, separater Suchdienst und Elasticsearch/Typesense/Meilisearch bleiben ohne belegten Engpass ausgeschlossen.

Die Schwellen sind Messpunkte, keine harten Katalogzahlen.

## Invarianten

1. Keine zweite veränderbare Wahrheit in Commonworld.
2. Nur veröffentlichte und sichtbarkeitsgeprüfte Daten gelangen in Snapshots.
3. Verborgene Orte bleiben ohne rekonstruierte Geometrie.
4. Jede Generation bindet Schema, Datensatzrevision, Inhalts-Hashes und Erzeugungszeit.
5. Ein Manifest verweist ausschließlich auf Artefakte derselben Generation.
6. Ein fehlgeschlagener Snapshotwechsel lässt die vorherige vollständige Generation aktiv.
7. Suche und Karte verwenden dieselbe zulässige Kandidatenmenge.
8. Details sind bedarfsgeladen; der Bootstrap enthält keine wachsende Commons-Liste.

## Alternative Sinnachse

Wird minimale Betriebsfläche höher gewichtet, kann Commonworld lange rein statisch bleiben. Wird maximale Aktualität höher gewichtet, kann Axum Teilabfragen direkt beantworten. Wird maximale Offlinefähigkeit höher gewichtet, werden Snapshots und Shards in IndexedDB gehalten. Der Vertrag bleibt in allen drei Fällen gleich.

## Migrationsfolge

1. Vertrag und deterministischen kompakten Weltindex einführen.
2. Indexgröße und Browserkosten mit 10k/100k synthetischen Einträgen messen; Messbeleg unter `docs/evidence/catalog-platform-scaling-v1.json`.
3. Client auf Manifest plus Weltindex umstellen; Details lazy laden.
4. Bootstrap-Katalog entfernen und Größenbudget auf Anwendungscode beziehen.
5. Shards und PMTiles erst nach gemessenem Bedarf aktivieren.
6. Weltgewebe-Publisher an denselben Vertrag anbinden.
7. Statische Repository-Katalogwahrheit nach belegtem Weltgewebe-Cutover zurückbauen.

## Nicht behauptet

Dieser Schnitt belegt noch keinen PostGIS-, Outbox-, Axum- oder Weltgewebe-Produktionspfad. Er schafft den kompatiblen öffentlichen Liefervertrag und einen lokalen deterministischen Snapshot-Compiler.

## Umsetzungsstand der Skalierungsgrundlage

Der Runtime-Compiler erzeugt neben Manifest und vollständigem Offline-Weltindex deterministische SHA-256-Präfix-Shards. Zwei Hexzeichen ergeben höchstens 256 stabile Partitionen. Ein Datensatz wechselt seinen Shard nur bei Änderung seiner ID; Inhaltsänderungen invalidieren nicht den gesamten Katalog.

Der vollständige Weltindex bleibt als maschinenlesbarer Export und Prüffläche erhalten. Er ist bei großen Katalogen ausdrücklich nicht der Browser-Startpfad. Der spätere Browser lädt ein kleines Aggregatmanifest, danach nur für Viewport, Suchergebnis oder digitale Taxonomie benötigte Shards und schließlich vollständige Details.

Der UI-Cutover ist fail-closed an Feldparität gebunden. Die heutige Oberfläche benötigt neben Identität und Geometrie auch Zusammenfassung, Handlungswege, Sprache, Zugang und redaktionelle Felder. Solange Lazy-Detailzustände und Deep-Link-Fehlerpfade diese Anforderungen nicht vollständig abdecken, bleibt der bestehende Bootstrap als kompatibler Übergangspfad aktiv.

## Gemessene Skalierungsgrenzen vom 25. Juli 2026

Die reproduzierbare synthetische Messung liegt in `docs/evidence/catalog-platform-scaling-v1.json`. Sie verwendet dieselbe kompakte Datensatzform und eine deterministische SHA-256-Präfixverteilung.

| Einträge | Vollindex gzip | Median Parsezeit | größter Shard gzip | maximale Einträge je Shard |
| ---: | ---: | ---: | ---: | ---: |
| 10.000 | 154.620 Byte | 44,812 ms | 1.405 Byte | 59 |
| 100.000 | 1.541.423 Byte | 804,028 ms | 7.885 Byte | 440 |

Damit ist der vollständige 100k-Weltindex als initiale Browserlieferung verworfen. Die 256 Präfix-Shards sind als technische Grundpartition tragfähig, lösen aber allein noch keine räumliche Auswahl: Ein kleines Aggregatmanifest oder ein räumlicher PMTiles-/PostGIS-Index muss bestimmen, welche Shards beziehungsweise IDs für Viewport und Suche benötigt werden.

Die Messung ist synthetisch und keine Endgeräte- oder Netzwerkmessung. Sie belegt Payload- und lokale Parsegrößen, nicht reale Interaktionslatenz auf iPad oder Mobilfunk.

## Aggregatmanifest und Shadow-Laufzeit

Der Compiler erzeugt nun `catalog/runtime/aggregate.v1.json`. Das Aggregat enthält ausschließlich Zuordnungen von Themen, 10-Grad-Raumzellen und digitaler Verfügbarkeit zu stabilen Shard-Schlüsseln. Es enthält keine Zusammenfassungen, Links, Quellen oder redaktionellen Notizen.

Die öffentliche Anwendung lädt Manifest und Aggregat bereits nach dem kompatiblen Bootstrap im Hintergrund. Bytezahl und SHA-256 des Aggregats werden mit WebCrypto gegen das Manifest geprüft. Ein Ausfall markiert den Katalogpfad als `degraded`, verändert aber weder sichtbare Daten noch Bedienbarkeit. Damit entsteht reale Laufzeitbeobachtung vor dem eigentlichen Cutover.

Die Auswahl mehrerer aktiver Dimensionen verwendet Schnittmengen: beispielsweise Thema Wasser plus Raumzelle plus digitale Verfügbarkeit. Innerhalb derselben Dimension werden Werte vereinigt. Das Aggregat liefert nur Shard-Kandidaten; die abschließende Datensatzfilterung bleibt verbindlich.

## Selektionsgebundener Shard-Shadow-Pfad

Bei einer konkreten Commons-Auswahl leitet der Browser den stabilen Zwei-Zeichen-Shard aus dem SHA-256 der `CommonProject.id` ab. Er lädt genau diesen im Manifest deklarierten Shard, prüft URL, Bytezahl und SHA-256 und validiert anschließend Schlüssel, Eintragszahl, Identitäten und die kompakte Datensatzform. Fehlgeschlagene Anfragen werden nicht dauerhaft gecacht und können bei einer späteren Auswahl erneut versucht werden.

Die sichtbare Oberfläche bleibt weiterhin vollständig an den buildgebundenen Bootstrap gebunden. Der Shard-Pfad vergleicht nur die im kompakten Record vorhandenen Felder mit dem kanonischen Bootstrap-Datensatz und veröffentlicht einen kleinen diagnostischen Zustand am Stage-Element. Schnelle Auswahlwechsel dürfen veraltete Antworten nicht auf den aktuellen Fokus anwenden. Ein Fehler oder Mismatch leert weder Fokus, Suche, Karte noch Textansicht.

Dieser Schritt belegt noch keine Lazy-Detail-Ladung, keinen Bootstrap-Cutover, keine physische Gerätefreigabe und keine Weltgewebe-Publisher-Kette. Das nächste Gate ist ein generationsgebundener Detailpfad mit definierten Lade-, Fehler- und Deep-Link-Zuständen.

### Cutover-Gate

Der Bootstrap darf erst entfernt werden, wenn Feldparität, Deep-Link-Parität, definierte Lade- und Fehlerzustände für Details, Browser-Smoke und physischer Geräte-Readback belegt sind. Bis dahin bleibt die neue Plattform beobachtend und rückwärtskompatibel.
