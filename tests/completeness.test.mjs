import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { completeness } from '../app/static/completeness.mjs';
import { createState, editField, editMeaning, sourceChanged, reconcileField, canApprove, beginRequest, acceptResponse, newReferral, printAttribution } from '../app/static/state.mjs';
const config=JSON.parse(fs.readFileSync(new URL('../config/referral.v0.6.json',import.meta.url)));
const warnings=s=>completeness(s,config);
const ids=s=>warnings(s).map(w=>w.id);
test('demo ID suffices, real ID and codes are not mandatory',()=>{
 const s=createState(config);editField(s,'patient','DEV-002');
 assert(!ids(s).includes('patient'));assert(!ids(s).includes('identifier'));assert(!ids(s).includes('diagnosis_code'));assert(ids(s).includes('phone'));
});
test('no pending results suppresses owner/method, pending requires both, unknown asks confirmation',()=>{
 const s=createState(config);assert(ids(s).includes('pending_status'));assert(!ids(s).includes('pending_owner'));
 editField(s,'pending_status','Байхгүй гэж эхэд тэмдэглэсэн');assert(!ids(s).some(x=>['pending_status','pending_owner','pending_method'].includes(x)));
 editField(s,'pending_status','Байгаа');assert(ids(s).includes('pending_owner'));assert(ids(s).includes('pending_method'));
});
test('medication details required, frequency only repeated, response never fabricated/required',()=>{
 const s=createState(config);editField(s,'treatment_status','Эм өгсөн');editField(s,'treatment_rows',JSON.stringify([{kind:'medication',schedule:'single',name:'Парацетамол',dose:'500 мг',route:'Амаар',time:'10:15'}]));
 assert(!ids(s).includes('treatment_rows'));
 editField(s,'treatment_rows',JSON.stringify([{kind:'medication',schedule:'repeated',name:'Парацетамол',dose:'500 мг',route:'Амаар',time:'10:15'}]));assert(warnings(s).some(w=>w.message.includes('давтамж дутуу')));
 editField(s,'treatment_rows',JSON.stringify([{kind:'medication',schedule:'single',name:'Парацетамол'}]));assert.equal(warnings(s).filter(w=>w.id==='treatment_rows').length,3);
});
test('qualitative/not performed investigation needs no numeric result; oxygen and transport conditional',()=>{
 const s=createState(config);editField(s,'investigation_review','Чанарын / хийгээгүй / хүлээгдэж буй шинжилгээ — тоон нэгж шаардахгүй');assert(!ids(s).includes('investigation_review'));
 editField(s,'current_oxygen_used','Хэрэглээгүй');assert(!ids(s).includes('current_oxygen_device'));
 editField(s,'current_oxygen_used','Хэрэглэсэн');assert(ids(s).includes('current_oxygen_device'));assert(ids(s).includes('current_oxygen_flow'));
 editField(s,'transport_needed','Хамаарахгүй');assert(!ids(s).includes('transport'));
});
test('absence/not assessed/missing/failure distinct; missing can be acknowledged, source reconciliation cannot',()=>{
 const s=createState(config);editField(s,'patient','DEV-002');editMeaning(s,'allergies','explicit_absence');editMeaning(s,'examination','not_assessed');
 assert.equal(s.fields.allergies.meaning,'explicit_absence');assert.equal(s.fields.examination.meaning,'not_assessed');assert.equal(s.fields.phone.status,'manual_pending');s.fields.history.status='failed';assert(warnings(s).some(w=>w.id==='history'&&w.message.includes('алдаа')));
 assert(!canApprove(s,{reviewed:true}));assert(canApprove(s,{reviewed:true,acknowledged:true}));
 s.approved=true;sourceChanged(s,'new source',config);assert(!s.approved);assert(!canApprove(s,{reviewed:true,acknowledged:true}));assert(s.fields.allergies.needsReconciliation);
 Object.keys(s.fields).forEach(id=>reconcileField(s,id));assert(canApprove(s,{reviewed:true,acknowledged:true}));assert(!canApprove(s,{busy:true,reviewed:true,acknowledged:true}));
});
test('treatment rows retain manual attribution and obey case reset/late response isolation',()=>{
 const s=createState(config);editField(s,'treatment_rows',JSON.stringify([{name:'A'}]));const t=beginRequest(s);assert(printAttribution(s.fields.treatment_rows).includes('баталгаажсан гэж үзэхгүй'));
 newReferral(s,config);assert.equal(s.fields.treatment_rows.text,'');assert(!acceptResponse(s,t,{fields:{},units:[]}));
});
