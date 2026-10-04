// Export clinical form values, not the source-suggestion/debug interface.
import { completeness, meanings, rowsOf, rowColumns } from './completeness.mjs';

export const manualLegend = '* Эмч оруулсан / зассан: энэ агуулгыг эхээр баталгаажсан гэж үзэхгүй. Анхны ялгалтын эх болон шинэ санал нь хяналтын дэлгэцэд үлдэнэ.';

function treatmentText(row, index) {
  const kind = row.kind === 'procedure' ? 'Ажилбар' : row.kind === 'medication' ? 'Эм' : 'Төрөл тодорхойгүй';
  const schedule = row.schedule === 'single' ? 'Нэг удаа' : row.schedule === 'repeated' ? 'Давтан' : 'Давтамж тодорхойгүй';
  const details = rowColumns
    .filter(([key]) => row[key] || (key !== 'frequency' && row.kind !== 'procedure'))
    .map(([key, label]) => `${label}: ${row[key] || 'Эмч нөхөөгүй'}`);
  return `${index + 1}. ${kind} • ${schedule}\n${details.join('; ')}`;
}

export function printSections(state, config) {
  const rows = rowsOf(state);
  const skip = new Set(['investigation_review']);
  // A redundant row-kind confirmation need not print. Explicit no-treatment,
  // unknown states and pending status remain, including potential conflicts.
  const confirmedKind = { 'Эм өгсөн': 'medication', 'Зөвхөн ажилбар хийсэн': 'procedure' }[state.fields.treatment_status?.text];
  if (rows.length && confirmedKind && rows.every(row => row.kind === confirmedKind)) {
    skip.add('treatment_status');
  }
  const labels = {
    initial_oxygen_used: 'Анхны үзлэг — хүчилтөрөгч',
    current_oxygen_used: 'Одоогийн үзлэг — хүчилтөрөгч',
    treatment_status: 'Эмчилгээ',
    pending_status: 'Хүлээгдэж буй хариу — эмчийн тэмдэглэл',
    transport_needed: 'Тээвэрлэлтийн шаардлага',
    agreement_needed: 'Урьдчилан тохиролцох шаардлага',
  };
  return config.sections.map(section => ({
    ...section,
    fields: config.fields
      .filter(f => f.section === section.id && f.kind !== 'source_suggestion' && !skip.has(f.id))
      .flatMap(f => {
        const value = state.fields[f.id];
        const meaning = value.meaning && !['unreviewed', 'documented'].includes(value.meaning)
          ? meanings[value.meaning] : '';
        const rowTexts = f.kind === 'treatment_rows' ? rows.map(treatmentText) : null;
        const text = rowTexts ? rowTexts.join('\n\n') : value.text.trim();
        if (!text && !meaning && !['signature', 'reviewer', 'review_time', 'stamp'].includes(f.id)) return [];
        return [{
          id: f.id,
          label: labels[f.id] || f.label,
          text: text || (meaning ? '' : 'Бөглөөгүй'),
          meaning,
          manual: value.status === 'manual',
          rows: rowTexts,
          compact: f.manual && !['treatment_rows', 'review_notes', 'transport', 'agreement'].includes(f.id),
        }];
      }),
  }));
}

export function printWarnings(state, config) {
  const suggestions = new Set(config.fields.filter(f => f.kind === 'source_suggestion').map(f => f.id));
  return [...new Set(completeness(state, config).filter(w => !suggestions.has(w.id)).map(w => w.message))];
}
