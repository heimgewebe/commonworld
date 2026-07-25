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
2. Indexgröße und Browserkosten mit 10k/100k synthetischen Einträgen messen.
3. Client auf Manifest plus Weltindex umstellen; Details lazy laden.
4. Bootstrap-Katalog entfernen und Größenbudget auf Anwendungscode beziehen.
5. Shards und PMTiles erst nach gemessenem Bedarf aktivieren.
6. Weltgewebe-Publisher an denselben Vertrag anbinden.
7. Statische Repository-Katalogwahrheit nach belegtem Weltgewebe-Cutover zurückbauen.

## Nicht behauptet

Dieser Schnitt belegt noch keinen PostGIS-, Outbox-, Axum- oder Weltgewebe-Produktionspfad. Er schafft den kompatiblen öffentlichen Liefervertrag und einen lokalen deterministischen Snapshot-Compiler.
