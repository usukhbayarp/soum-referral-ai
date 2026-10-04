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
test("new extraction keeps previous doctor edits while attaching evidence", () => {
  const s = createState(config);
  editField(s, "history", "manual");
  const t = beginRequest(s);
  assert.ok(acceptResponse(s, t, output));
  assert.equal(s.fields.history.text, "manual");
  assert.equal(s.fields.history.original, "Халуураагүй.");
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
test('failed re-extraction keeps edited-field evidence navigable', () => {
  const s=createState(config); acceptResponse(s,beginRequest(s),output);
  editField(s,'history','manual'); failResponse(s,beginRequest(s));
  assert.equal(s.fields.history.evidence[0].id,1);
  assert.equal(s.units[0].id,1);
});
