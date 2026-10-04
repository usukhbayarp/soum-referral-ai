import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  createState,
  sourceChanged,
  editField,
  beginRequest,
  acceptResponse,
  failResponse,
  resetState,
  replaceReferral,
  reconcileField,
  pendingReconciliations,
  canApprove,
  printAttribution,
} from "../app/static/state.mjs";
const config = JSON.parse(
  fs.readFileSync(new URL("../config/referral.v0.1.json", import.meta.url)),
);
const output = {
  units: [{ id: 1, start: 0, end: 11, text: "Халуураагүй." }],
  fields: {
    history: {
      text: "Халуураагүй.",
      status: "extracted",
      evidence: [{ id: 1, text: "Халуураагүй." }],
    },
  },
};
test("edits invalidate approval and retain original negative evidence", () => {
  const s = createState(config);
  const t = beginRequest(s);
  assert.ok(acceptResponse(s, t, output));
  s.approved = true;
  editField(s, "history", "Эмч зассан");
  assert.equal(s.approved, false);
  assert.equal(s.fields.history.original, "Халуураагүй.");
  assert.equal(s.fields.history.evidence[0].text, "Халуураагүй.");
});
test("late response cannot overwrite new source", () => {
  const s = createState(config);
  const t = beginRequest(s);
  sourceChanged(s, "new source", config);
  assert.equal(acceptResponse(s, t, output), false);
  assert.equal(s.fields.history.text, "");
});
test("late response and failure cannot overwrite doctor edits", () => {
  const s = createState(config);
  const t = beginRequest(s);
  editField(s, "history", "manual");
  assert.equal(acceptResponse(s, t, output), false);
  assert.equal(failResponse(s, t), false);
  assert.equal(s.fields.history.text, "manual");
});
test("new extraction keeps previous doctor edits with a separate proposal", () => {
  const s = createState(config);
  editField(s, "history", "manual");
  const t = beginRequest(s);
  assert.ok(acceptResponse(s, t, output));
  assert.equal(s.fields.history.text, "manual");
  assert.equal(s.fields.history.original, "");
  assert.equal(s.fields.history.suggestion.text, "Халуураагүй.");
});
test("failures distinct from not found and manually recoverable", () => {
  const s = createState(config);
  const t = beginRequest(s);
  assert.ok(failResponse(s, t));
  assert.equal(s.fields.history.status, "failed");
  editField(s, "history", "manual");
  assert.equal(s.fields.history.status, "manual");
});
test("reset clears note, evidence and approval; rejects outstanding response", () => {
  const s = createState(config);
  s.note = "test";
  const t = beginRequest(s);
  acceptResponse(s, t, output);
  s.approved = true;
  resetState(s, config);
  assert.equal(s.note, "");
  assert.equal(s.fields.history.original, "");
  assert.equal(s.fields.history.text, "");
  assert.equal(s.approved, false);
  assert.equal(acceptResponse(s, t, output), false);
});
test("blank administrative fields are not labeled doctor-entered or model-failed", () => {
  const s = createState(config);
  assert.equal(s.fields.patient.status, "manual_pending");
  failResponse(s, beginRequest(s));
  assert.equal(s.fields.patient.status, "manual_pending");
  sourceChanged(s, "new", config);
  assert.equal(s.fields.patient.status, "manual_pending");
});
test("failed re-extraction keeps edited-field evidence navigable", () => {
  const s = createState(config);
  acceptResponse(s, beginRequest(s), output);
  editField(s, "history", "manual");
  failResponse(s, beginRequest(s));
  assert.equal(s.fields.history.evidence[0].id, 1);
  assert.equal(s.units[0].id, 1);
});

test("new referral and confirmed example replacement erase every Patient A value", () => {
  for (const note of ["", "Fictional Patient B note"]) {
    const s = createState(config);
    sourceChanged(s, "Patient A", config);
    acceptResponse(s, beginRequest(s), output);
    editField(s, "patient", "Patient A identifiers");
    editField(s, "facilities", "Patient A facility");
    editField(s, "history", "Patient A manual history");
    s.approved = true;
    const pending = beginRequest(s);
    let confirmations = 0;
    assert.ok(
      replaceReferral(s, config, note, () => {
        confirmations++;
        return true;
      }),
    );
    assert.equal(confirmations, 1);
    assert.equal(s.note, note);
    assert.equal(s.approved, false);
    assert.deepEqual(s.units, []);
    for (const field of Object.values(s.fields)) {
      assert.equal(field.text, "");
      assert.equal(field.original, "");
      assert.deepEqual(field.evidence, []);
      assert.equal(field.suggestion, null);
      assert.equal(field.needsReconciliation, false);
    }
    assert.equal(acceptResponse(s, pending, output), false);
    assert.equal(failResponse(s, pending), false);
  }
});
test("canceling example replacement preserves the entire current referral", () => {
  const s = createState(config);
  editField(s, "patient", "Patient A");
  s.approved = true;
  const before = structuredClone(s);
  assert.equal(
    replaceReferral(s, config, "Patient B", () => false),
    false,
  );
  assert.deepEqual(s, before);
});
test("source keystrokes retain manual work but block approval until explicit reconciliation", () => {
  const s = createState(config);
  editField(s, "patient", "Patient A");
  editField(s, "history", "Manually corrected history");
  const acknowledgments = { reviewed: true, acknowledged: true };
  assert.ok(canApprove(s, acknowledgments));
  for (const note of ["n", "ne", "new source"]) sourceChanged(s, note, config);
  assert.equal(s.fields.patient.text, "Patient A");
  assert.equal(s.fields.history.text, "Manually corrected history");
  assert.deepEqual(pendingReconciliations(s), ["patient", "history"]);
  assert.equal(canApprove(s, acknowledgments), false);
  editField(s, "history", "Another correction");
  assert.equal(s.fields.history.needsReconciliation, true);
  acceptResponse(s, beginRequest(s), output);
  assert.equal(canApprove(s, acknowledgments), false);
  reconcileField(s, "patient");
  assert.equal(canApprove(s, acknowledgments), false);
  reconcileField(s, "history");
  assert.ok(canApprove(s, acknowledgments));
  sourceChanged(s, "newer source", config);
  assert.equal(canApprove(s, acknowledgments), false);
});
test("re-extraction never overwrites original evidence or attests retained manual text", () => {
  const s = createState(config);
  acceptResponse(s, beginRequest(s), output);
  editField(s, "history", "Doctor edit");
  const original = structuredClone(s.fields.history.evidence);
  const next = {
    units: [{ id: 2, text: "New proposal" }],
    fields: {
      history: {
        status: "extracted",
        text: "New proposal",
        evidence: [{ id: 2, text: "New proposal" }],
      },
    },
  };
  acceptResponse(s, beginRequest(s), next);
  assert.equal(s.fields.history.text, "Doctor edit");
  assert.deepEqual(s.fields.history.evidence, original);
  assert.equal(s.fields.history.original, "Халуураагүй.");
  assert.equal(s.fields.history.suggestion.text, "New proposal");
  const attribution = printAttribution(s.fields.history);
  assert.match(attribution, /Эмч оруулсан \/ зассан/);
  assert.match(attribution, /баталгаажсан гэж үзэхгүй/);
  assert.doesNotMatch(attribution, /\| Эх:/);
  assert.doesNotMatch(attribution, /1|2/);
  assert.match(printAttribution(output.fields.history), /\| Эх: 1/);
});
test("historical evidence stays readable but is not linked to the changed source", () => {
  const s = createState(config);
  acceptResponse(s, beginRequest(s), output);
  editField(s, "history", "Retained edit");
  sourceChanged(s, "different source", config);
  assert.equal(s.fields.history.original, "Халуураагүй.");
  assert.equal(s.fields.history.evidenceCurrent, false);
  assert.equal(s.fields.history.suggestion, null);
});
