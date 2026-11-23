# Commonworld – geografischer Kontext statt künstlicher Einzelpunkte (Plan v1)

**Stand:** 23. November 2026 · **Status:** zur Umsetzung vorgesehen, **nicht implementiert** · **Ausgangsrevision:** `8b203c8760af3bf0d83152111f891ce852bddd04` (PR #250)
**Leitfrage:** Wie werden verortbare Commons auf dem Globus auffindbar, wenn sie kein einzelner Standort sind?

## 1. Ziel und Erfolg

Geografisch zuordenbare Commons sollen auffindbar und verständlich sein, ohne deshalb eine Gebäudeadresse oder einen erfundenen Mittelpunkt erhalten zu müssen. Auf der aktiven Version sind **120 CommonProjects**, **70 mit öffentlicher Geometrie**, **72 öffentliche Geometrien**, **20 mit ausschließlich verborgenen Ortsbezügen** und **30 ohne geografische Präsenz** vorhanden. Dies ist eine **Basismessung**, kein dauerhaft hartkodierter Zielwert. Der [Einzelfallbericht vom 22. November](../evidence/commonworld-hidden-geography-review-2026-11-22.md) begründet die 20 offenen geografischen Fälle.

**Erfolg** ist nicht, aus 20 verborgenen Orten 20 Punkte zu machen. Erfolg ist, dass ein Commons mit belegtem regionalem oder verteiltem Wirkungsbezug über Globus *und* Textansicht gefunden, richtig eingeordnet und ausgewählt werden kann; private Standorte bleiben privat. Die Oberfläche sagt, ob sie einen **Ort**, einen **geografischen Zusammenhang** oder eine **nachgewiesene Teilmenge eines Netzwerks** zeigt. Sie suggeriert keine Vollständigkeit.

Der Plan ergänzt die bestehende Beschränkung in [Masterplan, Aggregation](../blueprints/commonworld-masterplan.md), die bereits einen ausdrücklich quellengebundenen Regionskontext vorsieht. Er setzt **keinen neuen Kartenprovider, Backenddienst, GIS-Stack oder generellen Datenmodellumbau** voraus.

## 2. Vier getrennte räumliche Aussagen

| Aussage | Öffentliche Repräsentation | Was ausdrücklich nicht behauptet wird |
| --- | --- | --- |
| **Konkreter Standort** | Verifizierter öffentlicher Punkt oder echte öffentliche Projektfläche, bestehende Modi `exact` / `approximate` | Dass ein Büro den gesamten Verbund abdeckt |
| **Regionaler Bezug / Wirkungsraum** | Identifizierbare Stadt, Verwaltungseinheit, Landschaft oder Bioregion mit Quellenbindung, *eigenem Kontext-Look* und Aussageart | Dass die Verwaltungsgrenze das tatsächliche Commons-Gebiet exakt beschreibt |
| **Dezentrales Netzwerk** | Belegte öffentliche Teilregionen oder Teilstandorte einer Identität; gegebenenfalls nur Länder-/Regionszuordnung samt Netzwerkliste | Vollständige Mitgliederliste, Netzgeometrie oder künstlicher Zentralstandort; keine Linien zwischen bloßen Verbindungen |
| **Vertrauliche Lage** | Kein aus dem verborgenen Eintrag abgeleiteter Kartenpunkt, keine Grenze und keine räumliche Aggregation; höchstens **separat** verifizierter, freigegebener öffentlicher Kontext | Indirekte Rekonstruktion der eigentlichen verborgenen Orte |

**Grundsatz:** „Ort liegt hier“ ist eine andere Aussage als „Projekt bezieht sich auf diese Region“. Ein Regionsumriss als **Kartengrundlage/Referenz** darf niemals im gleichen visuellen Modus wie ein tatsächlich belegter Commons-Flächenumfang erscheinen. Bei unbestimmter Gebietsausdehnung **keine erfundene Polygonfläche**. Das Einblenden eines Regionennamens schafft keinen neuen exakten Projektstandort.

## 3. Kleinste fachlich tragfähige Architektur

1. **Bestehendes beibehalten:** `catalog/projects/*.json` bleibt die einzige kanonische Commons-Identität; `presence.geographic` mit `exact`, `approximate`, `hidden` sowie Point/Polygon/MultiPolygon bleibt zunächst unverändert. Vorhandene sichtbare Punkte dürfen nicht zu Kontextmarkern umetikettiert werden.
2. **Öffentlichen Kontext gesondert modellieren:** Zuerst eine schmale, versionierte, **redaktionell geprüfte Ableitung außerhalb des CommonProject-v4-Schemas** (beispielsweise `catalog/regional-contexts.v1.json`). Das folgt dem vorhandenen Abschnitt `future_aggregate_only_region_context` in `contracts/commonworld/aggregation-zoom.contract.json` und vermeidet eine vorgezogene v4→v5-Migration. Nur falls ein konkreter Pilot nachweislich daran scheitert, eine additive kanonische Felderweiterung evaluieren.
3. **Minimaler Datensatz je Zusammenhang:** stabile `project_id`, öffentliche `region_id`/Verweis auf etablierte geografische Referenz, `relation` (z. B. Sitz/Koordination, öffentlicher Wirkungsbezug oder belegter Netzwerkbezug), `source_ids`, öffentlich begründete Sichtbarkeit, minimale sinnvolle semantische Ebene, `coverage_claim` (z. B. `none`/ `partial`/ `authoritative_extent`) und eine verständliche DE/EN-Beschreibung. Quellen-IDs müssen auf **prüfbare Primärquellen** des Commons oder ein ausdrücklich versioniertes Quellenverzeichnis verweisen; der bloße bisherige `hidden.label`-Text autorisiert **keine** Veröffentlichung. Keine personenbezogenen Mitgliederpositionen.
4. **Bestehende Geo-Assets nutzen:** Die MapLibre-Globusoberfläche, öffentliche Ländergrenzen und `fitBounds` für den **Bildausschnitt** reichen für den ersten vertikalen Schnitt. Eine Bildschirmfahrt zu einer benannten Region ist **kein gespeicherter Projektpunkt**. Zusätzliche Regionalgrenzen nur dann als kleine, lizenzgeprüfte statische Teilmenge aufnehmen, wenn ein Pilot ohne sie tatsächlich keinen brauchbaren Kartenbezug erhält. Eine dynamische Welt-Grenzdatenbank ist nicht erforderlich.
5. **Eine Identität, mehrere Bezüge:** `CommonProject.id` bleibt Auswahl-, Such- und Zähleinheit. Netzwerke mit mehreren belegten Teilregionen werden global **einmal** gezählt; Filter und Fokus bleiben über Karten-, Digital- und Textansicht erhalten. Kontext-Regionen werden **nicht** als `public_points`, neue `spatial_cells` oder als echte Betriebsflächen gezählt.

**Umgang mit Zählungen und Datenschutz:** Die bisherigen Ländereindrücke basieren auf veröffentlichten Geometrien und dürfen nicht stillschweigend um bloße Regionszugehörigkeiten erweitert werden. Falls später regionale Kontext-Summen angezeigt werden, erhalten sie eine **separat gekennzeichnete Zahl dokumentierter Bezüge**, nicht eine Flächendichte oder Behauptung über die Zahl aller Commons. Für dynamische kleine Teilmengen gelten die bestehenden Schutz- und Kohortenregeln aus `visual-semantics.contract.json`. Verborgene Lage bleibt außerhalb jeder regionalen Projektionsableitung. Öffentlicher Regionskontext muss **unabhängig** belegt und hinsichtlich indirekter Rückschlüsse geprüft sein.

## 4. Pilot: drei absichtlich unterschiedliche Nutzerwege

| Pilot-Common | Aussage | Erstes abnahmefähiges Verhalten |
| --- | --- | --- |
| `berkshares` | Regionales Tausch- und Währungssystem in der Berkshire-Region, Massachusetts | Suche findet BerkShares; „Berkshire-Region – geografischer Bezug, keine einzelne Ausgabestelle“; Globus markiert den **Referenzraum** unterscheidbar von Büro/Standort, falls sein Umriss quellengesichert vorliegt; sonst benannte Region mit begrenztem Kartenausschnitt und sichtbarer Kontextinformation |
| `great-lakes-commons` | Grenzüberschreitender ökologischer/gesellschaftlicher Bezug zu den Großen Seen | Auswahl zeigt einen benannten **Bioregionsbezug**, keine US-/Kanada-Verwaltungsgrenze als vermeintliche Commons-Grenze; wenn keine redaktionell geeignete Referenzgeometrie vorhanden ist, **keine Fläche erfinden**; Text- und Kartenkontext bleiben benutzbar |
| `coopcycle` | Mehrere unabhängige, wechselnde lokale Kurierkooperativen | Kein Weltmittelpunkt; belegte, aktuell öffentlich geführte **Teilorte/-regionen** nur als nachweislich unvollständige Netzwerkauswahl und ein einzelner Commons-Fokus. Wo die Quelle die Standorte nicht zuverlässig bestätigt, ist die Netzwerkaussage ohne lokale Marker verfügbar |

**Negativkontrollen:** `zapatista-autonomy` und `north-east-syria-autonomous-administration` dürfen nicht durch die neue Funktion automatisch mit Gebietsgrenzen oder administrativen/sicherheitsbezogenen Standorten erscheinen. `sewa-sangini-childcare-cooperative` darf keine Betreuungs- oder Kinderadressen freigeben; `the-things-network` erhält keine aus Gateways rekonstruierte Karte. Ein ausschließlich digitales Commons bleibt ohne erfundene Geografie. Die bisherigen 70 öffentlich abgebildeten Commons bleiben unverändert.

Die genannten Pilotbezüge sind **Arbeitsannahmen aus veröffentlichten Projektbeschreibungen**, keine hiermit freigegebenen geometrischen Wahrheiten. Vor Datenänderung Primärquellen, geografische Referenzidentität, Änderungsdatum, Lizenz und Bedeutung des öffentlichen Bezugs je Pilot neu dokumentieren.

## 5. Umsetzung – höchstens drei kleine PRs

### PR A: Drei geprüfte öffentliche Regionskontexte

- Ein eng begrenztes, versioniertes Kontextmanifest samt Validator und **genau den drei Pilotfällen** anlegen, ohne bestehende `presence.geographic`-Records umzudeuten.
- Referenz-IDs, Aussageart, Quellen, Sichtbarkeitsentscheidung, Mindestzoom und Vollständigkeitskennzeichen prüfen; fehlende amtliche/autoritative Grenzgeometrie **nicht** in einen synthetischen Punkt umwandeln.
- Tests: nicht autorisierte/ungeprüfte Region, unbekannte Referenz-ID, `hidden.label` als einzige Quelle, falsche Quellen-IDs, versteckte Teilstandorte, doppelte Identitäten sowie Koordinaten-/Grenz-Leaks müssen abgewiesen werden.

**Exit A:** Quellen und Datenmodell bilden alle drei Beispiele ausdrucksstark ab, ohne bestehende öffentliche Geometrie oder versteckte Lage zu verändern. Kein neuer Anbieter-/Backendbedarf.

### PR B: Sichtbarer Globus- und Textansichts-Nutzerweg

- Im bestehenden MapLibre-Pfad eine **eigenständige, eindeutig betitelte Kontextdarstellung** für benannte Regionen nutzen; nur bei passender öffentlich überprüfter Referenzgeometrie Rand/Highlight anzeigen. Keine angeblichen Commons-Ausdehnungen aus Verwaltungsgrenzen machen.
- Auswahl/Fokus: Im Suchresultat und Projektpanel „Standort“, „regionaler Bezug“ bzw. „verteiltes Netzwerk“ anzeigen; bei Regionenauswahl den bekannten **Regionen-Bildausschnitt** statt einen erfundenen Koordinatenpunkt anfahren.
- Text-/No-JS-Ansicht zeigt denselben Kontext mit Quellen und gegebenenfalls öffentlichem Regionslink. Sprachwechsel, Suche, Filter und Fokus erhalten `CommonProject.id`; mobile Touch- und Tastaturnavigation bleiben nutzbar.
- Keine interaktiven flächendeckenden Regionskarten mit Tausenden Features vorab, kein zusätzlicher WebGL-Kontext und keine vollständigen Mitglieds-/Gateway-Listen.

**Exit B:** BerkShares, Great Lakes Commons und CoopCycle sind über Suche → Kontext → Globus/Text/Fokus **ohne irreführende Standortbehauptung** zugänglich; private Lage nicht exponiert.

### PR C: Die übrigen 17 Einträge erneut redaktionell entscheiden

- Alle 20 bislang `hidden`-only Einträge nach PR B neu in drei Klassen prüfen: **öffentlich kontextualisierbar**, **nur klar belegte öffentliche Teilorte darstellbar**, **weiterhin ohne geografische Veröffentlichung**. Die drei Pilotfälle nicht doppelt zählen.
- Kandidaten mit allgemein belegtem Regionalkontext sind unter anderem `bioleft`, `community-energy-network-new-zealand`, `sungai-utik-community-forest`, `tela-botanica`, `open-source-seed-initiative` und `bangladesh-palli-bidyut-samities`. Das ist **keine pauschale Freigabe**: Einzelfallprüfung von Quellen, Verwechslungsrisiko und möglicher Sensibilität.
- Für jedes der 20 Projekte Ergebnis, Quellenbeleg, öffentliche Aussage und begründeten Ausschluss im bestehenden [Geo-Audit](../evidence/commonworld-hidden-geography-review-2026-11-22.md) aktualisieren. **Keine Quote „alle 20 müssen auf die Karte“**; eindeutig unerklärbare/gefährdende Kontexte bleiben ohne räumliche Veröffentlichung.

**Exit C:** 20/20 Entscheidungen mit begründetem Ergebnis; jede genehmigte Kontext-Darstellung im aktiven Produkt auffindbar; der Rest ausdrücklich nachvollziehbar.

## 6. Produktabnahme und Erfolgsmessung

1. **Funktion:** Alle drei Piloten über echte Suche → Auswahl → Region/Netzwerk-Kontext → Globus/Textansicht, auch bei Mobile/iPad-Viewport und Tastatur; Auswahl bleibt nach Sprach-/Ansichtswechsel erhalten. Keine irreführende Aussage „Das Projekt befindet sich exakt hier“.
2. **Datenwahrheit:** bestehende öffentliche `exact`-/`approximate`-Geometrien byte- bzw. semantikgleich; für verborgene Orte null neue Detailkoordinaten, Leitungen, Wohnungen, Schutzflächen oder abgeleitete Personennetze. Öffentliches `project_id` nur einmal pro Identitätszählung. Regionskontext zählt **nicht** als zusätzliches physisches Commons.
3. **Evidenz:** eine verifizierte offizielle/autoritative Quelle plus bei jeder neuen Kartengrenze deren belastbare Referenz, Versions-/Lizenznachweis und öffentlich verständliche Aussageart. Negative/sensible Fälle durch Validator- und Browser-Regressionsfälle beweisen.
4. **Betrieb:** deterministischer `npm run build`, `make validate`, relevante echte Chromium- und WebKit/BrowserStack-Nutzerpfade mit **vorhandenem Scan 4341414** nur falls Accessibility-Scan tatsächlich benötigt wird; bestehende statische Lieferbudgets nicht durch dynamische Welt-Polygonmengen sprengen.
5. **Produktivschluss:** geprüften Head integrieren, Pages-Deployment und Produktions-Readback exakt an Merge SHA binden, reale öffentliche Suche/Region-Fokus und DE-/EN-Text-Readback ausführen. **Merge oder grüne CI allein sind keine Endabnahme.**

**Messwerte getrennt ausweisen:** Commons insgesamt, Commons mit öffentlich exakten/ungefähren/geometrischen Standorten, Commons **mit zusätzlichem regionalem Kontext ohne punktgenauen Standort**, Commons mit bewusst zurückgehaltener Lage und geografisch tatsächlich ortslose digitale Commons. Keine Doppelzählung oder Umdeutung von `hidden` als „nicht geografisch existent“.

## 7. Grenzen und kleinster nächster Schritt

Der erste ausführbare Arbeitsschritt ist **PR A mit drei Pilotfällen**. Erst wenn dieser belegt, dass Regionskontexte mit dem vorhandenen statischen Kartensatz brauchbar sind, wird ein möglicher zusätzlicher kleiner Regionalgrenzen-Datensatz oder eine additive Feldänderung erwogen. Kein PostGIS, PMTiles, Server, dynamischer Netzwerkscraper, globales Geocoding aller Kontakte, neuer Genehmigungsprozess oder umfassender CommonProject-v5-Umbau.

Die ältere Bureau-Aufgabe `COMMONWORLD-PUBLIC-GLOBE-V1-T021` ist **cancelled** und wird durch diesen Plan **nicht automatisch reaktiviert**. Neue Umsetzung ausschließlich als aktuelle, duplikatfreie, eng umrissene Arbeit gegen die verifizierte Hauptrevision registrieren. Das historische `future_aggregate_only_region_context` bleibt Entscheidungsbeleg, nicht ein zusätzlicher operativer Gate.

**Nicht in diesem Plan erledigt:** Datenschemaänderung, neue Kartenfunktion, Freigabe konkreter Regionspolygone oder Produktivveröffentlichung neuer Kontexte.
