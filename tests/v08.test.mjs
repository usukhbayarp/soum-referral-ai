import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createState, editField, sourceChanged, beginRequest, acceptResponse, reconcileField, newReferral, canApprove} from '../app/static/state.mjs';
import {printSections} from '../app/static/print.mjs';
const c=JSON.parse(fs.readFileSync(new URL('../config/referral.v0.8.json',import.meta.url)));
test('v08 keeps extraction contract and makes chronic history manual only',()=>{
 const old=JSON.parse(fs.readFileSync(new URL('../config/referral.v0.7.json',import.meta.url)));
 assert.deepEqual(c.proposal_mapping,old.proposal_mapping);
 assert.equal(c.extraction_schema_version,'experimental-0.6');
 assert.equal(c.fields.find(f=>f.id==='medical_history').label,'Одоогийн өвчний түүх');
 assert(c.fields.find(f=>f.id==='chronic_history').manual);
 assert(!c.fields.some(f=>f.label==='Өгөөгүй эм'));
});
test('old history proposals require category review and never fill chronic history',()=>{
 const s=createState(c),t=beginRequest(s);
 acceptResponse(s,t,{units:[],fields:{medical_history:{status:'extracted',text:'Эхийн түүх',evidence:[]}}},c);
 assert(s.fields.medical_history.needsReconciliation);assert.equal(s.fields.chronic_history.text,'');
 assert(!canApprove(s,{reviewed:true,acknowledged:true}));
 reconcileField(s,'medical_history');assert(canApprove(s,{reviewed:true,acknowledged:true}));
});
test('manual chronic history survives same-case edits, requires reconciliation, prints honestly, resets across cases',()=>{
 const s=createState(c);editField(s,'chronic_history','Зохиомол урт түүх Ө ү');editField(s,'medical_history','Диклофенак өгөөгүй. Гэртээ уусан эм.');
 sourceChanged(s,'Өөр эх',c);assert.equal(s.fields.chronic_history.text,'Зохиомол урт түүх Ө ү');assert(s.fields.chronic_history.needsReconciliation);
 const p=printSections(s,c).flatMap(g=>g.fields);const h=p.find(f=>f.id==='chronic_history');assert(h.manual && !h.compact);assert(p.find(f=>f.id==='medical_history').text.includes('өгөөгүй'));
 const t=beginRequest(s);newReferral(s,c);assert.equal(s.fields.chronic_history.text,'');assert(!acceptResponse(s,t,{units:[],fields:{}},c));
});
