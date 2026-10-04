import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createState,editField,sourceChanged,canApprove,newReferral,beginRequest,acceptResponse} from '../app/static/state.mjs';
import {completeness} from '../app/static/completeness.mjs';
import {printSections} from '../app/static/print.mjs';
const c=JSON.parse(fs.readFileSync(new URL('../config/referral.v0.7.json',import.meta.url)));
const warningIds=s=>completeness(s,c).map(w=>w.id);
const printed=s=>printSections(s,c).flatMap(s=>s.fields);
test('form 0.7 maps exactly 19 unchanged extraction categories; new fields manual and optional',()=>{
 const old=JSON.parse(fs.readFileSync(new URL('../config/referral.v0.6.json',import.meta.url)));
 assert.equal(c.sections.length,6);assert.equal(c.extraction_schema_version,old.version);
 assert.deepEqual(Object.keys(c.proposal_mapping).sort(),old.fields.filter(f=>!f.manual).map(f=>f.id).sort());
 assert.equal(Object.keys(c.proposal_mapping).length,19);
 for(const id of ['birth_date','receiving_phone','initial_fio2','current_fio2','transport_staff'])assert(c.fields.find(f=>f.id===id).manual);
 assert(old.fields.every(f=>c.fields.some(n=>n.id===f.id))); // no removed data keys
});
test('requested action optional but populated print retained with honest manual attribution',()=>{
 const s=createState(c);assert(!warningIds(s).includes('requested_action'));assert(!printed(s).some(f=>f.id==='requested_action'));
 editField(s,'requested_action','Эмчийн нэмэлт');const p=printed(s).find(f=>f.id==='requested_action');assert.equal(p.text,'Эмчийн нэмэлт');assert(p.manual);
 assert.equal(s.fields.referral_type.text,'');assert.deepEqual(c.fields.find(f=>f.id==='referral_type').options,['Яаралтай','Төлөвлөгөөт','Тодруулаагүй']);
});
test('oxygen units preserved; neither room air nor FiO2 inferred, no universal flow plus FiO2 requirement',()=>{
 const s=createState(c);editField(s,'current_spo2','94 %');assert.equal(s.fields.current_oxygen_used.text,'');assert.equal(s.fields.current_fio2.text,'');
 editField(s,'current_oxygen_used','Дэмжлэгтэй');editField(s,'current_fio2','0.28');assert(!warningIds(s).some(id=>['current_oxygen_flow','current_oxygen_device'].includes(id)));
 assert.equal(printed(s).find(f=>f.id==='current_fio2').text,'0.28');
 editField(s,'current_oxygen_used','Өрөөний агаарт');assert(warningIds(s).includes('current_oxygen_used'));
});
test('organized transport alone requires vehicle and staff; agreement optional; pending owner only explicit confirmation',()=>{
 const s=createState(c);editField(s,'referral_type','Төлөвлөгөөт');assert(!warningIds(s).some(id=>['transport','transport_staff','agreement','agreement_needed','pending_owner','pending_method'].includes(id)));
 editField(s,'pending_results','Хариу хүлээгдэж байж болзошгүй');assert(!warningIds(s).includes('pending_owner'));
 editField(s,'pending_status','Байгаа');assert(warningIds(s).includes('pending_owner'));assert(warningIds(s).includes('pending_method'));
 editField(s,'transport_needed','Зохион байгуулсан');assert(warningIds(s).includes('transport'));assert(warningIds(s).includes('transport_staff'));
 editField(s,'plan','Эхэд бичсэн төлөвлөгөө');assert(printed(s).some(f=>f.id==='plan'));assert(printed(s).some(f=>f.id==='pending_results'));
});
test('new manual values participate in reconciliation, approval invalidation and stale-case isolation',()=>{
 const s=createState(c);editField(s,'birth_date','зохиомол');s.approved=true;sourceChanged(s,'өөр эх',c);assert.equal(s.fields.birth_date.text,'зохиомол');assert(!s.approved);assert(s.fields.birth_date.needsReconciliation);assert(!canApprove(s,{reviewed:true,acknowledged:true}));const t=beginRequest(s);newReferral(s,c);assert.equal(s.fields.birth_date.text,'');assert(!acceptResponse(s,t,{fields:{},units:[]}));
});
