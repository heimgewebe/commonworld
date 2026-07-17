import test from "node:test";
import assert from "node:assert/strict";
import {
  buildIssueBody,
  buildIssueUrl,
  containsContactData,
  containsSensitiveLocation,
  isSafeHttpsUrl,
  proposalFromFields,
  validateProposal,
} from "../../assets/commonworld-proposal.js";

const fields = {
  name: "Example Commons",
  description: "Eine gemeinschaftlich verwaltete Ressource mit offenen Regeln, primärnahen Quellen und einem realen öffentlichen Beteiligungsweg.",
  official_website: "https://example.org/commons",
  commons_type: "other",
  presence_geographic: true,
  presence_digital: true,
  region: "Norddeutschland",
  actions: [{ type: "learn", url: "https://example.org/commons/about" }, { type: "", url: "" }, { type: "", url: "" }],
  sources: "https://example.org/commons/governance",
  sensitive_location_risk: false,
  editorial_note: "Keine privaten Orte enthalten.",
  public_issue_acknowledged: true,
  processing_agreed: true,
  no_sensitive_data_confirmed: true,
};

function validProposal() {
  return proposalFromFields(fields, new Date("2026-07-16T12:00:00Z"));
}

test("gültiger Vorschlag erfüllt den Clientvertrag", () => {
  assert.deepEqual(validateProposal(validProposal()), []);
});

test("rein digitales Commons benötigt und erfindet keine Region", () => {
  const proposal = proposalFromFields({ ...fields, presence_geographic: false, presence_digital: true, region: "" }, new Date("2026-07-16T12:00:00Z"));
  assert.equal(Object.hasOwn(proposal.project, "region"), false);
  assert.equal(Object.hasOwn(proposal.project, "location_precision"), false);
  assert.deepEqual(validateProposal(proposal), []);
  assert.match(buildIssueBody(proposal), /nicht zutreffend \(nur digital\)/u);

  const fabricated = structuredClone(proposal);
  fabricated.project.region = "Berlin";
  assert.match(validateProposal(fabricated).join(" "), /rein digitaler Präsenz/u);
});

test("Vor-Ort-Präsenz benötigt eine grobe Region", () => {
  const proposal = validProposal();
  delete proposal.project.region;
  assert.match(validateProposal(proposal).join(" "), /Region/u);
});

test("Pflichtquelle, unbekannte Felder und unsichere URLs werden abgelehnt", () => {
  const missing = validProposal(); missing.project.sources = [];
  assert.match(validateProposal(missing).join(" "), /Quellen/u);
  const unknown = validProposal(); unknown.project.unreviewed = true;
  assert.match(validateProposal(unknown).join(" "), /unbekanntes Feld/u);
  const unsafe = validProposal(); unsafe.project.official_website = "javascript:alert(1)";
  assert.match(validateProposal(unsafe).join(" "), /HTTPS/u);
  assert.equal(isSafeHttpsUrl("https://example.org/path"), true);
  assert.equal(isSafeHttpsUrl("javascript:alert(1)"), false);
});

test("präzise private Orte und Kontaktdaten werden fail-closed blockiert", () => {
  assert.equal(containsSensitiveLocation("52.5200, 13.4050"), true);
  assert.equal(containsSensitiveLocation("Router auf Dach Straße 12"), true);
  assert.equal(containsContactData("alex@example.org"), true);
  const proposal = validProposal(); proposal.project.region = "52.5200, 13.4050";
  assert.match(validateProposal(proposal).join(" "), /Adresse oder Koordinate/u);
});

test("Dubletten werden über Titel und offizielle Domain erkannt", () => {
  const proposal = validProposal();
  const errors = validateProposal(proposal, ["Example Commons"], ["example.org"]);
  assert.match(errors.join(" "), /Name ist bereits/u);
  assert.match(errors.join(" "), /Domain ist bereits/u);
});


test("unvollständige optionale Handlungswege werden nicht still verworfen", () => {
  const incomplete = proposalFromFields({ ...fields, actions: [fields.actions[0], { type: "contact", url: "" }, fields.actions[2]] }, new Date("2026-07-16T12:00:00Z"));
  assert.match(validateProposal(incomplete).join(" "), /Handlungswege/u);
});

test("Issue-Handoff bleibt Kandidat und enthält keine automatische Veröffentlichung", () => {
  const proposal = validProposal();
  const body = buildIssueBody(proposal);
  const url = buildIssueUrl(proposal);
  assert.match(body, /nicht automatisch veröffentlicht/u);
  assert.match(body, /status=submitted/u);
  assert.match(url, /^https:\/\/github\.com\/heimgewebe\/commonworld\/issues\/new\?/u);
  assert.ok(url.includes("body="));
  assert.equal(url.includes("template="), false);
});

test("überlange und injizierte Eingaben werden abgelehnt oder escaped", () => {
  const proposal = validProposal();
  proposal.project.description = "x".repeat(801);
  proposal.project.editorial_note = "<script>alert(1)</script>";
  const errors = validateProposal(proposal);
  assert.match(errors.join(" "), /höchstens 800/u);
  assert.match(errors.join(" "), /Script-Inhalt/u);
});
