import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {createState,sourceChanged,beginRequest,editField,newReferral,canApprove} from '../app/static/state.mjs';
import {receivePicker,decidePicker} from '../app/static/treatment-picker.mjs';
import {printSections,manualLegend} from '../app/static/print.mjs';
const config=JSON.parse(fs.readFileSync('config/referral.v0.8.json'));
const note='Эмчилгээ хийгээгүй.',unit={id:1,start:0,end:Array.from(note).length,text:note};
function ready(){const s=createState(config);sourceChanged(s,note,config);receivePicker(s,beginRequest(s),{units:[unit],suggestions:[{unit,context:[]}]});return s;}
test('accept exact narrative once; rows stay empty; edited attribution and print remain honest',()=>{
 const s=ready();s.approved=true;assert(decidePicker(s,1,true));assert(!s.approved);assert.equal(s.fields.treatment_narrative.text,note);assert.equal(s.fields.treatment_rows.text,'');assert(!decidePicker(s,1,true));
 receivePicker(s,beginRequest(s),{units:[unit],suggestions:[{unit,context:[]}]});assert(!decidePicker(s,1,true));
 editField(s,'treatment_narrative','Эмчийн засвар');assert.equal(s.fields.treatment_narrative.original,note);
 const f=printSections(s,config).flatMap(g=>g.fields).find(f=>f.id==='treatment_narrative');assert(f.manual&&!f.compact);assert.equal(f.text,'Эмчийн засвар');assert(manualLegend.includes('баталгаажсан гэж үзэхгүй'));
});
test('rejection and empty selection never mean explicit absence',()=>{
 const s=ready();decidePicker(s,1,false);assert.equal(s.fields.treatment_narrative.text,'');receivePicker(s,beginRequest(s),{units:[unit],suggestions:[]});assert.equal(s.fields.treatment_narrative.meaning,'unreviewed');assert.equal(s.fields.treatment_narrative.text,'');
});
test('source edits preserve accepted work but demand reconciliation; reset and stale isolation',()=>{
 const s=ready();decidePicker(s,1,true);const ticket=beginRequest(s);sourceChanged(s,note+' Өөр эх.',config);assert.equal(s.treatmentPicker,null);assert(s.fields.treatment_narrative.needsReconciliation);assert(!canApprove(s,{reviewed:true,acknowledged:true}));assert(!receivePicker(s,ticket,{units:[],suggestions:[]}));
 const old=beginRequest(s);newReferral(s,config);assert(!receivePicker(s,old,{units:[],suggestions:[]}));assert.equal(s.fields.treatment_narrative.text,'');assert.equal(s.treatmentPicker,null);
});
test('manual edits while waiting reject stale response; invalid client evidence rejected',()=>{
 const s=ready(),t=beginRequest(s);editField(s,'patient','DEMO');assert(!receivePicker(s,t,{units:[],suggestions:[]}));
 assert.throws(()=>receivePicker(s,beginRequest(s),{units:[],suggestions:[{unit:{...unit,text:'invented'},context:[]}]}));
});
test('placement has one regular entry, manual nested home use, no automatic copying',()=>{
 const home=config.fields.find(f=>f.id==='home_medication');assert(home.manual&&home.parent_id==='medical_history');assert.equal(config.fields.filter(f=>f.id==='regular_medication').length,1);
 const s=createState(config);editField(s,'regular_medication','Лозартан 50 мг гэртээ 07:10-д уусан гэж хэлэв.');assert.equal(s.fields.home_medication.text,'');assert.equal(s.fields.treatment_rows.text,'');
 assert.equal(config.proposal_mapping.medical_history,'past_history_source');
});
