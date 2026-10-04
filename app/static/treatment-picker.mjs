import {isCurrent, editField} from './state.mjs';
export function receivePicker(state,ticket,result) {
  if(!isCurrent(state,ticket)) return false;
  const ids=new Set();
  for(const s of result.suggestions) {
    const u=s.unit;
    if(!Number.isInteger(u.id)||ids.has(u.id)||Array.from(state.note).slice(u.start,u.end).join('')!==u.text) throw Error('Invalid source evidence');
    ids.add(u.id);
  }
  state.treatmentPicker={caseId:state.caseId,note:state.note,provenance:{model:result.model,model_digest:result.model_digest,prompt_version:result.prompt_version,contract_version:result.contract_version,settings:result.settings},items:result.suggestions.map(s=>({...s,decision:'pending'}))};
  state.units=result.units;
  return true;
}
export function decidePicker(state,id,accept) {
  const picker=state.treatmentPicker;
  if(!picker||picker.caseId!==state.caseId||picker.note!==state.note)return false;
  const item=picker.items.find(s=>s.unit.id===id);
  if(!item||item.decision!=='pending')return false;
  if(!accept){item.decision='rejected';return true;}
  const f=state.fields.treatment_narrative,u=item.unit;
  if((f.acceptedSources||[]).some(e=>e.note===state.note&&e.id===id)||f.text.includes(u.text)){item.decision='duplicate';return false;}
  editField(state,'treatment_narrative',[f.text,u.text].filter(Boolean).join('\n'));
  f.originKind='accepted_source';f.original=[f.original,u.text].filter(Boolean).join('\n');
  // Original snapshots remain accessible after edits; never attest edited text.
  f.evidence.push({...u});f.acceptedSources=[...(f.acceptedSources||[]),{...u,note:state.note,provenance:picker.provenance}];
  item.decision='accepted';return true;
}
