# Commonworld-Katalogauslieferung: gemessene Optionen

## Entscheidung

Commonworld verwendet vorerst einen **buildgebundenen vollständigen Bootstrap**: Die interaktive Anwendung erhält genau eine generierte JavaScript-Projektion aller kanonischen `CommonProject`-Dateien. Der Browser lädt beim Start nicht zusätzlich `catalog/catalog.json` und alle einzelnen Projektdateien. Diese öffentlichen JSON-Dateien bleiben dennoch für Menschen, Prüfwerkzeuge und Suchmaschinen erreichbar.

Ein *Bootstrap* ist der Datensatz, mit dem die Anwendung unmittelbar startet. *Buildgebunden* bedeutet: Er wird vor der Veröffentlichung aus den kanonischen Projektdateien erzeugt und in CI auf Gleichheit geprüft.

Die zweite statische Kartenliste in `<noscript>` bleibt bestehen. Sie ist keine zweite veränderbare Wahrheit, sondern eine ebenfalls generierte Projektion, die ohne JavaScript lesbar ist.

## Gemessener Ausgangspunkt

Bei 41 Einträgen enthielt der Bootstrap 118.546 rohe beziehungsweise 20.526 gzip-komprimierte Bytes. Anschließend lud die Anwendung dieselben 41 Projektdateien erneut: weitere 155.840 rohe beziehungsweise 51.789 gzip-Bytes. Zwei vierfach CPU-gedrosselte Browserprofile bestätigten 41 zusätzliche Projektanfragen.

Die gewählte Änderung entfernt diese 41 Abrufe und die zugehörigen JSON-Parse- und Gleichheitsvergleiche. Der initial ausgelieferte Kataloganteil sinkt komprimiert von 72.315 auf 20.526 Bytes.

## Vergleich der vier statischen Entwürfe

| Entwurf | Barrierefreiheit und No-JS | SEO | Datenschutz | Caching | Komplexität und Pages | Bewertung |
|---|---|---|---|---|---|---|
| Generierter vollständiger Bootstrap | Interaktive Ansicht startet sofort; separate generierte `<noscript>`-Karten bleiben vollständig lesbar. | Statische Karten und öffentliche JSON-Verweise bleiben im HTML. | Nur statische Dateien, keine Telemetrie oder API. | Ein versioniertes Modul kann als Ganzes gecacht werden. | Sehr gering; vollständig mit GitHub Pages vereinbar. | **Jetzt gewählt.** |
| HTML-Hydration | Könnte sichtbare Karten wiederverwenden, müsste aber vollständige strukturierte Daten im DOM tragen oder HTML zur Datenquelle machen. Das erhöht Kopplung und Risiko für Fokus- und No-JS-Verhalten. | Gut, solange alle Karten statisch bleiben. | Statisch möglich. | HTML wird häufiger invalidiert; Daten und Darstellung sind eng gekoppelt. | Mittlere bis hohe Komplexität; Gefahr einer zweiten Wahrheit. | Derzeit nicht gerechtfertigt. |
| Segmentiertes statisches JSON | Ein Grundsegment könnte Karte und Suche starten; Detailsegmente würden später geladen. No-JS braucht weiterhin HTML. | Öffentliche Detaildateien bleiben indexierbar, die interaktive Vollständigkeit wird asynchron. | Statisch und datensparsam möglich. | Gute Teilcaches. | Mittlere Komplexität: Segmentvertrag, Fehlerzustände und Deep-Links. | Nächste Option bei Überschreitung des Bootstrap-Budgets. |
| Bedarfsgeladene schreibgeschützte statische Lieferung | Lädt Details erst bei Auswahl. Eine vollständige Suche und globale Darstellung brauchen jedoch einen kompakten Index; No-JS bleibt separat. | Erfordert sorgfältige statische Verweise. | Statisch; keine Laufzeit-API nötig. | Beste Detailcaches. | Höchste Client-Komplexität und mehr Fehlerpfade, aber weiterhin Pages-fähig. | Erst bei belegtem Bedarf. |

## Schwellenwert statt Katalogzahl

Ein Umbau wird nicht durch eine bestimmte Zahl von Commons ausgelöst. Entscheidend sind übertragene und verarbeitete Arbeit: Bootstrap-Größe, Doppelabrufe, DOM-Knoten sowie repräsentative Start-, Skript- und Task-Zeit unter vierfach gedrosselter CPU. Die verbindlichen Grenzwerte stehen in `contracts/commonworld/catalog-delivery-budget.contract.json`.

Eine deterministische Größenüberschreitung löst sofort eine Architekturprüfung aus. Schwankende Browserzeiten müssen in zwei aufeinanderfolgenden repräsentativen Läufen überschritten werden.

## Next Actions: gemessene Umschaltschwellen

- **Unter 28 KiB gzip:** Der vollständige buildgebundene Bootstrap bleibt der Normalfall.
- **Ab 28 KiB gzip:** CI gibt eine Warnung aus. Sie blockiert nicht, verlangt aber eine erneute Messung der vier statischen Entwürfe.
- **Über 32 KiB gzip:** Der deterministische Vertrag schlägt fehl; eine Veröffentlichung darf den Grenzwert nicht stillschweigend überschreiten.
- **Bei steigender Parse-/Compile-Zeit:** Segmentiertes statisches JSON wird gegen den Voll-Bootstrap gemessen.
- **Bei nicht startrelevanten Feldern:** Ein schlankes Startmodell wird geprüft, während vollständige öffentliche Projektdateien erhalten bleiben.
- **Keine Katalogzahl als Auslöser:** Eine Migration erfolgt ausschließlich anhand gemessener Payload-, Request-, DOM- und Laufzeitwerte.

Die Warnschwelle steht als `warn_bootstrap_gzip_bytes`, die harte Grenze als `max_bootstrap_gzip_bytes` im Contract. `new Function` bleibt für die Compile-Messung bewusst erhalten: Der Quelltext ist kontrollierter Build-Output, und die unveränderte Messmethode hält neue Werte mit T019 vergleichbar. Die Normalisierung wird separat streng getestet und verlangt exakt eine Exportzuweisung.

## Grenzen der Aussage

Die Messung beweist die entfernten Abrufe und Bytes. Einzelne Zeitwerte hängen zusätzlich von Browser, Rechner und Scheduling ab und beweisen allein keine Beschleunigung. Die vollständigen kanonischen Projektdateien bleiben unverändert die einzige Katalogwahrheit.
