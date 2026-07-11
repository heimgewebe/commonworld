# Commonworld – geschichtete digitale Sphäre v1

Stand: 11. Juli 2026

## Urteil

Die digitale Sphäre ist jetzt als kanonischer Darstellungsvertrag festgelegt und in einem nichtöffentlichen v3-Prototyp umgesetzt. Sie ist keine Punktwolke mehr. Sechs übereinanderliegende Bahnschichten aus kurzen Commons-Namen und deterministisch aus stabilen Identitäten abgeleiteten Binärfragmenten umgeben den Globus.

Der Prototyp bestätigt die Grundinteraktion. Er autorisiert weder eine Produktionsengine noch die öffentliche Architektur.

```text
engine_selected                     = false
production_architecture_authorized  = false
```

## Ausgangspunkt und ehrliche Testwahrheit

Der zugrunde liegende Nutzerbeleg war unvollständig. Die drei automatischen Messläufe fehlten; die identitätsgleiche Auswahl zwischen Ansichten und VoiceOver oder TalkBack wurden nicht ausgeführt. Der belegte Hintergrundrundlauf und Reduced Motion bleiben gültige Teilbefunde. Die beschriebene Sphärenidee wurde als Produktentwurf übernommen, nicht als bestandene Geräteabnahme.

Der Rohbeleg war in der Operatorlaufzeit nicht als Datei gemountet und wurde deshalb nicht künstlich rekonstruiert oder mit einem erfundenen Hash versehen. Im Repository stehen nur die normalisierte Testwahrheit und die abgeleiteten Produktregeln.

## Schichten und Bahnen

Die sechs vorläufigen Darstellungsschichten sind:

1. Wissen und offene Daten;
2. freie Software und Infrastruktur;
3. offene Medien und Kultur;
4. freies Lernen und Bildung;
5. Kommunikation und Netze;
6. gemischte und weitere digitale Commons.

Diese Schichten sind keine neuen redaktionellen Katalogfelder. Ihre Zuordnung wird aus vorhandenen Themen, Commons-Familien und der belegten digitalen Präsenz abgeleitet. Der Katalog behält weiterhin genau eine `CommonProject.id` je Commons.

Die Bahnen wechseln zwischen lesbaren Namensfragmenten und kurzen Binärfolgen. Die Binärfolge wird deterministisch aus der stabilen Identität erzeugt. Sie ist weder tatsächlicher Projektcode noch Inhaltsmenge, Aktivität, Qualität oder Rang. Beziehungen zwischen Bahnen dürfen nur aus belegten Katalogrelationen entstehen.

## Globusverhalten

In der Totalen liegen sechs Bahnen außerhalb des sichtbaren Erdrands. Die innerste Hülle hat das 1,2-Fache des Erdradius, die äußerste das 1,42-Fache. Eine radiale Maske blendet die Zeichen zur Bildmitte aus und hält den Blick auf die Commons-Welt frei.

Die Sphäre ist bis Zoom 1,8 vollständig sichtbar, bei Zoom 2,2 ungefähr halb sichtbar und ab Zoom 2,6 verborgen. Beim weiteren Herauszoomen ist die vollständige Umhüllung sichtbar. Diese Schwellen sind Präsentationsparameter, keine Katalogdaten.

## Seitenansicht

Der transparente Rand der Sphäre ist als ringförmige Zielzone anklickbar. Er öffnet dieselbe Oberfläche in einer Seitenansicht mit sechs übereinanderliegenden Schichten. Die Erde bleibt als gedämpfter Bezug erhalten. Der Zustand besitzt einen Deep Link über `digital=layers`; Schließen und Browsernavigation führen zur vorherigen Globusansicht zurück.

Bei reduzierter Bewegung wechselt die Ansicht ohne Kamerafahrt. Ein sichtbarer Schalter bietet denselben Weg, falls die ringförmige Zielzone nicht erkannt oder nicht präzise getroffen wird. Der Prototyp beweist das gestapelte Seitenlayout, aber noch keine räumlich ausgearbeitete seitliche Kamerafahrt; diese bleibt ein eigener Gestaltungs- und Leistungstest.

## Was „dieselbe Auswahl“ bedeutet

Die frühere Bezeichnung „Auswahlparität“ wird in der Prüfoberfläche nicht mehr verwendet. Die konkrete Regel lautet:

> Ein Commons in einer Ansicht auswählen, in eine andere Ansicht wechseln und prüfen, ob dort derselbe Name markiert bleibt und dasselbe Fokuspanel geöffnet ist.

Der automatisierte Prototyp wählte `common-00002` in der digitalen Schichtansicht aus. In der linearen Ansicht blieb dieselbe ID ausgewählt und der Name `Proof identity 2` sichtbar. Damit sind Identität und Markierung gleich. Ein echtes Fokuspanel besitzt dieser Forschungsprototyp jedoch noch nicht; die vollständige Auswahlregel ist deshalb nicht bestanden. Der Nutzer selbst hat den Ablauf ebenfalls noch nicht geprüft.

## Zugänglichkeit

Die dekorativen Namens- und Binärströme sind für Screenreader verborgen. Der Sphärenrand besitzt den zugänglichen Namen „Digitale Commons-Schichten öffnen“. Die Schichten besitzen normale Schaltflächen und dieselben Identitäten stehen in der linearen Ansicht bereit.

Der Accessibility-Tree und der Tastaturpfad wurden automatisiert geprüft. VoiceOver und TalkBack wurden nicht physisch ausprobiert. Dieser Punkt bleibt ausdrücklich offen und darf in einem späteren Beleg nur als bestanden gelten, wenn die Assistenztechnik tatsächlich eingeschaltet und benutzt wurde.

## Leistung

Die Messungen verwenden weiterhin Software-WebGL und sind nur relative Vergleichswerte:

| Profil | Planet | Lokal |
| --- | ---: | ---: |
| 800 × 600, Faktor 1 | 47,48 FPS | 60,02 FPS |
| 1180 × 701, Faktor 2 | 22,36 FPS | 27,25 FPS |

Die deutlich niedrigere große Darstellung ist ein offener Optimierungsbefund. Vor einer Produktionsfreigabe müssen sichtbare Zeichenmenge, Textpfade, Aktualisierungsfrequenz und mobile Hardwareleistung begrenzt und erneut gemessen werden.

## Veröffentlichungsgrenze

Der öffentliche Repository-Slice enthält Vertrag, normalisierten Forschungsbeleg, Validator und Mutationstests. Ausführbarer Harness, private Adresse, Screenshots, vollständige Browserdaten und lokale Ergebnisdateien verbleiben im nichtöffentlichen Forschungsarchiv.

## Lokale Belegbindung

- Forschungsarchiv: `8204e0007e52276cd30b5f323f56ca74b770da46665d1331fd3701d012f1f3e6`;
- installierter Browserbeweis: `c8b8e7fd6bba758fb9c4911bd9c67c7eb3485b5b5c46ae291e95e661eb18bdcd`;
- Übersichtsbild: `9f858abc64fb6a5052ba3f3ac6ab20c8de8f41e301d871584ed899d48f8050cd`;
- Seitenansicht: `6037f8c8287dd9808a8d006139e4783e8682b9eeb2d6a24947d58ba6edecc6ad`;
- Dateimanifest: `eb22906f6574b82199c69fa559b0099f07e63457ac40ffdb037adfb7887e0cab`;
- normalisierte Eingabeauswertung: `4fac1c316de32a2090a4f5b7ea7a16f36d4859d5ce3d4e17de0865d793189daa`;
- installierter Release-Manifest-Hash: `a9f850c98dcf7b845cf7c7e17a1d7273a68393783aa0b70d280b214588b1fe6c`.
