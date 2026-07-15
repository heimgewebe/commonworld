# Reale geografische und hybride Commons – Umsetzungsvertrag v1

## Zweck

Diese Vertikalscheibe erweitert den bisherigen rein digitalen Startkatalog um zwei reale, quellengebundene Identitäten. Alle Darstellungen werden aus `CommonProject` abgeleitet; Karte, digitale Sphäre, Textansicht und Fokus besitzen keine eigene Datenwahrheit.

## Fälle

### Le Nid

`cltb-le-nid` ist ein geografisches Commons. Die offizielle CLTB-Seite nennt Adresse, sieben Wohnungen, Gemeinschaftsraum und halböffentlichen Garten. OpenStreetMap enthält am selben Ort ein ausdrücklich `Le Nid` benanntes Gebäude mit sieben Wohnungen. Deshalb werden ein öffentlicher Adresseinstieg als Punkt und die benannte Gebäudefläche als Polygon veröffentlicht. Benachbarte, nicht eindeutig zugeordnete Flächen werden nicht übernommen.

### Freifunk Hamburg

`freifunk-hamburg` ist ein hybrides Commons. Die offizielle Freifunk-API liefert einen Community-Kontaktpunkt und digitale Community-Metadaten. Der Punkt wird mit mindestens fünf Kilometern Unschärfe als Community-Verortung veröffentlicht. Private Heimrouter bleiben als verborgene Ortsrepräsentation ohne Geometrie dokumentiert. Die Identität verweist mit einer quellengebundenen `chapter-of`-Beziehung auf `freifunk`.

## Ableitungsregeln

- Exakte Punkte werden als `exact_anchor` abgeleitet.
- Exakte Polygone und Mehrfachpolygone werden als `public_extent` abgeleitet.
- Ungefähre öffentliche Geometrien werden als `approximate_anchor` abgeleitet und behalten `uncertainty_meters_min`.
- Verborgene Orte erzeugen niemals GeoJSON, Marker, Fläche oder Ersatzkoordinate.
- Jede Kartenrepräsentation trägt `project_id = CommonProject.id`.
- Eine hybride Identität bleibt eine Identität, auch wenn sie geografisch und digital sichtbar ist.
- Beziehungen werden nur aus katalogisierten `relations` übernommen; unbekannte Ziele oder bloß vermutete Verbindungen werden nicht dargestellt.

## Semantischer Zoom

`planet` und `macroregion` zeigen nur zusammenfassende Information. `region` darf öffentliche Flächen und ungefähre Verortungen zeigen. `local` zeigt alle öffentlichen Punkte und Flächen. `focus` zeigt genau einen vollständigen CommonProject-Datensatz. Zoomstufen sind Präsentationslogik und werden nie in den Katalog geschrieben.

## Prüfgrenzen

Der allgemeine Produktionsvalidator erlaubt geografische, digitale und hybride Datensätze mit offiziellen Quellen oder öffentlichen Registern. Ein eigener Seed-Validator bewahrt die ursprünglichen zehn rein digitalen Startdatensätze. Ein dritter Validator bindet die T006-Fälle und Datenschutzinvarianten.
