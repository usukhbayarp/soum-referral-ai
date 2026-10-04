import {
  labels,
  createState,
  invalidate,
  sourceChanged,
  editField,
  beginRequest,
  acceptResponse,
  failResponse,
  replaceReferral,
  reconcileField,
  pendingReconciliations,
  canApprove,
  printAttribution,
  editMeaning,
} from "./state.mjs";
import { completeness, meanings, rowColumns, rowsOf } from "./completeness.mjs";
const $ = (id) => document.getElementById(id);
let printRule = null;
let config,
  state,
  controller,
  busy = false;
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
function clearPrintHeader() {
  if(printRule !== null) {document.styleSheets[0].deleteRule(printRule);printRule=null;}
}
function invalidateUI() {
  clearPrintHeader();
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
  const warnings = completeness(state, config);
  $("unresolved").replaceChildren(node("p", "Эдгээр нь хяналтын сануулга; шилжүүлэх эсэхийг шийдэхгүй. Нөхцөлүүдийг эмч батална; бөглөсөн текст нь эмнэлзүйн бүрэн байдлын баталгаа биш."));
  const list = node("ul");
  warnings.forEach(w => list.append(node("li", w.message)));
  $("unresolved").append(list);
  const oversized = Object.values(state.fields).some(
    (f) => Array.from(f.text).length > 6000,
  );
  if (oversized)
    $("unresolved").append(
      " Нэг талбар 6000 тэмдэгтээс урт байна. Агуулгыг таслаагүй; хянаж богиносгоно уу.");
  const pending = pendingReconciliations(state);
  if (pending.length)
    $("unresolved").append(
      ` Эх өөрчлөгдсөн: хадгалсан ${pending.length} талбарыг шинэ эхтэй тулгаж дахин хянана уу.`);
  $("approve").disabled = !canApprove(state, {
    busy,
    reviewed: $("reviewed").checked,
    acknowledged: $("acknowledged").checked,
  });
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
  if(field.review_flags?.length) container.textContent += " • " + field.review_flags.join(" ");
  const ev = $(id + "-evidence");
  ev.replaceChildren();
  for (const unit of field.evidence) {
    const b = node(
      "button",
      `${field.status === "manual" ? "Анхны ялгалтын эх" : "Эх"} ${unit.id}`,
    );
    b.type = "button";
    b.disabled = !field.evidenceCurrent;
    b.addEventListener("click", () => highlight(unit.id));
    ev.append(b);
  }
  const original = $(id + "-original");
  original.textContent = field.original
    ? `Анхны ялгалтын эх — эмчийн зассан агуулгыг батлахгүй.${!field.evidenceCurrent ? " Өмнөх эхийн хувилбар; одоогийн эхтэй холбохгүй." : ""}\n${field.original}`
    : "";
  const proposal = $(id + "-suggestion");
  proposal.replaceChildren();
  if (field.suggestion) {
    proposal.append(
      node(
        "p",
        "Дахин ялгалтын тусдаа санал — хадгалсан гар засварын нотолгоо биш.",
        "hint",
      ),
    );
    proposal.append(
      node("p", field.suggestion.text || "Модель олоогүй — эхийг хянана уу."),
    );
    for (const unit of field.suggestion.evidence) {
      const b = node("button", `Саналын эх ${unit.id}`);
      b.type = "button";
      b.addEventListener("click", () => highlight(unit.id));
      proposal.append(b);
    }
  }
  const reconciliation = $(id + "-reconciliation");
  reconciliation.replaceChildren();
  if (field.needsReconciliation) {
    container.textContent += " • Шинэ эхтэй тулгаж хянана";
    reconciliation.append(
      node(
        "p",
        "Эх өөрчлөгдсөн. Гараар оруулсан утгыг хадгалсан; шинэ эхтэй тулгаж хянах хүртэл батлах боломжгүй.",
        "hint",
      ),
    );
    const review = node("button", "Хадгалсан утгыг шинэ эхтэй тулгаж хянасан");
    review.type = "button";
    review.addEventListener("click", () => {
      reconcileField(state, id);
      invalidateUI();
      refreshField(id);
    });
    reconciliation.append(review);
  }
}
function grow(input) {
  if(input.tagName !== "TEXTAREA") return;
  input.style.height="auto"; input.style.height=Math.max(60,input.scrollHeight)+"px";
}
function renderTreatmentRows(section) {
  const rows=rowsOf(state);
  const save=()=> { editField(state,"treatment_rows",JSON.stringify(rows)); invalidateUI(); refreshField("treatment_rows"); };
  rows.forEach((row,i)=> {
    const card=node("fieldset",undefined,"treatment-row"); card.append(node("legend", `Эмчилгээ / ажилбар ${i+1} — эмч оруулна`));
    for(const [key,label,options] of [["kind","Төрөл",[["medication","Эм"],["procedure","Ажилбар"]]],["schedule","Хийсэн давтамж",[["single","Нэг удаа"],["repeated","Давтан"]]]]) {
      const select=node("select"); select.setAttribute("aria-label",`${i+1} ${label}`); select.append(new Option("— Тодруулна —",""));
      options.forEach(([v,t])=>select.append(new Option(t,v))); select.value=row[key]||"";
      select.addEventListener("change",()=>{row[key]=select.value;save();}); card.append(node("label",label),select);
    }
    for(const [key,label] of rowColumns) {
      const input=node("textarea"); input.value=row[key]||""; input.rows=1; input.setAttribute("aria-label",`${i+1} ${label}`);
      input.addEventListener("input",()=>{row[key]=input.value;grow(input);save();}); card.append(node("label",label),input); requestAnimationFrame(()=>grow(input));
    }
    const remove=node("button","Мөр устгах"); remove.type="button";
    remove.addEventListener("click",()=>{rows.splice(i,1);save();renderFields();});card.append(remove);section.append(card);
  });
  const add=node("button","Эмчилгээний мөр нэмэх"); add.type="button";
  add.addEventListener("click",()=>{ rows.push({});save();renderFields(); });section.append(add);
}
function renderFields() {
  $("fields").replaceChildren();
  let group, previous;
  for (const field of config.fields) {
    if (previous !== field.section) {
      group = node("div", undefined, "form-section");
      group.append(node("h2", `${field.section} ${config.sections.find(s=>s.id===field.section).label}`));
      $("fields").append(group); previous = field.section;
    }
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
    const input = node(field.options ? "select" : "textarea");
    if (field.options) {
      input.append(new Option("— Эмч сонгоно —", ""));
      field.options.forEach(v=>input.append(new Option(v,v)));
    }
    input.id = "field-" + field.id;
    input.rows = 2;
    input.autocomplete = "off";
    input.spellcheck = false;
    input.value = state.fields[field.id].text;
    input.addEventListener("input", () => {
      grow(input);
      editField(state, field.id, input.value);
      invalidateUI();
      refreshField(field.id);
      if (busy)
        status(
          "Засвар хийсэн тул ирж буй хуучин хариуг хэрэглэхгүй.",
          "loading",
        );
    });
    if (field.kind === "treatment_rows") renderTreatmentRows(section);
    else { section.append(input); requestAnimationFrame(()=>grow(input)); }
    if (field.kind === "source_suggestion") section.append(node("p", "Зөвхөн эхийн санал. Доорх нарийвчилсан утга бүрийн баталгаа биш; утгыг эмч тусад нь оруулна.", "hint"));
    if (!field.options && field.kind !== "treatment_rows") {
      const meaning = node("select"); meaning.setAttribute("aria-label", field.label + " — эхийн утгын төлөв");
      for (const [key,label] of Object.entries(meanings)) meaning.append(new Option(label,key));
      meaning.value = state.fields[field.id].meaning || "unreviewed";
      meaning.addEventListener("change", ()=> { editMeaning(state,field.id,meaning.value); invalidateUI(); refreshField(field.id); });
      section.append(meaning);
    }
    if (field.source_group) {
      const groupField=state.fields[field.source_group];
      const details=node("details", undefined, "source-suggestion");
      details.append(node("summary", "Эхийн тусдаа санал — энэ гар утгыг батлахгүй"));
      details.append(node("p", groupField.text || labels[groupField.status]));
      for(const unit of groupField.evidence) {
        const b=node("button", `Саналын эх ${unit.id}`); b.type="button"; b.disabled=!groupField.evidenceCurrent;
        b.addEventListener("click",()=>highlight(unit.id)); details.append(b);
      }
      if (field.id.endsWith("time") || field.kind === "treatment_rows") details.append(node("p", "Цаг дангаар байвал бүтэн огноо автоматаар нөхөхгүй. Эхийн огноо ба тухайн цагийн холбоог эмч шалгаж, эргэлзээтэй бол эхийн цагийг хэвээр үлдээнэ."));
      section.append(details);
    }
    const ev = node("div", undefined, "evidence");
    ev.id = field.id + "-evidence";
    section.append(ev);
    const original = node("div", undefined, "original");
    original.id = field.id + "-original";
    section.append(original);
    for (const suffix of ["suggestion", "reconciliation"]) {
      const area = node("div", undefined, suffix);
      area.id = field.id + "-" + suffix;
      section.append(area);
    }
    group.append(section);
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
  status(
    "Одоогийн тохиолдлын эх шинэчлэгдсэн. Хадгалсан гар засваруудыг шинэ эхтэй тулгаж хянана уу.",
  );
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
    if (data.schema_version !== config.version || data.prompt_version !== config.prompt_version) throw new Error("Хариуны загвар / prompt хувилбар тохирохгүй. Дахин ачаална уу.");
    if (!acceptResponse(state, ticket, data)) {
      if (ticket.caseId === state.caseId && ticket.request === state.request)
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
  const view = $("print-view"); view.replaceChildren();
  const header=node("div",undefined,"print-repeat");
  const patient=state.fields.patient.text || state.fields.identifier.text || "Таних мэдээлэл дутуу";
  header.append(node("div", `Өвчтөн шилжүүлэх хураангуй • ${Array.from(patient).slice(0,90).join("")}${Array.from(patient).length>90?"… (бүтэн утга доор)":""}`),node("small", `${config.version} • ЗОХИОМОЛ • АЛБАН ЁСНЫ МАЯГТ БИШ • 13А-г орлохгүй`));
  clearPrintHeader();
  const shortID=Array.from(patient).slice(0,90).join("").replace(/[\r\n\f]/g," ").replace(/\\/g,"\\\\").replace(/"/g,'\\"');
  const sheet=document.styleSheets[0];
  printRule=sheet.insertRule(`@page referral { size: A4; margin: 25mm 17mm 20mm; @top-left { content: "Өвчтөн шилжүүлэх хураангуй • ${shortID}"; font: bold 10pt Arial; } @bottom-right { content: "Хуудас " counter(page); font: 9pt Arial; } }`,sheet.cssRules.length);
  const cell=node("div");view.append(header,cell);
  cell.append(node("p", `${config.model} | ${config.prompt_version} | Эмч хянаж баталсан үйлдэл: ${new Date().toLocaleString("mn-MN")} — цахим гарын үсэг биш.`));
  let previous;
  for (const f of config.fields) {
    if(previous!==f.section) {cell.append(node("h2",`${f.section} ${config.sections.find(s=>s.id===f.section).label}`));previous=f.section;}
    const value=state.fields[f.id], section=node("section",undefined,"print-field");
    section.append(node("h3",f.label));
    if(f.kind === "treatment_rows") {
      const rows=rowsOf(state);
      if(!rows.length) section.append(node("p","Эмчилгээний мөр оруулаагүй — эмч хянана"));
      rows.forEach((r,i)=> {
        const card=node("div",undefined,"print-treatment-row");
        card.append(node("h4", `Мөр ${i+1} • ${r.kind==="procedure"?"Ажилбар":r.kind==="medication"?"Эм":"Төрөл тодорхойгүй"} • ${r.schedule==="single"?"Нэг удаа":r.schedule==="repeated"?"Давтан":"Давтамж тодорхойгүй"}`));
        for(const [key,label] of rowColumns) card.append(node("p",`${label}: ${r[key] || (key==="frequency" && r.schedule==="single" ? "Хамаарахгүй — нэг удаа" : "Эмч нөхөөгүй")}`));
        section.append(card);
      });
    } else section.append(node("p",value.text.trim() || `Эмч нөхөөгүй — ${labels[value.status]}`));
    if(f.kind === "source_suggestion") section.append(node("strong", "Эхийн санал төдий — нарийвчилсан утга бүрийн баталгаа биш."));
    section.append(node("small", printAttribution(value)));
    value.review_flags?.forEach(flag=>section.append(node("p",flag)));
    if(value.meaning && value.meaning!=="unreviewed") section.append(node("small",` | Эмчийн тэмдэглэсэн утгын төлөв: ${meanings[value.meaning]}`));
    if(value.status==="manual" && value.original) section.append(node("p",`Анхны ялгалтын эх — зассан утгын нотолгоо биш: ${value.original}`,"print-original"));
    cell.append(section);
  }
  cell.append(node("h2","Хяналтын үлдсэн сануулга — шилжүүлэх эсэхийн шийдвэр биш"));
  completeness(state,config).forEach(w=>cell.append(node("p",w.message)));
  cell.append(node("p","Эмч эх, талбаруудыг хянаж, дутуу / тодруулах боломжгүй зүйлсийг хэвээр экспортлохыг зөвшөөрсөн. Гарын үсэг, тамгыг автоматаар үүсгээгүй."));
}
$("note").addEventListener("input", () => changeNote($("note").value));
function startReferral(note = "") {
  if (
    !replaceReferral(state, config, note, () =>
      window.confirm(
        "Шинэ илгээх бичиг эхлүүлэх үү? Одоогийн эх, өвчтөн ба байгууллагын мэдээлэл, бүх гар засвар, нотолгоо, баталгаа болон хэвлэх агуулга арилна.",
      ),
    )
  )
    return false;
  controller?.abort();
  busy = false;
  $("note").value = state.note;
  $("count").textContent =
    `${Array.from(state.note).length} / ${config.max_chars} тэмдэгт`;
  invalidateUI();
  renderFields();
  renderSource();
  status(
    "Шинэ илгээх бичиг эхэллээ. Өмнөх тохиолдлын мэдээлэл арилсан; экспортолсон файл тусдаа үлдэнэ.",
  );
  return true;
}
$("example").addEventListener("click", async () => {
  const originalCase=state.caseId, originalRevision=state.revision;
  try { const response = await fetch("/api/example/dev002"); if(!response.ok) throw new Error();
    const example = await response.json();
    if(state.caseId!==originalCase || state.revision!==originalRevision) return;
    if(!startReferral(example.source_note)) return;
    status("DEV-002 • Бүрэн зохиомол • Хөгжүүлэлтийн жишээ • Эмчийн эцсийн хяналт хийгдээгүй • Сургалтад ашиглахгүй");
  } catch { status("Жишээ ачаалсангүй", "error"); }
});
$("new-referral").addEventListener("click", () => startReferral());
$("extract").addEventListener("click", extract);
$("reset").addEventListener("click", () => startReferral());
for (const id of ["reviewed", "acknowledged"])
  $(id).addEventListener("change", () => {
    if (state.approved) {
      clearPrintHeader();
      invalidate(state);
      document.body.classList.remove("approved");
      $("print-view").replaceChildren();
      $("print").disabled = true;
      $("approval-status").textContent = "Баталгаажаагүй";
    }
    updateApproval();
  });
$("approve").addEventListener("click", () => {
  if (
    !canApprove(state, {
      busy,
      reviewed: $("reviewed").checked,
      acknowledged: $("acknowledged").checked,
    })
  )
    return;
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
  const hosted = config.deployment_mode === "hosted";
  $("deployment-location").textContent = hosted
    ? "Демо сервер дээр"
    : "Энэ компьютер дээр";
  $("deployment-notice").textContent = hosted
    ? "Серверийн демо: таны илгээсэн текстийг демо сервер дээр боловсруулна. Зөвхөн зохиомол өгөгдөл ашиглана уу."
    : "Дотоод горим: моделийн боловсруулалт энэ компьютер дээр ажиллана.";
  $("schema-version").textContent = config.version;
  $("example").textContent = "DEV-002 зохиомол жишээ";
  renderFields();
  status("Зохиомол тэмдэглэл оруулах эсвэл жишээг нээнэ үү.");
} catch {
  status("Тохиргоо ачаалсангүй. Програмыг дахин ажиллуулна уу.", "error");
  for (const id of ["example", "new-referral", "reset", "note"])
    $(id).disabled = true;
}
