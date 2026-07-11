# Commonworld Geräte-Abnahmepaket v1

Stand: 11. Juli 2026

## Urteil

Die virtualisierte lineare Parallelansicht und das nichtöffentliche Geräte-Abnahmepaket sind vorbereitet und lokal installiert. Die physische Geräte- und Assistenztechnikabnahme ist noch nicht erfolgt. Deshalb bleiben Enginewahl und Produktionsarchitektur gesperrt.

```text
engine_selected                    = false
production_architecture_authorized = false
```

## Was „virtualisiert“ bedeutet

Eine gewöhnliche Liste baut für jeden Datensatz ein eigenes Seitenelement. Bei 50.000 Identitäten wären das 50.000 Schaltflächen im Browser. Die virtualisierte Liste hält dagegen nur die gerade sichtbaren Zeilen und einen kleinen Puffer im DOM, also im aktiven Seitenbaum des Browsers.

Der Belastungsbeweis verwendete 50.000 synthetische Identitäten. Beim Sprung zum letzten Eintrag wurden höchstens 17 Zeilen gleichzeitig gerendert; die aus Fensterhöhe und Puffer berechnete Obergrenze betrug 25. Suche, Home/End-Navigation und der letzte Eintrag `49.999` wurden erreicht. Der 5.000er Modus bewies zusätzlich, dass Globus und lineare Ansicht dieselbe CommonProject-Auswahl behalten.

Dieser Befund beweist die technische Listenbegrenzung. Er beweist noch nicht die Qualität einer Suche über reale Katalogdaten.

## Nichtöffentliches Abnahmepaket

Das Paket enthält ausschließlich synthetische Daten und läuft als lokaler Benutzer-Systemdienst im privaten Tailnet. Es besitzt keinen öffentlichen Eingang, lauscht nicht auf Loopback und veröffentlicht seine Geräteadresse nicht im Repository. Der direkte Tailnet-Zugriff wurde geprüft; ein bequemer MagicDNS-Name war auf dem ausführenden Rechner nicht verifizierbar.

Der Dienst stellt bereit:

- den geografischen MapLibre-Globus;
- die abstrakte digitale Sphäre im selben WebGL-Kontext;
- Abdeckungsmuster und Unsicherheitsdarstellung;
- die 5.000er Paritätsliste und die 50.000er Virtualisierungslast;
- drei automatische Rotationsmessungen auf Planet- und Lokalstufe;
- acht geführte manuelle Geräteprüfungen;
- einen fail-closed JSON-Belegempfänger.

Gespeicherte Belege erhalten Dateirechte `0600`. Der Empfänger akzeptiert nur Same-Origin-JSON, höchstens 1 MiB pro Anfrage und insgesamt höchstens 100 Belegdateien. Er verwirft außerdem unbekannte Prüfpunkte, eine verletzte DOM-Obergrenze und jede Behauptung, die Engine oder Produktionsarchitektur sei bereits freigegeben.

## Vorbereitungsmessung

Die gebündelte Release-Version wurde in einem mobilen Browserfenster von 390 × 844 CSS-Pixeln bei Faktor 2 geprüft. Pro Maßstab liefen drei Messungen.

| Maßstab | Median | höchstes p95-Frameintervall |
| --- | ---: | ---: |
| Planet | 45,60 FPS | 23,30 ms |
| Lokal | 60,00 FPS | 17,20 ms |

Diese Werte stammen weiterhin aus Chrome über Software-WebGL. Touch und Mobilviewport wurden emuliert. Die Messung ist kein Beleg für Safari, Chrome oder einen Grafikchip auf einem realen Mobilgerät.

## Sicherheitsgrenzen

Der Zugriff wird nur durch Mitgliedschaft im privaten Tailnet begrenzt; das Paket besitzt keinen zusätzlichen App-Login. Zum Prüfzeitpunkt war der Dienst aktiv und ohne Neustart. Dieser datierte Beleg ist keine dauerhafte Gesundheitsgarantie.

Das installierte Paket verwendet:

- eine Tailnet-only-Bindung;
- `NoNewPrivileges`;
- ein schreibgeschütztes Home- und Systemabbild mit einem einzelnen privaten Ergebnis-Schreibpfad;
- einen privaten temporären Ordner;
- beschränkte Netzwerk-Adressfamilien;
- eine Content Security Policy ohne externe Skripte, Frames oder Verbindungen;
- deaktivierte Geolokalisierung, Kamera, Mikrofon, Payment und USB;
- keine Referrer-Weitergabe.

Der Tailnet-Zugriff erfolgt derzeit über HTTP und ist daher im Browser kein „Secure Context“. Weil `crypto.randomUUID()` dort nicht verfügbar ist, verwendet das Paket einen geprüften UUID-v4-Fallback auf Basis von `crypto.getRandomValues()`.

## Noch offene physische Abnahme

Auf realen Geräten müssen weiterhin geprüft werden:

1. Drehen und semantischer Zoom;
2. Erkennbarkeit der drei Abdeckungszustände;
3. Unsicherheitshalo und gestrichelter Rand;
4. Stabilität der digitalen Sphäre;
5. Auswahlparität zwischen Globus und Liste;
6. echter Hintergrundtab-Rundlauf;
7. VoiceOver oder TalkBack;
8. Reduced Motion.

Zusätzlich fehlen physische Safari- und Chrome-Leistungsmessungen mit Hardware-GPU. Die Abnahmeseite speichert Resultate, entscheidet aber nicht selbst über eine Freigabe.

## Repository- und Veröffentlichungsgrenze

Im Repository liegen nur dieser Bericht, ein normalisierter Ergebnisdatensatz, Validator und Tests. Nicht eingecheckt sind:

- ausführbarer Harness und Node-Abhängigkeiten;
- Release-Paket;
- Screenshots;
- Gerätebelege;
- Tailnet-IP oder Tailnet-DNS-Name;
- Ergebnisdateien;
- öffentliche Produktänderungen.

## Lokale Belegbindung

- vollständiges Forschungsarchiv: `be7b673e30bfe4e124f6d21c068962cd1450760568e235b9e28763e0ce811b22`;
- Vorbereitungsergebnis: `3241ac53bf1e9c9044c10a4ca508bbd9dc11eca52e402009b00911ee109108f0`;
- installierter Dienstbeleg: `60372bcc86a10cbf0758729e07ea490cdbf99b480f9abe4af6173534528ccb0b`;
- Dateimanifest: `8986c58d4660e34bf807796530da27bc3d7cc036ed13a75aeeccc930bed4d396`;
- Virtualisierungsbild: `e9edd3c778b2b74d8fdf4ee8e66952902acf7fef2d589e80acac060b4f7f7123`;
- Abnahmepanel-Bild: `3d6c7d80c156fa6e98c20f8cdf82fed2ebcceba33a550451bdf32123fb6aa47c`.
