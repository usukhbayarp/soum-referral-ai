import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createState, editField, sourceChanged, beginRequest, acceptResponse, reconcileField, newReferral, canApprove} from '../app/static/state.mjs';
import {printSections} from '../app/static/print.mjs';
const c=JSON.parse(fs.readFileSync(new URL('../config/referral.v0.8.json',import.meta.url)));
test('v08 keeps extraction contract and makes chronic history manual only',()=>{
 const old=JSON.parse(fs.readFileSync(new URL('../config/referral.v0.7.json',import.meta.url)));
 assert.deepEqual(Object.keys(c.proposal_mapping),Object.keys(old.proposal_mapping));
 assert.equal(c.proposal_mapping.medical_history,"past_history_source");
 assert(c.fields.find(f=>f.id==="medical_history").manual);
 assert.equal(c.extraction_schema_version,'experimental-0.6');
 assert.equal(c.fields.find(f=>f.id==='medical_history').label,'Одоогийн өвчний түүх');
 assert(c.fields.find(f=>f.id==='chronic_history').manual);
 assert(!c.fields.some(f=>f.label==='Өгөөгүй эм'));
});
test('legacy past-history proposals never populate current or chronic history or print',()=>{
 const s=createState(c),t=beginRequest(s);
 acceptResponse(s,t,{units:[],fields:{medical_history:{status:'extracted',text:'Өмнөх өвчний түүх',evidence:[]}}},c);
 assert.equal(s.fields.medical_history.text,'');assert.equal(s.fields.chronic_history.text,'');
 assert.equal(s.fields.past_history_source.text,'Өмнөх өвчний түүх');
 assert(!printSections(s,c).flatMap(g=>g.fields).some(f=>f.id==='past_history_source'));
 editField(s,'medical_history','Эмчийн одоогийн түүх');editField(s,'chronic_history','Эмчийн архаг түүх');
 acceptResponse(s,beginRequest(s),{units:[],fields:{medical_history:{status:'extracted',text:'Шинэ санал',evidence:[]}}},c);
 assert.equal(s.fields.medical_history.text,'Эмчийн одоогийн түүх');assert.equal(s.fields.chronic_history.text,'Эмчийн архаг түүх');
 assert.equal(s.fields.past_history_source.text,'Шинэ санал');
});
test('manual chronic history survives same-case edits, requires reconciliation, prints honestly, resets across cases',()=>{
 const s=createState(c);editField(s,'chronic_history','Зохиомол урт түүх Ө ү');editField(s,'medical_history','Диклофенак өгөөгүй. Гэртээ уусан эм.');
 sourceChanged(s,'Өөр эх',c);assert.equal(s.fields.chronic_history.text,'Зохиомол урт түүх Ө ү');assert(s.fields.chronic_history.needsReconciliation);
 const p=printSections(s,c).flatMap(g=>g.fields);const h=p.find(f=>f.id==='chronic_history');assert(h.manual && !h.compact);assert(p.find(f=>f.id==='medical_history').text.includes('өгөөгүй'));assert(!p.find(f=>f.id==='medical_history').compact);
 const t=beginRequest(s);newReferral(s,c);assert.equal(s.fields.chronic_history.text,'');assert(!acceptResponse(s,t,{units:[],fields:{}},c));
});
