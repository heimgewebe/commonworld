# Commonworld – ausgewogenes Katalogwachstum v1

Stand: 16. Juli 2026

## Ausgangslage

Der öffentliche Katalog enthielt zwölf Commons. Zehn davon waren rein digital; nur zwei Identitäten besaßen eine öffentliche Kartendarstellung. Dadurch war die technische Globusoberfläche inhaltlich stark auf freie Software und Wikimedia-Projekte konzentriert.

## Ziel dieses Pakets

Das Paket erweitert den Katalog auf zwanzig geprüfte Commons und erhöht die räumlich sichtbaren Identitäten auf zehn. Es ergänzt unterschiedliche Commons-Arten:

- Gemeinschaftsgarten
- Community Land Trust und gemeinschaftlich gebundener Wohnraum
- Werkzeugbibliothek und Reparatur
- gemeinschaftliche Telekommunikationsnetze
- offene Hardware und verteilte Fertigung

Die Auswahl erweitert außerdem die geografische Reichweite nach Nordamerika und auf die südliche Hemisphäre.

## Aufgenommene CommonProjects

- Prinzessinnengarten Kollektiv Berlin
- Granby Four Streets Community Land Trust
- Edinburgh Tool Library
- guifi.net
- NYC Mesh
- Zenzeleni Community Networks
- Sarantaporo.gr Community Network
- Open Source Ecology

## Evidenz- und Datenschutzregeln

Jeder Eintrag verwendet offizielle Projektquellen und besitzt ein Prüfdatum sowie einen nächsten Prüftermin. Aktionen werden nur veröffentlicht, wenn ein passender öffentlicher HTTPS-Weg vorhanden ist.

Öffentliche Geografie wird bewusst konservativ modelliert:

- öffentlich bekannte Standorte werden angenähert,
- regionale Netze erhalten nur grobe Regionspunkte,
- Unsicherheitsradien sind ausdrücklich angegeben,
- private Haushalte, Router, Dächer, Funkstrecken und Anschlüsse bleiben verborgen und besitzen keine Geometrie.

Die Karte behauptet daher weder vollständige Netzabdeckung noch exakte private Infrastrukturstandorte.

## Technische Folge

Historische Vertikalbeweise waren teilweise auf exakt zwölf Katalogeinträge und drei Kartenmerkmale festgeschrieben. Diese Prüfungen wurden getrennt:

- Die ursprünglichen zwölf Identitäten und drei Referenzgeometrien bleiben als unveränderliche Mindest- und Regressionsmenge erhalten.
- Der aktuelle Produktionskatalog wird vollständig aus `catalog/catalog.json` abgeleitet und darf kontrolliert wachsen.
- Such-, Filter-, Karten- und Browserprüfungen leiten erwartete Mengen aus dem veröffentlichten Manifest und den behaupteten Aktionen ab.

## Abnahme

Die Browsermatrix prüft zwanzig indizierte Einträge, sechzehn digitale oder hybride Identitäten, zwölf öffentliche Kartenmerkmale und zehn räumlich sichtbare CommonProjects. Getestet werden Desktop, Mobilansicht, iPad Hochformat und iPad Querformat sowie Reduced Motion, Katalogausfall und Kartenanbieter-Ausfall.

## Grenzen

Dieses Paket erfüllt noch nicht das Masterplanziel von 30 bis 50 ausgewogenen Einträgen. Asien, Lateinamerika und Ozeanien fehlen weiterhin. Ebenso fehlt noch ein öffentlicher Kandidaten- und redaktioneller Prüfpfad für neue Vorschläge.
