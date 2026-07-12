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
