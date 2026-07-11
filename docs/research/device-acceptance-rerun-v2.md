# Commonworld Geräteabnahme – erster physischer Fund und Wiederholung v2

Stand: 11. Juli 2026

## Urteil

Der erste physische Lauf war nützlich, aber **nicht bestanden**. Er wird als Fehlerfund bewahrt und darf keine Engine- oder Architekturentscheidung auslösen.

```text
first_physical_run_accepted         = false
engine_selected                     = false
production_architecture_authorized  = false
```

## Was der Lauf gezeigt hat

Der Lauf erfolgte auf einem Apple-WebKit-Touchgerät mit Hardware-WebGL 2. Alle acht manuellen Felder wurden als bestanden markiert. Der Beleg enthält jedoch keine der drei verpflichtenden automatischen Messungen. Außerdem war Reduced Motion laut Browserzustand nicht aktiv, der zehnsekündige Hintergrundaufenthalt war nicht maschinell gebunden und die Notiz widersprach der manuellen Bewertung der digitalen Sphäre.

Die entscheidende Beobachtung lautete: Die digitale Sphäre blieb optisch gleich groß, statt räumlich um den Globus zu liegen. Das bestätigt einen echten Fehler im ersten Harness. Die alte Darstellung wurde direkt in Bildschirmkoordinaten gezeichnet und war deshalb nur schwach an den Kartenzoom gekoppelt.

## Korrektur im Abnahmepaket v2

Version 2 misst den sichtbaren Erdradius über die Kartenprojektion. Die digitale Hülle erhält einen Radius von exakt dem 1,2-Fachen der Erde. In der geprüften mobilen Ansicht betrug der Erdradius rund 188,42 Pixel, die äußere Hülle rund 226,10 Pixel. Beim Lokalzoom wächst dieselbe räumliche Hülle mit dem Globus und wird anschließend ausgeblendet. Sie bleibt damit nicht mehr bildschirmfest.

Der neue Belegvertrag ist fail-closed:

- genau drei automatische Planet-/Lokalmessungen sind Pflicht;
- alle acht manuellen Prüfpunkte müssen bearbeitet sein;
- ein bestandener Hintergrundrundlauf benötigt mindestens 10.000 Millisekunden gemessene Verbergung;
- ein bestandenes Reduced-Motion-Feld benötigt eine aktive Systemeinstellung und eine tatsächlich animationsfreie Kamerabewegung;
- die automatische Messung muss die digitale Hülle als globusrelativ, in der Totalen sichtbar und lokal ausgeblendet belegen;
- bei einem fehlgeschlagenen Prüffeld ist eine Notiz Pflicht;
- unvollständige Läufe können nicht gespeichert werden.

## Was weiterhin offen bleibt

Der korrigierte Release ist installiert und technisch geprüft. Ein neuer physischer Apple-WebKit-Lauf ist jedoch noch erforderlich. Danach bleibt ein unabhängiger Chrome-Lauf auf Android nötig; Chrome auf iOS oder iPadOS verwendet ebenfalls Apples Browserengine und wäre kein zweiter Enginebeleg.

Auch nach einem vollständigen Gerätebeleg bleibt eine Repositoryauswertung Pflicht. Die Abnahmeseite selbst kann weder MapLibre auswählen noch eine Produktionsarchitektur freigeben.

## Veröffentlichungsgrenze

Im Repository liegen nur dieser normalisierte Bericht, ein maschinenlesbarer Ergebnisdatensatz, Validator und Mutationstests. Nicht veröffentlicht werden der Rohbeleg, Gerätekennung, private Tailnet-Adresse, Screenshots, ausführbarer Harness oder lokale Ergebnisdateien.

## Lokale Belegbindung

- korrigiertes v2-Forschungsarchiv: `068ecc3050d5900b34a1f80990ba9ce18131fd35924ced4652dd73b31a5a773c`;
- v2-Vorbereitungsbeleg: `79ebd4f8de00bd9d8f97aeafea6120c5aa631cd25a0cc4e4c53b754784bbd52b`;
- installierter v2-Dienstbeleg: `574bf5d04bfc7e9238eabf7e4f931229b5b4b48e547fff072713eaf8768474a3`;
- Auswertung des ersten physischen Belegs: `ec35a118b30e4618583a6149227217c0ad2d6bcc6cad428091521b8d6603ec5c`;
- unveränderter Rohbeleg: `08966f7fa788e6f4dd96735844f254d379320c5f0c864cb23ddecad18596b320`;
- v2-Dateimanifest: `66aa23a5d700ec7d35a40436483a1e5e711cf2a011df4bd020580629adc971a9`;
- installierter Release-Manifest-Hash: `2378646d2755aefbf5f56ac2a3e93407ac025960a4b02042e7731d985deaaa69`.
