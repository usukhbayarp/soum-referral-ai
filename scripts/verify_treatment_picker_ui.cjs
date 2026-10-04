/* Fictional manually completed print mechanics fixture. Never an extraction result. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(__dirname,'..'), out=path.join(root,'.runtime/treatment-picker-review');fs.mkdirSync(out,{recursive:true});
 const fixture=JSON.parse(fs.readFileSync(path.join(root,'evaluation/recovery-v06/normal-print-fixture.json')));
 fixture.rows=fixture.rows.map(row=>({...row,response:(row.response||'').replace(' Энэ үзлэгээр өөр эмчилгээ хийгээгүй.','')})); // Move this exact negative to narrative in this new QA fixture only.
 const note=fs.readFileSync(path.join(root,'evaluation/dev002-v06/source-note.txt'),'utf8').trimEnd();
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 const results=[];
 try {for(const mode of ['normal']) {
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/*', async route=>{
   const u=new URL(route.request().url());if(u.hostname!=='127.0.0.1')return route.abort();
   if(u.pathname==='/api/treatment-suggestions') {const input=route.request().postDataJSON();const result=JSON.parse(fs.readFileSync(path.join(root,'evaluation/treatment-picker-v1/review-display.json')))[0].result;return route.fulfill({json:{...result,request_id:input.request_id}});}
   if(u.pathname==='/api/extract')throw Error('Print test must not run inference');
   return route.continue();
  });
  await page.goto(process.env.REFERRAL_URL || 'http://127.0.0.1:8001');await page.locator('#field-patient').waitFor();
  await page.locator('#note').fill(note);
  assert.equal(await page.locator('#schema-version').textContent(),'experimental-0.8');
  assert.equal(await page.locator('#field-chronic_history').inputValue(),'');
  fixture.values.chronic_history=fixture.values.medical_history;fixture.values.medical_history='';
  for(const [id,value] of Object.entries(fixture.values)) {
   const e=page.locator('#field-'+id); // Preserve existing history text; no automatic chronic migration.
   if(await e.evaluate(e=>e.tagName)==='SELECT') await e.selectOption(value === "Хэрэглээгүй" ? "Өрөөний агаарт" : value);else await e.fill(value);
  }
  const names={name:'Эм / ажилбарын нэр',dose:'Тун, нэгж',frequency:'Давтамж (давтан бол)',route:'Хэрэглэх зам',time:'Хийсэн / сүүлд өгсөн огноо, цаг',response:'Баримтжуулсан үр дүн / урвал'};
  for(const [i,row] of fixture.rows.entries()) {
   await page.getByRole('button',{name:'Эмчилгээний мөр нэмэх',exact:true}).click();
   await page.getByRole('combobox',{name:`${i+1} Төрөл`,exact:true}).selectOption(row.kind);
   await page.getByRole('combobox',{name:`${i+1} Хийсэн давтамж`,exact:true}).selectOption(row.schedule);
   for(const [key,label] of Object.entries(names)) if(row[key])await page.getByRole('textbox',{name:`${i+1} ${label}`,exact:true}).fill(row[key]);
  }
  if(mode==='long') {
   const long=Array.from({length:35},(_,i)=>`Архаг түүхийн хэвлэлийн зохиомол мөр ${i+1}: Ө ө Ү ү. Урт талбарын төгсгөлийг таслахгүй.`).join('\n');
   await page.locator('#field-chronic_history').fill(long);
   assert(await page.locator('#field-chronic_history').evaluate(e=>e.scrollHeight<=e.clientHeight+2));
  }
  assert(await page.locator('#treatment-picker').isVisible());
  assert(await page.locator('#section-medical_history #field-home_medication').count()===1);
  assert.equal(await page.locator('#field-home_medication').inputValue(),'');
  await page.locator('#find-treatment').click();await page.getByRole('button',{name:'Татгалзах',exact:true}).waitFor();
  assert((await page.locator('#treatment-suggestions').textContent()).includes('500 мг'));
  await page.getByRole('button',{name:'Татгалзах',exact:true}).click();assert.equal(await page.locator('#field-treatment_narrative').inputValue(),'');
  await page.locator('#find-treatment').click();await page.getByRole('button',{name:'Хянаад хүүрнэлд оруулах',exact:true}).waitFor();
  await page.getByRole('button',{name:'Хянаад хүүрнэлд оруулах',exact:true}).click();
  assert.equal(await page.locator('#field-treatment_narrative').inputValue(),'Энэ үзлэгээр өөр эмчилгээ хийгээгүй.');
  await page.locator('#field-treatment_narrative').fill('Тэмдэглэл: Энэ үзлэгээр өөр эмчилгээ хийгээгүй.');
  assert((await page.locator('#treatment_narrative-original').textContent()).includes('эмчийн зассан агуулгыг батлахгүй'));
  // Simulated acknowledgement for layout QA, not a clinician signature/review.
  assert.equal(await page.locator('#field-signature').inputValue(),'');
  await page.locator('#reviewed').check();await page.locator('#acknowledged').check();await page.locator('#approve').click();assert(await page.locator('#print').isEnabled());
  const text=await page.locator('#print-view').textContent();
  if(mode==='normal') {
   assert(!text.includes('эхийн санал'));assert(!text.includes('Анхны ялгалтын эх — зассан утгын нотолгоо биш:'));
   assert(text.includes('энэ агуулгыг эхээр баталгаажсан гэж үзэхгүй'));
   assert(text.includes('Архаг хууч өвчний түүх'));
   assert(text.includes('Тэмдэглэл: Энэ үзлэгээр өөр эмчилгээ хийгээгүй.'));
   assert.equal((text.match(/Амлодипин/g)||[]).length,1);
   assert(!text.includes('Өгөөгүй эм'));

   for(const s of ['Парацетамол','Амлодипин','асуугаагүй','үнэлээгүй','хийгээгүй','6/10','4/10','134/82','128/80','RF','CRP'])assert(text.includes(s),s);
  }
  if(mode==='long') {assert(text.includes('Архаг хууч өвчний түүх'));assert(text.includes('мөр 35:'));}
  if(process.env.SKIP_PDF!=='1') await page.pdf({path:path.join(out,`${mode}.pdf`),printBackground:true,preferCSSPageSize:true});
  await page.locator('#note').fill(note+'\nШинэ зохиомол тэмдэглэл.');assert(await page.locator('#approve').isDisabled());assert.equal(await page.locator('#print-view').textContent(),'');assert((await page.locator('#field-treatment_narrative').inputValue()).includes('хийгээгүй'));
  assert.deepEqual(errors,[]);results.push({mode,status:'pass',inference:'none; preserved model response mocked; manual fictional layout fixture',signature:'blank',pdf:`${mode}.pdf`});await page.close();
 }
 fs.writeFileSync(path.join(out,'browser-print-check.json'),JSON.stringify(results,null,2));console.log(results);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
