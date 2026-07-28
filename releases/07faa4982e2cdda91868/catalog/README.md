# Öffentlicher Commonworld-Katalog

`catalog.json` ist das öffentliche Verzeichnis der redaktionell freigegebenen CommonProject-v3-Datensätze. Jeder Eintrag liegt einzeln unter `projects/`.

## Grenze

- Nur `curation.state = listed` oder ein später ausdrücklich freigegebener öffentlicher Zustand darf erscheinen.
- Quellen müssen im Datensatz stehen und für diesen Startkatalog offizielle Projektquellen sein.
- Testfälle unter `tests/cases/` sind niemals Katalogeinträge.
- Digitale Commons erhalten keine erfundenen geografischen Koordinaten.
- Importe oder Generatoren veröffentlichen nichts automatisch.
- Dieser Katalog wählt keine Globe-Engine und autorisiert keine Produktionsarchitektur.

## Prüfung

```bash
make validate-public-catalog
```
## Maschinenlesbarer Zugang

`catalog/catalog.json` ist zugleich der stabile Einstieg in die statische, ausschließlich lesende Maschinenoberfläche. `machine_surface` benennt Manifest, Projektpfad und CommonProject-Schema sowie die explizite Grenze: keine API-Laufzeit, kein Schreibweg und keine eigenständige CLI. Die Einzeldateien liegen unter `catalog/projects/<CommonProject.id>.json`. Der vollständige Vertrag steht in `docs/ops/machine-readable-surface.md`.
