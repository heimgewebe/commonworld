# Intentionsorientierte Suche und Entdeckung – Umsetzungsvertrag v1

## Zweck

T007 ersetzt die bisherige lineare Teilzeichensuche durch eine nachvollziehbare Entdeckungslogik. Menschen können auf Deutsch nach Vorhaben, Aktionen, Themen und öffentlichen Orten suchen. Die Suchoberfläche zeigt eine feste Rangfolge, Trefferzahl, leere Zustände und sechs kombinierbare Filter.

## Wahrheitsgrenze

`CommonProject` bleibt die einzige dauerhafte Projektwahrheit. Der Suchindex wird beim Laden eines Katalogstandes einmalig im Arbeitsspeicher abgeleitet und nie als zweite Projektdatei gespeichert. Das deutsche Vokabular übersetzt nur bekannte katalogisierte Werte, etwa „mitmachen“ auf die Aktion `contribute`; es erfindet keine Fähigkeiten, Orte oder Beziehungen.

Verborgene Ortsangaben werden nicht indexiert. Rein digitale Commons erhalten auch durch Suchtreffer keine Kartenkoordinate. Ein geografischer Treffer darf die Karte erst nach ausdrücklicher Aktivierung und nur zu einer bereits veröffentlichten Kartenrepräsentation bewegen. Tippen und Filtern verändern die Kamera nicht.

## Ergebnisoberfläche

Die Globusoberfläche und die Textansicht verwenden denselben vorbereiteten Index, dieselbe Rangfolge und dieselben `CommonProject.id`-Werte. Die Ergebnisliste ist per Pfeiltasten, Pos1, Ende und Escape bedienbar. Auf iPad und mobilen Ansichten bleiben Filter und Treffer innerhalb des sichtbaren Bereichs; Bedienelemente besitzen mindestens 44 CSS-Pixel Höhe.

## Filter

Die Filter `presence`, `action`, `language`, `access`, `freshness` und `curation` werden gemeinsam mit der Suchanfrage in der URL gespeichert. Unbekannte URL-Werte werden verworfen. Fehlende Sprach- oder Zugangsangaben bleiben ehrlich `unknown`.

## Handlungsziele

Eine im Katalog behauptete Aktion darf nur erscheinen, wenn genau ein direkter HTTPS-Link desselben Aktionstyps vorhanden ist. Der Link muss über `source_ids` an eine vorhandene Provenienzquelle gebunden sein. Nicht belegbare Aktionen werden entfernt, nicht auf eine allgemeine Homepage umgedeutet.

## Skalierungsgrenze

Eine reproduzierbare Probe mit 50.000 synthetischen Identitäten belegt den einmaligen Indexaufbau und die anschließende Suche über ein invertiertes Stichwortverzeichnis. T007 behauptet damit keine endgültige Millionen-Commons-Auslieferung, keine serverseitige Suche und kein semantisches KI-Modell. Segmentierte Veröffentlichung und verteilte Suchindizes bleiben eine spätere Architekturaufgabe.
