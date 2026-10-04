// Review prompts only, not transfer eligibility or clinical validation.
export const meanings = {
  unreviewed: "Утгыг эмч хянаагүй",
  documented: "Эхэд тэмдэглэсэн",
  explicit_absence: "Байхгүй гэж эхэд тэмдэглэсэн",
  not_assessed: "Үнэлээгүй / асуугаагүй",
  not_documented: "Эхэд бичээгүй",
  uncertain: "Тодорхойгүй / зөрүүтэй",
};
export const rowColumns = [
  ["name", "Эм / ажилбарын нэр"], ["dose", "Тун, нэгж"],
  ["frequency", "Давтамж (давтан бол)"], ["route", "Хэрэглэх зам"],
  ["time", "Хийсэн / сүүлд өгсөн огноо, цаг"], ["response", "Баримтжуулсан үр дүн / урвал"],
];
export function rowsOf(state) {
  try { const rows = JSON.parse(state.fields.treatment_rows?.text || "[]"); return Array.isArray(rows) ? rows : []; } catch { return []; }
}
export function completeness(state, config) {
  const text = (id) => state.fields[id]?.text.trim() || "";
  const v07 = ["experimental-0.7", "experimental-0.8"].includes(config.version);
  const warnings = [];
  const warn = (id, message) => warnings.push({id, message});
  const labels = Object.fromEntries(config.fields.map(f => [f.id,f.label]));
  const need = (id) => { if (!text(id)) warn(id, `${labels[id]} — дутуу / эмч хянана`); };
  for (const id of ["patient", "sending_facility", "sending_clinician", "phone", "receiving", "referral", "history", "diagnosis", "current_condition", "current_time", "allergies"]) need(id);
  if (!v07) need("requested_action");
  if (!text("patient") && text("identifier")) {
    const i = warnings.findIndex(w=>w.id==="patient"); if(i>=0) warnings.splice(i,1);
  }
  if (!["Яаралтай", "Төлөвлөгөөт"].includes(text("referral_type"))) warn("referral_type", "Эмчийн баримтжуулсан шилжүүлгийн төрөл — хянана / тодруулна");
  for (const [id, field] of Object.entries(state.fields)) {
    field.review_flags?.forEach(message=>warn(id, `${labels[id]} — ${message}`));
    if (field.status === "failed") warn(id, `${labels[id]} — ялгалтын алдаа; мэдээлэлгүй гэсэн үг биш`);
    if (field.meaning === "uncertain" || field.meaning === "not_assessed") warn(id, `${labels[id]} — ${meanings[field.meaning]}`);
  }
  const treatment = text("treatment_status"), rows = rowsOf(state);
  if (!["Эм өгсөн", "Зөвхөн ажилбар хийсэн", "Эмчилгээ хийгээгүй гэж эхэд тэмдэглэсэн"].includes(treatment)) warn("treatment_status", "Бодитоор эмчилгээ хийсэн эсэхийг эмч тодруулна");
  if (treatment === "Эмчилгээ хийгээгүй гэж эхэд тэмдэглэсэн" && rows.some(r=>Object.values(r).some(Boolean))) warn("treatment_rows", "Эмчилгээ хийгээгүй гэсэн сонголт ба бөглөсөн мөр зөрүүтэй — хянана");
  if (["Эм өгсөн", "Зөвхөн ажилбар хийсэн"].includes(treatment) && !rows.length) warn("treatment_rows", "Хийсэн эмчилгээ / ажилбарын мөр оруулж эхтэй тулгана");
  rows.forEach((r,i)=> {
    if (!r.kind) warn("treatment_rows", `${i+1}-р мөр: эм эсвэл ажилбар эсэхийг тодруулна`);
    const required = r.kind === "procedure" ? ["name","time"] : ["name","dose","route","time"];
    required.forEach(k=>{ if (!(r[k]||"").trim()) warn("treatment_rows", `${i+1}-р мөр: ${rowColumns.find(c=>c[0]===k)[1]} дутуу`); });
    if (r.kind !== "procedure" && !r.schedule) warn("treatment_rows", `${i+1}-р мөр: нэг удаа / давтан эсэхийг эмч тодруулна`);
    if (r.schedule === "repeated" && !(r.frequency||"").trim()) warn("treatment_rows", `${i+1}-р мөр: давтан эмчилгээний давтамж дутуу`);
  });
  for (const prefix of ["initial","current"]) {
    const used=text(prefix+"_oxygen_used");
    if (v07) {
      if (used === "Дэмжлэгтэй") {
        if (!text(prefix+"_oxygen_device") && !text(prefix+"_oxygen_flow") && !text(prefix+"_fio2")) warn(prefix+"_oxygen_used", "Хүчилтөрөгчийн дэмжлэгийн баримтжуулсан дэлгэрэнгүйг хянана");
      } else if (used !== "Өрөөний агаарт") warn(prefix+"_oxygen_used", "Хүчилтөрөгчийн дэмжлэг эхэд бичээгүй / тодруулаагүй — өрөөний агаарт гэж дүгнээгүй");
      if (used === "Өрөөний агаарт" && ["_oxygen_device","_oxygen_flow","_fio2"].some(k=>text(prefix+k))) warn(prefix+"_oxygen_used", "Өрөөний агаарт гэсэн сонголт ба дэмжлэгийн дэлгэрэнгүй зөрүүтэй байж болно — хянана");
    } else if (used === "Хэрэглэсэн") { need(prefix+"_oxygen_device"); need(prefix+"_oxygen_flow"); }
    else if (used !== "Хэрэглээгүй") warn(prefix+"_oxygen_used", "Хүчилтөрөгчийн хэрэглээг эмч хянана; эхийн саналаас автоматаар дүгнээгүй");
  }
  const inv=text("investigation_review");
  if (!inv || inv.includes("дутуу") || inv.startsWith("Тодорхойгүй")) warn("investigation_review", "Шинжилгээ: хийгдсэн / хийгдээгүй / чанарын / тоон / хүлээгдэж буйг эмч ялгаж, хамаарах огноо, хариу, нэгжийг шалгана");
  if (text("pending_status") === "Байгаа") { need("pending_owner"); need("pending_method"); }
  else if(text("pending_status") !== "Байхгүй гэж эхэд тэмдэглэсэн") warn("pending_status", "Хүлээгдэж буй хариу байгаа эсэхийг эмч хянана");
  if (v07) {
    if (text("transport_needed") === "Зохион байгуулсан") { need("transport"); need("transport_staff"); }
    if (text("transport_needed") === "Тодорхойгүй") warn("transport_needed", "Тээвэрлэлтийн зохион байгуулалт тодорхойгүй — хянана");
    if (text("transport_needed") === "Хамаарахгүй" && (text("transport") || text("transport_staff"))) warn("transport_needed", "Тээвэрлэлтийн сонголт ба дэлгэрэнгүйг тулгаж хянана");
    // Optional agreement stays visible if entered; absence is not a universal warning.
    if (text("agreement_needed") === "Шаардлагатай") need("agreement");
    if (text("agreement_needed") === "Тодорхойгүй") warn("agreement_needed", "Урьдчилан тохиролцох шаардлага тодорхойгүй — хянана");
  } else for(const [trigger, detail] of [["transport_needed","transport"],["agreement_needed","agreement"]]) {
    if(text(trigger)==="Шаардлагатай") need(detail);
    else if(text(trigger)!=="Хамаарахгүй") warn(trigger, `${labels[trigger]} — эмч тодруулна`);
  }
  return warnings;
}
