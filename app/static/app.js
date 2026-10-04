import {
  labels,
  createState,
  invalidate,
  sourceChanged,
  editField,
  beginRequest,
  isCurrent,
  acceptResponse,
  failResponse,
  resetState,
} from "./state.mjs";
const $ = (id) => document.getElementById(id);
let config,
  state,
  controller,
  busy = false;
const example =
  "Сүүлийн 3 хоног ханиалгасан. Халуураагүй.\nҮзлэгт: халуун 36.7 °C, судасны цохилт 78/мин.\nОнош: амьсгалын дээд замын халдвар гэж тэмдэглэсэн.\nПарацетамол 500 мг нэг удаа уусан.\nЭмийн харшилгүй гэж өвчтөн хэлсэн.\nШинжилгээ хийгдээгүй.\nХүлээн авах эмчид: удаан үргэлжилсэн ханиалгын талаар зөвлөгөө хүссэн.";
const errors = {
  local_model_required: "Сонгосон модель дотоод GGUF сангаас олдсонгүй.",
  queue_full: "Хүлээлгийн дараалал дүүрсэн.",
  queue_timeout: "Хүлээх хугацаа дууссан.",
  inference_timeout: "Моделийн хариу хүлээх хугацаа дууссан.",
  runtime_unavailable: "Ollama эсвэл сонгосон модель ажиллахгүй байна.",
  input_limit:
    "Тэмдэглэл урт байна. Бүтэн утгыг хадгалсан богино зохиомол тэмдэглэл ашиглана уу.",
  too_many_units: "Эхийн хэсэг хэт олон байна (дээд хэмжээ 80).",
  invalid_request: "Оролтын хэмжээ эсвэл бүтэц буруу байна.",
  incomplete_output: "Моделийн хариу бүрэн дуусаагүй.",
  invalid_evidence: "Модель буруу эхийн дугаар эсвэл бүтэц буцаасан.",
  unexpected_thinking: "Моделийн бодох горим унтраагүй.",
  invalid_response: "Моделийн хариуг шалгаж чадсангүй.",
  output_limit: "Хариу зөвшөөрөгдсөн хэмжээнээс хэтэрсэн.",
};
function node(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
function status(text, kind = "") {
  $("status").textContent = text;
  $("status").dataset.kind = kind;
}
function invalidateUI() {
  state.approved = false;
  document.body.classList.remove("approved");
  $("print-view").replaceChildren();
  $("reviewed").checked = false;
  $("acknowledged").checked = false;
  $("print").disabled = true;
  $("approval-status").textContent =
    "Баталгаажаагүй — өөрчлөлт бүрийн дараа дахин хянана.";
  updateApproval();
}
function unresolved() {
  return config.fields.filter((f) => !state.fields[f.id].text.trim());
}
function updateApproval() {
  if (!state) return;
  const missing = unresolved();
  $("unresolved").textContent = missing.length
    ? `Шийдээгүй ${missing.length} талбар: ${missing.map((f) => f.label).join("; ")}`
    : "Бүх талбарт текст байна. Зөв ангилал, бүрэн байдлыг эмч шалгана.";
  const oversized = Object.values(state.fields).some(
    (f) => Array.from(f.text).length > 6000,
  );
  if (oversized)
    $("unresolved").textContent +=
      " Нэг талбар 6000 тэмдэгтээс урт байна. Агуулгыг таслаагүй; хянаж богиносгоно уу.";
  $("approve").disabled =
    oversized ||
    busy ||
    !$("reviewed").checked ||
    !$("acknowledged").checked ||
    !Object.values(state.fields).some((f) => f.text.trim());
  $("extract").disabled =
    busy ||
    !state.note.trim() ||
    Array.from(state.note).length > config.max_chars;
}
function refreshField(id) {
  const field = state.fields[id],
    container = $(id + "-status");
  container.textContent = labels[field.status];
  container.dataset.state = field.status;
  const ev = $(id + "-evidence");
  ev.replaceChildren();
  for (const unit of field.evidence) {
    const b = node("button", `Эх ${unit.id}`);
    b.type = "button";
    b.addEventListener("click", () => highlight(unit.id));
    ev.append(b);
  }
  const original = $(id + "-original");
  original.textContent = field.original
    ? `Ялгасан эх (засвараас үл хамааран):\n${field.original}`
    : "";
}
function renderFields() {
  $("fields").replaceChildren();
  for (const field of config.fields) {
    const section = node("section", undefined, "field"),
      head = node("div", undefined, "field-header"),
      label = node("label", field.label);
    label.htmlFor = "field-" + field.id;
    head.append(label);
    const badge = node("span", "", "field-status");
    badge.id = field.id + "-status";
    head.append(badge);
    section.append(head);
    if (field.required)
      section.append(
        node(
          "p",
          "Түр ажлын урсгалын шаардлагатай талбар — мэдээлэлгүй бол тэмдэглэсэн хэвээр үлдээнэ.",
          "required",
        ),
      );
    const input = node("textarea");
    input.id = "field-" + field.id;
    input.rows = 2;
    input.autocomplete = "off";
    input.spellcheck = false;
    input.value = state.fields[field.id].text;
    input.addEventListener("input", () => {
      editField(state, field.id, input.value);
      invalidateUI();
      refreshField(field.id);
      if (busy)
        status(
          "Засвар хийсэн тул ирж буй хуучин хариуг хэрэглэхгүй.",
          "loading",
        );
    });
    section.append(input);
    const ev = node("div", undefined, "evidence");
    ev.id = field.id + "-evidence";
    section.append(ev);
    const original = node("div", undefined, "original");
    original.id = field.id + "-original";
    section.append(original);
    $("fields").append(section);
    refreshField(field.id);
  }
  updateApproval();
}
function renderSource(selected) {
  const pre = $("source-view");
  pre.replaceChildren();
  const chars = Array.from(state.note);
  let cursor = 0;
  for (const unit of state.units) {
    pre.append(
      document.createTextNode(chars.slice(cursor, unit.start).join("")),
    );
    const span = node("span", chars.slice(unit.start, unit.end).join(""));
    span.id = "unit-" + unit.id;
    if (unit.id === selected) span.className = "selected";
    pre.append(span);
    cursor = unit.end;
  }
  pre.append(document.createTextNode(chars.slice(cursor).join("")));
}
function highlight(id) {
  renderSource(id);
  const target = $("unit-" + id);
  if (target) {
    target.scrollIntoView({ behavior: "smooth", block: "nearest" });
    $("source-view").focus({ preventScroll: true });
  }
}
function changeNote(note) {
  sourceChanged(state, note, config);
  controller?.abort();
  busy = false;
  $("note").value = note;
  $("count").textContent =
    `${Array.from(note).length} / ${config.max_chars} тэмдэгт`;
  invalidateUI();
  renderFields();
  renderSource();
  status("Эх шинэчлэгдсэн. Ялгах эсвэл гараар нөхөж болно.");
}
async function extract() {
  if (busy) return;
  const ticket = beginRequest(state);
  invalidateUI();
  busy = true;
  updateApproval();
  status(
    `Модель эхийн хэсгүүдийг ангилж байна… (${config.inference_timeout} секунд хүртэл)`,
    "loading",
  );
  controller = new AbortController();
  const ownController = controller;
  const timer = setTimeout(
    () => ownController.abort(),
    (config.inference_timeout + 20) * 1000,
  );
  try {
    const response = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        note: state.note,
        request_id: String(ticket.request),
      }),
      signal: ownController.signal,
    });
    const data = await response.json();
    if (!response.ok)
      throw new Error(errors[data.error] || "Ялгалт амжилтгүй боллоо.");
    if (data.request_id !== String(ticket.request))
      throw new Error("Хариуны дугаар тохирохгүй.");
    if (!acceptResponse(state, ticket, data)) {
      status(
        "Хуучин хариуг хэрэглэлгүй орхилоо. Таны шинэ тэмдэглэл, засвар хэвээр үлдсэн.",
      );
      return;
    }
    renderFields();
    renderSource();
    status(
      "Ялгалт дууслаа. Ангилал ба дутуу мэдээллийг эхтэй тулгаж хянана уу.",
    );
  } catch (error) {
    if (failResponse(state, ticket)) {
      renderFields();
      renderSource();
      status(
        `${error.name === "AbortError" ? "Хүсэлтийг зогсоосон эсвэл хугацаа дууссан." : error.message} Энэ нь “мэдээлэлгүй” гэсэн үг биш. Гараар нөхөж болно.`,
        "error",
      );
    }
  } finally {
    clearTimeout(timer);
    if (ticket.request === state.request) {
      busy = false;
      updateApproval();
    }
  }
}
function printView() {
  const view = $("print-view");
  view.replaceChildren();
  view.append(
    node(
      "p",
      "ЗОХИОМОЛ ӨГӨГДӨЛ • ТУРШИЛТ • ҮНДЭСНИЙ БАТЛАГДСАН МАЯГТ БИШ",
      "print-notice",
    ),
    node("h1", "Илгээх бичгийн бэлтгэл"),
    node(
      "small",
      `${config.version} | ${config.model} | Эмч хянаж баталсан: ${new Date().toLocaleString("mn-MN")}`,
    ),
  );
  for (const f of config.fields) {
    const value = state.fields[f.id],
      section = node("section", undefined, "print-field");
    section.append(
      node("h2", f.label),
      node(
        "p",
        value.text.trim()
          ? value.text
          : `ШИЙДЭЭГҮЙ / МЭДЭЭЛЭЛ НӨХӨӨГҮЙ — ${labels[value.status]}`,
      ),
      node(
        "small",
        `${labels[value.status]}${value.evidence.length ? " | Эх: " + value.evidence.map((e) => e.id).join(", ") : ""}`,
      ),
    );
    view.append(section);
  }
  view.append(
    node(
      "p",
      "Эмч бүх талбарыг хянаж, шийдээгүй зүйлсийг тэмдэглэсэн хэвээр экспортлохыг зөвшөөрсөн. Энэ баталгаа нь цахим гарын үсэг биш.",
    ),
    node(
      "footer",
      "Баримт бичгийн туршилт. Экспортолсон файлыг тусад нь хадгалж, дундын төхөөрөмж дээр зохицуулна.",
    ),
  );
}
$("note").addEventListener("input", () => changeNote($("note").value));
$("example").addEventListener("click", () => {
  if (state.note || Object.values(state.fields).some((f) => f.text)) {
    if (
      !window.confirm(
        "Одоогийн эхийг зохиомол жишээгээр солих уу? Эмчийн гараар оруулсан талбарууд хадгалагдана.",
      )
    )
      return;
  }
  changeNote(example);
});
$("extract").addEventListener("click", extract);
$("reset").addEventListener("click", () => {
  controller?.abort();
  resetState(state, config);
  busy = false;
  $("note").value = "";
  $("count").textContent = `0 / ${config.max_chars} тэмдэгт`;
  invalidateUI();
  renderFields();
  renderSource();
  status("Хуудсын агуулгыг цэвэрлэлээ. Өмнө экспортолсон файл тусдаа үлдэнэ.");
});
for (const id of ["reviewed", "acknowledged"])
  $(id).addEventListener("change", () => {
    if (state.approved) {
      invalidate(state);
      document.body.classList.remove("approved");
      $("print-view").replaceChildren();
      $("print").disabled = true;
      $("approval-status").textContent = "Баталгаажаагүй";
    }
    updateApproval();
  });
$("approve").addEventListener("click", () => {
  if ($("approve").disabled) return;
  state.approved = true;
  document.body.classList.add("approved");
  printView();
  $("print").disabled = false;
  $("approval-status").textContent =
    "Хянаж баталсан. Өөрчлөлт хийвэл баталгаа хүчингүй болно.";
});
$("print").addEventListener("click", () => {
  if (state.approved) window.print();
});
window.addEventListener("beforeprint", () => {
  if (!state?.approved) document.body.classList.remove("approved");
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted) location.reload();
});
try {
  const response = await fetch("/api/config");
  if (!response.ok) throw new Error();
  config = await response.json();
  state = createState(config);
  $("model").textContent = config.model;
  $("schema-version").textContent = config.version;
  renderFields();
  status("Зохиомол тэмдэглэл оруулах эсвэл жишээг нээнэ үү.");
} catch {
  status("Тохиргоо ачаалсангүй. Програмыг дахин ажиллуулна уу.", "error");
  for (const id of ["example", "reset", "note"]) $(id).disabled = true;
}
