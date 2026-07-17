#!/usr/bin/env python3
"""Render the static, privacy-preserving Commons proposal page."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def catalog_index() -> dict[str, list[str]]:
    manifest = json.loads((ROOT / "catalog/catalog.json").read_text(encoding="utf-8"))
    titles: list[str] = []
    hosts: list[str] = []
    for relative in manifest["project_files"]:
        record = json.loads((ROOT / "catalog" / relative).read_text(encoding="utf-8"))
        titles.append(record["title"])
        homepage = next(link["url"] for link in record["links"] if link["type"] == "homepage")
        hosts.append(urlparse(homepage).hostname or "")
    return {"titles": sorted(titles), "hosts": sorted(set(hosts))}


def render() -> str:
    index = json.dumps(catalog_index(), ensure_ascii=False, separators=(",", ":")).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return f'''<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="dark" />
    <meta name="referrer" content="strict-origin-when-cross-origin" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none';" />
    <meta name="description" content="Ein Commons zur redaktionellen Prüfung für Commonworld vorschlagen." />
    <title>Commonworld — Commons vorschlagen</title>
    <link rel="icon" href="./assets/commonworld-mark.svg" type="image/svg+xml" />
    <link rel="stylesheet" href="./index.css" />
    <link rel="stylesheet" href="./assets/proposal.css" />
    <script type="module" src="./assets/commonworld-proposal.js"></script>
  </head>
  <body class="proposal-page">
    <a class="skip-link" href="#commons-proposal-form">Zum Vorschlagsformular springen</a>
    <script id="proposal-catalog-index" type="application/json">{index}</script>
    <main>
      <p class="kicker">Commonworld-Redaktion</p>
      <h1>Ein Commons vorschlagen</h1>
      <p><a class="secondary-back-link" href="./">← Zurück zum Globus</a></p>
      <section class="proposal-intro" aria-labelledby="proposal-process-title">
        <h2 id="proposal-process-title">Was danach passiert</h2>
        <p>Der Vorschlag wird <strong>nicht automatisch veröffentlicht</strong>. Commonworld prüft Identität, Quellen, Commons-Eigenschaft, Handlungswege, Ortsgenauigkeit, Datenschutz und Aktualität. Erst ein separat geprüfter Repository-Commit kann einen Katalogeintrag veröffentlichen.</p>
        <p><strong>Öffentlichkeit:</strong> Der bevorzugte Eingang ist ein öffentliches GitHub-Issue. Trage deshalb keine E-Mail-Adresse, Telefonnummer, private Adresse, Koordinate, Wohnung, Dach-, Router- oder Haushaltsangabe ein. Dein GitHub-Konto dient als Kontaktmöglichkeit; Commonworld erhebt kein zusätzliches Kontaktfeld.</p>
        <p>Ohne GitHub oder bei Netzfehlern kannst du eine validierte JSON-Datei lokal herunterladen. Commonworld speichert Formulareingaben nicht.</p>
      </section>

      <form id="commons-proposal-form" class="proposal-form" novalidate>
        <div class="honeypot" aria-hidden="true"><label>Website bestätigen <input name="website_confirm" type="text" tabindex="-1" autocomplete="off" /></label></div>
        <fieldset>
          <legend>Projekt</legend>
          <label><span>Name des Commons</span><input name="name" type="text" minlength="2" maxlength="140" required autocomplete="organization" /></label>
          <label><span>Kurze Beschreibung</span><textarea name="description" minlength="40" maxlength="800" required rows="5" aria-describedby="description-help"></textarea><small id="description-help">Beschreibe gemeinschaftliche Verwaltung, geteilte Ressource und öffentlichen Nutzen – ohne unbelegte Wirkungsaussagen.</small></label>
          <label><span>Offizielle Website</span><input name="official_website" type="url" inputmode="url" maxlength="300" required placeholder="https://…" /></label>
          <div class="proposal-grid">
            <label><span>Commons-Art</span><select name="commons_type" required><option value="">Bitte wählen</option><option value="knowledge">Wissen und Daten</option><option value="software">Software und Infrastruktur</option><option value="culture">Kultur und Medien</option><option value="food-seeds">Saatgut und Ernährung</option><option value="water">Wasser und Bewässerung</option><option value="energy">Energie</option><option value="housing-land">Boden und Wohnen</option><option value="health-care">Pflege und Gesundheit</option><option value="tools-repair">Werkzeuge, Reparatur und Fertigung</option><option value="community-network">Gemeinschaftsnetz</option><option value="other">Andere</option></select></label>
            <fieldset class="presence-fieldset"><legend>Präsenz</legend><div class="presence-options"><label class="check-row"><input type="checkbox" name="presence_geographic" value="true" /><span>Vor Ort</span></label><label class="check-row"><input type="checkbox" name="presence_digital" value="true" /><span>Digital</span></label></div><small class="presence-help">Mindestens eine wählen.</small></fieldset>
          </div>
          <label id="proposal-region-field"><span>Grobe Region oder Ort <small>(nur bei „Vor Ort“)</small></span><input name="region" type="text" minlength="2" maxlength="120" placeholder="z. B. Uruguay, Taiwan oder Aotearoa Neuseeland" aria-describedby="region-help" /><small id="region-help">Nur Land, Großregion oder öffentlich unproblematische Stadt. Keine Adresse oder Koordinate. Für rein digitale Commons bleibt das Feld leer.</small></label>
          <label class="check-row" id="proposal-sensitive-location-field"><input name="sensitive_location_risk" type="checkbox" /><span>Der Vorschlag betrifft möglicherweise private oder sensible Orte. Die Redaktion soll die Ortsangabe besonders streng prüfen.</span></label>
        </fieldset>

        <fieldset>
          <legend>Belegte Handlungswege</legend>
          <p>Mindestens ein realer Weg, über den Menschen das Commons nutzen, kennenlernen, unterstützen oder daran mitwirken können.</p>
          <div class="proposal-action-row"><label><span>Aktion 1</span><select name="action_type_1" required><option value="learn">Lernen</option><option value="use">Nutzen</option><option value="visit">Besuchen</option><option value="borrow">Ausleihen</option><option value="contribute">Mitmachen</option><option value="volunteer">Ehrenamt</option><option value="donate">Spenden</option><option value="contact">Kontakt</option><option value="replicate">Übertragen</option></select></label><label><span>HTTPS-Link</span><input name="action_url_1" type="url" maxlength="300" required placeholder="https://…" /></label></div>
          <div class="proposal-action-row"><label><span>Aktion 2 (optional)</span><select name="action_type_2"><option value="">Keine</option><option value="learn">Lernen</option><option value="use">Nutzen</option><option value="visit">Besuchen</option><option value="borrow">Ausleihen</option><option value="contribute">Mitmachen</option><option value="volunteer">Ehrenamt</option><option value="donate">Spenden</option><option value="contact">Kontakt</option><option value="replicate">Übertragen</option></select></label><label><span>HTTPS-Link</span><input name="action_url_2" type="url" maxlength="300" placeholder="https://…" /></label></div>
          <div class="proposal-action-row"><label><span>Aktion 3 (optional)</span><select name="action_type_3"><option value="">Keine</option><option value="learn">Lernen</option><option value="use">Nutzen</option><option value="visit">Besuchen</option><option value="borrow">Ausleihen</option><option value="contribute">Mitmachen</option><option value="volunteer">Ehrenamt</option><option value="donate">Spenden</option><option value="contact">Kontakt</option><option value="replicate">Übertragen</option></select></label><label><span>HTTPS-Link</span><input name="action_url_3" type="url" maxlength="300" placeholder="https://…" /></label></div>
        </fieldset>

        <fieldset>
          <legend>Quellen und Hinweise</legend>
          <label><span>Primärnahe Quellen</span><textarea name="sources" required rows="4" placeholder="Eine HTTPS-Adresse pro Zeile" aria-describedby="sources-help"></textarea><small id="sources-help">Mindestens eine offizielle oder primärnahe Quelle. Höchstens fünf.</small></label>
          <label><span>Hinweis für die Redaktion (optional)</span><textarea name="editorial_note" maxlength="500" rows="4" placeholder="Zum Beispiel: Welche Behauptung belegt welche Quelle?"></textarea></label>
        </fieldset>

        <fieldset>
          <legend>Einwilligung und Öffentlichkeit</legend>
          <label class="check-row"><input name="public_issue_acknowledged" type="checkbox" required /><span>Mir ist bewusst, dass der bevorzugte GitHub-Eingang öffentlich ist.</span></label>
          <label class="check-row"><input name="processing_agreed" type="checkbox" required /><span>Ich willige in die redaktionelle Verarbeitung der übermittelten Angaben ein.</span></label>
          <label class="check-row"><input name="no_sensitive_data_confirmed" type="checkbox" required /><span>Ich habe keine private Adresse, Koordinate, E-Mail-Adresse, Telefonnummer oder private Netz- und Haushaltsangabe eingetragen.</span></label>
        </fieldset>

        <div id="proposal-errors" class="proposal-errors" role="alert" tabindex="-1" hidden></div>
        <div class="proposal-controls"><button class="proposal-primary" type="submit">Öffentliches GitHub-Issue vorbereiten</button><button id="proposal-download" class="quiet-button" type="button">Validiertes JSON herunterladen</button></div>
        <p id="proposal-status" class="proposal-status" role="status" aria-live="polite"></p>
        <div id="proposal-fallback" class="proposal-fallback" hidden><p>Der Vorschlag bleibt ein Kandidat. Er erscheint dadurch nicht im Katalog.</p><p><a id="proposal-direct-link" href="https://github.com/heimgewebe/commonworld/issues/new?template=commons-proposal.yml" rel="external noreferrer">GitHub direkt öffnen</a></p></div>
      </form>

      <section class="proposal-contracts" aria-labelledby="contracts-title"><h2 id="contracts-title">Maschinenlesbare Regeln</h2><ul><li><a href="./contracts/commonworld/proposal.schema.json">Vorschlagsschema</a></li><li><a href="./contracts/commonworld/editorial-review.contract.json">Redaktions- und Statusvertrag</a></li><li><a href="./contracts/commonworld/proposal-path.contract.json">Technischer Einreichungsweg</a></li><li><a href="./method.html">Methode und Datenschutz</a></li></ul></section>
    </main>
  </body>
</html>
'''


def main() -> int:
    (ROOT / "propose.html").write_text(render(), encoding="utf-8")
    print("commonworld proposal page rendered from catalog index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
