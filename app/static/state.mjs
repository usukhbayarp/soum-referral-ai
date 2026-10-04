export const labels = {
  manual_pending: "Гараар оруулах",
  pending: "Ялгаагүй — гараар нөхөж болно",
  extracted: "Эхээс авсан — хянана уу",
  not_found: "Модель олоогүй — эхийг хянана уу",
  failed: "Ялгалт / нотолгоо алдаатай",
  manual: "Эмч оруулсан / зассан",
};
export function initialFields(config) {
  return Object.fromEntries(
    config.fields.map((f) => [
      f.id,
      {
        text: "",
        status: f.manual ? "manual_pending" : "pending",
        evidence: [],
        original: "",
        meaning: "unreviewed",
        evidenceCurrent: true,
        suggestion: null,
        needsReconciliation: false,
      },
    ]),
  );
}
export function createState(config) {
  return {
    caseId: 0,
    revision: 0,
    request: 0,
    approved: false,
    note: "",
    units: [],
    fields: initialFields(config),
  };
}
export function invalidate(state) {
  state.revision++;
  state.approved = false;
}
export function sourceChanged(state, note, config) {
  invalidate(state);
  state.note = note;
  state.units = [];
  for (const f of config.fields) {
    const old = state.fields[f.id];
    if (old.status === "manual") {
      // A source edit stays in this case. Retain work, but require explicit review.
      old.needsReconciliation = Boolean(old.text.trim() || (old.meaning && old.meaning !== "unreviewed"));
      old.reconciliationReason = "source";
      old.evidenceCurrent = false;
      old.suggestion = null;
    } else {
      state.fields[f.id] = initialFields(config)[f.id];
    }
  }
}
export function editField(state, id, text) {
  invalidate(state);
  state.fields[id].text = text;
  state.fields[id].status = "manual";
}
export function beginRequest(state) {
  invalidate(state);
  return {
    caseId: state.caseId,
    revision: state.revision,
    request: ++state.request,
  };
}
export function isCurrent(state, ticket) {
  return (
    ticket.caseId === state.caseId &&
    ticket.revision === state.revision &&
    ticket.request === state.request
  );
}
export function acceptResponse(state, ticket, result, config = {}) {
  if (!isCurrent(state, ticket)) return false;
  state.units = result.units;
  for (const [id, value] of Object.entries(result.fields)) {
    if (!state.fields[id]) continue;
    if (state.fields[id].status !== "manual") {
      state.fields[id] = {
        ...value,
        original: value.text,
        meaning: "unreviewed",
        evidenceCurrent: true,
        suggestion: null,
        needsReconciliation: Boolean(value.text?.trim() && config.proposal_review_required?.includes(id)),
        reconciliationReason: config.proposal_review_required?.includes(id) ? "category" : null,
      };
    } else {
      // A fresh extraction is a separate proposal, never support for retained edits.
      state.fields[id].suggestion = {
        text: value.text,
        evidence: value.evidence,
        status: value.status,
      };
    }
  }
  return true;
}
export function failResponse(state, ticket) {
  if (!isCurrent(state, ticket)) return false;
  for (const field of Object.values(state.fields)) {
    if (field.status !== "manual" && field.status !== "manual_pending") {
      field.status = "failed";
      field.text = "";
      field.evidence = [];
      field.original = "";
    }
  }
  // Existing units still refer to the same source; keep edited fields' evidence clickable.
  return true;
}
export function newReferral(state, config, note = "") {
  invalidate(state);
  state.request++;
  state.caseId++;
  state.note = note;
  state.units = [];
  state.fields = initialFields(config);
}

export function resetState(state, config) {
  newReferral(state, config);
}
export function hasReferralContent(state) {
  return Boolean(
    state.note ||
      state.approved ||
      state.units.length ||
      Object.values(state.fields).some(
        (f) => f.text || f.original || f.suggestion || (f.meaning && f.meaning !== "unreviewed"),
      ),
  );
}
export function replaceReferral(state, config, note, confirmReplacement) {
  if (hasReferralContent(state) && !confirmReplacement()) return false;
  newReferral(state, config, note);
  return true;
}
export function reconcileField(state, id) {
  if (!state.fields[id].needsReconciliation) return;
  invalidate(state);
  state.fields[id].needsReconciliation = false;
  state.fields[id].reconciliationReason = null;
}
export function pendingReconciliations(state) {
  return Object.entries(state.fields)
    .filter(([, field]) => field.needsReconciliation)
    .map(([id]) => id);
}
export function canApprove(
  state,
  { busy = false, reviewed = false, acknowledged = false } = {},
) {
  return (
    !busy &&
    reviewed &&
    acknowledged &&
    pendingReconciliations(state).length === 0 &&
    Object.values(state.fields).some((f) => f.text.trim()) &&
    !Object.values(state.fields).some((f) => Array.from(f.text).length > 6000)
  );
}
export function printAttribution(field) {
  if (field.status === "manual") {
    return "Эмч оруулсан / зассан — энэ агуулгыг эхээр баталгаажсан гэж үзэхгүй. Анхны ялгалт болон дахин ялгалтын санал нь засварын нотолгоо биш.";
  }
  return `${labels[field.status]}${field.evidence.length ? " | Эх: " + field.evidence.map((e) => e.id).join(", ") : ""}`;
}

export function editMeaning(state, id, meaning) {
  editField(state, id, state.fields[id].text);
  state.fields[id].meaning = meaning;
}
