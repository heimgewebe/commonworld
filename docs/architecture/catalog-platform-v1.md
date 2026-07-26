# Commonworld Catalog Platform v1

## Entscheidung

Commonworld trennt Anwendung, Katalogwahrheit und öffentliche Projektion.

- **Commonworld** bleibt eine konto- und schreibfreie Entdeckungsoberfläche.
- **Weltgewebe** ist die geplante Erfassungs-, Vorschlags-, Moderations- und Administrationsgrenze.
- **PostgreSQL** ist perspektivisch die einzige veränderbare Katalogwahrheit.
- **PostGIS** ergänzt räumliche Filter, Kacheln und regionale Aggregationen, sobald der Weltgewebe-Cutover belegt ist.
- **Rust/Axum** liefert dieselben öffentlichen, sichtbarkeitsgeprüften Projektionen als API und Snapshot-Exporter.
- **Immutable statische Snapshots** bleiben der primäre Commonworld-Lesepfad und können über GitHub Pages oder später ein CDN ausgeliefert werden.

Der öffentliche Browser erhält nur veröffentlichte Daten. Der Übergangspfad liefert weiterhin den buildgebundenen vollständigen Bootstrap; zusätzlich lädt die Runtime ein kleines Aggregat, genau den Shard einer ausgewählten Identität und danach genau deren hashadressiertes Detail im Shadow-Modus. Der Shadow-Pfad ersetzt keine sichtbaren Daten.

## Warum diese Grundlage zum Weltgewebe passt

Weltgewebe verwendet bereits SvelteKit, TypeScript/Vite, Rust/Axum, PostgreSQL, MapLibre/PMTiles und plant PostGIS, Kubernetes/GitOps, NATS JetStream und eine Transactional Outbox. Commonworld übernimmt davon nur die stabilen Plattformgrenzen, nicht die gesamte Runtime.

Die gemeinsame Linie lautet:

1. Weltgewebe mutiert und moderiert kanonische Datensätze.
2. Eine Outbox beziehungsweise revisionsgebundene Projektionspipeline erzeugt öffentliche Generationen.
3. Axum exportiert dieselbe Projektion als API und immutable Snapshot.
4. Commonworld konsumiert bevorzugt Snapshots; API-Abfragen dienen später Suche, Deep-Links und sehr frischen Teilmengen.
5. CDN, Pages oder Object Storage dürfen austauschbar sein, weil Dateiformat, Hashbindung und Generations-ID unabhängig vom Auslieferer sind.

## Datenebenen

### Ebene 0: Manifest

Klein, cachebar und atomar austauschbar. Es enthält Generation, Anzahl, Aggregat- und Weltindexdescriptoren, Sharddescriptoren sowie den Vertrag für hashadressierte Details.

Die Generations-ID ist SHA-256 über einen kanonischen Seed aus:

- Hash des Quellkatalogs,
- Hash der geordneten Detaildescriptor-Menge,
- CommonProject-Schemaversion,
- Detaildescriptor-Version.

Damit ändert sich die Generation bei jeder relevanten Detail- oder Vertragsänderung, ohne einen zirkulären Hash zwischen Manifest und Shards zu erzeugen.

### Ebene 1: Weltindex

Startrelevante Felder: Identität, Titel, Themen, Handlungen, Sprachen, Zugang, öffentliche Präsenz, Aktivitätsstatus und ein generationsgebundener Detaildescriptor. Keine Zusammenfassungen, Quellenlisten, Links, redaktionellen Notizen oder Handoff-Daten.

Der vollständige Weltindex bleibt Export- und Prüffläche. Er ist für große Kataloge ausdrücklich kein initialer Browserpfad.

### Ebene 2: Aggregat und Shards

Das Aggregat ordnet Themen, 10-Grad-Raumzellen und digitale Verfügbarkeit stabilen SHA-256-Präfix-Shards zu. Ein Shard enthält kompakte Records einschließlich Detaildescriptor, aber keine vollständigen Details.

Zwei Hexzeichen ergeben höchstens 256 Partitionen. Eine Identität bleibt bei Inhaltsänderungen im selben Shard; die Generation und die Integritätshashes ändern sich trotzdem.

### Ebene 3: Details

Jede vollständige öffentliche CommonProject-Projektion wird kanonisch serialisiert und unter

`catalog/runtime/details/{sha256}.v1.json`

abgelegt. Der Compact Record trägt `identity`, `generation`, `url`, `sha256` und `bytes`. Ein mutable Pfad wie `catalog/projects/{id}.json` ist kein Runtime-Ladepfad.

## Zweischichtige Validierungsgrenze

Build und CI validieren jeden kanonischen Datensatz vollständig gegen CommonProject-Schema v4 und serialisieren ihn deterministisch.

Der Browser implementiert bewusst keine zweite vollständige JSON-Schema-Engine. Er prüft stattdessen:

1. Same-Origin und Dokumentwurzel,
2. aktuell akzeptierte Manifestgeneration,
3. Descriptor-Identität und content-addressed URL,
4. Bytezahl und SHA-256 vor dem Parsen,
5. UTF-8 und JSON,
6. `schema_version: 4` und begrenzte Top-Level-Form,
7. ausgewählte Identität,
8. exakte Parität der kompakten Projektion,
9. exakte Parität mit dem buildgebundenen kanonischen Datensatz im Shadow-Modus.

Die Byte- und Hashbindung macht die vollständige CI-Schemavalidierung transportwirksam. Ein Fehler oder Mismatch ersetzt niemals den sichtbaren Bootstrap.

## Runtime-Zustände und Cachegrenzen

Für die ausgewählte Identität veröffentlicht die Stage getrennte Shard- und Detailzustände:

- `idle`
- `loading`
- `retrying`
- `ready`
- `mismatch`
- `degraded`

Der Shardcache ist auf 8, der Detailcache auf 16 Einträge begrenzt. Beide verwenden deterministische LRU-Verdrängung. Fehlgeschlagene Promises werden entfernt und können erneut geladen werden. Ein Generationswechsel leert beide Caches. Ein gemeinsamer Auswahlzähler verhindert, dass verspätete Antworten eine neuere Auswahl überschreiben.

Bei einem Detailfehler bleiben Titel, Zusammenfassung, Links, Quellen, Karte, Suche und Textansicht aus dem kompatiblen Bootstrap nutzbar. Eine sichtbare, lokalisierte Wiederholungsaktion verwirft beide Shadow-Caches, lädt Manifest und Aggregat frisch und verifiziert danach Shard und Detail der weiterhin ausgewählten Identität erneut. Damit kann sie sowohl einen transienten Plattformausfall als auch einen gestaffelten Snapshot-Rollout überwinden. Nach erfolgreicher Wiederholung wird der Tastaturfokus auf einen sichtbaren Kontext zurückgeführt.

## Skalierungsweg

- Bis zu einem gemessenen Payload- oder Renderengpass: buildgebundener Übergang plus Shadow-Manifest, Aggregat, ausgewählter Shard und ausgewähltes Detail.
- Nach vollständig belegtem Cutover: kleines Aggregat plus bedarfsgeladene Shards und Details.
- Bei globaler Volltextsuche: serverseitige PostgreSQL-FTS/`pg_trgm`-Suche über Axum; semantische Ergänzung nur nach Qualitätsvertrag.
- Bei sehr großen Geometrien: PMTiles aus PostGIS-Projektionen, nicht GeoJSON-Volltransfer.
- ANN/HNSW, separater Suchdienst und Elasticsearch/Typesense/Meilisearch bleiben ohne belegten Engpass ausgeschlossen.

Die Schwellen sind Messpunkte, keine harten Katalogzahlen.

## Gemessene Skalierungsgrenzen vom 26. Juli 2026

Die reproduzierbare synthetische Messung liegt in `docs/evidence/catalog-platform-scaling-v1.json`. Sie verwendet die aktuelle kompakte Datensatzform einschließlich generationsgebundener Detaildescriptoren und eine deterministische SHA-256-Präfixverteilung.

| Einträge | Vollindex gzip | Median Parsezeit | größter Shard gzip | maximale Einträge je Shard |
| ---: | ---: | ---: | ---: | ---: |
| 10.000 | 624.128 Byte | 59,844 ms | 4.231 Byte | 59 |
| 100.000 | 6.237.810 Byte | 1.003,180 ms | 28.683 Byte | 440 |

Der Descriptor erhöht den Weltindex gegenüber der früheren ungebundenen Detailreferenz deutlich. Genau deshalb bleibt der vollständige 100k-Weltindex als initiale Browserlieferung verworfen. Der größte bedarfsgeladene Shard bleibt unter dem festgelegten 32-KiB-gzip-Budget.

Die Messung ist synthetisch. Sie belegt Payload, lokale Parsegröße und Shardgrenze, aber keine reale Mobilfunklatenz oder physische iPad-Bedienbarkeit.

## Invarianten

1. Keine zweite veränderbare Wahrheit in Commonworld.
2. Nur veröffentlichte und sichtbarkeitsgeprüfte Daten gelangen in Snapshots.
3. Verborgene Orte bleiben ohne rekonstruierte Geometrie.
4. Eine Manifestgeneration bindet Quellkatalog, Detailmenge und relevante Schemaverträge.
5. Ein Manifest verweist nur auf Artefakte, deren Hash und Größe es oder ein generationsgebundener Sharddescriptor festlegt.
6. Ein fehlgeschlagener Shadow-Leseweg lässt den buildgebundenen vollständigen Datensatz aktiv.
7. Suche und Karte verwenden dieselbe zulässige Kandidatenmenge.
8. Schnelle Auswahlwechsel dürfen keine ältere Antwort auf den aktuellen Fokus anwenden.
9. Erfolgreiche Shadow-Parität autorisiert weder Bootstrap-Entfernung noch Deployment oder physischen Geräte-Cutover.

## Cutover-Gate

Der Bootstrap darf erst entfernt werden, wenn alle folgenden Punkte an demselben geprüften Stand belegt sind:

- kompakte Shard- und vollständige Detailparität,
- deutsche und englische Darstellung,
- Deep-Link-, Vor-/Zurück- und No-JavaScript-Parität,
- Offline-, Integritäts-, Netzwerk-, Retry- und Stale-Response-Fälle,
- unterstützte Desktop-, Mobil- und iPad-Browserprofile,
- 4-fache CPU-Drosselung innerhalb des Budgets,
- revisionsgebundenes Rollback-Artefakt,
- Produktionsgeneration und öffentlicher Readback,
- separat ausgewiesener physischer Gerätebeleg.

Der aktuelle Vertrag setzt `cutover_authorized: false`.

## Alternative Sinnachse

Wird minimale Betriebsfläche höher gewichtet, kann Commonworld lange beim buildgebundenen Bootstrap bleiben. Wird maximale Aktualität höher gewichtet, kann Axum Teilabfragen direkt beantworten. Wird maximale Offlinefähigkeit höher gewichtet, werden Snapshots und Shards in IndexedDB gehalten. Die Integritäts- und Generationsgrenze bleibt in allen drei Fällen gleich.

## Nicht behauptet

Dieser Stand belegt noch keinen PostGIS-, Outbox-, Axum- oder Weltgewebe-Produktionspfad. Er belegt noch keine Bootstrap-Entfernung und keine physische Gerätefreigabe. Er schafft den generationsgebundenen öffentlichen Liefervertrag, einen deterministischen Snapshot-Compiler und einen fehlertoleranten ausgewählten Detail-Shadow-Pfad.
