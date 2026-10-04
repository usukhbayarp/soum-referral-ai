import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createState,editField} from '../app/static/state.mjs';
import {printSections,printWarnings,manualLegend} from '../app/static/print.mjs';
const config=JSON.parse(fs.readFileSync(new URL('../config/referral.v0.6.json',import.meta.url)));
test('printed manual content has explicit attribution and never duplicates old/new evidence',()=>{
 const state=createState(config);editField(state,'allergies','Doctor corrected text');
 Object.assign(state.fields.allergies,{original:'OLD EXTRACT',evidence:[{id:13,text:'OLD EXTRACT'}],suggestion:{text:'NEW EXTRACT'}});
 editField(state,'identity_source','SOURCE SUGGESTION ONLY');
 const result=printSections(state,config),encoded=JSON.stringify(result);
 const allergy=result.flatMap(s=>s.fields).find(f=>f.id==='allergies');
 assert.equal(allergy.manual,true);assert.equal(allergy.text,'Doctor corrected text');
 for(const text of ['OLD EXTRACT','NEW EXTRACT','SOURCE SUGGESTION ONLY'])assert(!encoded.includes(text));
 assert(manualLegend.includes('энэ агуулгыг эхээр баталгаажсан гэж үзэхгүй'));
});
test('print retains explicit uncertainty, clinical values, missing notes and blank signature',()=>{
 const state=createState(config);editField(state,'regular_medication','Usual medicine; today not asked');
 editField(state,'review_notes','Phone unavailable');state.fields.examination.meaning='not_assessed';
 const fields=printSections(state,config).flatMap(s=>s.fields);
 assert(fields.some(f=>f.id==='regular_medication'&&f.text.includes('not asked')));
 assert(fields.some(f=>f.id==='examination'&&f.meaning));
 assert(fields.some(f=>f.id==='signature'&&f.text==='Бөглөөгүй'));
 assert(printWarnings(state,config).some(w=>w.includes('Утас')));
});
test('treatment rows preserve entered frequency even when single, and explicit no-treatment conflicts',()=>{
 const state=createState(config);editField(state,'treatment_rows',JSON.stringify([{kind:'medication',schedule:'single',name:'Medicine',dose:'500 mg',frequency:'conflicting repeated entry',route:'oral',time:'10:15',response:'later report'}]));
 editField(state,'treatment_status','Эмчилгээ хийгээгүй гэж эхэд тэмдэглэсэн');
 const fields=printSections(state,config).flatMap(s=>s.fields);
 assert(fields.find(f=>f.id==='treatment_rows').text.includes('conflicting repeated entry'));
 assert(fields.some(f=>f.id==='treatment_status'));
 assert(printWarnings(state,config).some(w=>w.includes('зөрүүтэй')));
 editField(state,'treatment_status','Зөвхөн ажилбар хийсэн');
 assert(printSections(state,config).flatMap(s=>s.fields).some(f=>f.id==='treatment_status'));
});
test('pending clinician status cannot disappear behind an existing contradictory narrative',()=>{
 const state=createState(config);editField(state,'pending_results','No pending results in original note');
 editField(state,'pending_status','Байгаа');
 const fields=printSections(state,config).flatMap(s=>s.fields);
 assert(fields.some(f=>f.id==='pending_results'));
 assert(fields.some(f=>f.id==='pending_status'&&f.text==='Байгаа'&&f.manual));
 assert(printWarnings(state,config).some(w=>w.includes('Хүлээгдэж буй хариуг хянах хүн')));
});
test('multiline treatment response stays in its own row without truncation',()=>{
 const state=createState(config);
 editField(state,'treatment_rows',JSON.stringify([{kind:'procedure',name:'Procedure',time:'10:00',response:'First paragraph\n\nSecond paragraph'}]));
 const row=printSections(state,config).flatMap(s=>s.fields).find(f=>f.id==='treatment_rows');
 assert.equal(row.rows.length,1);assert(row.rows[0].includes('First paragraph\n\nSecond paragraph'));
});
