#!/usr/bin/env python3
"""Materialize the one-time Commons admission migration on its isolated branch."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace_once(path: Path, old: str, new: str, *, already: str) -> None:
    source = path.read_text(encoding="utf-8")
    if already in source:
        return
    if old not in source:
        raise ValueError(f"{path}: materialization marker missing")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    manifest_path = ROOT / "catalog/catalog.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = sorted(set(manifest["project_files"]) | {"projects/meshtastic.json"})
    manifest["project_files"] = files
    manifest["entry_count"] = len(files)
    manifest["published_at"] = "2026-07-31"
    write_json(manifest_path, manifest)

    locale_path = ROOT / "catalog/locales/en.json"
    locale = json.loads(locale_path.read_text(encoding="utf-8"))
    locale["projects"]["meshtastic"] = {
        "summary": "A community-driven open-source ecosystem for decentralized off-grid communication over affordable low-power LoRa devices, with shared firmware, protocols, documentation and contribution paths.",
        "geographic_labels": {},
        "digital_label": "Open-source off-grid mesh software, protocols, documentation and community collaboration",
    }
    locale["projects"] = dict(sorted(locale["projects"].items()))
    write_json(locale_path, locale)

    ttn_path = ROOT / "catalog/projects/the-things-network.json"
    ttn = json.loads(ttn_path.read_text(encoding="utf-8"))
    ttn["curation"]["reviewed_at"] = "2026-07-31"
    ttn["curation"]["next_review_at"] = "2026-10-31"
    ttn["curation"]["notes"] = (
        "Aufgenommen als digitale Commons-Infrastruktur. Kommerzielle Angebote von The Things Industries "
        "werden nicht mit dem Community-Netz gleichgesetzt; katalogisiert ist der offene Community-Pfad. "
        "Der strukturierte Commons-Basisnachweis wurde am 31. Juli 2026 rückwirkend ergänzt."
    )
    write_json(ttn_path, ttn)

    readme_path = ROOT / "README.md"
    readme_section = '''## Commons-Begriff und Aufnahme

Commonworld bleibt offen für physische, digitale, lokale und globale Formen von Commons, verlangt aber eine überprüfbare Begründung. Ein Common ist eine benennbare Ressource, Infrastruktur, Praxis oder Wissensbasis, die von mehreren Menschen gemeinsam genutzt, erhalten oder weiterentwickelt wird und deren Umgang durch gemeinschaftliche Regeln, Rechte oder belastbare Verantwortungspraktiken geprägt ist.

Open Source, Kostenfreiheit, Gemeinnützigkeit, Dezentralität, eine öffentliche API, viele Nutzer oder das Wort „Community“ genügen für sich allein nicht. Maßgeblich sind fünf quellengebundene Dimensionen: gemeinsame Ressource, Gemeinschaft, Commoning-Praxis, Regeln und Verantwortung sowie gemeinsamer Nutzen.

Maschinenlesbare Grundlage:

- [`contracts/commonworld/commons-definition.contract.json`](contracts/commonworld/commons-definition.contract.json)
- [`contracts/commonworld/commons-basis.schema.json`](contracts/commonworld/commons-basis.schema.json)
- [`catalog/commons-bases/index.json`](catalog/commons-bases/index.json)
- [`catalog/commons-bases/retroreview-policy.json`](catalog/commons-bases/retroreview-policy.json)

Seit dem 31. Juli 2026 benötigen neue oder wesentlich neu geprüfte Einträge einen strukturierten Commons-Basisnachweis. Ältere Einträge werden dynamisch bis zu ihrer bestehenden Wiedervorlage rückgeprüft; bereits fällige Altbestände erhalten einmalig eine Migrationsfrist bis zum 31. August 2026. Das Prinzip lautet: offen in den Formen, streng bei der Begründung.

'''
    replace_once(
        readme_path,
        "## Internationalisierung\n",
        readme_section + "## Internationalisierung\n",
        already="## Commons-Begriff und Aufnahme\n",
    )

    render_path = ROOT / "scripts/render_public_shell.py"
    old_section = '''      <section><h2>Vorschläge und Redaktion</h2><p>Über <a href="./propose.html">Commons vorschlagen</a> können öffentliche Kandidaten vorbereitet werden. Commonworld speichert das Formular nicht. Der bevorzugte Eingang ist ein öffentliches GitHub-Issue; alternativ entsteht eine lokale JSON-Datei. Vorschläge werden nie automatisch veröffentlicht. Die Redaktion prüft Identität, primärnahe Quellen, Commons-Eigenschaft, Handlungswege, Datenschutz, Ortsgenauigkeit, Dubletten und Aktualität nach dem <a href="./contracts/commonworld/editorial-review.contract.json">Redaktionsvertrag</a>.</p></section>'''
    new_section = '''      <section><h2>Was als Common gilt</h2><p>Commonworld versteht ein Common als eine benennbare Ressource, Infrastruktur, Praxis oder Wissensbasis, die von mehreren Menschen gemeinsam genutzt, erhalten oder weiterentwickelt wird. Für die Aufnahme müssen gemeinsame Ressource, Gemeinschaft, Commoning-Praxis, Regeln und Verantwortung sowie gemeinsamer Nutzen durch primärnahe Quellen belegt sein. Open Source, Kostenfreiheit, Gemeinnützigkeit, Dezentralität oder viele Nutzer reichen für sich allein nicht aus. Die Formen bleiben offen; die Begründung ist verbindlich und im <a href="./contracts/commonworld/commons-definition.contract.json">Commons-Definitionsvertrag</a> maschinenlesbar.</p></section>
      <section><h2>Vorschläge und Redaktion</h2><p>Über <a href="./propose.html">Commons vorschlagen</a> können öffentliche Kandidaten vorbereitet werden. Commonworld speichert das Formular nicht. Der bevorzugte Eingang ist ein öffentliches GitHub-Issue; alternativ entsteht eine lokale JSON-Datei. Vorschläge werden nie automatisch veröffentlicht. Die Redaktion prüft Identität, primärnahe Quellen, Commons-Eigenschaft, Handlungswege, Datenschutz, Ortsgenauigkeit, Dubletten und Aktualität nach dem <a href="./contracts/commonworld/editorial-review.contract.json">Redaktionsvertrag</a> und dokumentiert die Aufnahme im <a href="./contracts/commonworld/commons-basis.schema.json">Commons-Basisnachweis</a>. Seit dem 31. Juli 2026 benötigen neue oder wesentlich neu geprüfte Einträge diesen Nachweis; ältere Einträge werden spätestens zu ihrer bestehenden Wiedervorlage rückwirkend geprüft. Bereits fällige Altbestände erhalten einmalig bis zum 31. August 2026 Zeit.</p></section>'''
    replace_once(
        render_path,
        old_section,
        new_section,
        already="<h2>Was als Common gilt</h2>",
    )

    i18n_path = ROOT / "scripts/commonworld_i18n.py"
    old_entries = '''    '<h2>Vorschläge und Redaktion</h2>': '<h2>Suggestions and editorial review</h2>',
    'Über <a href="./propose.html">Commons vorschlagen</a> können öffentliche Kandidaten vorbereitet werden. Commonworld speichert das Formular nicht. Der bevorzugte Eingang ist ein öffentliches GitHub-Issue; alternativ entsteht eine lokale JSON-Datei. Vorschläge werden nie automatisch veröffentlicht. Die Redaktion prüft Identität, primärnahe Quellen, Commons-Eigenschaft, Handlungswege, Datenschutz, Ortsgenauigkeit, Dubletten und Aktualität nach dem': 'Public candidates can be prepared through <a href="./propose.html">Suggest a Commons</a>. Commonworld does not store the form. The preferred intake path is a public GitHub issue; alternatively, a local JSON file is produced. Suggestions are never published automatically. Editorial review checks identity, primary-near sources, Commons characteristics, ways to engage, privacy, location precision, duplicates and freshness under the',
    '>Redaktionsvertrag</a>.': '>editorial review contract</a>.','''
    new_entries = '''    '<h2>Was als Common gilt</h2>': '<h2>What counts as a Common</h2>',
    'Commonworld versteht ein Common als eine benennbare Ressource, Infrastruktur, Praxis oder Wissensbasis, die von mehreren Menschen gemeinsam genutzt, erhalten oder weiterentwickelt wird. Für die Aufnahme müssen gemeinsame Ressource, Gemeinschaft, Commoning-Praxis, Regeln und Verantwortung sowie gemeinsamer Nutzen durch primärnahe Quellen belegt sein. Open Source, Kostenfreiheit, Gemeinnützigkeit, Dezentralität oder viele Nutzer reichen für sich allein nicht aus. Die Formen bleiben offen; die Begründung ist verbindlich und im <a href="./contracts/commonworld/commons-definition.contract.json">Commons-Definitionsvertrag</a> maschinenlesbar.': 'Commonworld understands a Common as an identifiable resource, infrastructure, practice or body of knowledge that multiple people use, maintain or develop together. Admission requires primary-near evidence for a shared resource, community, commoning practice, rules and responsibility, and common benefit. Open source, free access, nonprofit status, decentralization or many users are not sufficient on their own. Forms remain open; justification is binding and machine-readable in the <a href="./contracts/commonworld/commons-definition.contract.json">Commons definition contract</a>.',
    '<h2>Vorschläge und Redaktion</h2>': '<h2>Suggestions and editorial review</h2>',
    'Über <a href="./propose.html">Commons vorschlagen</a> können öffentliche Kandidaten vorbereitet werden. Commonworld speichert das Formular nicht. Der bevorzugte Eingang ist ein öffentliches GitHub-Issue; alternativ entsteht eine lokale JSON-Datei. Vorschläge werden nie automatisch veröffentlicht. Die Redaktion prüft Identität, primärnahe Quellen, Commons-Eigenschaft, Handlungswege, Datenschutz, Ortsgenauigkeit, Dubletten und Aktualität nach dem <a href="./contracts/commonworld/editorial-review.contract.json">Redaktionsvertrag</a> und dokumentiert die Aufnahme im <a href="./contracts/commonworld/commons-basis.schema.json">Commons-Basisnachweis</a>. Seit dem 31. Juli 2026 benötigen neue oder wesentlich neu geprüfte Einträge diesen Nachweis; ältere Einträge werden spätestens zu ihrer bestehenden Wiedervorlage rückwirkend geprüft. Bereits fällige Altbestände erhalten einmalig bis zum 31. August 2026 Zeit.': 'Public candidates can be prepared through <a href="./propose.html">Suggest a Commons</a>. Commonworld does not store the form. The preferred intake path is a public GitHub issue; alternatively, a local JSON file is produced. Suggestions are never published automatically. Editorial review checks identity, primary-near sources, Commons characteristics, ways to engage, privacy, location precision, duplicates and freshness under the <a href="./contracts/commonworld/editorial-review.contract.json">editorial review contract</a> and documents admission in a <a href="./contracts/commonworld/commons-basis.schema.json">Commons basis record</a>. Since 31 July 2026, new or materially re-reviewed entries require this record; older entries are reviewed retroactively no later than their existing review date. Legacy entries already due receive a one-time grace period until 31 August 2026.','''
    replace_once(
        i18n_path,
        old_entries,
        new_entries,
        already="'<h2>Was als Common gilt</h2>'",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
