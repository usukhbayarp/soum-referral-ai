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
      },
    ]),
  );
}
export function createState(config) {
  return {
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
    state.fields[f.id] = {
      text: old.status === "manual" ? old.text : "",
      status:
        old.status === "manual"
          ? "manual"
          : f.manual
            ? "manual_pending"
            : "pending",
      evidence: [],
      original: "",
    };
  }
}
export function editField(state, id, text) {
  invalidate(state);
  state.fields[id].text = text;
  state.fields[id].status = "manual";
}
export function beginRequest(state) {
  invalidate(state);
  return { revision: state.revision, request: ++state.request };
}
export function isCurrent(state, ticket) {
  return ticket.revision === state.revision && ticket.request === state.request;
}
export function acceptResponse(state, ticket, result) {
  if (!isCurrent(state, ticket)) return false;
  state.units = result.units;
  for (const [id, value] of Object.entries(result.fields)) {
    if (state.fields[id].status !== "manual") {
      state.fields[id] = { ...value, original: value.text };
    } else {
      state.fields[id].evidence = value.evidence;
      state.fields[id].original = value.text;
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
export function resetState(state, config) {
  invalidate(state);
  state.request++;
  state.note = "";
  state.units = [];
  state.fields = initialFields(config);
}
