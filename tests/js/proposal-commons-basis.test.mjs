import test from "node:test";
import assert from "node:assert/strict";
import { buildIssueBody, proposalFromFields, validateProposal } from "../../assets/commonworld-proposal.js";

const baseFields = {
  name: "Basis Example Commons",
  description: "Eine gemeinschaftlich verwaltete Ressource mit offenen Regeln, primärnahen Quellen und einem realen öffentlichen Beteiligungsweg.",
  official_website: "https://example.org/basis-commons",
  commons_type: "other",
  presence_geographic: false,
  presence_digital: true,
  region: "",
  actions: [{ type: "learn", url: "https://example.org/basis-commons/about" }, { type: "", url: "" }, { type: "", url: "" }],
  sources: "https://example.org/basis-commons/governance\nhttps://example.org/basis-commons/community",
  sensitive_location_risk: false,
  editorial_note: "",
  public_issue_acknowledged: true,
  processing_agreed: true,
  no_sensitive_data_confirmed: true,
};

function basisFields() {
  return {
    shared_good: {
      classification: "confirmed",
      text: "Eine gemeinsam gepflegte Wissensressource mit offen dokumentierter Nutzung.",
      refs: ["source-1"],
    },
    community: { classification: "open", text: "", refs: [] },
    rules_and_governance: { classification: "", text: "", refs: [] },
    stewardship: { classification: "", text: "", refs: [] },
    legitimacy: { classification: "not_applicable", text: "", refs: [] },
  };
}

function proposal() {
  return proposalFromFields({ ...baseFields, commons_basis: basisFields() }, new Date("2026-08-06T03:30:00Z"));
}

test("legacy proposals remain valid without a Commons basis draft", () => {
  const legacy = proposalFromFields(baseFields, new Date("2026-08-06T03:30:00Z"));
  assert.equal(Object.hasOwn(legacy, "commons_basis_draft"), false);
  assert.deepEqual(validateProposal(legacy), []);
});

test("optional dimensions serialize with explicit unknown and source references", () => {
  const value = proposal();
  assert.deepEqual(validateProposal(value), []);
  assert.equal(value.commons_basis_draft.status, "needs_review");
  assert.equal(value.commons_basis_draft.dimensions.community.classification, "open");
  assert.deepEqual(value.commons_basis_draft.dimensions.shared_good.refs, ["source-1"]);
  assert.equal(Object.hasOwn(value.commons_basis_draft.dimensions, "rules_and_governance"), false);
});

test("GitHub issue contains the identical structured draft object", () => {
  const value = proposal();
  const body = buildIssueBody(value);
  const sectionStart = body.indexOf("### Optionaler Commons-Basisentwurf\n");
  const sectionEnd = body.indexOf("\n### Bestätigungen", sectionStart);
  assert.ok(sectionStart >= 0 && sectionEnd > sectionStart, body);
  const sectionLines = body.slice(sectionStart, sectionEnd).trimEnd().split("\n");
  const embedded = JSON.parse(
    sectionLines
      .slice(2)
      .map((line) => {
        assert.ok(line.startsWith("    "), body);
        return line.slice(4);
      })
      .join("\n"),
  );
  assert.deepEqual(embedded, value.commons_basis_draft);
  assert.match(body, /source-1: https:\/\/example\.org\/basis-commons\/governance/u);
  assert.doesNotMatch(body, /Punktzahl:\s*\d/iu);
});

test("confirmed dimensions require evidence text and a listed source", () => {
  const missingRef = proposal();
  missingRef.commons_basis_draft.dimensions.shared_good.refs = [];
  assert.match(validateProposal(missingRef).join(" "), /Quellenverweis/u);
  const unknownRef = proposal();
  unknownRef.commons_basis_draft.dimensions.shared_good.refs = ["source-5"];
  assert.match(validateProposal(unknownRef).join(" "), /aufgeführten Quellen/u);
  const shortText = proposal();
  shortText.commons_basis_draft.dimensions.shared_good.text = "zu kurz";
  assert.match(validateProposal(shortText).join(" "), /20 Zeichen/u);
});

test("new basis text uses the same privacy boundary as every public field", () => {
  const value = proposal();
  value.commons_basis_draft.dimensions.community = {
    classification: "open",
    text: "Treffen in der Musterstraße 12 in Berlin.",
    refs: [],
  };
  assert.match(validateProposal(value).join(" "), /Adresse oder Koordinate/u);
  assert.throws(() => buildIssueBody(value), /public issue handoff rejected/u);
});
